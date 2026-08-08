"""Object asset registry model; object keys remain an internal implementation detail."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pcbknowledge.platform.database import Base
from pcbknowledge.platform.ids import new_uuid7


class ObjectAssetState(StrEnum):
    AVAILABLE = "AVAILABLE"
    QUARANTINED = "QUARANTINED"
    TOMBSTONED = "TOMBSTONED"


class StagingUploadState(StrEnum):
    PENDING = "PENDING"
    FINALIZED = "FINALIZED"
    CLEANED = "CLEANED"
    EXPIRED = "EXPIRED"


class ObjectAsset(Base):
    """Authorized registry identity for one organization-isolated content object."""

    __tablename__ = "object_asset"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_object_asset_project_organization",
        ),
        ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_object_asset_creator_organization",
        ),
        ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            ondelete="RESTRICT",
            name="fk_object_asset_access_scope_organization",
        ),
        ForeignKeyConstraint(
            ["license_policy_id", "organization_id", "access_scope_id"],
            [
                "source.license_policy.id",
                "source.license_policy.organization_id",
                "source.license_policy.access_scope_id",
            ],
            ondelete="RESTRICT",
            name="fk_object_asset_license_policy_scope",
        ),
        Index(
            "uq_object_asset_logical_scope",
            "organization_id",
            sa_text("COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "access_scope",
            "asset_kind",
            "sha256",
            unique=True,
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_object_asset_id_uuid7"),
        CheckConstraint("byte_size >= 0", name="ck_object_asset_byte_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_object_asset_sha256"),
        CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_object_asset_access_scope",
        ),
        CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_object_asset_scope_project",
        ),
        CheckConstraint(
            "state IN ('AVAILABLE', 'QUARANTINED', 'TOMBSTONED')",
            name="ck_object_asset_state",
        ),
        CheckConstraint(
            "object_key = 'organizations/' || organization_id::text || '/sha256/' || "
            "left(sha256, 2) || '/' || sha256",
            name="ck_object_asset_content_key",
        ),
        CheckConstraint(
            "bucket ~ '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$'",
            name="ck_object_asset_bucket",
        ),
        UniqueConstraint("id", "organization_id", name="uq_object_asset_id_organization"),
        Index("ix_object_asset_scope", "organization_id", "project_id", "state"),
        {"schema": "platform"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    access_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    access_scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    license_policy_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    asset_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ObjectAssetState.AVAILABLE.value
    )
    created_by_subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class StagingUploadReservation(Base):
    """Persistent binding for one server-issued staging object identifier."""

    __tablename__ = "staging_upload_reservation"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_staging_upload_project_organization",
        ),
        ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_staging_upload_creator_organization",
        ),
        ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            ondelete="RESTRICT",
            name="fk_staging_upload_access_scope_organization",
        ),
        ForeignKeyConstraint(
            ["license_policy_id", "organization_id", "access_scope_id"],
            [
                "source.license_policy.id",
                "source.license_policy.organization_id",
                "source.license_policy.access_scope_id",
            ],
            ondelete="RESTRICT",
            name="fk_staging_upload_license_policy_scope",
        ),
        ForeignKeyConstraint(
            ["asset_id", "organization_id"],
            ["platform.object_asset.id", "platform.object_asset.organization_id"],
            ondelete="RESTRICT",
            name="fk_staging_upload_asset_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_staging_upload_id_uuid7"),
        CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_staging_upload_access_scope",
        ),
        CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_staging_upload_scope_project",
        ),
        CheckConstraint(
            "state IN ('PENDING', 'FINALIZED', 'CLEANED', 'EXPIRED')",
            name="ck_staging_upload_state",
        ),
        CheckConstraint(
            "(state = 'PENDING' AND asset_id IS NULL AND finalized_at IS NULL "
            "AND cleaned_at IS NULL) OR "
            "(state = 'FINALIZED' AND asset_id IS NOT NULL AND finalized_at IS NOT NULL "
            "AND cleaned_at IS NULL) OR "
            "(state = 'CLEANED' AND asset_id IS NOT NULL AND finalized_at IS NOT NULL "
            "AND cleaned_at IS NOT NULL) OR "
            "(state = 'EXPIRED' AND asset_id IS NULL AND finalized_at IS NULL "
            "AND cleaned_at IS NOT NULL)",
            name="ck_staging_upload_state_fields",
        ),
        CheckConstraint("expires_at > created_at", name="ck_staging_upload_expiry"),
        CheckConstraint(
            "length(btrim(media_type)) > 0 AND octet_length(media_type) <= 200",
            name="ck_staging_upload_media_type",
        ),
        CheckConstraint(
            "expected_byte_size BETWEEN 1 AND 2147483648",
            name="ck_staging_upload_expected_byte_size",
        ),
        UniqueConstraint("id", "organization_id", name="uq_staging_upload_id_organization"),
        Index(
            "ix_staging_upload_scope_state",
            "organization_id",
            "project_id",
            "state",
            "expires_at",
        ),
        {"schema": "platform"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    access_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    access_scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    license_policy_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_by_subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=StagingUploadState.PENDING.value
    )
    asset_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.clock_timestamp()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
