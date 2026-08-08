"""Executable, tenant-safe dispatch for M1 storage-cleanup outbox events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from pcbknowledge.platform.database import DatabaseRuntime
from pcbknowledge.platform.jobs import AccessScope, TenantScope
from pcbknowledge.platform.outbox.errors import (
    OutboxLeaseLostError,
    OutboxPayloadIntegrityError,
    OutboxTransitionError,
)
from pcbknowledge.platform.outbox.models import OutboxEvent
from pcbknowledge.platform.outbox.service import OutboxService
from pcbknowledge.platform.storage.adapter import (
    SeaweedFsS3Adapter,
    StagingCleanupIntent,
)
from pcbknowledge.platform.storage.errors import (
    ObjectStoreUnavailableError,
    StagingUploadNotFoundError,
    StagingUploadStateError,
)
from pcbknowledge.platform.storage.repository import StagingUploadRepository
from pcbknowledge.platform.time import utc_now

STORAGE_CLEANUP_EVENT = "storage.staging_cleanup.requested"


class InvalidStorageCleanupEventError(RuntimeError):
    """Raised without serializing the malformed payload."""


class StorageCleanupPayload(BaseModel):
    """Bounded payload emitted by ObjectStorageService.finalize_staging."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: UUID
    upload_id: UUID


@dataclass(frozen=True, slots=True)
class ClaimedOutboxEvent:
    scope: TenantScope
    event_id: UUID


class StorageCleanupPublisher:
    """Delete staging only after validating its durable tenant/asset binding."""

    def __init__(
        self,
        *,
        adapter: SeaweedFsS3Adapter,
        session: Session,
        scope: TenantScope,
        repository: StagingUploadRepository | None = None,
    ) -> None:
        self._adapter = adapter
        self._session = session
        self._scope = scope
        self._repository = repository or StagingUploadRepository()

    def publish(self, event: OutboxEvent) -> None:
        if event.event_type != STORAGE_CLEANUP_EVENT or event.aggregate_type != "object_asset":
            raise InvalidStorageCleanupEventError()
        try:
            payload = StorageCleanupPayload.model_validate(event.payload)
        except ValidationError:
            raise InvalidStorageCleanupEventError() from None
        if payload.asset_id != event.aggregate_id:
            raise InvalidStorageCleanupEventError()
        if (
            event.organization_id != self._scope.organization_id
            or event.project_id != self._scope.project_id
            or event.access_scope != self._scope.access_scope.value
        ):
            raise InvalidStorageCleanupEventError()
        try:
            reservation = self._repository.require_finalized_cleanup(
                self._session,
                scope=self._scope,
                upload_id=payload.upload_id,
                asset_id=payload.asset_id,
            )
        except StagingUploadNotFoundError, StagingUploadStateError:
            raise InvalidStorageCleanupEventError() from None
        self._adapter.cleanup_staging(
            StagingCleanupIntent(
                organization_id=event.organization_id,
                upload_id=payload.upload_id,
            )
        )
        self._repository.mark_cleaned(reservation, now=utc_now())


class WorkerOutboxDispatcher:
    """Discover only claimable scopes, then process each under FORCE RLS."""

    def __init__(
        self,
        *,
        database: DatabaseRuntime,
        adapter: SeaweedFsS3Adapter,
        worker_id: str,
        service: OutboxService | None = None,
    ) -> None:
        self._database = database
        self._adapter = adapter
        self._worker_id = worker_id
        self._service = service or OutboxService()
        self._uploads = StagingUploadRepository()

    def run_once(self, *, maximum_scopes: int = 100, batch_size: int = 25) -> int:
        """Dispatch one bounded batch and return the number marked published."""

        if not 1 <= maximum_scopes <= 1000 or not 1 <= batch_size <= 100:
            raise ValueError("worker dispatch bounds are invalid")
        with self._database.transaction() as session:
            scopes = self._discover_scopes(session, maximum_scopes=maximum_scopes)

        completed = 0
        for scope in scopes:
            for _ in range(batch_size):
                with self._database.transaction() as session:
                    _install_worker_scope(session, scope)
                    events = self._service.claim(
                        session,
                        scope=scope,
                        worker_id=self._worker_id,
                        batch_size=1,
                        event_types=frozenset({STORAGE_CLEANUP_EVENT}),
                    )
                if not events:
                    break
                claim = ClaimedOutboxEvent(scope=scope, event_id=events[0].id)
                try:
                    with self._database.transaction() as session:
                        _install_worker_scope(session, claim.scope)
                        self._service.publish(
                            session,
                            scope=claim.scope,
                            event_id=claim.event_id,
                            worker_id=self._worker_id,
                            publisher=StorageCleanupPublisher(
                                adapter=self._adapter,
                                session=session,
                                scope=claim.scope,
                            ),
                        )
                    completed += 1
                except InvalidStorageCleanupEventError:
                    self._mark_failed(
                        claim,
                        failure_code="INVALID_CLEANUP_EVENT",
                        retryable=False,
                    )
                except OutboxPayloadIntegrityError:
                    self._mark_failed(
                        claim,
                        failure_code="PAYLOAD_INTEGRITY_FAILED",
                        retryable=False,
                    )
                except ObjectStoreUnavailableError, OSError:
                    self._mark_failed(
                        claim,
                        failure_code="OBJECT_STORE_UNAVAILABLE",
                        retryable=True,
                    )
                except OutboxLeaseLostError:
                    continue
            completed += self._sweep_expired_uploads(scope, batch_size=batch_size)
        return completed

    def _sweep_expired_uploads(self, scope: TenantScope, *, batch_size: int) -> int:
        cleaned = 0
        for _ in range(batch_size):
            try:
                with self._database.transaction() as session:
                    _install_worker_scope(session, scope)
                    reservation = self._uploads.claim_one_expired(
                        session,
                        scope=scope,
                        cleanup_before=utc_now() - timedelta(minutes=1),
                    )
                    if reservation is None:
                        break
                    self._adapter.cleanup_staging(
                        StagingCleanupIntent(
                            organization_id=reservation.organization_id,
                            upload_id=reservation.id,
                        )
                    )
                    self._uploads.mark_expired(reservation, now=utc_now())
                    cleaned += 1
            except ObjectStoreUnavailableError:
                break
        return cleaned

    def _mark_failed(
        self,
        claim: ClaimedOutboxEvent,
        *,
        failure_code: str,
        retryable: bool,
    ) -> None:
        try:
            with self._database.transaction() as session:
                _install_worker_scope(session, claim.scope)
                self._service.fail(
                    session,
                    scope=claim.scope,
                    event_id=claim.event_id,
                    worker_id=self._worker_id,
                    failure_code=failure_code,
                    retryable=retryable,
                )
        except OutboxLeaseLostError, OutboxTransitionError:
            # A lease can expire while an external dependency stalls. Another
            # worker will recover it; never widen scope or force an update.
            return

    @staticmethod
    def _discover_scopes(session: Session, *, maximum_scopes: int) -> list[TenantScope]:
        rows = session.execute(
            text(
                "SELECT organization_id, project_id, access_scope "
                "FROM platform.claimable_storage_cleanup_scopes(:maximum_scopes)"
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


def _install_worker_scope(session: Session, scope: TenantScope) -> None:
    project_ids = "" if scope.project_id is None else str(scope.project_id)
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.organization_id', :value, true)"),
        {"value": str(scope.organization_id)},
    )
    session.execute(
        text("SELECT pg_catalog.set_config('pcbknowledge.project_ids', :value, true)"),
        {"value": project_ids},
    )
