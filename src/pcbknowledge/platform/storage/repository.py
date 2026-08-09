"""Object asset registry repository."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.jobs.repository import TenantScope
from pcbknowledge.platform.storage.adapter import StoredObjectRef
from pcbknowledge.platform.storage.errors import (
    ObjectAssetNotFoundError,
    ObjectIntegrityError,
    StagingUploadNotFoundError,
    StagingUploadStateError,
)
from pcbknowledge.platform.storage.models import (
    ObjectAsset,
    ObjectAssetState,
    StagingUploadReservation,
    StagingUploadState,
)


class ObjectAssetRepository:
    """Registry operations scoped by stable asset UUID, never caller-provided keys."""

    def register(
        self,
        session: Session,
        *,
        asset_id: UUID,
        scope: TenantScope,
        asset_kind: str,
        access_scope_id: UUID,
        license_policy_id: UUID,
        reference: StoredObjectRef,
        sha256: str,
        byte_size: int,
        media_type: str,
        created_by_subject_id: UUID,
        created_at: datetime,
    ) -> ObjectAsset:
        statement = (
            insert(ObjectAsset)
            .values(
                id=asset_id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
                asset_kind=asset_kind,
                bucket=reference.bucket,
                object_key=reference.key,
                sha256=sha256,
                byte_size=byte_size,
                media_type=media_type,
                state=ObjectAssetState.AVAILABLE.value,
                created_by_subject_id=created_by_subject_id,
                created_at=created_at,
            )
            .on_conflict_do_nothing()
            .returning(ObjectAsset)
        )
        created = session.execute(statement).scalar_one_or_none()
        if created is not None:
            return created
        existing = session.scalar(
            select(ObjectAsset).where(
                ObjectAsset.organization_id == scope.organization_id,
                ObjectAsset.project_id == scope.project_id,
                ObjectAsset.access_scope == scope.access_scope.value,
                ObjectAsset.asset_kind == asset_kind,
                ObjectAsset.sha256 == sha256,
            )
        )
        if existing is None:
            raise ObjectIntegrityError()
        if (
            existing.bucket != reference.bucket
            or existing.object_key != reference.key
            or existing.byte_size != byte_size
            or existing.access_scope_id != access_scope_id
            or existing.license_policy_id != license_policy_id
        ):
            raise ObjectIntegrityError()
        return existing

    def get_available(
        self,
        session: Session,
        *,
        organization_id: UUID,
        asset_id: UUID,
    ) -> ObjectAsset:
        asset = session.scalar(
            select(ObjectAsset).where(
                ObjectAsset.id == asset_id,
                ObjectAsset.organization_id == organization_id,
                ObjectAsset.state == ObjectAssetState.AVAILABLE.value,
            )
        )
        if asset is None:
            raise ObjectAssetNotFoundError()
        return asset


class StagingUploadRepository:
    """Persist and validate the ownership binding for opaque staging IDs."""

    def reserve(
        self,
        session: Session,
        *,
        scope: TenantScope,
        access_scope_id: UUID,
        license_policy_id: UUID,
        created_by_subject_id: UUID,
        media_type: str,
        expected_byte_size: int,
        created_at: datetime,
        expires_at: datetime,
    ) -> StagingUploadReservation:
        reservation = session.execute(
            insert(StagingUploadReservation)
            .values(
                id=new_uuid7(),
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                access_scope=scope.access_scope.value,
                access_scope_id=access_scope_id,
                license_policy_id=license_policy_id,
                created_by_subject_id=created_by_subject_id,
                media_type=media_type,
                expected_byte_size=expected_byte_size,
                state=StagingUploadState.PENDING.value,
                created_at=created_at,
                expires_at=expires_at,
            )
            .returning(StagingUploadReservation)
        ).scalar_one()
        return reservation

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
        reservation = session.scalar(
            self._scoped(scope).where(StagingUploadReservation.id == upload_id).with_for_update()
        )
        if reservation is None:
            raise StagingUploadNotFoundError()
        if (
            reservation.state != StagingUploadState.PENDING.value
            or reservation.expires_at <= now
            or reservation.access_scope_id != access_scope_id
            or reservation.license_policy_id != license_policy_id
            or reservation.created_by_subject_id != created_by_subject_id
            or reservation.media_type != media_type
        ):
            raise StagingUploadStateError()
        return reservation

    def require_submitted(
        self,
        session: Session,
        *,
        scope: TenantScope,
        upload_id: UUID,
        access_scope_id: UUID,
        license_policy_id: UUID,
        created_by_subject_id: UUID,
        media_type: str,
    ) -> StagingUploadReservation:
        """Lock an accepted upload; queue latency must not invalidate its bytes."""

        reservation = session.scalar(
            self._scoped(scope).where(StagingUploadReservation.id == upload_id).with_for_update()
        )
        if reservation is None:
            raise StagingUploadNotFoundError()
        if (
            reservation.state != StagingUploadState.SUBMITTED.value
            or reservation.access_scope_id != access_scope_id
            or reservation.license_policy_id != license_policy_id
            or reservation.created_by_subject_id != created_by_subject_id
            or reservation.media_type != media_type
        ):
            raise StagingUploadStateError()
        return reservation

    @staticmethod
    def acquire_content_lock(session: Session, *, organization_id: UUID, sha256: str) -> None:
        """Serialize canonical first-write per organization/digest until commit."""

        session.execute(
            text("SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(:key, 0))"),
            {"key": f"{organization_id}:{sha256}"},
        )

    @staticmethod
    def mark_submitted(reservation: StagingUploadReservation) -> None:
        reservation.state = StagingUploadState.SUBMITTED.value

    @staticmethod
    def mark_pending_after_terminal_failure(reservation: StagingUploadReservation) -> None:
        reservation.state = StagingUploadState.PENDING.value

    @staticmethod
    def mark_finalized(
        reservation: StagingUploadReservation,
        *,
        asset_id: UUID,
        now: datetime,
    ) -> None:
        reservation.state = StagingUploadState.FINALIZED.value
        reservation.asset_id = asset_id
        reservation.finalized_at = now

    def require_finalized_cleanup(
        self,
        session: Session,
        *,
        scope: TenantScope,
        upload_id: UUID,
        asset_id: UUID,
    ) -> StagingUploadReservation:
        reservation = session.scalar(
            self._scoped(scope).where(StagingUploadReservation.id == upload_id).with_for_update()
        )
        if reservation is None:
            raise StagingUploadNotFoundError()
        if (
            reservation.state != StagingUploadState.FINALIZED.value
            or reservation.asset_id != asset_id
        ):
            raise StagingUploadStateError()
        return reservation

    def claim_one_expired(
        self,
        session: Session,
        *,
        scope: TenantScope,
        cleanup_before: datetime,
    ) -> StagingUploadReservation | None:
        return session.scalar(
            self._scoped(scope)
            .where(
                StagingUploadReservation.state == StagingUploadState.PENDING.value,
                StagingUploadReservation.expires_at <= cleanup_before,
            )
            .order_by(StagingUploadReservation.expires_at, StagingUploadReservation.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )

    @staticmethod
    def mark_cleaned(reservation: StagingUploadReservation, *, now: datetime) -> None:
        reservation.state = StagingUploadState.CLEANED.value
        reservation.cleaned_at = now

    @staticmethod
    def mark_expired(reservation: StagingUploadReservation, *, now: datetime) -> None:
        reservation.state = StagingUploadState.EXPIRED.value
        reservation.cleaned_at = now

    @staticmethod
    def _scoped(scope: TenantScope) -> Select[tuple[StagingUploadReservation]]:
        return select(StagingUploadReservation).where(
            StagingUploadReservation.organization_id == scope.organization_id,
            StagingUploadReservation.project_id == scope.project_id,
            StagingUploadReservation.access_scope == scope.access_scope.value,
        )
