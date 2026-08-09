"""Real PostgreSQL tests for the isolated document-intake boundary."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Barrier, Event, Thread
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pcbknowledge.document.contracts import (
    CompleteUploadSessionRequest,
    CreateUploadSessionRequest,
    UploadSessionProjectionState,
)
from pcbknowledge.document.errors import UploadSessionConflictError, UploadSessionStateError
from pcbknowledge.document.models import (
    Document,
    DocumentAsset,
    DocumentRevision,
    UploadSession,
)
from pcbknowledge.document.service import DocumentService
from pcbknowledge.document.verifier import ClaimedUpload, DocumentVerifierWorker
from pcbknowledge.platform.audit import AuditWriter
from pcbknowledge.platform.authorization import (
    SourceOrganization,
    install_principal_context,
)
from pcbknowledge.platform.database.health import (
    DatabaseContractError,
    _require_document_database_contract,
)
from pcbknowledge.platform.database.runtime import DatabaseRuntime
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import AccessScope, JobService, TenantScope
from pcbknowledge.platform.outbox import OutboxService
from pcbknowledge.platform.storage import (
    ObjectStorageService,
    PolicyStorageAuthorizer,
    SeaweedFsS3Adapter,
    StagingUploadRepository,
    StagingUploadReservation,
)
from pcbknowledge.platform.storage.adapter import S3Client
from pcbknowledge.platform.storage.service import AssetReadAuditor
from pcbknowledge.platform.time import utc_now
from tests.platform_jobs.postgres_support import (
    IdentitySeed,
    require_postgres_engine,
    reset_and_seed,
)

_PDF = b"%PDF-1.7\n%%EOF\n"
_DIGEST = hashlib.sha256(_PDF).hexdigest()
_WORKER_ID = "document-verifier-postgres-test"


class _PresignS3:
    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: Mapping[str, object],
        ExpiresIn: int,
        HttpMethod: str | None = None,
    ) -> str:
        del Params, ExpiresIn, HttpMethod
        return f"https://storage.invalid/{ClientMethod}"


class _UnusedAuditor:
    def record_asset_read(self, *_args: object, **_kwargs: object) -> UUID:
        raise AssertionError("document intake must not audit an asset read")


class _VerifierDatabase:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with Session(self._engine) as session, session.begin():
            session.execute(text("SET LOCAL ROLE pcbknowledge_verifier"))
            yield session


class _BlockingStagingRepository(StagingUploadRepository):
    def __init__(self, *, locked: Event, release: Event) -> None:
        self._locked = locked
        self._release = release

    def require_pending(
        self,
        session: Session,
        *,
        scope: TenantScope,
        upload_id: UUID,
        access_scope_id: UUID,
        license_policy_id: UUID,
        created_by_subject_id: UUID,
        media_type: str,
        now: datetime,
    ) -> StagingUploadReservation:
        reservation = super().require_pending(
            session,
            scope=scope,
            upload_id=upload_id,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
            created_by_subject_id=created_by_subject_id,
            media_type=media_type,
            now=now,
        )
        self._locked.set()
        if not self._release.wait(timeout=5):
            raise AssertionError("concurrent cleanup test did not release completion")
        return reservation


def _document_service(
    seed: DocumentSeed,
    *,
    uploads: StagingUploadRepository | None = None,
) -> DocumentService:
    client = _PresignS3()
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, client),
        presign_client=cast(S3Client, client),
        bucket="pcbknowledge-doc-test",
        staging_bucket="pcbknowledge-doc-test-staging",
    )
    audit = AuditWriter()
    storage = ObjectStorageService(
        adapter=adapter,
        authorizer=PolicyStorageAuthorizer(seed.identity.principal_a),
        auditor=cast(AssetReadAuditor, _UnusedAuditor()),
        outbox=OutboxService(jitter=lambda _attempt: 0.5),
    )
    return DocumentService(storage=storage, adapter=adapter, audit=audit, uploads=uploads)


def _verifier_worker(engine: Engine) -> DocumentVerifierWorker:
    client = _PresignS3()
    adapter = SeaweedFsS3Adapter(
        internal_client=cast(S3Client, client),
        presign_client=cast(S3Client, client),
        bucket="pcbknowledge-doc-test",
        staging_bucket="pcbknowledge-doc-test-staging",
        allow_content_write=True,
    )
    return DocumentVerifierWorker(
        database=cast(DatabaseRuntime, _VerifierDatabase(engine)),
        adapter=adapter,
        worker_id=_WORKER_ID,
        jobs=JobService(jitter=lambda _attempt: 0.5),
    )


@dataclass(frozen=True, slots=True)
class DocumentSeed:
    identity: IdentitySeed
    source_organization_id: UUID


@dataclass(frozen=True, slots=True)
class QueuedIntake:
    upload_id: UUID
    job_id: UUID
    document_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class ReservedIntake:
    upload_id: UUID
    document_id: UUID
    revision_id: UUID


@pytest.fixture
def database() -> Iterator[tuple[Engine, DocumentSeed]]:
    engine = require_postgres_engine()
    identity = reset_and_seed(engine)
    source = SourceOrganization(
        organization_id=identity.organization_a,
        name="Document PostgreSQL test authority",
        authority_tier="PRIMARY",
    )
    with Session(engine) as session, session.begin():
        session.add(source)
        session.flush((source,))
        source_organization_id = source.id
    try:
        yield (
            engine,
            DocumentSeed(
                identity=identity,
                source_organization_id=source_organization_id,
            ),
        )
    finally:
        engine.dispose()


def _seed_queued_intake(
    engine: Engine,
    seed: DocumentSeed,
    *,
    created_at_offset: timedelta = timedelta(),
    expires_after: timedelta = timedelta(minutes=15),
) -> QueuedIntake:
    identity = seed.identity
    now = utc_now() + created_at_offset
    reservation_id = new_uuid7()
    reservation = StagingUploadReservation(
        id=reservation_id,
        organization_id=identity.organization_a,
        project_id=identity.project_a1,
        access_scope="PROJECT",
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        created_by_subject_id=identity.subject_a,
        media_type="application/pdf",
        expected_byte_size=len(_PDF),
        state="PENDING",
        created_at=now,
        expires_at=now + expires_after,
    )
    document_id = new_uuid7()
    revision_id = new_uuid7()
    upload = UploadSession(
        id=reservation_id,
        organization_id=identity.organization_a,
        project_id=identity.project_a1,
        access_scope="PROJECT",
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        source_organization_id=seed.source_organization_id,
        target_document_id=document_id,
        target_revision_id=revision_id,
        creates_document=True,
        title="Verified PostgreSQL document",
        document_number="DOC-PG-1",
        revision_label="A",
        original_filename="verified.pdf",
        media_type="application/pdf",
        expected_byte_size=len(_PDF),
        idempotency_key=f"pg-intake-{reservation_id}",
        request_sha256="0" * 64,
        state="RESERVED",
        created_by_subject_id=identity.subject_a,
        created_at=now,
        updated_at=now,
    )
    jobs = JobService(jitter=lambda _attempt: 0.5)
    scope = TenantScope(
        identity.organization_a,
        identity.project_a1,
        AccessScope.PROJECT,
    )
    with Session(engine, expire_on_commit=False) as session, session.begin():
        session.add(reservation)
        session.flush((reservation,))
        session.add(upload)
        session.flush((upload,))
        job = jobs.enqueue(
            session,
            scope=scope,
            job_type="document.intake.verify",
            payload={"upload_session_id": str(upload.id)},
            idempotency_key=f"verify:{upload.id}",
            max_attempts=5,
        )
        reservation.state = "SUBMITTED"
        session.flush((reservation,))
        upload.state = "QUEUED"
        upload.completion_job_id = job.id
        upload.updated_at = utc_now()
        session.flush((upload,))
    return QueuedIntake(
        upload_id=upload.id,
        job_id=job.id,
        document_id=document_id,
        revision_id=revision_id,
    )


def _seed_reserved_intake(
    engine: Engine,
    seed: DocumentSeed,
    *,
    created_at_offset: timedelta = timedelta(),
    expires_after: timedelta = timedelta(minutes=15),
) -> ReservedIntake:
    identity = seed.identity
    now = utc_now() + created_at_offset
    reservation_id = new_uuid7()
    document_id = new_uuid7()
    revision_id = new_uuid7()
    reservation = StagingUploadReservation(
        id=reservation_id,
        organization_id=identity.organization_a,
        project_id=identity.project_a1,
        access_scope="PROJECT",
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        created_by_subject_id=identity.subject_a,
        media_type="application/pdf",
        expected_byte_size=len(_PDF),
        state="PENDING",
        created_at=now,
        expires_at=now + expires_after,
    )
    upload = UploadSession(
        id=reservation_id,
        organization_id=identity.organization_a,
        project_id=identity.project_a1,
        access_scope="PROJECT",
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        source_organization_id=seed.source_organization_id,
        target_document_id=document_id,
        target_revision_id=revision_id,
        creates_document=True,
        title="Reserved PostgreSQL document",
        document_number=f"DOC-RESERVED-{reservation_id}",
        revision_label="A",
        original_filename="reserved.pdf",
        media_type="application/pdf",
        expected_byte_size=len(_PDF),
        idempotency_key=f"pg-reserved-{reservation_id}",
        request_sha256="0" * 64,
        state="RESERVED",
        created_by_subject_id=identity.subject_a,
        created_at=now,
        updated_at=now,
    )
    with Session(engine) as session, session.begin():
        session.add(reservation)
        session.flush((reservation,))
        session.add(upload)
        session.flush((upload,))
    return ReservedIntake(
        upload_id=reservation_id,
        document_id=document_id,
        revision_id=revision_id,
    )


def test_application_upload_session_is_semantically_idempotent_and_async(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    identity = seed.identity
    service = _document_service(seed)
    request = CreateUploadSessionRequest(
        project_id=identity.project_a1,
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        source_organization_id=seed.source_organization_id,
        title="Idempotent PDF",
        document_number="IDEMP-1",
        revision_label="A",
        original_filename="idempotent.pdf",
        byte_size=len(_PDF),
    )
    with Session(engine) as session, session.begin():
        session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
        install_principal_context(session, identity.principal_a)
        first = service.create_upload_session(
            session,
            principal=identity.principal_a,
            request=request,
            idempotency_key="browser-retry-1",
            request_id="request-1",
        )
        replay = service.create_upload_session(
            session,
            principal=identity.principal_a,
            request=request,
            idempotency_key="browser-retry-1",
            request_id="request-2",
        )
        assert replay.id == first.id
        assert replay.replayed
        assert replay.upload is not None
        assert replay.upload.headers == {"Content-Type": "application/pdf"}
        with pytest.raises(UploadSessionConflictError):
            service.create_upload_session(
                session,
                principal=identity.principal_a,
                request=request.model_copy(update={"revision_label": "B"}),
                idempotency_key="browser-retry-1",
                request_id="request-3",
            )
        queued = service.complete_upload_session(
            session,
            principal=identity.principal_a,
            upload_id=first.id,
            request=CompleteUploadSessionRequest(),
            request_id="request-4",
        )
        assert (
            session.scalar(
                text("SELECT count(*) FROM document.upload_session WHERE id = :id"),
                {"id": first.id},
            )
            == 1
        )
        assert (
            session.scalar(
                text("SELECT count(*) FROM platform.staging_upload_reservation WHERE id = :id"),
                {"id": first.id},
            )
            == 1
        )
        assert (
            session.scalar(
                text("SELECT count(*) FROM platform.knowledge_job WHERE id = :id"),
                {"id": queued.job_id},
            )
            == 1
        )
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM document.upload_session upload "
                    "JOIN platform.staging_upload_reservation reservation "
                    "ON reservation.id = upload.id AND reservation.organization_id = "
                    "upload.organization_id LEFT JOIN platform.knowledge_job job "
                    "ON job.id = upload.completion_job_id AND job.organization_id = "
                    "upload.organization_id WHERE upload.id = :id AND "
                    "upload.created_by_subject_id = :subject"
                ),
                {"id": first.id, "subject": identity.subject_a},
            )
            == 1
        )
        complete_replay = service.complete_upload_session(
            session,
            principal=identity.principal_a,
            upload_id=first.id,
            request=CompleteUploadSessionRequest(),
            request_id="request-5",
        )
        assert queued.state is UploadSessionProjectionState.QUEUED
        assert complete_replay.state is UploadSessionProjectionState.QUEUED
        assert complete_replay.replayed
        assert complete_replay.job_id == queued.job_id

    with Session(engine) as verification:
        assert verification.scalar(select(func.count()).select_from(UploadSession)) == 1
        assert (
            verification.scalar(
                text(
                    "SELECT count(*) FROM platform.knowledge_job "
                    "WHERE job_type = 'document.intake.verify'"
                )
            )
            == 1
        )

    with (
        pytest.raises(DBAPIError, match="invalid upload session state transition"),
        Session(engine) as session,
        session.begin(),
    ):
        session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
        install_principal_context(session, identity.principal_a)
        session.execute(
            text(
                "UPDATE document.upload_session SET updated_at = "
                "pg_catalog.clock_timestamp() WHERE id = :upload_id"
            ),
            {"upload_id": first.id},
        )


def test_existing_document_revision_intent_conflicts_across_idempotency_keys(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
        _store_closed_intake(session, seed, intake)

    identity = seed.identity
    service = _document_service(seed)
    request = CreateUploadSessionRequest(
        project_id=identity.project_a1,
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        source_organization_id=seed.source_organization_id,
        document_id=intake.document_id,
        revision_label="B",
        original_filename="existing-b.pdf",
        byte_size=len(_PDF),
    )
    with Session(engine) as session, session.begin():
        session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
        install_principal_context(session, identity.principal_a)
        first = service.create_upload_session(
            session,
            principal=identity.principal_a,
            request=request,
            idempotency_key="existing-document-b-first",
            request_id="existing-document-b-first",
        )

    with Session(engine) as session, session.begin():
        session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
        install_principal_context(session, identity.principal_a)
        with pytest.raises(UploadSessionConflictError):
            service.create_upload_session(
                session,
                principal=identity.principal_a,
                request=request,
                idempotency_key="existing-document-b-second",
                request_id="existing-document-b-second",
            )

    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(UploadSession)
                .where(
                    UploadSession.target_document_id == intake.document_id,
                    UploadSession.revision_label == "B",
                    UploadSession.state != "FAILED",
                )
            )
            == 1
        )
        assert first.document_id == intake.document_id


def test_existing_document_revision_intent_is_serialized_concurrently(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
        _store_closed_intake(session, seed, intake)

    identity = seed.identity
    request = CreateUploadSessionRequest(
        project_id=identity.project_a1,
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        source_organization_id=seed.source_organization_id,
        document_id=intake.document_id,
        revision_label="B",
        original_filename="concurrent-b.pdf",
        byte_size=len(_PDF),
    )
    barrier = Barrier(2)
    created: list[UUID] = []
    conflicts: list[UploadSessionConflictError] = []
    unexpected: list[BaseException] = []

    def reserve(idempotency_key: str) -> None:
        try:
            barrier.wait(timeout=5)
            with Session(engine) as session, session.begin():
                session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
                install_principal_context(session, identity.principal_a)
                result = _document_service(seed).create_upload_session(
                    session,
                    principal=identity.principal_a,
                    request=request,
                    idempotency_key=idempotency_key,
                    request_id=idempotency_key,
                )
                created.append(result.id)
        except UploadSessionConflictError as error:
            conflicts.append(error)
        except BaseException as error:  # pragma: no cover - asserted below
            unexpected.append(error)

    threads = [Thread(target=reserve, args=(f"concurrent-revision-{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert unexpected == []
    assert len(created) == 1
    assert len(conflicts) == 1
    with Session(engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(UploadSession)
                .where(
                    UploadSession.target_document_id == intake.document_id,
                    UploadSession.revision_label == "B",
                    UploadSession.state != "FAILED",
                )
            )
            == 1
        )


def _install_verifier_context(session: Session, seed: DocumentSeed) -> None:
    identity = seed.identity
    session.execute(text("SET LOCAL ROLE pcbknowledge_verifier"))
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.organization_id', :value, true)"),
        {"value": str(identity.organization_a)},
    )
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.project_ids', :value, true)"),
        {"value": str(identity.project_a1)},
    )


def _install_worker_context(session: Session, seed: DocumentSeed) -> None:
    identity = seed.identity
    session.execute(text("SET LOCAL ROLE pcbknowledge_worker"))
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.organization_id', :value, true)"),
        {"value": str(identity.organization_a)},
    )
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.project_ids', :value, true)"),
        {"value": str(identity.project_a1)},
    )


def _claim(session: Session, intake: QueuedIntake) -> None:
    claimed = session.execute(
        text(
            "UPDATE platform.knowledge_job "
            "SET state = 'RUNNING', lease_owner = :worker, "
            "lease_expires_at = pg_catalog.clock_timestamp() + "
            "INTERVAL '5 minutes', attempts = attempts + 1, "
            "updated_at = pg_catalog.clock_timestamp() "
            "WHERE id = :job_id AND state = 'READY' RETURNING id"
        ),
        {"worker": _WORKER_ID, "job_id": intake.job_id},
    ).scalar_one()
    assert claimed == intake.job_id


def _record_effect(session: Session, seed: DocumentSeed, intake: QueuedIntake) -> UUID:
    receipt_id = new_uuid7()
    session.execute(
        text(
            "INSERT INTO platform.job_effect_receipt ("
            "id, job_id, organization_id, project_id, access_scope, "
            "effect_name, effect_sha256, lease_attempt, lease_owner, recorded_at"
            ") VALUES ("
            ":id, :job_id, :organization_id, :project_id, 'PROJECT', "
            "'document-original-promotion', :digest, 1, :worker, "
            "pg_catalog.clock_timestamp())"
        ),
        {
            "id": receipt_id,
            "job_id": intake.job_id,
            "organization_id": seed.identity.organization_a,
            "project_id": seed.identity.project_a1,
            "digest": _DIGEST,
            "worker": _WORKER_ID,
        },
    )
    return receipt_id


def _store_closed_intake(
    session: Session,
    seed: DocumentSeed,
    intake: QueuedIntake,
    *,
    finalize_staging: bool = True,
    record_audit: bool = True,
) -> tuple[UUID, UUID]:
    identity = seed.identity
    object_id = new_uuid7()
    relation_id = new_uuid7()
    _record_effect(session, seed, intake)
    session.execute(
        text(
            "INSERT INTO platform.object_asset ("
            "id, organization_id, project_id, access_scope, access_scope_id, "
            "license_policy_id, asset_kind, bucket, object_key, sha256, "
            "byte_size, media_type, state, created_by_subject_id, created_at"
            ") VALUES ("
            ":id, :organization_id, :project_id, 'PROJECT', :scope_id, "
            ":policy_id, 'DOCUMENT_ORIGINAL', 'pcbknowledge-doc-test', "
            ":object_key, :digest, :byte_size, 'application/pdf', 'AVAILABLE', "
            ":subject_id, pg_catalog.clock_timestamp())"
        ),
        {
            "id": object_id,
            "organization_id": identity.organization_a,
            "project_id": identity.project_a1,
            "scope_id": identity.scope_a1,
            "policy_id": identity.policy_a1_allow,
            "object_key": (
                f"organizations/{identity.organization_a}/sha256/{_DIGEST[:2]}/{_DIGEST}"
            ),
            "digest": _DIGEST,
            "byte_size": len(_PDF),
            "subject_id": identity.subject_a,
        },
    )
    if finalize_staging:
        session.execute(
            text(
                "UPDATE platform.staging_upload_reservation "
                "SET state = 'FINALIZED', asset_id = :asset_id, "
                "finalized_at = pg_catalog.clock_timestamp() "
                "WHERE id = :upload_id"
            ),
            {"asset_id": object_id, "upload_id": intake.upload_id},
        )
    session.execute(
        text(
            "INSERT INTO document.document ("
            "id, organization_id, project_id, title, document_number, "
            "created_by_subject_id, created_at"
            ") SELECT target_document_id, organization_id, project_id, title, "
            "document_number, created_by_subject_id, created_at "
            "FROM document.upload_session WHERE id = :upload_id"
        ),
        {"upload_id": intake.upload_id},
    )
    session.execute(
        text(
            "INSERT INTO document.document_revision ("
            "id, organization_id, project_id, document_id, "
            "source_organization_id, access_scope, access_scope_id, "
            "license_policy_id, revision_label, original_filename, media_type, "
            "state, created_by_subject_id, created_at"
            ") SELECT target_revision_id, organization_id, project_id, "
            "target_document_id, source_organization_id, access_scope, "
            "access_scope_id, license_policy_id, revision_label, "
            "original_filename, media_type, 'STORED', created_by_subject_id, "
            "pg_catalog.clock_timestamp() FROM document.upload_session "
            "WHERE id = :upload_id"
        ),
        {"upload_id": intake.upload_id},
    )
    session.execute(
        text(
            "INSERT INTO document.document_asset ("
            "id, organization_id, project_id, revision_id, object_asset_id, "
            "asset_kind, created_at"
            ") VALUES ("
            ":id, :organization_id, :project_id, :revision_id, :object_id, "
            "'ORIGINAL', pg_catalog.clock_timestamp())"
        ),
        {
            "id": relation_id,
            "organization_id": identity.organization_a,
            "project_id": identity.project_a1,
            "revision_id": intake.revision_id,
            "object_id": object_id,
        },
    )
    session.execute(
        text(
            "UPDATE document.upload_session "
            "SET state = 'STORED', actual_sha256 = :digest, "
            "object_asset_id = :object_id, completed_at = "
            "pg_catalog.clock_timestamp(), updated_at = "
            "pg_catalog.clock_timestamp() WHERE id = :upload_id"
        ),
        {
            "digest": _DIGEST,
            "object_id": object_id,
            "upload_id": intake.upload_id,
        },
    )
    if record_audit:
        session.execute(
            text(
                "INSERT INTO audit.audit_event ("
                "id, organization_id, project_id, occurred_at, actor_subject_id, "
                "actor_kind, action, resource_type, resource_id, outcome, detail"
                ") VALUES ("
                ":id, :organization_id, :project_id, "
                "pg_catalog.clock_timestamp(), NULL, NULL, "
                "'document.revision.stored', 'document_revision', :revision_id, "
                "'SUCCEEDED', pg_catalog.jsonb_build_object("
                "'upload_session_id', CAST(:upload_id AS text), "
                "'job_id', CAST(:job_id AS text), "
                "'object_asset_id', CAST(:object_id AS text), "
                "'sha256', CAST(:digest AS text), "
                "'byte_size', CAST(:byte_size AS bigint)))"
            ),
            {
                "id": new_uuid7(),
                "organization_id": identity.organization_a,
                "project_id": identity.project_a1,
                "revision_id": intake.revision_id,
                "upload_id": intake.upload_id,
                "job_id": intake.job_id,
                "object_id": object_id,
                "digest": _DIGEST,
                "byte_size": len(_PDF),
            },
        )
    session.execute(
        text(
            "UPDATE platform.knowledge_job SET state = 'COMPLETED', "
            "lease_owner = NULL, lease_expires_at = NULL, "
            "completed_at = pg_catalog.clock_timestamp(), "
            "updated_at = pg_catalog.clock_timestamp() WHERE id = :job_id"
        ),
        {"job_id": intake.job_id},
    )
    return object_id, relation_id


def test_verifier_can_commit_only_a_complete_closed_intake(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)

    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
        object_id, _relation_id = _store_closed_intake(session, seed, intake)

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Document)) == 1
        assert session.scalar(select(func.count()).select_from(DocumentRevision)) == 1
        assert session.scalar(select(func.count()).select_from(DocumentAsset)) == 1
        state = session.execute(
            text(
                "SELECT upload.state, job.state, reservation.state, object.state "
                "FROM document.upload_session AS upload "
                "JOIN platform.knowledge_job AS job "
                "ON job.id = upload.completion_job_id "
                "JOIN platform.staging_upload_reservation AS reservation "
                "ON reservation.id = upload.id "
                "JOIN platform.object_asset AS object "
                "ON object.id = upload.object_asset_id "
                "WHERE upload.id = :upload_id AND object.id = :object_id"
            ),
            {"upload_id": intake.upload_id, "object_id": object_id},
        ).one()
        assert tuple(state) == ("STORED", "COMPLETED", "FINALIZED", "AVAILABLE")

    with (
        pytest.raises(DBAPIError, match="stored document records are immutable"),
        engine.begin() as connection,
    ):
        connection.execute(
            text("UPDATE document.document SET title = 'mutated' WHERE id = :id"),
            {"id": intake.document_id},
        )


def test_deferred_closure_rejects_orphan_even_with_active_verifier_lease(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    session = Session(engine)
    try:
        session.begin()
        _install_verifier_context(session, seed)
        _claim(session, intake)
        session.execute(
            text(
                "INSERT INTO document.document ("
                "id, organization_id, project_id, title, document_number, "
                "created_by_subject_id, created_at"
                ") SELECT target_document_id, organization_id, project_id, title, "
                "document_number, created_by_subject_id, created_at "
                "FROM document.upload_session WHERE id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        )
        with pytest.raises(DBAPIError, match="stored document transaction is incomplete"):
            session.commit()
    finally:
        session.rollback()
        session.close()

    with Session(engine) as verification:
        assert verification.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.parametrize("omission", ["audit", "staging"])
def test_deferred_closure_rejects_missing_authoritative_receipt(
    database: tuple[Engine, DocumentSeed],
    omission: str,
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    session = Session(engine)
    try:
        session.begin()
        _install_verifier_context(session, seed)
        _claim(session, intake)
        if omission == "staging":
            with pytest.raises(DBAPIError, match="staging lifecycle is invalid"):
                _store_closed_intake(
                    session,
                    seed,
                    intake,
                    finalize_staging=False,
                )
        else:
            _store_closed_intake(
                session,
                seed,
                intake,
                record_audit=False,
            )
            with pytest.raises(DBAPIError, match="stored document transaction is incomplete"):
                session.commit()
    finally:
        session.rollback()
        session.close()

    with Session(engine) as verification:
        assert verification.scalar(select(func.count()).select_from(Document)) == 0


def test_verifier_failure_transition_and_staging_fences_are_database_enforced(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    identity = seed.identity
    unrelated_id = new_uuid7()
    unrelated = StagingUploadReservation(
        id=unrelated_id,
        organization_id=identity.organization_a,
        project_id=identity.project_a1,
        access_scope="PROJECT",
        access_scope_id=identity.scope_a1,
        license_policy_id=identity.policy_a1_allow,
        created_by_subject_id=identity.subject_a,
        media_type="application/pdf",
        expected_byte_size=len(_PDF),
        state="PENDING",
        created_at=utc_now(),
        expires_at=utc_now() + timedelta(minutes=15),
    )
    with Session(engine) as session, session.begin():
        session.add(unrelated)
        session.flush((unrelated,))

    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
        assert (
            session.scalar(
                select(func.count())
                .select_from(StagingUploadReservation)
                .where(StagingUploadReservation.id == unrelated_id)
            )
            == 0
        )
        session.execute(
            text(
                "UPDATE platform.staging_upload_reservation "
                "SET state = 'PENDING' WHERE id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        )
        session.execute(
            text(
                "UPDATE document.upload_session SET state = 'FAILED', "
                "failure_code = 'UPLOAD_NOT_PDF', completed_at = "
                "pg_catalog.clock_timestamp(), updated_at = "
                "pg_catalog.clock_timestamp() WHERE id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        )
        session.execute(
            text(
                "UPDATE platform.knowledge_job SET state = 'DEAD_LETTER', "
                "lease_owner = NULL, lease_expires_at = NULL, "
                "last_failure_code = 'UPLOAD_NOT_PDF', updated_at = "
                "pg_catalog.clock_timestamp() WHERE id = :job_id"
            ),
            {"job_id": intake.job_id},
        )

    with Session(engine) as session:
        state = session.execute(
            text(
                "SELECT upload.state AS upload_state, upload.failure_code, "
                "job.state AS job_state, job.last_failure_code "
                "FROM document.upload_session upload "
                "JOIN platform.knowledge_job job "
                "ON job.id = upload.completion_job_id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        ).one()
        assert tuple(state) == (
            "FAILED",
            "UPLOAD_NOT_PDF",
            "DEAD_LETTER",
            "UPLOAD_NOT_PDF",
        )


@pytest.mark.parametrize(
    ("retryable", "expected_upload_state", "expected_job_state"),
    [
        (True, "QUEUED", "READY"),
        (False, "FAILED", "DEAD_LETTER"),
    ],
)
def test_verifier_worker_failure_path_preserves_transactional_state(
    database: tuple[Engine, DocumentSeed],
    retryable: bool,
    expected_upload_state: str,
    expected_job_state: str,
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)

    scope = TenantScope(
        seed.identity.organization_a,
        seed.identity.project_a1,
        AccessScope.PROJECT,
    )
    _verifier_worker(engine)._mark_failed(
        ClaimedUpload(scope=scope, job_id=intake.job_id),
        "OBJECT_STORE_UNAVAILABLE" if retryable else "UPLOAD_NOT_PDF",
        retryable=retryable,
    )

    with Session(engine) as session:
        state = session.execute(
            text(
                "SELECT upload.state AS upload_state, upload.failure_code, "
                "job.state AS job_state, job.last_failure_code "
                "FROM document.upload_session upload "
                "JOIN platform.knowledge_job job "
                "ON job.id = upload.completion_job_id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        ).one()
        assert state.upload_state == expected_upload_state
        assert state.failure_code == (None if retryable else "UPLOAD_NOT_PDF")
        assert state.job_state == expected_job_state
        assert state.last_failure_code == (
            "OBJECT_STORE_UNAVAILABLE" if retryable else "UPLOAD_NOT_PDF"
        )
        audit_count = session.scalar(
            text(
                "SELECT count(*) FROM audit.audit_event WHERE "
                "action = 'document.upload_verification.failed' "
                "AND resource_id = :resource_id"
            ),
            {"resource_id": intake.upload_id},
        )
        assert audit_count == 1


def test_submitted_expired_upload_is_not_cleaned_until_terminal_failure(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(
        engine,
        seed,
        created_at_offset=timedelta(minutes=-5),
        expires_after=timedelta(minutes=1),
    )
    scope = TenantScope(
        seed.identity.organization_a,
        seed.identity.project_a1,
        AccessScope.PROJECT,
    )
    uploads = StagingUploadRepository()

    with Session(engine) as session, session.begin():
        _install_worker_context(session, seed)
        assert (
            uploads.claim_one_expired(
                session,
                scope=scope,
                cleanup_before=utc_now(),
            )
            is None
        )

    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
    _verifier_worker(engine)._mark_failed(
        ClaimedUpload(scope=scope, job_id=intake.job_id),
        "UPLOAD_NOT_PDF",
        retryable=False,
    )

    with Session(engine) as session, session.begin():
        _install_worker_context(session, seed)
        reservation = uploads.claim_one_expired(
            session,
            scope=scope,
            cleanup_before=utc_now(),
        )
        assert reservation is not None
        assert reservation.id == intake.upload_id
        uploads.mark_expired(reservation, now=utc_now())
        session.flush((reservation,))

    with Session(engine) as session:
        state = session.execute(
            text(
                "SELECT upload.state, reservation.state "
                "FROM document.upload_session AS upload "
                "JOIN platform.staging_upload_reservation AS reservation "
                "ON reservation.id = upload.id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        ).one()
        assert tuple(state) == ("FAILED", "EXPIRED")


def test_cleanup_winning_reservation_lock_prevents_completion(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_reserved_intake(
        engine,
        seed,
        created_at_offset=timedelta(minutes=-5),
        expires_after=timedelta(minutes=1),
    )
    scope = TenantScope(
        seed.identity.organization_a,
        seed.identity.project_a1,
        AccessScope.PROJECT,
    )
    uploads = StagingUploadRepository()
    with Session(engine) as session, session.begin():
        _install_worker_context(session, seed)
        reservation = uploads.claim_one_expired(
            session,
            scope=scope,
            cleanup_before=utc_now(),
        )
        assert reservation is not None
        uploads.mark_expired(reservation, now=utc_now())
        session.flush((reservation,))

    with Session(engine) as session, session.begin():
        session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
        install_principal_context(session, seed.identity.principal_a)
        with pytest.raises(UploadSessionStateError):
            _document_service(seed).complete_upload_session(
                session,
                principal=seed.identity.principal_a,
                upload_id=intake.upload_id,
                request=CompleteUploadSessionRequest(),
                request_id="cleanup-won",
            )

    with Session(engine) as session:
        state = session.execute(
            text(
                "SELECT upload.state, reservation.state, "
                "upload.completion_job_id "
                "FROM document.upload_session AS upload "
                "JOIN platform.staging_upload_reservation AS reservation "
                "ON reservation.id = upload.id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        ).one()
        assert tuple(state) == ("RESERVED", "EXPIRED", None)


def test_completion_winning_reservation_lock_excludes_concurrent_cleanup(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_reserved_intake(
        engine,
        seed,
        expires_after=timedelta(milliseconds=250),
    )
    scope = TenantScope(
        seed.identity.organization_a,
        seed.identity.project_a1,
        AccessScope.PROJECT,
    )
    locked = Event()
    release = Event()
    errors: list[BaseException] = []
    uploads = _BlockingStagingRepository(locked=locked, release=release)
    service = _document_service(seed, uploads=uploads)

    def complete() -> None:
        try:
            with Session(engine) as session, session.begin():
                session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
                install_principal_context(session, seed.identity.principal_a)
                service.complete_upload_session(
                    session,
                    principal=seed.identity.principal_a,
                    upload_id=intake.upload_id,
                    request=CompleteUploadSessionRequest(),
                    request_id="completion-won",
                )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    completion = Thread(target=complete, name="document-completion-race")
    completion.start()
    try:
        assert locked.wait(timeout=5)
        time.sleep(0.35)
        with Session(engine) as session, session.begin():
            _install_worker_context(session, seed)
            assert (
                StagingUploadRepository().claim_one_expired(
                    session,
                    scope=scope,
                    cleanup_before=utc_now(),
                )
                is None
            )
    finally:
        release.set()
        completion.join(timeout=5)
    assert not completion.is_alive()
    assert errors == []

    with Session(engine) as session:
        state = session.execute(
            text(
                "SELECT upload.state, reservation.state, job.state "
                "FROM document.upload_session AS upload "
                "JOIN platform.staging_upload_reservation AS reservation "
                "ON reservation.id = upload.id "
                "JOIN platform.knowledge_job AS job "
                "ON job.id = upload.completion_job_id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        ).one()
        assert tuple(state) == ("QUEUED", "SUBMITTED", "READY")


def test_expired_intake_lease_is_discovered_recovered_and_reclaimed(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE platform.knowledge_job SET lease_expires_at = "
                "pg_catalog.clock_timestamp() - INTERVAL '1 second' "
                "WHERE id = :job_id"
            ),
            {"job_id": intake.job_id},
        )

    scope = TenantScope(
        seed.identity.organization_a,
        seed.identity.project_a1,
        AccessScope.PROJECT,
    )
    service = JobService(jitter=lambda _attempt: 0.5)
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        discovered = session.execute(
            text(
                "SELECT organization_id, project_id, access_scope "
                "FROM platform.claimable_document_intake_scopes(10)"
            )
        ).one()
        assert tuple(discovered) == (
            seed.identity.organization_a,
            seed.identity.project_a1,
            "PROJECT",
        )
        claimed = service.claim(
            session,
            scope=scope,
            worker_id="document-verifier-recovered",
            batch_size=1,
            job_types=frozenset({"document.intake.verify"}),
        )
        assert [job.id for job in claimed] == [intake.job_id]
        assert claimed[0].attempts == 2
        assert claimed[0].state == "RUNNING"
        assert claimed[0].lease_owner == "document-verifier-recovered"


def test_expired_final_attempt_is_reclaimed_and_terminalized_with_cleanup_receipt(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(
        engine,
        seed,
        created_at_offset=timedelta(minutes=-5),
        expires_after=timedelta(minutes=1),
    )
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE platform.knowledge_job "
                "SET attempts = max_attempts, lease_expires_at = "
                "pg_catalog.clock_timestamp() - INTERVAL '1 second' "
                "WHERE id = :job_id"
            ),
            {"job_id": intake.job_id},
        )

    assert _verifier_worker(engine).run_once() == 0

    with Session(engine) as session:
        state = session.execute(
            text(
                "SELECT upload.state, upload.failure_code, reservation.state, "
                "job.state, job.last_failure_code, job.lease_owner, "
                "(SELECT count(*) FROM audit.audit_event AS audit "
                " WHERE audit.action = 'document.upload_verification.failed' "
                " AND audit.resource_id = upload.id) AS audit_count "
                "FROM document.upload_session AS upload "
                "JOIN platform.staging_upload_reservation AS reservation "
                "ON reservation.id = upload.id "
                "JOIN platform.knowledge_job AS job "
                "ON job.id = upload.completion_job_id "
                "WHERE upload.id = :upload_id"
            ),
            {"upload_id": intake.upload_id},
        ).one()
        assert tuple(state) == (
            "FAILED",
            "LEASE_EXPIRED_MAX_ATTEMPTS",
            "PENDING",
            "DEAD_LETTER",
            "LEASE_EXPIRED_MAX_ATTEMPTS",
            None,
            1,
        )

    scope = TenantScope(
        seed.identity.organization_a,
        seed.identity.project_a1,
        AccessScope.PROJECT,
    )
    with Session(engine) as session, session.begin():
        _install_worker_context(session, seed)
        cleanup = StagingUploadRepository().claim_one_expired(
            session,
            scope=scope,
            cleanup_before=utc_now(),
        )
        assert cleanup is not None
        assert cleanup.id == intake.upload_id


def test_verifier_cross_project_and_cross_organization_rows_are_invisible(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, seed = database
    intake = _seed_queued_intake(engine, seed)
    with Session(engine) as session, session.begin():
        _install_verifier_context(session, seed)
        _claim(session, intake)
        _store_closed_intake(session, seed, intake)

    contexts = (
        (seed.identity.organization_a, seed.identity.project_a2),
        (seed.identity.organization_b, seed.identity.project_b1),
    )
    for organization_id, project_id in contexts:
        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL ROLE pcbknowledge_verifier"))
            session.execute(
                text("SELECT pg_catalog.set_config('pcbknowledge.organization_id', :value, true)"),
                {"value": str(organization_id)},
            )
            session.execute(
                text("SELECT pg_catalog.set_config('pcbknowledge.project_ids', :value, true)"),
                {"value": str(project_id)},
            )
            counts = session.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM document.upload_session) AS uploads, "
                    "(SELECT count(*) FROM document.document) AS documents, "
                    "(SELECT count(*) FROM document.document_revision) AS revisions, "
                    "(SELECT count(*) FROM document.document_asset) AS relations, "
                    "(SELECT count(*) FROM platform.object_asset) AS objects"
                )
            ).one()
            assert tuple(counts) == (0, 0, 0, 0, 0)
            updated = session.scalar(
                text(
                    "UPDATE document.upload_session SET state = 'FAILED' "
                    "WHERE id = :upload_id RETURNING id"
                ),
                {"upload_id": intake.upload_id},
            )
            assert updated is None


def test_verifier_restrictive_policy_drift_is_rejected(
    database: tuple[Engine, DocumentSeed],
) -> None:
    engine, _seed = database
    drift = (
        "ALTER POLICY outbox_verifier_cleanup_only ON platform.outbox_event "
        "USING (event_type = 'storage.staging_cleanup.requested' OR true) "
        "WITH CHECK (event_type = 'storage.staging_cleanup.requested')"
    )
    restore = (
        "ALTER POLICY outbox_verifier_cleanup_only ON platform.outbox_event "
        "USING (event_type = 'storage.staging_cleanup.requested') "
        "WITH CHECK (event_type = 'storage.staging_cleanup.requested')"
    )
    with engine.connect() as connection:
        _require_document_database_contract(connection)
    try:
        with engine.begin() as connection:
            connection.execute(text(drift))
        with engine.connect() as connection, pytest.raises(DatabaseContractError):
            _require_document_database_contract(connection)
    finally:
        with engine.begin() as connection:
            connection.execute(text(restore))
