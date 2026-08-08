"""Authorized object upload/finalization/download application service."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs.models import AccessScope
from pcbknowledge.platform.jobs.repository import TenantScope
from pcbknowledge.platform.outbox import OutboxService
from pcbknowledge.platform.storage.adapter import (
    PresignedRequest,
    SeaweedFsS3Adapter,
    StagingCleanupIntent,
    StoredObjectRef,
)
from pcbknowledge.platform.storage.errors import (
    ObjectAccessDeniedError,
    ObjectAuditRequiredError,
)
from pcbknowledge.platform.storage.keys import require_sha256
from pcbknowledge.platform.storage.models import ObjectAsset
from pcbknowledge.platform.storage.repository import (
    ObjectAssetRepository,
    StagingUploadRepository,
)
from pcbknowledge.platform.time import utc_now

_ASSET_KIND = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass(frozen=True, slots=True)
class StorageRequestContext:
    organization_id: UUID
    project_ids: frozenset[UUID]
    actor_subject_id: UUID


@dataclass(frozen=True, slots=True)
class AssetDownload:
    asset_id: UUID
    audit_event_id: UUID
    url: str = field(repr=False)
    expires_in_seconds: int


@dataclass(frozen=True, slots=True)
class StagingUpload:
    upload_id: UUID
    request: PresignedRequest


class StorageAuthorizer(Protocol):
    """Role/license policy supplied by the identity/application layer."""

    def authorize_upload(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        scope: TenantScope,
        access_scope_id: UUID,
        license_policy_id: UUID,
    ) -> None: ...

    def authorize_download(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        asset: ObjectAsset,
    ) -> None: ...


class AssetReadAuditor(Protocol):
    """Append an audit event using the same SQLAlchemy transaction."""

    def record_asset_read(
        self,
        session: Session,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        actor_subject_id: UUID,
        asset_id: UUID,
    ) -> UUID: ...


class ObjectStorageService:
    """Public storage boundary accepting asset IDs, never raw object keys."""

    def __init__(
        self,
        *,
        adapter: SeaweedFsS3Adapter,
        authorizer: StorageAuthorizer,
        auditor: AssetReadAuditor,
        outbox: OutboxService,
        repository: ObjectAssetRepository | None = None,
        upload_repository: StagingUploadRepository | None = None,
    ) -> None:
        self._adapter = adapter
        self._authorizer = authorizer
        self._auditor = auditor
        self._outbox = outbox
        self._repository = repository or ObjectAssetRepository()
        self._upload_repository = upload_repository or StagingUploadRepository()

    def create_staging_upload(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        scope: TenantScope,
        access_scope_id: UUID,
        license_policy_id: UUID,
        media_type: str,
        expected_byte_size: int,
        expires_in_seconds: int = 900,
    ) -> StagingUpload:
        self._require_context_scope(context, scope)
        self._authorizer.authorize_upload(
            session,
            context=context,
            scope=scope,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
        )
        now = utc_now()
        reservation = self._upload_repository.reserve(
            session,
            scope=scope,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
            created_by_subject_id=context.actor_subject_id,
            media_type=media_type,
            expected_byte_size=expected_byte_size,
            created_at=now,
            expires_at=now + timedelta(seconds=expires_in_seconds),
        )
        request = self._adapter.presign_staging_put(
            organization_id=scope.organization_id,
            upload_id=reservation.id,
            media_type=media_type,
            expected_byte_size=expected_byte_size,
            expires_in_seconds=expires_in_seconds,
        )
        return StagingUpload(upload_id=reservation.id, request=request)

    def finalize_staging(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        scope: TenantScope,
        upload_id: UUID,
        expected_sha256: str,
        media_type: str,
        asset_kind: str,
        access_scope_id: UUID,
        license_policy_id: UUID,
    ) -> ObjectAsset:
        self._require_context_scope(context, scope)
        self._authorizer.authorize_upload(
            session,
            context=context,
            scope=scope,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
        )
        digest = require_sha256(expected_sha256)
        if _ASSET_KIND.fullmatch(asset_kind) is None:
            raise ValueError("asset kind is invalid")
        now = utc_now()
        reservation = self._upload_repository.require_pending(
            session,
            scope=scope,
            upload_id=upload_id,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
            created_by_subject_id=context.actor_subject_id,
            media_type=media_type,
            now=now,
        )
        snapshot = self._adapter.snapshot_staging(
            organization_id=scope.organization_id,
            upload_id=upload_id,
            expected_sha256=digest,
            expected_byte_size=reservation.expected_byte_size,
        )
        try:
            self._upload_repository.acquire_content_lock(
                session,
                organization_id=scope.organization_id,
                sha256=digest,
            )
            reference = self._adapter.promote_snapshot(snapshot)
        finally:
            self._adapter.cleanup_snapshot(snapshot)
        inspection = snapshot.inspection
        cleanup = StagingCleanupIntent(
            organization_id=scope.organization_id,
            upload_id=upload_id,
        )
        asset = self._repository.register(
            session,
            asset_id=new_uuid7(),
            scope=scope,
            asset_kind=asset_kind,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
            reference=reference,
            sha256=digest,
            byte_size=inspection.byte_size,
            media_type=media_type,
            created_by_subject_id=context.actor_subject_id,
            created_at=utc_now(),
        )
        self._upload_repository.mark_finalized(
            reservation,
            asset_id=asset.id,
            now=now,
        )
        self._outbox.add(
            session,
            scope=scope,
            event_type="storage.staging_cleanup.requested",
            aggregate_type="object_asset",
            aggregate_id=asset.id,
            payload={
                "asset_id": str(asset.id),
                "upload_id": str(cleanup.upload_id),
            },
            idempotency_key=f"staging-cleanup:{cleanup.upload_id}",
            available_at=reservation.expires_at + timedelta(minutes=1),
        )
        return asset

    def create_download(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        asset_id: UUID,
        expires_in_seconds: int = 300,
    ) -> AssetDownload:
        asset = self._repository.get_available(
            session,
            organization_id=context.organization_id,
            asset_id=asset_id,
        )
        self._require_context_asset(context, asset)
        self._authorizer.authorize_download(session, context=context, asset=asset)
        try:
            audit_event_id = self._auditor.record_asset_read(
                session,
                organization_id=asset.organization_id,
                project_id=asset.project_id,
                actor_subject_id=context.actor_subject_id,
                asset_id=asset.id,
            )
            session.flush()
        except Exception:
            raise ObjectAuditRequiredError() from None
        request = self._adapter.presign_download(
            StoredObjectRef(bucket=asset.bucket, key=asset.object_key),
            expires_in_seconds=expires_in_seconds,
        )
        return AssetDownload(
            asset_id=asset.id,
            audit_event_id=audit_event_id,
            url=request.url,
            expires_in_seconds=request.expires_in_seconds,
        )

    @staticmethod
    def _require_context_scope(context: StorageRequestContext, scope: TenantScope) -> None:
        if context.organization_id != scope.organization_id:
            raise ObjectAccessDeniedError()
        if (
            scope.access_scope is AccessScope.PROJECT
            and scope.project_id not in context.project_ids
        ):
            raise ObjectAccessDeniedError()

    @staticmethod
    def _require_context_asset(context: StorageRequestContext, asset: ObjectAsset) -> None:
        if context.organization_id != asset.organization_id:
            raise ObjectAccessDeniedError()
        if asset.project_id is not None and asset.project_id not in context.project_ids:
            raise ObjectAccessDeniedError()
