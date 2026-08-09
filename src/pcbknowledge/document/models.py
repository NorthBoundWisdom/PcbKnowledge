"""Immutable document records and asynchronous upload-session persistence."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pcbknowledge.platform.database import Base
from pcbknowledge.platform.ids import new_uuid7


class UploadSessionState(StrEnum):
    """Durable upload state; transient worker states are projected from its job."""

    RESERVED = "RESERVED"
    QUEUED = "QUEUED"
    STORED = "STORED"
    FAILED = "FAILED"


class DocumentRevisionState(StrEnum):
    """The first implemented state from the architecture's revision state machine."""

    STORED = "STORED"


class DocumentAssetKind(StrEnum):
    """Permanent asset relations implemented by the first intake slice."""

    ORIGINAL = "ORIGINAL"


class UploadSession(Base):
    """One authorized browser upload reservation and its immutable metadata intent."""

    __tablename__ = "upload_session"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "organization_id"],
            [
                "platform.staging_upload_reservation.id",
                "platform.staging_upload_reservation.organization_id",
            ],
            ondelete="RESTRICT",
            name="fk_upload_session_staging_reservation",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_upload_session_project_organization",
        ),
        ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            ondelete="RESTRICT",
            name="fk_upload_session_access_scope_organization",
        ),
        ForeignKeyConstraint(
            ["license_policy_id", "organization_id", "access_scope_id"],
            [
                "source.license_policy.id",
                "source.license_policy.organization_id",
                "source.license_policy.access_scope_id",
            ],
            ondelete="RESTRICT",
            name="fk_upload_session_license_policy_scope",
        ),
        ForeignKeyConstraint(
            ["source_organization_id", "organization_id"],
            [
                "source.source_organization.id",
                "source.source_organization.organization_id",
            ],
            ondelete="RESTRICT",
            name="fk_upload_session_source_organization",
        ),
        ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_upload_session_creator_organization",
        ),
        ForeignKeyConstraint(
            ["completion_job_id", "organization_id"],
            ["platform.knowledge_job.id", "platform.knowledge_job.organization_id"],
            ondelete="RESTRICT",
            name="fk_upload_session_completion_job",
        ),
        ForeignKeyConstraint(
            ["object_asset_id", "organization_id"],
            ["platform.object_asset.id", "platform.object_asset.organization_id"],
            ondelete="RESTRICT",
            name="fk_upload_session_object_asset",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_upload_session_id_uuid7"),
        CheckConstraint(
            "substring(target_document_id::text, 15, 1) = '7'",
            name="ck_upload_session_document_id_uuid7",
        ),
        CheckConstraint(
            "substring(target_revision_id::text, 15, 1) = '7'",
            name="ck_upload_session_revision_id_uuid7",
        ),
        CheckConstraint("access_scope = 'PROJECT'", name="ck_upload_session_project_scope"),
        CheckConstraint(
            "state IN ('RESERVED', 'QUEUED', 'STORED', 'FAILED')",
            name="ck_upload_session_state",
        ),
        CheckConstraint(
            "expected_byte_size BETWEEN 1 AND 268435456",
            name="ck_upload_session_byte_size",
        ),
        CheckConstraint("media_type = 'application/pdf'", name="ck_upload_session_pdf_only"),
        CheckConstraint(
            "expected_sha256 IS NULL OR expected_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_upload_session_expected_sha256",
        ),
        CheckConstraint(
            "actual_sha256 IS NULL OR actual_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_upload_session_actual_sha256",
        ),
        CheckConstraint(
            "request_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_upload_session_request_sha256",
        ),
        CheckConstraint(
            "length(btrim(idempotency_key)) BETWEEN 1 AND 200",
            name="ck_upload_session_idempotency_key",
        ),
        CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 500",
            name="ck_upload_session_title",
        ),
        CheckConstraint(
            "document_number IS NULL OR length(btrim(document_number)) BETWEEN 1 AND 255",
            name="ck_upload_session_document_number",
        ),
        CheckConstraint(
            "length(btrim(revision_label)) BETWEEN 1 AND 128",
            name="ck_upload_session_revision_label",
        ),
        CheckConstraint(
            "length(btrim(original_filename)) BETWEEN 1 AND 255 "
            "AND original_filename !~ '[\\r\\n]'",
            name="ck_upload_session_original_filename",
        ),
        CheckConstraint(
            "(state = 'RESERVED' AND completion_job_id IS NULL "
            "AND expected_sha256 IS NULL "
            "AND actual_sha256 IS NULL AND object_asset_id IS NULL "
            "AND completed_at IS NULL AND failure_code IS NULL) OR "
            "(state = 'QUEUED' AND completion_job_id IS NOT NULL "
            "AND actual_sha256 IS NULL AND object_asset_id IS NULL "
            "AND completed_at IS NULL AND failure_code IS NULL) OR "
            "(state = 'STORED' AND completion_job_id IS NOT NULL "
            "AND actual_sha256 IS NOT NULL AND object_asset_id IS NOT NULL "
            "AND completed_at IS NOT NULL AND failure_code IS NULL) OR "
            "(state = 'FAILED' AND completion_job_id IS NOT NULL "
            "AND object_asset_id IS NULL AND completed_at IS NOT NULL "
            "AND failure_code IS NOT NULL)",
            name="ck_upload_session_state_fields",
        ),
        CheckConstraint(
            "failure_code IS NULL OR failure_code ~ '^[A-Z0-9][A-Z0-9_.-]{0,127}$'",
            name="ck_upload_session_failure_code",
        ),
        UniqueConstraint("id", "organization_id", name="uq_upload_session_id_organization"),
        UniqueConstraint(
            "organization_id",
            "created_by_subject_id",
            "idempotency_key",
            name="uq_upload_session_actor_idempotency",
        ),
        Index(
            "uq_upload_session_active_document_revision",
            "target_document_id",
            "revision_label",
            unique=True,
            postgresql_where=sa_text("state <> 'FAILED'"),
        ),
        Index("ix_upload_session_scope_state", "organization_id", "project_id", "state"),
        {"schema": "document"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    access_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="PROJECT")
    access_scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    license_policy_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    creates_document: Mapped[bool] = mapped_column(Boolean, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(255))
    revision_label: Mapped[str] = mapped_column(String(128), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_sha256: Mapped[str | None] = mapped_column(String(64), server_default=sa_text("NULL"))
    actual_sha256: Mapped[str | None] = mapped_column(String(64), server_default=sa_text("NULL"))
    completion_job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), server_default=sa_text("NULL")
    )
    object_asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), server_default=sa_text("NULL")
    )
    failure_code: Mapped[str | None] = mapped_column(String(128), server_default=sa_text("NULL"))
    created_by_subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NULL")
    )


