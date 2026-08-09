"""Isolated upload verifier and content-addressed promotion worker."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from pcbknowledge.document.errors import InvalidUploadJobError
from pcbknowledge.document.models import UploadSessionState
from pcbknowledge.document.repository import DocumentRepository
from pcbknowledge.document.service import VERIFY_UPLOAD_JOB
from pcbknowledge.platform.audit import AuditEventDraft, AuditOutcome, AuditWriter
from pcbknowledge.platform.config import (
    ObjectStorageSettings,
    Settings,
    get_object_storage_settings,
    get_settings,
)
from pcbknowledge.platform.database import (
    DatabaseContractError,
    DatabaseRuntime,
    UnsafeDatabaseRoleError,
    probe_database,
)
from pcbknowledge.platform.database.runtime import get_database_runtime
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs import AccessScope, JobService, JobState, KnowledgeJob, TenantScope
from pcbknowledge.platform.outbox import OutboxService
from pcbknowledge.platform.storage import (
    ObjectAssetRepository,
    ObjectDigestMismatchError,
    ObjectIntegrityError,
    ObjectMagicMismatchError,
    ObjectSizeMismatchError,
    ObjectStoreUnavailableError,
    SeaweedFsS3Adapter,
    StagingUploadNotFoundError,
    StagingUploadRepository,
    StagingUploadStateError,
    probe_object_storage,
)
from pcbknowledge.platform.storage.runtime import get_object_storage_adapter
from pcbknowledge.platform.time import utc_now

logger = logging.getLogger(__name__)


class VerifyUploadPayload(BaseModel):
    """The durable queue carries one identifier and never document content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_session_id: UUID


