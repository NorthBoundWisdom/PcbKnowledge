"""Source authority, license policy, and access-scope persistence models."""

from datetime import datetime
from enum import StrEnum
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
from sqlalchemy.orm import Mapped, mapped_column

from pcbknowledge.platform.database import Base
from pcbknowledge.platform.ids import new_uuid7


class AccessScopeKind(StrEnum):
    """Access partition attached to protected sources and records."""

    ORGANIZATION = "ORGANIZATION"
    PROJECT = "PROJECT"


class LicenseClass(StrEnum):
    """Architecture-defined source data classifications."""

    OPEN_LICENSE = "OPEN_LICENSE"
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"
    LICENSED = "LICENSED"
    LICENSED_BLOCKED_FOR_AI = "LICENSED_BLOCKED_FOR_AI"
    INTERNAL = "INTERNAL"
    PROJECT_CONFIDENTIAL = "PROJECT_CONFIDENTIAL"


class SourceOrganization(Base):
    """Manufacturer, standards body, board house, or internal source authority."""

    __tablename__ = "source_organization"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_source_organization_name"),
        UniqueConstraint("id", "organization_id", name="uq_source_organization_id_organization"),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_source_organization_id_uuid7"),
        {"schema": "source"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    authority_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class AccessScope(Base):
    """Explicit organization-wide or project-confidential access boundary."""

    __tablename__ = "access_scope"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_access_scope_organization_name"),
        UniqueConstraint("id", "organization_id", name="uq_access_scope_id_organization"),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_access_scope_id_uuid7"),
        CheckConstraint(
            "(scope_kind = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(scope_kind = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_access_scope_kind_project",
        ),
        ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_access_scope_project_organization",
        ),
        {"schema": "source"},
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_kind: Mapped[AccessScopeKind] = mapped_column(
        Enum(
            AccessScopeKind,
            native_enum=False,
            length=16,
            create_constraint=True,
            name="ck_access_scope_kind",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )


class LicensePolicy(Base):
    """Versionable processing policy; every permission defaults to deny."""

    __tablename__ = "license_policy"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_license_policy_organization_name"),
        UniqueConstraint("id", "organization_id", name="uq_license_policy_id_organization"),
        UniqueConstraint(
            "id",
            "organization_id",
            "access_scope_id",
            name="uq_license_policy_id_organization_scope",
        ),
        CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_license_policy_id_uuid7"),
        CheckConstraint(
            "license_class <> 'LICENSED_BLOCKED_FOR_AI' OR "
            "(NOT allow_parse AND NOT allow_external_model AND NOT allow_local_model "
            "AND NOT allow_embedding AND NOT allow_agent_raw_access)",
            name="ck_license_policy_blocked_ai_deny",
        ),
        ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            ondelete="RESTRICT",
            name="fk_license_policy_scope_organization",
        ),
        {"schema": "source"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=new_uuid7
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("identity.organization.id", ondelete="RESTRICT"),
        nullable=False,
    )
    access_scope_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_class: Mapped[LicenseClass] = mapped_column(
        Enum(
            LicenseClass,
            native_enum=False,
            length=32,
            create_constraint=True,
            name="ck_license_policy_class",
        ),
        nullable=False,
    )
    allow_metadata_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allow_human_raw_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allow_parse: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    allow_external_model: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allow_local_model: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    allow_embedding: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    allow_agent_raw_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allow_redistribution: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
        onupdate=func.clock_timestamp(),
    )
