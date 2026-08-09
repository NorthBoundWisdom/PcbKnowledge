"""Authorized application service for upload sessions and immutable documents."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from pcbknowledge.document.contracts import (
    AccessScopeOption,
    CompleteUploadSessionRequest,
    CreateUploadSessionRequest,
    DocumentListItem,
    DocumentListResponse,
    DocumentRevisionResponse,
    IntakeOptionsResponse,
    LicensePolicyOption,
    OriginalDownloadResponse,
    PresignedUploadResponse,
    ProjectOption,
    ProjectSummary,
    RevisionSummary,
    SourceOrganizationOption,
    SourceOrganizationSummary,
    UploadSessionProjectionState,
    UploadSessionResponse,
)
from pcbknowledge.document.errors import (
    DocumentAccessDeniedError,
    IntakeOptionsUnavailableError,
    UploadSessionConflictError,
    UploadSessionStateError,
    UploadTooLargeError,
)
from pcbknowledge.document.models import UploadSession, UploadSessionState
from pcbknowledge.document.repository import (
    DocumentRepository,
    DocumentRevisionRow,
    UploadSessionView,
)
from pcbknowledge.platform.audit import AuditEventDraft, AuditOutcome, AuditWriter
from pcbknowledge.platform.authorization import (
    AccessScope,
    AccessScopeKind,
    AccessScopeRef,
    AuthorizationDeniedError,
    Capability,
    LicenseAction,
    LicensePolicy,
    LicensePolicySnapshot,
    ResourceAuthorization,
    SourceOrganization,
    authorize,
    require_authorized,
)
from pcbknowledge.platform.identity.models import Project
from pcbknowledge.platform.identity.types import Principal
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import AccessScope as JobAccessScope
from pcbknowledge.platform.jobs import JobService, JobState, TenantScope
from pcbknowledge.platform.storage import (
    ObjectStorageService,
    SeaweedFsS3Adapter,
    StagingUploadNotFoundError,
    StagingUploadRepository,
    StagingUploadState,
    StagingUploadStateError,
    StorageRequestContext,
)
from pcbknowledge.platform.time import utc_now

VERIFY_UPLOAD_JOB = "document.intake.verify"
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")


class DocumentService:
    """Join authorization, storage, jobs, audit, and document persistence."""

    def __init__(
        self,
        *,
        storage: ObjectStorageService,
        adapter: SeaweedFsS3Adapter,
        repository: DocumentRepository | None = None,
        uploads: StagingUploadRepository | None = None,
        jobs: JobService | None = None,
        audit: AuditWriter | None = None,
    ) -> None:
        self._storage = storage
        self._adapter = adapter
        self._repository = repository or DocumentRepository()
        self._uploads = uploads or StagingUploadRepository()
        self._jobs = jobs or JobService()
        self._audit = audit or AuditWriter()

    def get_intake_options(
        self,
        session: Session,
        *,
        principal: Principal,
    ) -> IntakeOptionsResponse:
        projects = list(
            session.scalars(
                select(Project)
                .where(
                    Project.organization_id == principal.organization_id,
                    Project.active.is_(True),
                )
                .order_by(Project.display_name, Project.id)
            )
        )
        scopes = list(
            session.scalars(
                select(AccessScope)
                .where(
                    AccessScope.organization_id == principal.organization_id,
                    AccessScope.scope_kind == AccessScopeKind.PROJECT,
                    AccessScope.project_id.in_(tuple(principal.project_ids)),
                )
                .order_by(AccessScope.name, AccessScope.id)
            )
        )
        authorized_scopes = [
            scope
            for scope in scopes
            if authorize(
                principal,
                Capability.DOCUMENT_INGEST,
                _resource_from_models(scope=scope, policy=None, license_action=None),
            ).allowed
        ]
        scope_ids = tuple(scope.id for scope in authorized_scopes)
        policies = (
            list(
                session.scalars(
                    select(LicensePolicy)
                    .where(
                        LicensePolicy.organization_id == principal.organization_id,
                        LicensePolicy.access_scope_id.in_(scope_ids),
                        LicensePolicy.allow_metadata_read.is_(True),
                    )
                    .order_by(LicensePolicy.name, LicensePolicy.id)
                )
            )
            if scope_ids
            else []
        )
        policy_scope_ids = frozenset(policy.access_scope_id for policy in policies)
        authorized_scopes = [scope for scope in authorized_scopes if scope.id in policy_scope_ids]
        authorized_project_ids = frozenset(
            scope.project_id for scope in authorized_scopes if scope.project_id is not None
        )
        projects = [project for project in projects if project.id in authorized_project_ids]
        sources = (
            list(
                session.scalars(
                    select(SourceOrganization)
                    .where(SourceOrganization.organization_id == principal.organization_id)
                    .order_by(SourceOrganization.name, SourceOrganization.id)
                )
            )
            if projects
            else []
        )
        if not projects or not authorized_scopes or not policies or not sources:
            raise IntakeOptionsUnavailableError()
        return IntakeOptionsResponse(
            projects=tuple(
                ProjectOption(id=project.id, display_name=project.display_name)
                for project in projects
            ),
            access_scopes=tuple(
                AccessScopeOption(
                    id=scope.id,
                    project_id=scope.project_id,
                    name=scope.name,
                )
                for scope in authorized_scopes
                if scope.project_id is not None
            ),
            license_policies=tuple(
                LicensePolicyOption(
                    id=policy.id,
                    access_scope_id=policy.access_scope_id,
                    name=policy.name,
                    license_class=policy.license_class,
                    allow_human_raw_access=policy.allow_human_raw_access,
                    allow_parse=policy.allow_parse,
                )
                for policy in policies
            ),
            source_organizations=tuple(
                SourceOrganizationOption(
                    id=source.id,
                    name=source.name,
                    authority_tier=source.authority_tier,
                )
                for source in sources
            ),
        )

    def create_upload_session(
        self,
        session: Session,
        *,
        principal: Principal,
        request: CreateUploadSessionRequest,
        idempotency_key: str,
        request_id: str | None,
    ) -> UploadSessionResponse:
        _require_idempotency_key(idempotency_key)
        request_sha256 = _request_digest(request)
        self._repository.acquire_idempotency_lock(
            session,
            organization_id=principal.organization_id,
            actor_subject_id=principal.subject_id,
            idempotency_key=idempotency_key,
        )
        existing = self._repository.find_upload_by_idempotency(
            session,
            organization_id=principal.organization_id,
            actor_subject_id=principal.subject_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if existing.request_sha256 != request_sha256:
                raise UploadSessionConflictError()
            view = self._repository.get_upload_view(
                session,
                organization_id=principal.organization_id,
                upload_id=existing.id,
                actor_subject_id=principal.subject_id,
            )
            self._require_ingest_authorization(session, principal=principal, upload=existing)
            return self._upload_response(view, replayed=True, include_presign=True)

        scope, policy = self._load_intake_policy(
            session,
            principal=principal,
            project_id=request.project_id,
            access_scope_id=request.access_scope_id,
            license_policy_id=request.license_policy_id,
        )
        _require_capability(
            principal,
            Capability.DOCUMENT_INGEST,
            _resource_from_models(scope=scope, policy=policy, license_action=None),
        )
        source = session.scalar(
            select(SourceOrganization).where(
                SourceOrganization.id == request.source_organization_id,
                SourceOrganization.organization_id == principal.organization_id,
            )
        )
        if source is None:
            raise DocumentAccessDeniedError()

        creates_document = request.document_id is None
        if creates_document:
            target_document_id = new_uuid7()
            assert request.title is not None
            title = request.title
            document_number = request.document_number
        else:
            assert request.document_id is not None
            document = self._repository.get_document(
                session,
                organization_id=principal.organization_id,
                project_id=request.project_id,
                document_id=request.document_id,
            )
            self._repository.acquire_revision_intent_lock(
                session,
                organization_id=principal.organization_id,
                document_id=document.id,
                revision_label=request.revision_label,
            )
            if self._repository.revision_label_exists(
                session,
                document_id=document.id,
                revision_label=request.revision_label,
            ) or self._repository.active_revision_upload_exists(
                session,
                organization_id=principal.organization_id,
                document_id=document.id,
                revision_label=request.revision_label,
            ):
                raise UploadSessionConflictError()
            target_document_id = document.id
            title = document.title
            document_number = document.document_number

        tenant_scope = TenantScope(
            organization_id=principal.organization_id,
            project_id=request.project_id,
            access_scope=JobAccessScope.PROJECT,
        )
        storage_context = _storage_context(principal)
        if request.byte_size > self._adapter.maximum_upload_bytes:
            raise UploadTooLargeError()
        staging = self._storage.create_staging_upload(
            session,
            context=storage_context,
            scope=tenant_scope,
            access_scope_id=request.access_scope_id,
            license_policy_id=request.license_policy_id,
            media_type=request.media_type,
            expected_byte_size=request.byte_size,
        )
        upload = UploadSession(
            id=staging.upload_id,
            organization_id=principal.organization_id,
            project_id=request.project_id,
            access_scope="PROJECT",
            access_scope_id=request.access_scope_id,
            license_policy_id=request.license_policy_id,
            source_organization_id=request.source_organization_id,
            target_document_id=target_document_id,
            target_revision_id=new_uuid7(),
            creates_document=creates_document,
            title=title,
            document_number=document_number,
            revision_label=request.revision_label,
            original_filename=request.original_filename,
            media_type=request.media_type,
            expected_byte_size=request.byte_size,
            idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            state=UploadSessionState.RESERVED.value,
            created_by_subject_id=principal.subject_id,
        )
        self._repository.add_upload(session, upload)
        self._audit.append(
            session,
            AuditEventDraft(
                organization_id=principal.organization_id,
                project_id=request.project_id,
                action="document.upload_session.reserved",
                resource_type="upload_session",
                resource_id=upload.id,
                outcome=AuditOutcome.SUCCEEDED,
                request_id=request_id,
                detail={"media_type": request.media_type, "byte_size": request.byte_size},
            ),
            principal=principal,
        )
        view = UploadSessionView(
            upload=upload,
            reservation=self._repository.get_upload_view(
                session,
                organization_id=principal.organization_id,
                upload_id=upload.id,
                actor_subject_id=principal.subject_id,
            ).reservation,
            job=None,
        )
        return self._upload_response(
            view,
            replayed=False,
            presigned=PresignedUploadResponse(
                url=staging.request.url,
                headers=_browser_upload_headers(staging.request.headers),
                expires_in_seconds=staging.request.expires_in_seconds,
            ),
        )

    def complete_upload_session(
        self,
        session: Session,
        *,
        principal: Principal,
        upload_id: UUID,
        request: CompleteUploadSessionRequest,
        request_id: str | None,
    ) -> UploadSessionResponse:
        view = self._repository.get_upload_view(
            session,
            organization_id=principal.organization_id,
            upload_id=upload_id,
            actor_subject_id=principal.subject_id,
            for_update=True,
        )
        upload = view.upload
        self._require_ingest_authorization(session, principal=principal, upload=upload)
        if upload.state != UploadSessionState.RESERVED.value:
            if upload.expected_sha256 != request.expected_sha256:
                raise UploadSessionConflictError()
            return self._upload_response(view, replayed=True)
        scope = TenantScope(
            organization_id=upload.organization_id,
            project_id=upload.project_id,
            access_scope=JobAccessScope.PROJECT,
        )
        try:
            reservation = self._uploads.require_pending(
                session,
                scope=scope,
                upload_id=upload.id,
                access_scope_id=upload.access_scope_id,
                license_policy_id=upload.license_policy_id,
                created_by_subject_id=upload.created_by_subject_id,
                media_type=upload.media_type,
                now=utc_now(),
            )
        except (StagingUploadNotFoundError, StagingUploadStateError) as exc:
            raise UploadSessionStateError() from exc
        job = self._jobs.enqueue(
            session,
            scope=scope,
            job_type=VERIFY_UPLOAD_JOB,
            payload={"upload_session_id": str(upload.id)},
            idempotency_key=f"verify:{upload.id}",
            max_attempts=5,
        )
        now = utc_now()
        self._uploads.mark_submitted(reservation)
        session.flush((reservation,))
        self._repository.mark_queued(
            upload,
            job_id=job.id,
            expected_sha256=request.expected_sha256,
            now=now,
        )
        session.flush((upload,))
        self._audit.append(
            session,
            AuditEventDraft(
                organization_id=upload.organization_id,
                project_id=upload.project_id,
                action="document.upload_session.queued",
                resource_type="upload_session",
                resource_id=upload.id,
                outcome=AuditOutcome.SUCCEEDED,
                request_id=request_id,
                detail={"job_id": str(job.id)},
            ),
            principal=principal,
        )
        return self._upload_response(
            UploadSessionView(upload=upload, reservation=view.reservation, job=job),
            replayed=False,
        )

    def get_upload_session(
        self,
        session: Session,
        *,
        principal: Principal,
        upload_id: UUID,
    ) -> UploadSessionResponse:
        view = self._repository.get_upload_view(
            session,
            organization_id=principal.organization_id,
            upload_id=upload_id,
            actor_subject_id=principal.subject_id,
        )
        self._require_ingest_authorization(session, principal=principal, upload=view.upload)
        return self._upload_response(view, replayed=False)

    def list_documents(
        self,
        session: Session,
        *,
        principal: Principal,
        project_id: UUID,
        cursor: UUID | None,
        limit: int,
    ) -> DocumentListResponse:
        if project_id not in principal.project_ids:
            raise DocumentAccessDeniedError()
        rows = self._repository.list_documents(
            session,
            organization_id=principal.organization_id,
            project_id=project_id,
            cursor=cursor,
            limit=limit + 1,
        )
        authorized = []
        for row in rows:
            decision = authorize(
                principal,
                Capability.DOCUMENT_METADATA_WRITE,
                _resource_from_models(
                    scope=row.access_scope,
                    policy=row.license_policy,
                    license_action=LicenseAction.READ_METADATA,
                ),
            )
            if decision.allowed:
                authorized.append(row)
        page = authorized[:limit]
        items = tuple(
            DocumentListItem(
                id=row.document.id,
                project=ProjectSummary(
                    id=row.project.id,
                    display_name=row.project.display_name,
                ),
                title=row.document.title,
                document_number=row.document.document_number,
                latest_revision=RevisionSummary(
                    id=row.revision.id,
                    revision_label=row.revision.revision_label,
                    state=row.revision.state,
                    created_at=row.revision.created_at,
                ),
            )
            for row in page
        )
        next_cursor = page[-1].document.id if len(authorized) > limit and page else None
        return DocumentListResponse(items=items, next_cursor=next_cursor)

    def get_revision_metadata(
        self,
        session: Session,
        *,
        principal: Principal,
        revision_id: UUID,
    ) -> DocumentRevisionResponse:
        row = self._repository.get_revision(
            session,
            organization_id=principal.organization_id,
            revision_id=revision_id,
        )
        self._require_metadata_read(principal, row)
        return _revision_response(row)

    def create_original_download(
        self,
        session: Session,
        *,
        principal: Principal,
        revision_id: UUID,
    ) -> OriginalDownloadResponse:
        row = self._repository.get_revision(
            session,
            organization_id=principal.organization_id,
            revision_id=revision_id,
        )
        download = self._storage.create_download(
            session,
            context=_storage_context(principal),
            asset_id=row.object_asset.id,
        )
        return OriginalDownloadResponse(
            revision_id=revision_id,
            audit_event_id=download.audit_event_id,
            url=download.url,
            expires_in_seconds=download.expires_in_seconds,
        )

    def _load_intake_policy(
        self,
        session: Session,
        *,
        principal: Principal,
        project_id: UUID,
        access_scope_id: UUID,
        license_policy_id: UUID,
    ) -> tuple[AccessScope, LicensePolicy]:
        scope = session.scalar(
            select(AccessScope).where(
                AccessScope.id == access_scope_id,
                AccessScope.organization_id == principal.organization_id,
                AccessScope.project_id == project_id,
                AccessScope.scope_kind == AccessScopeKind.PROJECT,
            )
        )
        policy = session.scalar(
            select(LicensePolicy).where(
                LicensePolicy.id == license_policy_id,
                LicensePolicy.organization_id == principal.organization_id,
                LicensePolicy.access_scope_id == access_scope_id,
                LicensePolicy.allow_metadata_read.is_(True),
            )
        )
        if scope is None or policy is None:
            raise DocumentAccessDeniedError()
        return scope, policy

    def _require_ingest_authorization(
        self,
        session: Session,
        *,
        principal: Principal,
        upload: UploadSession,
    ) -> None:
        scope, policy = self._load_intake_policy(
            session,
            principal=principal,
            project_id=upload.project_id,
            access_scope_id=upload.access_scope_id,
            license_policy_id=upload.license_policy_id,
        )
        _require_capability(
            principal,
            Capability.DOCUMENT_INGEST,
            _resource_from_models(scope=scope, policy=policy, license_action=None),
        )

    @staticmethod
    def _require_metadata_read(principal: Principal, row: DocumentRevisionRow) -> None:
        _require_capability(
            principal,
            Capability.DOCUMENT_METADATA_WRITE,
            _resource_from_models(
                scope=row.access_scope,
                policy=row.license_policy,
                license_action=LicenseAction.READ_METADATA,
            ),
        )

    def _upload_response(
        self,
        view: UploadSessionView,
        *,
        replayed: bool,
        include_presign: bool = False,
        presigned: PresignedUploadResponse | None = None,
    ) -> UploadSessionResponse:
        upload_request = presigned
        if include_presign and view.upload.state == UploadSessionState.RESERVED.value:
            remaining = int((view.reservation.expires_at - utc_now()).total_seconds())
            if remaining > 0 and view.reservation.state == StagingUploadState.PENDING.value:
                refreshed = self._adapter.presign_staging_put(
                    organization_id=view.upload.organization_id,
                    upload_id=view.upload.id,
                    media_type=view.upload.media_type,
                    expected_byte_size=view.upload.expected_byte_size,
                    expires_in_seconds=min(remaining, 900),
                )
                upload_request = PresignedUploadResponse(
                    url=refreshed.url,
                    headers=_browser_upload_headers(refreshed.headers),
                    expires_in_seconds=refreshed.expires_in_seconds,
                )
        state, failure_code = _project_upload_state(view)
        return UploadSessionResponse(
            id=view.upload.id,
            document_id=view.upload.target_document_id,
            revision_id=view.upload.target_revision_id,
            project_id=view.upload.project_id,
            state=state,
            created_at=view.upload.created_at,
            updated_at=view.upload.updated_at,
            job_id=view.upload.completion_job_id,
            actual_sha256=view.upload.actual_sha256,
            failure_code=failure_code,
            upload=upload_request,
            replayed=replayed,
        )


def _resource_from_models(
    *,
    scope: AccessScope,
    policy: LicensePolicy | None,
    license_action: LicenseAction | None,
) -> ResourceAuthorization:
    snapshot = None
    if policy is not None:
        snapshot = LicensePolicySnapshot(
            id=policy.id,
            organization_id=policy.organization_id,
            access_scope_id=policy.access_scope_id,
            license_class=policy.license_class,
            allow_metadata_read=policy.allow_metadata_read,
            allow_human_raw_access=policy.allow_human_raw_access,
            allow_parse=policy.allow_parse,
            allow_external_model=policy.allow_external_model,
            allow_local_model=policy.allow_local_model,
            allow_embedding=policy.allow_embedding,
            allow_agent_raw_access=policy.allow_agent_raw_access,
            allow_redistribution=policy.allow_redistribution,
        )
    return ResourceAuthorization(
        organization_id=scope.organization_id,
        project_id=scope.project_id,
        access_scope=AccessScopeRef(
            id=scope.id,
            organization_id=scope.organization_id,
            project_id=scope.project_id,
            kind=scope.scope_kind,
        ),
        license_policy=snapshot,
        license_action=license_action,
    )


def _require_capability(
    principal: Principal,
    capability: Capability,
    resource: ResourceAuthorization,
) -> None:
    try:
        require_authorized(principal, capability, resource)
    except AuthorizationDeniedError:
        raise DocumentAccessDeniedError() from None


def _request_digest(request: CreateUploadSessionRequest) -> str:
    encoded = json.dumps(
        request.model_dump(mode="json", exclude_none=False),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _require_idempotency_key(value: str) -> None:
    if _IDEMPOTENCY_KEY.fullmatch(value) is None:
        raise UploadSessionConflictError()


def _storage_context(principal: Principal) -> StorageRequestContext:
    return StorageRequestContext(
        organization_id=principal.organization_id,
        project_ids=principal.project_ids,
        actor_subject_id=principal.subject_id,
    )


def _browser_upload_headers(headers: Mapping[str, str]) -> dict[str, str]:
    content_type = headers.get("Content-Type")
    return {"Content-Type": content_type} if content_type is not None else {}


def _project_upload_state(
    view: UploadSessionView,
) -> tuple[UploadSessionProjectionState, str | None]:
    upload = view.upload
    if upload.state == UploadSessionState.STORED.value:
        return UploadSessionProjectionState.STORED, None
    if upload.state == UploadSessionState.FAILED.value:
        return UploadSessionProjectionState.FAILED, upload.failure_code
    if upload.state == UploadSessionState.RESERVED.value:
        if (
            view.reservation.state
            in {
                StagingUploadState.EXPIRED.value,
                StagingUploadState.CLEANED.value,
            }
            or view.reservation.expires_at <= utc_now()
        ):
            return UploadSessionProjectionState.FAILED, "UPLOAD_EXPIRED"
        return UploadSessionProjectionState.RESERVED, None
    job = view.job
    if job is None:
        return UploadSessionProjectionState.FAILED, "JOB_BINDING_MISSING"
    if job.state == JobState.RUNNING.value:
        return UploadSessionProjectionState.VERIFYING, None
    if job.state == JobState.READY.value:
        if job.attempts > 0 or job.last_failure_code is not None:
            return UploadSessionProjectionState.RETRYING, job.last_failure_code
        return UploadSessionProjectionState.QUEUED, None
    if job.state in {JobState.DEAD_LETTER.value, JobState.CANCELLED.value}:
        return UploadSessionProjectionState.FAILED, job.last_failure_code or "JOB_TERMINATED"
    return UploadSessionProjectionState.FAILED, "JOB_COMPLETION_INCONSISTENT"


def _revision_response(row: DocumentRevisionRow) -> DocumentRevisionResponse:
    return DocumentRevisionResponse(
        id=row.revision.id,
        document_id=row.document.id,
        project=ProjectSummary(
            id=row.project.id,
            display_name=row.project.display_name,
        ),
        title=row.document.title,
        document_number=row.document.document_number,
        revision_label=row.revision.revision_label,
        state=row.revision.state,
        source_organization=SourceOrganizationSummary(
            id=row.source_organization.id,
            name=row.source_organization.name,
        ),
        original_filename=row.revision.original_filename,
        media_type=row.revision.media_type,
        sha256=row.object_asset.sha256,
        byte_size=row.object_asset.byte_size,
        created_at=row.revision.created_at,
    )
