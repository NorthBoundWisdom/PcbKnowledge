import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pcbknowledge.platform.audit import AuditEvent, AuditEventDraft, AuditOutcome, AuditWriter
from pcbknowledge.platform.auth import (
    AuthenticationError,
    AuthenticationFailure,
    VerifiedOidcClaims,
)
from pcbknowledge.platform.authorization import AccessScope, AccessScopeKind
from pcbknowledge.platform.authorization.session_context import install_principal_context
from pcbknowledge.platform.identity import (
    ExternalSubject,
    Membership,
    Organization,
    PrincipalKind,
    Project,
    Role,
)
from pcbknowledge.platform.identity.resolver import PrincipalResolver
from pcbknowledge.platform.ids import new_uuid7

pytestmark = pytest.mark.skipif(
    os.getenv("PCBKNOWLEDGE_RUN_POSTGRES_TESTS") != "1",
    reason="set PCBKNOWLEDGE_RUN_POSTGRES_TESTS=1 against disposable PostgreSQL",
)


class SecurityGraph(TypedDict):
    org_a: UUID
    org_b: UUID
    project_a: UUID
    project_a_inactive: UUID
    project_b: UUID
    human_a: UUID


@pytest.fixture()
def postgres_session() -> Iterator[Session]:
    dsn = os.environ["PCBKNOWLEDGE_DATABASE_DSN"]
    engine = create_engine(dsn)
    connection = engine.connect()
    transaction = connection.begin()
    connection.exec_driver_sql("SET LOCAL ROLE pcbknowledge_app")
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _set_context(
    session: Session,
    *,
    organization_id: UUID | str,
    project_ids: list[UUID] | str,
    subject_id: UUID | str = "",
) -> None:
    projects = project_ids if isinstance(project_ids, str) else ",".join(map(str, project_ids))
    session.execute(
        text("SELECT set_config('pcbknowledge.organization_id', :value, true)"),
        {"value": str(organization_id)},
    )
    session.execute(
        text("SELECT set_config('pcbknowledge.project_ids', :value, true)"),
        {"value": projects},
    )
    session.execute(
        text("SELECT set_config('pcbknowledge.external_subject_id', :value, true)"),
        {"value": str(subject_id)},
    )


