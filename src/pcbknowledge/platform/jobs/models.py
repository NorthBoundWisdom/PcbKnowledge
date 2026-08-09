"""SQLAlchemy models for the PostgreSQL-backed durable job queue."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pcbknowledge.platform.database.base import Base
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.time import utc_now


class AccessScope(StrEnum):
    """Storage scope repeated on platform rows for policy and RLS."""

    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"


class JobState(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DEAD_LETTER = "DEAD_LETTER"
    CANCELLED = "CANCELLED"


class KnowledgeJob(Base):
    """A leased, retryable unit of asynchronous work."""

    __tablename__ = "knowledge_job"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_job_project_organization",
        ),
        UniqueConstraint("id", "organization_id", name="uq_job_id_organization"),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_job_id_uuid7"),
        CheckConstraint("priority BETWEEN -1000 AND 1000", name="ck_job_priority"),
        CheckConstraint("attempts >= 0", name="ck_job_attempts_nonnegative"),
        CheckConstraint("max_attempts BETWEEN 1 AND 100", name="ck_job_max_attempts"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_job_payload_object"),
        CheckConstraint("octet_length(payload::text) <= 8192", name="ck_job_payload_small"),
        CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_job_payload_sha256"),
        CheckConstraint("length(btrim(job_type)) > 0", name="ck_job_type_nonempty"),
        CheckConstraint(
            "length(btrim(idempotency_key)) > 0",
            name="ck_job_idempotency_nonempty",
        ),
        CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_job_access_scope",
        ),
        CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_job_scope_project",
        ),
        CheckConstraint(
            "(state = 'RUNNING' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(state <> 'RUNNING' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_job_lease_state",
        ),
        CheckConstraint(
            "state IN ('READY', 'RUNNING', 'COMPLETED', 'DEAD_LETTER', 'CANCELLED')",
            name="ck_job_state",
        ),
        CheckConstraint(
            "last_failure_code IS NULL OR last_failure_code ~ '^[A-Z0-9][A-Z0-9_.-]{0,127}$'",
            name="ck_job_failure_code",
        ),
        Index(
            "uq_job_scope_type_idempotency",
            "organization_id",
            text("COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "access_scope",
            "job_type",
            "idempotency_key",
            unique=True,
        ),
        Index(
            "ix_job_claim",
            "organization_id",
            "state",
            "available_at",
            text("priority DESC"),
            "created_at",
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
    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=JobState.READY.value)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_failure_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobEffectReceipt(Base):
    """Transactional proof that one named domain effect ran for a durable job."""

    __tablename__ = "job_effect_receipt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["platform.knowledge_job.id", "platform.knowledge_job.organization_id"],
            ondelete="RESTRICT",
            name="fk_job_effect_job_organization",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_job_effect_project_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_job_effect_id_uuid7"),
        CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_job_effect_access_scope",
        ),
        CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_job_effect_scope_project",
        ),
        CheckConstraint(
            "length(btrim(effect_name)) > 0",
            name="ck_job_effect_name_nonempty",
        ),
        CheckConstraint(
            "effect_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_job_effect_sha256",
        ),
        CheckConstraint(
            "(lease_attempt IS NULL AND lease_owner IS NULL) OR "
            "(lease_attempt > 0 AND lease_owner IS NOT NULL)",
            name="ck_job_effect_lease_attempt",
        ),
        UniqueConstraint("job_id", "effect_name", name="uq_job_effect_once"),
        {"schema": "platform"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid7)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    access_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    effect_name: Mapped[str] = mapped_column(String(128), nullable=False)
    effect_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_attempt: Mapped[int | None] = mapped_column(
        Integer,
        comment="NULL with lease_owner NULL means pre-0008 lease provenance is UNKNOWN",
    )
    lease_owner: Mapped[str | None] = mapped_column(
        String(200),
        comment="NULL with lease_attempt NULL means pre-0008 lease provenance is UNKNOWN",
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
