"""FastAPI routes for authorized upload sessions and stored document metadata."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, cast

from fastapi import APIRouter, Header, Query, Request, Response, status

from pcbknowledge.document.contracts import (
    CompleteUploadSessionRequest,
    CreateUploadSessionRequest,
    DocumentListResponse,
    DocumentRevisionResponse,
    IntakeOptionsResponse,
    OriginalDownloadResponse,
    UploadSessionResponse,
)
from pcbknowledge.document.errors import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
    IntakeOptionsUnavailableError,
    UploadSessionConflictError,
    UploadSessionNotFoundError,
    UploadSessionStateError,
    UploadTooLargeError,
)
from pcbknowledge.document.service import DocumentService
from pcbknowledge.platform.audit import AuditWriter
from pcbknowledge.platform.http import PrincipalDependency, SessionDependency
from pcbknowledge.platform.identity.types import Principal
from pcbknowledge.platform.ids import UUID7
from pcbknowledge.platform.observability.context import current_request_context
from pcbknowledge.platform.outbox import OutboxService
from pcbknowledge.platform.storage import (
    AuditWriterAssetReadAuditor,
    ObjectAccessDeniedError,
    ObjectAssetNotFoundError,
    ObjectAuditRequiredError,
    ObjectStorageService,
    ObjectStoreUnavailableError,
    PolicyStorageAuthorizer,
    SeaweedFsS3Adapter,
    get_object_storage_adapter,
)
from pcbknowledge.shared.errors import ProblemDetail, ProblemException

router = APIRouter()
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$",
    ),
]

type DocumentServiceFactory = Callable[[Request, Principal], DocumentService]


def _problem_response(description: str) -> dict[str, object]:
    return {
        "description": description,
        "content": {
            "application/problem+json": {
                "schema": ProblemDetail.model_json_schema(),
            },
        },
    }


_AUTH_REQUIRED = _problem_response("A valid bearer token is required.")
_NOT_FOUND = _problem_response("The requested resource is unavailable in this scope.")
_FORBIDDEN = _problem_response("The authenticated identity is not authorized.")
_CONFLICT = _problem_response("The request conflicts with durable upload state.")
_DEPENDENCY_UNAVAILABLE = _problem_response("A required durable dependency is unavailable.")


@router.get(
    "/intake/options",
    operation_id="get_intake_options",
    response_model=IntakeOptionsResponse,
    responses={401: _AUTH_REQUIRED, 403: _FORBIDDEN},
    tags=["documents"],
)
def get_intake_options(
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> IntakeOptionsResponse:
    try:
        return _service(request, principal).get_intake_options(
            session,
            principal=principal,
        )
    except DocumentAccessDeniedError, IntakeOptionsUnavailableError:
        raise _forbidden_problem() from None


@router.post(
    "/upload-sessions",
    operation_id="create_upload_session",
    response_model=UploadSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": UploadSessionResponse,
            "description": "The same idempotent reservation already exists.",
        },
        401: _AUTH_REQUIRED,
        403: _FORBIDDEN,
        409: _CONFLICT,
        413: _problem_response("The qualified upload size limit was exceeded."),
        503: _DEPENDENCY_UNAVAILABLE,
    },
    tags=["documents"],
)
def create_upload_session(
    request_context: Request,
    response: Response,
    body: CreateUploadSessionRequest,
    idempotency_key: IdempotencyKey,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> UploadSessionResponse:
    try:
        result = _service(request_context, principal).create_upload_session(
            session,
            principal=principal,
            request=body,
            idempotency_key=idempotency_key,
            request_id=_request_id(),
        )
    except DocumentAccessDeniedError, DocumentNotFoundError:
        raise _forbidden_problem() from None
    except UploadSessionConflictError:
        raise _conflict_problem() from None
    except UploadTooLargeError:
        raise _too_large_problem() from None
    except ObjectStoreUnavailableError:
        raise _dependency_problem() from None
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/upload-sessions/{upload_session_id}/complete",
    operation_id="complete_upload_session",
    response_model=UploadSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {
            "model": UploadSessionResponse,
            "description": "The upload was already queued or reached a terminal state.",
        },
        401: _AUTH_REQUIRED,
        404: _NOT_FOUND,
        409: _CONFLICT,
    },
    tags=["documents"],
)
def complete_upload_session(
    request_context: Request,
    response: Response,
    upload_session_id: UUID7,
    body: CompleteUploadSessionRequest,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> UploadSessionResponse:
    try:
        result = _service(request_context, principal).complete_upload_session(
            session,
            principal=principal,
            upload_id=upload_session_id,
            request=body,
            request_id=_request_id(),
        )
    except UploadSessionNotFoundError, DocumentAccessDeniedError:
        raise _not_found_problem() from None
    except UploadSessionConflictError, UploadSessionStateError:
        raise _conflict_problem() from None
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/upload-sessions/{upload_session_id}",
    operation_id="get_upload_session",
    response_model=UploadSessionResponse,
    responses={401: _AUTH_REQUIRED, 404: _NOT_FOUND},
    tags=["documents"],
)
def get_upload_session(
    request: Request,
    upload_session_id: UUID7,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> UploadSessionResponse:
    try:
        return _service(request, principal).get_upload_session(
            session,
            principal=principal,
            upload_id=upload_session_id,
        )
    except UploadSessionNotFoundError, DocumentAccessDeniedError:
        raise _not_found_problem() from None


@router.get(
    "/documents",
    operation_id="list_documents",
    response_model=DocumentListResponse,
    responses={401: _AUTH_REQUIRED, 404: _NOT_FOUND},
    tags=["documents"],
)
def list_documents(
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
    project_id: Annotated[UUID7, Query()],
    cursor: Annotated[UUID7 | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DocumentListResponse:
    try:
        return _service(request, principal).list_documents(
            session,
            principal=principal,
            project_id=project_id,
            cursor=cursor,
            limit=limit,
        )
    except DocumentAccessDeniedError:
        raise _not_found_problem() from None


@router.get(
    "/document-revisions/{revision_id}",
    operation_id="get_document_revision",
    response_model=DocumentRevisionResponse,
    responses={401: _AUTH_REQUIRED, 404: _NOT_FOUND},
    tags=["documents"],
)
def get_document_revision(
    request: Request,
    revision_id: UUID7,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> DocumentRevisionResponse:
    try:
        return _service(request, principal).get_revision_metadata(
            session,
            principal=principal,
            revision_id=revision_id,
        )
    except DocumentNotFoundError, DocumentAccessDeniedError:
        raise _not_found_problem() from None


@router.post(
    "/document-revisions/{revision_id}/original-download",
    operation_id="create_document_original_download",
    response_model=OriginalDownloadResponse,
    responses={
        401: _AUTH_REQUIRED,
        404: _NOT_FOUND,
        503: _DEPENDENCY_UNAVAILABLE,
    },
    tags=["documents"],
)
def create_document_original_download(
    request: Request,
    revision_id: UUID7,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> OriginalDownloadResponse:
    try:
        return _service(request, principal).create_original_download(
            session,
            principal=principal,
            revision_id=revision_id,
        )
    except (
        DocumentNotFoundError,
        ObjectAccessDeniedError,
        ObjectAssetNotFoundError,
    ):
        raise _not_found_problem() from None
    except ObjectAuditRequiredError:
        raise _audit_problem() from None
    except ObjectStoreUnavailableError:
        raise _dependency_problem() from None


def _service(request: Request, principal: Principal) -> DocumentService:
    factory = cast(
        DocumentServiceFactory | None,
        getattr(request.app.state, "document_service_factory", None),
    )
    if factory is not None:
        return factory(request, principal)
    adapter = cast(
        SeaweedFsS3Adapter,
        getattr(request.app.state, "object_storage_adapter", None) or get_object_storage_adapter(),
    )
    audit_writer = cast(
        AuditWriter,
        getattr(request.app.state, "audit_writer", None) or AuditWriter(),
    )
    storage = ObjectStorageService(
        adapter=adapter,
        authorizer=PolicyStorageAuthorizer(principal),
        auditor=AuditWriterAssetReadAuditor(audit_writer, principal),
        outbox=OutboxService(),
    )
    return DocumentService(
        storage=storage,
        adapter=adapter,
        audit=audit_writer,
    )


def _request_id() -> str | None:
    context = current_request_context()
    return context.request_id if context is not None else None


def _not_found_problem() -> ProblemException:
    return ProblemException(
        status=404,
        title="Resource not found",
        detail="The requested resource was not found.",
        type_uri="urn:pcbknowledge:problem:resource-not-found",
    )


def _forbidden_problem() -> ProblemException:
    return ProblemException(
        status=403,
        title="Operation forbidden",
        detail="The authenticated identity cannot perform this operation.",
        type_uri="urn:pcbknowledge:problem:operation-forbidden",
    )


def _conflict_problem() -> ProblemException:
    return ProblemException(
        status=409,
        title="Request conflict",
        detail="The request conflicts with the current upload state.",
        type_uri="urn:pcbknowledge:problem:upload-conflict",
    )


def _dependency_problem() -> ProblemException:
    return ProblemException(
        status=503,
        title="Service unavailable",
        detail="The object storage dependency is unavailable.",
        type_uri="urn:pcbknowledge:problem:object-storage-unavailable",
    )


def _audit_problem() -> ProblemException:
    return ProblemException(
        status=503,
        title="Service unavailable",
        detail="The required access audit could not be recorded.",
        type_uri="urn:pcbknowledge:problem:audit-unavailable",
    )


def _too_large_problem() -> ProblemException:
    return ProblemException(
        status=413,
        title="Upload too large",
        detail="The file exceeds the configured upload size limit.",
        type_uri="urn:pcbknowledge:problem:upload-too-large",
    )