def _seed_security_graph(session: Session) -> SecurityGraph:
    # Fixtures seed through the migration owner. The runtime role is deliberately
    # read-only for identity/source policy so compromised request SQL cannot
    # manufacture memberships or relax licenses.
    session.execute(text("RESET ROLE"))
    org_a, org_b = new_uuid7(), new_uuid7()
    project_a, project_a_inactive, project_b = new_uuid7(), new_uuid7(), new_uuid7()
    human_a, human_inactive_project, human_disabled_org = (
        new_uuid7(),
        new_uuid7(),
        new_uuid7(),
    )

    _set_context(
        session,
        organization_id=org_a,
        project_ids=[project_a, project_a_inactive],
    )
    session.add(Organization(id=org_a, slug=f"org-a-{org_a}", display_name="Org A"))
    session.flush()
    session.add_all(
        [
            Project(
                id=project_a,
                organization_id=org_a,
                slug=f"project-a-{project_a}",
                display_name="Project A",
            ),
            Project(
                id=project_a_inactive,
                organization_id=org_a,
                slug=f"project-a-off-{project_a_inactive}",
                display_name="Inactive Project A",
                active=False,
            ),
        ]
    )
    session.add_all(
        [
            ExternalSubject(
                id=human_a,
                organization_id=org_a,
                issuer="https://id.example.test/realms/pcbknowledge",
                external_subject="human-a",
                subject_kind=PrincipalKind.HUMAN,
                display_name="Human A",
            ),
            ExternalSubject(
                id=human_inactive_project,
                organization_id=org_a,
                issuer="https://id.example.test/realms/pcbknowledge",
                external_subject="human-inactive-project",
                subject_kind=PrincipalKind.HUMAN,
                display_name="Inactive Project Human",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            Membership(
                id=new_uuid7(),
                organization_id=org_a,
                external_subject_id=human_a,
                project_id=project_a,
                role=Role.DATA_CURATOR,
            ),
            Membership(
                id=new_uuid7(),
                organization_id=org_a,
                external_subject_id=human_a,
                project_id=project_a_inactive,
                role=Role.DOMAIN_REVIEWER,
            ),
            Membership(
                id=new_uuid7(),
                organization_id=org_a,
                external_subject_id=human_inactive_project,
                project_id=project_a_inactive,
                role=Role.DATA_CURATOR,
            ),
        ]
    )
    session.add_all(
        [
            AccessScope(
                id=new_uuid7(),
                organization_id=org_a,
                name=f"org-a-scope-{org_a}",
                scope_kind=AccessScopeKind.ORGANIZATION,
            ),
            AccessScope(
                id=new_uuid7(),
                organization_id=org_a,
                project_id=project_a,
                name=f"project-a-scope-{project_a}",
                scope_kind=AccessScopeKind.PROJECT,
            ),
            AccessScope(
                id=new_uuid7(),
                organization_id=org_a,
                project_id=project_a_inactive,
                name=f"project-a-off-scope-{project_a_inactive}",
                scope_kind=AccessScopeKind.PROJECT,
            ),
        ]
    )
    session.flush()

    _set_context(session, organization_id=org_b, project_ids=[project_b])
    session.add(
        Organization(id=org_b, slug=f"org-b-{org_b}", display_name="Disabled Org B", active=False)
    )
    session.flush()
    session.add(
        Project(
            id=project_b,
            organization_id=org_b,
            slug=f"project-b-{project_b}",
            display_name="Project B",
        )
    )
    session.add(
        ExternalSubject(
            id=human_disabled_org,
            organization_id=org_b,
            issuer="https://id.example.test/realms/pcbknowledge",
            external_subject="human-disabled-org",
            subject_kind=PrincipalKind.HUMAN,
            display_name="Disabled Org Human",
        )
    )
    session.flush()
    session.add(
        Membership(
            id=new_uuid7(),
            organization_id=org_b,
            external_subject_id=human_disabled_org,
            project_id=project_b,
            role=Role.DATA_CURATOR,
        )
    )
    session.add(
        AccessScope(
            id=new_uuid7(),
            organization_id=org_b,
            project_id=project_b,
            name=f"project-b-scope-{project_b}",
            scope_kind=AccessScopeKind.PROJECT,
        )
    )
    session.flush()
    session.expire_all()
    session.execute(text("SET LOCAL ROLE pcbknowledge_app"))
    return {
        "org_a": org_a,
        "org_b": org_b,
        "project_a": project_a,
        "project_a_inactive": project_a_inactive,
        "project_b": project_b,
        "human_a": human_a,
    }


def _claims(subject: str) -> VerifiedOidcClaims:
    now = datetime.now(UTC)
    return VerifiedOidcClaims(
        issuer="https://id.example.test/realms/pcbknowledge",
        subject=subject,
        audience="pcbknowledge-api",
        authorized_party="pcbknowledge-curator-web",
        subject_kind=PrincipalKind.HUMAN,
        expires_at=now + timedelta(minutes=5),
        issued_at=now,
        not_before=None,
        token_id=None,
    )


def test_rls_helpers_and_cross_tenant_scope_fail_closed(postgres_session: Session) -> None:
    graph = _seed_security_graph(postgres_session)
    role_security = postgres_session.execute(
        text(
            "SELECT current_user, rolsuper, rolbypassrls "
            "FROM pg_catalog.pg_roles WHERE rolname = current_user"
        )
    ).one()
    assert role_security == ("pcbknowledge_app", False, False)
    role_memberships = postgres_session.scalar(
        text(
            "SELECT count(*) FROM pg_catalog.pg_auth_members AS member_map "
            "JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member "
            "JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid "
            "WHERE member_role.rolname = 'pcbknowledge_app' "
            "OR granted.rolname = 'pcbknowledge_app'"
        )
    )
    assert role_memberships == 0
    identity_policy_writes = postgres_session.scalar(
        text(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE grantee = 'pcbknowledge_app' "
            "AND table_schema IN ('identity', 'source') "
            "AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'TRIGGER')"
        )
    )
    assert identity_policy_writes == 0
    rls_flags = postgres_session.execute(
        text(
            "SELECT count(*) FROM pg_catalog.pg_class AS c "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname IN ('identity', 'source', 'audit') "
            "AND c.relname IN ("
            "'organization', 'project', 'external_subject', 'membership', "
            "'source_organization', 'access_scope', 'license_policy', 'audit_event') "
            "AND c.relrowsecurity AND c.relforcerowsecurity"
        )
    ).scalar_one()
    assert rls_flags == 8
    enum_checks = set(
        postgres_session.scalars(
            text(
                "SELECT con.conname FROM pg_catalog.pg_constraint AS con "
                "JOIN pg_catalog.pg_class AS rel ON rel.oid = con.conrelid "
                "JOIN pg_catalog.pg_namespace AS n ON n.oid = rel.relnamespace "
                "WHERE con.contype = 'c' "
                "AND n.nspname IN ('identity', 'source', 'audit')"
            )
        ).all()
    )
    assert {
        "ck_access_scope_kind",
        "ck_audit_event_actor_kind",
        "ck_audit_event_outcome",
        "ck_external_subject_kind",
        "ck_license_policy_class",
        "ck_membership_role",
    } <= enum_checks
    _set_context(postgres_session, organization_id="malformed", project_ids="")

    assert postgres_session.scalar(select(func.identity.current_organization_id())) is None
    assert postgres_session.scalar(select(func.count()).select_from(AccessScope)) == 0

    _set_context(
        postgres_session,
        organization_id=graph["org_a"],
        project_ids=f"{graph['project_a']},malformed",
    )
    assert not postgres_session.scalar(select(func.identity.can_access_project(graph["project_a"])))
    assert postgres_session.scalar(select(func.count()).select_from(AccessScope)) == 1

    _set_context(
        postgres_session,
        organization_id=graph["org_a"],
        project_ids=[graph["project_a"]],
    )
    assert postgres_session.scalar(select(func.count()).select_from(AccessScope)) == 2


def test_principal_resolver_rejects_disabled_org_and_inactive_only_projects(
    postgres_session: Session,
) -> None:
    graph = _seed_security_graph(postgres_session)

    principal = PrincipalResolver().resolve(postgres_session, _claims("human-a"))
    assert principal.project_ids == {graph["project_a"]}

    with pytest.raises(AuthenticationError) as inactive_project:
        PrincipalResolver().resolve(postgres_session, _claims("human-inactive-project"))
    assert inactive_project.value.reason is AuthenticationFailure.MEMBERSHIP_MISSING

    with pytest.raises(AuthenticationError) as disabled_org:
        PrincipalResolver().resolve(postgres_session, _claims("human-disabled-org"))
    assert disabled_org.value.reason is AuthenticationFailure.SUBJECT_DISABLED


def test_audit_event_is_written_and_database_rejects_mutation(
    postgres_session: Session,
) -> None:
    _seed_security_graph(postgres_session)
    principal = PrincipalResolver().resolve(postgres_session, _claims("human-a"))
    install_principal_context(postgres_session, principal)
    event = AuditWriter().append(
        postgres_session,
        AuditEventDraft(
            organization_id=principal.organization_id,
            project_id=next(iter(principal.project_ids)),
            action="document.metadata.update",
            resource_type="document_revision",
            outcome=AuditOutcome.SUCCEEDED,
            detail={"reason_code": "CURATOR_CONFIRMED"},
        ),
        principal=principal,
    )

    savepoint = postgres_session.begin_nested()
    with pytest.raises(DBAPIError):
        postgres_session.execute(
            update(AuditEvent).where(AuditEvent.id == event.id).values(action="tampered")
        )
    savepoint.rollback()

    persisted_event = postgres_session.get(AuditEvent, event.id)
    assert persisted_event is not None
    assert persisted_event.action == "document.metadata.update"
    audit_privileges = set(
        postgres_session.scalars(
            text(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE grantee = 'pcbknowledge_app' "
                "AND table_schema = 'audit' AND table_name = 'audit_event'"
            )
        ).all()
    )
    assert audit_privileges == {"INSERT", "SELECT"}
    trigger_exists = postgres_session.scalar(
        text(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_trigger "
            "WHERE tgrelid = 'audit.audit_event'::regclass "
            "AND tgname = 'reject_audit_event_mutation' AND NOT tgisinternal)"
        )
    )
    assert trigger_exists