class VerifierHealth(BaseModel):
    """Stable health output without connection details or credential material."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "failed"]]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimedUpload:
    scope: TenantScope
    job_id: UUID
    terminal_failure_code: str | None = None


class DocumentVerifierWorker:
    """Claim only upload-verification jobs and promote through privileged S3 access."""

    def __init__(
        self,
        *,
        database: DatabaseRuntime,
        adapter: SeaweedFsS3Adapter,
        worker_id: str,
        jobs: JobService | None = None,
        documents: DocumentRepository | None = None,
        uploads: StagingUploadRepository | None = None,
        assets: ObjectAssetRepository | None = None,
        outbox: OutboxService | None = None,
        audit: AuditWriter | None = None,
    ) -> None:
        self._database = database
        self._adapter = adapter
        self._worker_id = worker_id
        self._jobs = jobs or JobService()
        self._documents = documents or DocumentRepository()
        self._uploads = uploads or StagingUploadRepository()
        self._assets = assets or ObjectAssetRepository()
        self._outbox = outbox or OutboxService()
        self._audit = audit or AuditWriter()

    def run_once(self, *, maximum_scopes: int = 100) -> int:
        if not 1 <= maximum_scopes <= 1000:
            raise ValueError("verifier scope bound is invalid")
        with self._database.transaction() as session:
            scopes = self._discover_scopes(session, maximum_scopes=maximum_scopes)

        completed = 0
        for scope in scopes:
            claim = self._claim_one(scope)
            if claim is None:
                continue
            if claim.terminal_failure_code is not None:
                self._mark_failed(
                    claim,
                    claim.terminal_failure_code,
                    retryable=False,
                )
                continue
            try:
                self._verify(claim)
                completed += 1
            except ObjectDigestMismatchError:
                self._mark_failed(claim, "UPLOAD_DIGEST_MISMATCH", retryable=False)
            except ObjectSizeMismatchError:
                self._mark_failed(claim, "UPLOAD_SIZE_MISMATCH", retryable=False)
            except ObjectMagicMismatchError:
                self._mark_failed(claim, "UPLOAD_NOT_PDF", retryable=False)
            except ObjectIntegrityError:
                self._mark_failed(claim, "UPLOAD_INTEGRITY_FAILED", retryable=False)
            except StagingUploadNotFoundError, StagingUploadStateError:
                self._mark_failed(claim, "UPLOAD_RESERVATION_INVALID", retryable=False)
            except InvalidUploadJobError, ValidationError, IntegrityError:
                self._mark_failed(claim, "DOCUMENT_INTAKE_INVALID", retryable=False)
            except ObjectStoreUnavailableError, OSError:
                self._mark_failed(claim, "OBJECT_STORE_UNAVAILABLE", retryable=True)
        return completed

    def _claim_one(self, scope: TenantScope) -> ClaimedUpload | None:
        with self._database.transaction() as session:
            _install_verifier_scope(session, scope)
            terminal = self._reclaim_expired_terminal_job(session, scope=scope)
            if terminal is not None:
                return terminal
            jobs = self._jobs.claim(
                session,
                scope=scope,
                worker_id=self._worker_id,
                batch_size=1,
                job_types=frozenset({VERIFY_UPLOAD_JOB}),
            )
            if not jobs:
                return None
            return ClaimedUpload(scope=scope, job_id=jobs[0].id)

    def _reclaim_expired_terminal_job(
        self,
        session: Session,
        *,
        scope: TenantScope,
    ) -> ClaimedUpload | None:
        """Fence final-attempt lease expiry before domain terminalization."""

        now = utc_now()
        job = session.scalar(
            select(KnowledgeJob)
            .where(
                KnowledgeJob.organization_id == scope.organization_id,
                KnowledgeJob.project_id == scope.project_id,
                KnowledgeJob.access_scope == scope.access_scope.value,
                KnowledgeJob.job_type == VERIFY_UPLOAD_JOB,
                KnowledgeJob.state == JobState.RUNNING.value,
                KnowledgeJob.lease_expires_at <= now,
                KnowledgeJob.attempts >= KnowledgeJob.max_attempts,
            )
            .order_by(KnowledgeJob.lease_expires_at, KnowledgeJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.lease_owner = self._worker_id
        job.lease_expires_at = now + timedelta(minutes=5)
        job.updated_at = now
        session.flush((job,))
        return ClaimedUpload(
            scope=scope,
            job_id=job.id,
            terminal_failure_code="LEASE_EXPIRED_MAX_ATTEMPTS",
        )

    def _verify(self, claim: ClaimedUpload) -> None:
        with self._database.transaction() as session:
            _install_verifier_scope(session, claim.scope)
            job = self._locked_job(session, claim)
            payload = _validate_job(
                job,
                claim,
                worker_id=self._worker_id,
            )
            view = self._documents.get_upload_view(
                session,
                organization_id=claim.scope.organization_id,
                upload_id=payload.upload_session_id,
                for_update=True,
            )
            upload = view.upload
            if (
                upload.completion_job_id != job.id
                or upload.state != UploadSessionState.QUEUED.value
                or upload.project_id != claim.scope.project_id
                or upload.access_scope != claim.scope.access_scope.value
            ):
                raise InvalidUploadJobError()
            reservation = self._uploads.require_submitted(
                session,
                scope=claim.scope,
                upload_id=upload.id,
                access_scope_id=upload.access_scope_id,
                license_policy_id=upload.license_policy_id,
                created_by_subject_id=upload.created_by_subject_id,
                media_type=upload.media_type,
            )
            snapshot = self._adapter.snapshot_staging(
                organization_id=upload.organization_id,
                upload_id=upload.id,
                expected_sha256=upload.expected_sha256,
                expected_byte_size=upload.expected_byte_size,
                required_prefix=b"%PDF-",
            )
            try:
                effect_granted = self._jobs.record_effect_once(
                    session,
                    scope=claim.scope,
                    job_id=job.id,
                    effect_name="document-original-promotion",
                    effect_sha256=snapshot.inspection.sha256,
                    worker_id=self._worker_id,
                    lease_attempt=job.attempts,
                )
                if not effect_granted:
                    raise InvalidUploadJobError()
                self._uploads.acquire_content_lock(
                    session,
                    organization_id=upload.organization_id,
                    sha256=snapshot.inspection.sha256,
                )
                reference = self._adapter.promote_snapshot(snapshot)
            finally:
                self._adapter.cleanup_snapshot(snapshot)

            now = utc_now()
            object_asset = self._assets.register(
                session,
                asset_id=new_uuid7(),
                scope=claim.scope,
                asset_kind="DOCUMENT_ORIGINAL",
                access_scope_id=upload.access_scope_id,
                license_policy_id=upload.license_policy_id,
                reference=reference,
                sha256=snapshot.inspection.sha256,
                byte_size=snapshot.inspection.byte_size,
                media_type=upload.media_type,
                created_by_subject_id=upload.created_by_subject_id,
                created_at=now,
            )
            self._uploads.mark_finalized(reservation, asset_id=object_asset.id, now=now)
            session.flush((reservation,))
            _document, revision, _relation = self._documents.store_verified_records(
                session,
                upload=upload,
                object_asset=object_asset,
                actual_sha256=snapshot.inspection.sha256,
                now=now,
            )
            self._outbox.add(
                session,
                scope=claim.scope,
                event_type="storage.staging_cleanup.requested",
                aggregate_type="object_asset",
                aggregate_id=object_asset.id,
                payload={
                    "asset_id": str(object_asset.id),
                    "upload_id": str(upload.id),
                },
                idempotency_key=f"staging-cleanup:{upload.id}",
            )
            self._audit.append(
                session,
                AuditEventDraft(
                    organization_id=upload.organization_id,
                    project_id=upload.project_id,
                    action="document.revision.stored",
                    resource_type="document_revision",
                    resource_id=revision.id,
                    outcome=AuditOutcome.SUCCEEDED,
                    detail={
                        "upload_session_id": str(upload.id),
                        "job_id": str(job.id),
                        "object_asset_id": str(object_asset.id),
                        "sha256": snapshot.inspection.sha256,
                        "byte_size": snapshot.inspection.byte_size,
                    },
                ),
                principal=None,
            )
            self._jobs.complete(
                session,
                scope=claim.scope,
                job_id=job.id,
                worker_id=self._worker_id,
            )

    def _mark_failed(
        self,
        claim: ClaimedUpload,
        failure_code: str,
        *,
        retryable: bool,
    ) -> None:
        try:
            with self._database.transaction() as session:
                _install_verifier_scope(session, claim.scope)
                job = self._locked_job(session, claim)
                upload_id = _optional_upload_id(job)
                terminal = not retryable or job.attempts >= job.max_attempts
                resource_id = job.id
                if upload_id is not None:
                    try:
                        view = self._documents.get_upload_view(
                            session,
                            organization_id=claim.scope.organization_id,
                            upload_id=upload_id,
                            for_update=True,
                        )
                    except Exception:
                        view = None
                    if (
                        view is not None
                        and view.upload.completion_job_id == job.id
                        and view.upload.state == UploadSessionState.QUEUED.value
                    ):
                        resource_id = view.upload.id
                        if terminal:
                            if view.reservation.state == "SUBMITTED":
                                self._uploads.mark_pending_after_terminal_failure(view.reservation)
                                session.flush((view.reservation,))
                            self._documents.mark_failed(
                                view.upload,
                                failure_code=failure_code,
                                now=utc_now(),
                            )
                            session.flush((view.upload,))
                self._jobs.fail(
                    session,
                    scope=claim.scope,
                    job_id=job.id,
                    worker_id=self._worker_id,
                    failure_code=failure_code,
                    retryable=retryable,
                )
                self._audit.append(
                    session,
                    AuditEventDraft(
                        organization_id=claim.scope.organization_id,
                        project_id=claim.scope.project_id,
                        action="document.upload_verification.failed",
                        resource_type=(
                            "upload_session" if upload_id is not None else "knowledge_job"
                        ),
                        resource_id=resource_id,
                        outcome=AuditOutcome.FAILED,
                        detail={"failure_code": failure_code, "retryable": not terminal},
                    ),
                    principal=None,
                )
        except Exception:
            # If even the failure audit cannot commit, leave the active lease to
            # expire. No document record is made authoritative without audit.
            logger.exception("document upload failure transition rolled back")
            return

    @staticmethod
    def _discover_scopes(session: Session, *, maximum_scopes: int) -> list[TenantScope]:
        rows = session.execute(
            text(
                "SELECT organization_id, project_id, access_scope "
                "FROM platform.claimable_document_intake_scopes(:maximum_scopes)"
            ),
            {"maximum_scopes": maximum_scopes},
        ).mappings()
        return [
            TenantScope(
                organization_id=row["organization_id"],
                project_id=row["project_id"],
                access_scope=AccessScope(row["access_scope"]),
            )
            for row in rows
        ]

    @staticmethod
    def _locked_job(session: Session, claim: ClaimedUpload) -> KnowledgeJob:
        job = session.scalar(
            select(KnowledgeJob)
            .where(
                KnowledgeJob.id == claim.job_id,
                KnowledgeJob.organization_id == claim.scope.organization_id,
                KnowledgeJob.project_id == claim.scope.project_id,
                KnowledgeJob.access_scope == claim.scope.access_scope.value,
            )
            .with_for_update()
        )
        if job is None:
            raise InvalidUploadJobError()
        return job


def _validate_job(
    job: KnowledgeJob,
    claim: ClaimedUpload,
    *,
    worker_id: str,
) -> VerifyUploadPayload:
    now = utc_now()
    if (
        job.id != claim.job_id
        or job.job_type != VERIFY_UPLOAD_JOB
        or job.state != JobState.RUNNING.value
        or job.lease_owner != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
        or job.attempts < 1
    ):
        raise InvalidUploadJobError()
    return VerifyUploadPayload.model_validate(job.payload)


def _optional_upload_id(job: KnowledgeJob) -> UUID | None:
    try:
        return VerifyUploadPayload.model_validate(job.payload).upload_session_id
    except ValidationError:
        return None


def _install_verifier_scope(session: Session, scope: TenantScope) -> None:
    project_ids = "" if scope.project_id is None else str(scope.project_id)
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.organization_id', :value, true)"),
        {"value": str(scope.organization_id)},
    )
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.project_ids', :value, true)"),
        {"value": project_ids},
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcbknowledge-document-verifier")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "health-check",
        help="validate verifier configuration, database contract, and private S3 access",
    )
    serve = commands.add_parser("serve", help="run the isolated upload verifier")
    serve.add_argument("--interval-seconds", type=float, default=5.0)
    commands.add_parser("run-once", help="run one bounded verification cycle")
    return parser


def run_health_check(
    *,
    settings_loader: Callable[[], Settings] = get_settings,
    storage_settings_loader: Callable[[], ObjectStorageSettings] = get_object_storage_settings,
    database_probe: Callable[[Settings], None] = probe_database,
    storage_probe: Callable[[ObjectStorageSettings], None] = probe_object_storage,
) -> VerifierHealth:
    """Probe exact runtime contracts without claiming work or mutating storage."""

    try:
        settings = settings_loader()
        storage_settings = storage_settings_loader()
        if storage_settings.access_mode != "verifier":
            raise ValueError("isolated verifier access mode is required")
    except ValidationError, ValueError:
        return VerifierHealth(
            status="not_ready",
            checks={"configuration": "failed"},
            reason="required verifier configuration is missing or invalid",
        )
    try:
        database_probe(settings)
    except DatabaseContractError, SQLAlchemyError, UnsafeDatabaseRoleError, OSError:
        return VerifierHealth(
            status="not_ready",
            checks={"configuration": "ok", "database": "failed"},
            reason="PostgreSQL is unavailable",
        )
    try:
        storage_probe(storage_settings)
    except ObjectStoreUnavailableError, OSError:
        return VerifierHealth(
            status="not_ready",
            checks={
                "configuration": "ok",
                "database": "ok",
                "object_storage": "failed",
            },
            reason="object storage is unavailable",
        )
    return VerifierHealth(
        status="ready",
        checks={
            "configuration": "ok",
            "database": "ok",
            "object_storage": "ok",
        },
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run only with the isolated verifier database and promotion credentials."""

    arguments = _build_parser().parse_args(argv)
    if arguments.command == "health-check":
        health = run_health_check()
        print(json.dumps(health.model_dump(mode="json", exclude_none=True), sort_keys=True))
        return 0 if health.status == "ready" else 1
    settings = get_object_storage_settings()
    if settings.access_mode != "verifier":
        print(json.dumps({"status": "not_ready", "reason": "promotion access required"}))
        return 1
    worker = DocumentVerifierWorker(
        database=get_database_runtime(),
        adapter=get_object_storage_adapter(),
        worker_id=f"document-verifier-{new_uuid7()}",
    )
    if arguments.command == "run-once":
        print(json.dumps({"verified": worker.run_once()}, sort_keys=True))
        return 0
    if arguments.command != "serve":
        raise AssertionError("argparse accepted an unknown verifier command")
    if not 1 <= arguments.interval_seconds <= 300:
        _build_parser().error("interval must be between 1 and 300 seconds")

    stop_event = threading.Event()

    def request_stop(_signal_number: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stop_event.is_set():
        print(json.dumps({"verified": worker.run_once()}, sort_keys=True))
        stop_event.wait(arguments.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