class Document(Base):
    """Stable logical identity whose metadata is immutable in the first slice."""

    __tablename__ = "document"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_project_organization",
        ),
        ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_creator_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_document_id_uuid7"),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 500", name="ck_document_title"),
        CheckConstraint(
            "document_number IS NULL OR length(btrim(document_number)) BETWEEN 1 AND 255",
            name="ck_document_number",
        ),
        UniqueConstraint("id", "organization_id", "project_id", name="uq_document_id_scope"),
        Index("ix_document_scope_id", "organization_id", "project_id", "id"),
        {"schema": "document"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_number: Mapped[str | None] = mapped_column(String(255))
    created_by_subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class DocumentRevision(Base):
    """One immutable source revision after server-side storage verification."""

    __tablename__ = "document_revision"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "organization_id", "project_id"],
            [
                "document.document.id",
                "document.document.organization_id",
                "document.document.project_id",
            ],
            ondelete="RESTRICT",
            name="fk_document_revision_document_scope",
        ),
        ForeignKeyConstraint(
            ["source_organization_id", "organization_id"],
            ["source.source_organization.id", "source.source_organization.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_revision_source_organization",
        ),
        ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_revision_access_scope",
        ),
        ForeignKeyConstraint(
            ["license_policy_id", "organization_id", "access_scope_id"],
            [
                "source.license_policy.id",
                "source.license_policy.organization_id",
                "source.license_policy.access_scope_id",
            ],
            ondelete="RESTRICT",
            name="fk_document_revision_license_policy",
        ),
        ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_revision_creator_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_document_revision_id_uuid7"),
        CheckConstraint("access_scope = 'PROJECT'", name="ck_document_revision_project_scope"),
        CheckConstraint("state = 'STORED'", name="ck_document_revision_state"),
        CheckConstraint(
            "length(btrim(revision_label)) BETWEEN 1 AND 128",
            name="ck_document_revision_label",
        ),
        CheckConstraint(
            "length(btrim(original_filename)) BETWEEN 1 AND 255 "
            "AND original_filename !~ '[\\r\\n]'",
            name="ck_document_revision_original_filename",
        ),
        CheckConstraint("media_type = 'application/pdf'", name="ck_document_revision_pdf_only"),
        UniqueConstraint("id", "organization_id", name="uq_document_revision_id_organization"),
        UniqueConstraint(
            "id", "organization_id", "project_id", name="uq_document_revision_id_scope"
        ),
        UniqueConstraint(
            "document_id", "revision_label", name="uq_document_revision_document_label"
        ),
        Index("ix_document_revision_document", "document_id", "id"),
        {"schema": "document"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    access_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="PROJECT")
    access_scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    license_policy_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_label: Mapped[str] = mapped_column(String(128), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class DocumentAsset(Base):
    """Immutable relation from one revision to an authorized object registry row."""

    __tablename__ = "document_asset"
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "organization_id", "project_id"],
            [
                "document.document_revision.id",
                "document.document_revision.organization_id",
                "document.document_revision.project_id",
            ],
            ondelete="RESTRICT",
            name="fk_document_asset_revision_scope",
        ),
        ForeignKeyConstraint(
            ["object_asset_id", "organization_id"],
            ["platform.object_asset.id", "platform.object_asset.organization_id"],
            ondelete="RESTRICT",
            name="fk_document_asset_object_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_document_asset_id_uuid7"),
        CheckConstraint("asset_kind = 'ORIGINAL'", name="ck_document_asset_kind"),
        UniqueConstraint("revision_id", "asset_kind", name="uq_document_asset_revision_kind"),
        UniqueConstraint("id", "organization_id", name="uq_document_asset_id_organization"),
        {"schema": "document"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    object_asset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    asset_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
