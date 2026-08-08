"""Explicit real-PostgreSQL fixtures shared by M1 platform integration tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pcbknowledge.platform.authorization.models import (
    AccessScope,
    AccessScopeKind,
    LicenseClass,
    LicensePolicy,
)
from pcbknowledge.platform.database.health import EXPECTED_DATABASE_REVISION
from pcbknowledge.platform.identity.models import ExternalSubject, Membership, Organization, Project
from pcbknowledge.platform.identity.types import Principal, PrincipalKind, Role
from pcbknowledge.platform.ids import new_uuid7

TEST_DATABASE_DSN_ENV = "PCBKNOWLEDGE_M1_TEST_DATABASE_DSN"
TEST_ROLE = "pcbknowledge_app"


@dataclass(frozen=True, slots=True)
class IdentitySeed:
    organization_a: UUID
    organization_b: UUID
    project_a1: UUID
    project_a2: UUID
    project_b1: UUID
    subject_a: UUID
    scope_a1: UUID
    scope_a2: UUID
    policy_a1_allow: UUID
    policy_a1_deny: UUID
    policy_a2_allow: UUID
    principal_a: Principal


def require_postgres_engine() -> Engine:
    dsn = os.environ.get(TEST_DATABASE_DSN_ENV)
    if dsn is None:
        pytest.skip(f"set {TEST_DATABASE_DSN_ENV} to run real PostgreSQL integration tests")
    url = make_url(dsn)
    if url.drivername != "postgresql+psycopg" or url.database is None:
        pytest.fail(f"{TEST_DATABASE_DSN_ENV} must be a postgresql+psycopg DSN")
    if not url.database.startswith("pcbknowledge_m1_test"):
        pytest.fail("refusing to mutate a database without the pcbknowledge_m1_test prefix")
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.connect() as connection:
        revision = connection.scalar(
            text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
        )
    if revision != EXPECTED_DATABASE_REVISION:
        engine.dispose()
        pytest.fail(f"M1 test database must be migrated through {EXPECTED_DATABASE_REVISION}")
    return engine


def reset_and_seed(engine: Engine) -> IdentitySeed:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE platform.staging_upload_reservation, "
                "platform.job_effect_receipt, platform.outbox_event, "
                "platform.object_asset, platform.knowledge_job, audit.audit_event, "
                "source.license_policy, source.access_scope, source.source_organization, "
                "identity.membership, identity.external_subject, identity.project, "
                "identity.organization CASCADE"
            )
        )
    seed = _seed_identity(engine)
    _require_application_role(engine)
    return seed


def install_rls_context(
    session: Session, *, organization_id: UUID, project_ids: frozenset[UUID]
) -> None:
    """Become a non-owner role and install transaction-local trusted GUCs."""

    project_value = ",".join(sorted(str(project_id) for project_id in project_ids))
    session.execute(text(f"SET LOCAL ROLE {TEST_ROLE}"))
    session.execute(
        text("SELECT set_config('pcbknowledge.organization_id', :value, true)"),
        {"value": str(organization_id)},
    )
    session.execute(
        text("SELECT set_config('pcbknowledge.project_ids', :value, true)"),
        {"value": project_value},
    )


def _seed_identity(engine: Engine) -> IdentitySeed:
    organization_a = Organization(
        id=new_uuid7(), slug=f"org-a-{new_uuid7().hex[:8]}", display_name="Organization A"
    )
    organization_b = Organization(
        id=new_uuid7(), slug=f"org-b-{new_uuid7().hex[:8]}", display_name="Organization B"
    )
    project_a1 = Project(
        id=new_uuid7(),
        organization_id=organization_a.id,
        slug="project-a1",
        display_name="Project A1",
    )
    project_a2 = Project(
        id=new_uuid7(),
        organization_id=organization_a.id,
        slug="project-a2",
        display_name="Project A2",
    )
    project_b1 = Project(
        id=new_uuid7(),
        organization_id=organization_b.id,
        slug="project-b1",
        display_name="Project B1",
    )
    subject_a = ExternalSubject(
        id=new_uuid7(),
        organization_id=organization_a.id,
        issuer="https://identity.example.test/realms/pcbknowledge",
        external_subject="m1-storage-curator",
        subject_kind=PrincipalKind.HUMAN,
        display_name="M1 Storage Curator",
    )
    memberships = [
        Membership(
            id=new_uuid7(),
            organization_id=organization_a.id,
            external_subject_id=subject_a.id,
            project_id=project_a1.id,
            role=Role.DATA_CURATOR,
        ),
        Membership(
            id=new_uuid7(),
            organization_id=organization_a.id,
            external_subject_id=subject_a.id,
            project_id=project_a2.id,
            role=Role.DATA_CURATOR,
        ),
    ]
    scope_a1 = AccessScope(
        id=new_uuid7(),
        organization_id=organization_a.id,
        project_id=project_a1.id,
        name="Project A1 confidential",
        scope_kind=AccessScopeKind.PROJECT,
    )
    scope_a2 = AccessScope(
        id=new_uuid7(),
        organization_id=organization_a.id,
        project_id=project_a2.id,
        name="Project A2 confidential",
        scope_kind=AccessScopeKind.PROJECT,
    )
    allow_policy = LicensePolicy(
        id=new_uuid7(),
        organization_id=organization_a.id,
        access_scope_id=scope_a1.id,
        name="Human raw read allowed",
        license_class=LicenseClass.PROJECT_CONFIDENTIAL,
        allow_metadata_read=True,
        allow_human_raw_access=True,
    )
    deny_policy = LicensePolicy(
        id=new_uuid7(),
        organization_id=organization_a.id,
        access_scope_id=scope_a1.id,
        name="Raw read denied",
        license_class=LicenseClass.LICENSED_BLOCKED_FOR_AI,
    )
    allow_policy_a2 = LicensePolicy(
        id=new_uuid7(),
        organization_id=organization_a.id,
        access_scope_id=scope_a2.id,
        name="Project A2 human raw read allowed",
        license_class=LicenseClass.PROJECT_CONFIDENTIAL,
        allow_metadata_read=True,
        allow_human_raw_access=True,
    )
    with Session(engine, expire_on_commit=False) as session, session.begin():
        # These models deliberately avoid cross-aggregate ORM relationships;
        # explicit flush boundaries therefore mirror the database FK graph.
        session.add_all([organization_a, organization_b])
        session.flush()
        session.add_all([project_a1, project_a2, project_b1, subject_a])
        session.flush()
        session.add_all([*memberships, scope_a1, scope_a2])
        session.flush()
        session.add_all([allow_policy, deny_policy, allow_policy_a2])
    principal = Principal(
        subject_id=subject_a.id,
        issuer=subject_a.issuer,
        subject=subject_a.external_subject,
        kind=PrincipalKind.HUMAN,
        organization_id=organization_a.id,
        project_roles={
            project_a1.id: frozenset({Role.DATA_CURATOR}),
            project_a2.id: frozenset({Role.DATA_CURATOR}),
        },
    )
    return IdentitySeed(
        organization_a=organization_a.id,
        organization_b=organization_b.id,
        project_a1=project_a1.id,
        project_a2=project_a2.id,
        project_b1=project_b1.id,
        subject_a=subject_a.id,
        scope_a1=scope_a1.id,
        scope_a2=scope_a2.id,
        policy_a1_allow=allow_policy.id,
        policy_a1_deny=deny_policy.id,
        policy_a2_allow=allow_policy_a2.id,
        principal_a=principal,
    )


def _require_application_role(engine: Engine) -> None:
    """Prove migrations, rather than test setup, provision a non-bypass role."""

    with engine.connect() as connection:
        role = connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :role_name"),
            {"role_name": TEST_ROLE},
        ).one_or_none()
        if role is None:
            pytest.fail(f"migration must provision the {TEST_ROLE} role")
        if role.rolsuper or role.rolbypassrls:
            pytest.fail(f"{TEST_ROLE} must be NOSUPERUSER NOBYPASSRLS")
        required = {
            "platform.knowledge_job": ("SELECT",),
            "platform.job_effect_receipt": ("SELECT", "INSERT"),
            "platform.outbox_event": ("SELECT",),
            "platform.object_asset": ("SELECT", "INSERT"),
        }
        for table_name, privileges in required.items():
            for privilege in privileges:
                granted = connection.scalar(
                    text("SELECT has_table_privilege(:role, :table, :privilege)"),
                    {
                        "role": TEST_ROLE,
                        "table": table_name,
                        "privilege": privilege,
                    },
                )
                if granted is not True:
                    pytest.fail(f"{TEST_ROLE} lacks {privilege} on {table_name}")
        queue_columns = {
            "platform.knowledge_job": {
                "INSERT": {
                    "id",
                    "organization_id",
                    "project_id",
                    "access_scope",
                    "job_type",
                    "payload",
                    "payload_sha256",
                    "idempotency_key",
                    "priority",
                    "state",
                    "available_at",
                    "attempts",
                    "max_attempts",
                    "created_at",
                    "updated_at",
                },
                "UPDATE": {
                    "state",
                    "available_at",
                    "lease_owner",
                    "lease_expires_at",
                    "attempts",
                    "last_failure_code",
                    "updated_at",
                    "completed_at",
                    "cancelled_at",
                },
            },
            "platform.outbox_event": {
                "INSERT": {
                    "id",
                    "organization_id",
                    "project_id",
                    "access_scope",
                    "event_type",
                    "aggregate_type",
                    "aggregate_id",
                    "payload",
                    "payload_sha256",
                    "idempotency_key",
                    "state",
                    "available_at",
                    "attempts",
                    "max_attempts",
                    "created_at",
                    "updated_at",
                },
                "UPDATE": {
                    "state",
                    "available_at",
                    "lease_owner",
                    "lease_expires_at",
                    "attempts",
                    "last_failure_code",
                    "updated_at",
                    "published_at",
                },
            },
        }
        for table_name, privilege_columns in queue_columns.items():
            for privilege, columns in privilege_columns.items():
                for column in columns:
                    granted = connection.scalar(
                        text("SELECT has_column_privilege(:role, :table, :column, :privilege)"),
                        {
                            "role": TEST_ROLE,
                            "table": table_name,
                            "column": column,
                            "privilege": privilege,
                        },
                    )
                    if granted is not True:
                        pytest.fail(f"{TEST_ROLE} lacks {privilege} on {table_name}.{column}")
        for column, privilege in (
            ("id", "INSERT"),
            ("organization_id", "INSERT"),
            ("state", "INSERT"),
            ("state", "UPDATE"),
            ("asset_id", "UPDATE"),
            ("finalized_at", "UPDATE"),
        ):
            granted = connection.scalar(
                text("SELECT has_column_privilege(:role, :table, :column, :privilege)"),
                {
                    "role": TEST_ROLE,
                    "table": "platform.staging_upload_reservation",
                    "column": column,
                    "privilege": privilege,
                },
            )
            if granted is not True:
                pytest.fail(f"{TEST_ROLE} lacks {privilege} on staging reservation {column}")
