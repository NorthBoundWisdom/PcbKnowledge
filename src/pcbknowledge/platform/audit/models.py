"""Append-only audit event persistence model."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from pcbknowledge.platform.database import Base
from pcbknowledge.platform.identity.types import PrincipalKind
from pcbknowledge.platform.ids import new_uuid7


class AuditOutcome(StrEnum):
    """Outcome of an audited attempt."""

    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    FAILED = "FAILED"


class AuditEvent(Base):
    """Permanent event protected by RLS and database mutation triggers."""

    __tablename__ = "audit_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_audit_event_project_organization",
        ),
        ForeignKeyConstraint(
            ["actor_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_audit_event_actor_organization",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_audit_event_id_uuid7"),
        CheckConstraint(
            "resource_id IS NULL OR substring(resource_id::text, 15, 1) = '7'",
            name="ck_audit_event_resource_id_uuid7",
        ),
        CheckConstraint(
            "(actor_subject_id IS NULL AND actor_kind IS NULL) OR "
            "(actor_subject_id IS NOT NULL AND actor_kind IS NOT NULL)",
            name="ck_audit_event_actor_pair",
        ),
        CheckConstraint("jsonb_typeof(detail) = 'object'", name="ck_audit_event_detail_object"),
        {"schema": "audit"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    project_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    actor_subject_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    actor_kind: Mapped[PrincipalKind | None] = mapped_column(
        Enum(
            PrincipalKind,
            native_enum=False,
            length=32,
            create_constraint=True,
            name="ck_audit_event_actor_kind",
        )
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    outcome: Mapped[AuditOutcome] = mapped_column(
        Enum(
            AuditOutcome,
            native_enum=False,
            length=16,
            create_constraint=True,
            name="ck_audit_event_outcome",
        ),
        nullable=False,
    )
    request_id: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


Index(
    "ix_audit_event_tenant_time",
    AuditEvent.organization_id,
    AuditEvent.project_id,
    AuditEvent.occurred_at.desc(),
)
