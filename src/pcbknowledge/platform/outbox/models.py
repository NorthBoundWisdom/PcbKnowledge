"""SQLAlchemy model for transactional outbox delivery."""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pcbknowledge.platform.database.base import Base
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.time import utc_now


class OutboxState(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    PUBLISHED = "PUBLISHED"
    DEAD_LETTER = "DEAD_LETTER"


class OutboxEvent(Base):
    """An at-least-once event written in the caller's domain transaction."""

    __tablename__ = "outbox_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_outbox_project_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_outbox_id_uuid7"),
        CheckConstraint("attempts >= 0", name="ck_outbox_attempts_nonnegative"),
        CheckConstraint("max_attempts BETWEEN 1 AND 100", name="ck_outbox_max_attempts"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_outbox_payload_object"),
        CheckConstraint(
            "octet_length(payload::text) <= 8192",
            name="ck_outbox_payload_small",
        ),
        CheckConstraint(
            "payload_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_outbox_payload_sha256",
        ),
        CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_outbox_access_scope",
        ),
        CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_outbox_scope_project",
        ),
        CheckConstraint(
            "(state = 'RUNNING' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) OR "
            "(state <> 'RUNNING' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_outbox_lease_state",
        ),
        CheckConstraint(
            "state IN ('READY', 'RUNNING', 'PUBLISHED', 'DEAD_LETTER')",
            name="ck_outbox_state",
        ),
        CheckConstraint(
            "last_failure_code IS NULL OR last_failure_code ~ '^[A-Z0-9][A-Z0-9_.-]{0,127}$'",
            name="ck_outbox_failure_code",
        ),
        Index(
            "uq_outbox_scope_type_idempotency",
            "organization_id",
            text("COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "access_scope",
            "event_type",
            "idempotency_key",
            unique=True,
        ),
        Index(
            "ix_outbox_claim",
            "organization_id",
            "state",
            "available_at",
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
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default=OutboxState.READY.value)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_failure_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
