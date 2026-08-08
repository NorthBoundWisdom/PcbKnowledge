"""SQLAlchemy mappings for organizations and trusted external subjects."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pcbknowledge.platform.database import Base
from pcbknowledge.platform.identity.types import PrincipalKind, Role
from pcbknowledge.platform.ids import new_uuid7


class Organization(Base):
    """Tenant boundary."""

    __tablename__ = "organization"
    __table_args__ = (
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_organization_id_uuid7"),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class Project(Base):
    """Explicit project-isolation boundary inside an organization."""

    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_project_organization_slug"),
        UniqueConstraint("id", "organization_id", name="uq_project_id_organization"),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_project_id_uuid7"),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class ExternalSubject(Base):
    """Verified OIDC issuer/subject pair mapped to an internal organization."""

    __tablename__ = "external_subject"
    __table_args__ = (
        UniqueConstraint("issuer", "external_subject", name="uq_external_subject_issuer_subject"),
        UniqueConstraint("id", "organization_id", name="uq_external_subject_id_organization"),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_external_subject_id_uuid7"),
        CheckConstraint(
            "(subject_kind = 'HUMAN' AND client_id IS NULL) OR "
            "(subject_kind = 'SERVICE_ACCOUNT' AND client_id IS NOT NULL "
            "AND length(btrim(client_id)) > 0)",
            name="ck_external_subject_service_client",
        ),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    external_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    subject_kind: Mapped[PrincipalKind] = mapped_column(
        Enum(
            PrincipalKind,
            native_enum=False,
            length=32,
            create_constraint=True,
            name="ck_external_subject_kind",
        ),
        nullable=False,
    )
    client_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="external_subject_record", cascade="all, delete-orphan"
    )


class Membership(Base):
    """A trusted role grant at organization or explicit project scope."""

    __tablename__ = "membership"
    __table_args__ = (
        ForeignKeyConstraint(
            ["external_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="CASCADE",
            name="fk_membership_subject_organization",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="CASCADE",
            name="fk_membership_project_organization",
        ),
        UniqueConstraint(
            "external_subject_id",
            "organization_id",
            "project_id",
            "role",
            name="uq_membership_subject_scope_role",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_membership_id_uuid7"),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    external_subject_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            native_enum=False,
            length=32,
            create_constraint=True,
            name="ck_membership_role",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    external_subject_record: Mapped[ExternalSubject] = relationship(back_populates="memberships")
