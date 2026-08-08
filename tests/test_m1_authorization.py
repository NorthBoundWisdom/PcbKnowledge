import pytest
from pydantic import ValidationError

from pcbknowledge.platform.authorization import (
    AccessScopeKind,
    AccessScopeRef,
    Capability,
    DenialReason,
    LicenseAction,
    LicenseClass,
    LicensePolicySnapshot,
    ResourceAuthorization,
    authorize,
)
from pcbknowledge.platform.identity import Principal, PrincipalKind, Role
from pcbknowledge.platform.ids import UUID7, new_uuid7


def _principal(
    *,
    organization_id: UUID7,
    project_id: UUID7 | None,
    role: Role = Role.DATA_CURATOR,
) -> Principal:
    return Principal(
        subject_id=new_uuid7(),
        issuer="https://id.example.test/realms/pcbknowledge",
        subject="human-123",
        kind=PrincipalKind.HUMAN,
        organization_id=organization_id,
        organization_roles={role},
        project_roles={project_id: {role}} if project_id is not None else {},
    )


def _resource(
    *,
    organization_id: UUID7,
    project_id: UUID7 | None,
    allow_metadata: bool,
) -> ResourceAuthorization:
    scope = AccessScopeRef(
        id=new_uuid7(),
        organization_id=organization_id,
        project_id=project_id,
        kind=AccessScopeKind.PROJECT if project_id else AccessScopeKind.ORGANIZATION,
    )
    policy = LicensePolicySnapshot(
        id=new_uuid7(),
        organization_id=organization_id,
        access_scope_id=scope.id,
        license_class=LicenseClass.PUBLIC_REFERENCE,
        allow_metadata_read=allow_metadata,
    )
    return ResourceAuthorization(
        organization_id=organization_id,
        project_id=project_id,
        access_scope=scope,
        license_policy=policy,
        license_action=LicenseAction.READ_METADATA,
    )


def test_authorization_allows_explicit_role_project_scope_and_license() -> None:
    organization_id = new_uuid7()
    project_id = new_uuid7()

    decision = authorize(
        _principal(organization_id=organization_id, project_id=project_id),
        Capability.DOCUMENT_INGEST,
        _resource(
            organization_id=organization_id,
            project_id=project_id,
            allow_metadata=True,
        ),
    )

    assert decision.allowed
    assert decision.reason is None


def test_authorization_denies_cross_organization_and_project() -> None:
    organization_id = new_uuid7()
    principal = _principal(organization_id=organization_id, project_id=new_uuid7())

    wrong_org = authorize(
        principal,
        Capability.DOCUMENT_INGEST,
        _resource(
            organization_id=new_uuid7(),
            project_id=None,
            allow_metadata=True,
        ),
    )
    wrong_project = authorize(
        principal,
        Capability.DOCUMENT_INGEST,
        _resource(
            organization_id=organization_id,
            project_id=new_uuid7(),
            allow_metadata=True,
        ),
    )

    assert wrong_org.reason is DenialReason.ORGANIZATION_MISMATCH
    assert wrong_project.reason is DenialReason.PROJECT_ACCESS_REQUIRED


def test_org_role_does_not_grant_an_unassigned_project() -> None:
    organization_id = new_uuid7()
    principal = _principal(organization_id=organization_id, project_id=None)
    project_id = new_uuid7()

    decision = authorize(
        principal,
        Capability.DOCUMENT_INGEST,
        _resource(
            organization_id=organization_id,
            project_id=project_id,
            allow_metadata=True,
        ),
    )

    assert decision.reason is DenialReason.PROJECT_ACCESS_REQUIRED
    assert principal.roles_for_project(project_id) == frozenset()


def test_license_policy_is_default_deny() -> None:
    organization_id = new_uuid7()
    principal = _principal(organization_id=organization_id, project_id=None)

    decision = authorize(
        principal,
        Capability.DOCUMENT_INGEST,
        _resource(
            organization_id=organization_id,
            project_id=None,
            allow_metadata=False,
        ),
    )

    assert decision.reason is DenialReason.LICENSE_ACTION_DENIED


def test_blocked_for_ai_class_cannot_enable_automated_processing() -> None:
    with pytest.raises(ValidationError):
        LicensePolicySnapshot(
            id=new_uuid7(),
            organization_id=new_uuid7(),
            access_scope_id=new_uuid7(),
            license_class=LicenseClass.LICENSED_BLOCKED_FOR_AI,
            allow_parse=True,
        )


def test_human_and_service_roles_cannot_be_mixed() -> None:
    common = {
        "subject_id": new_uuid7(),
        "issuer": "https://id.example.test/realms/pcbknowledge",
        "subject": "actor",
        "organization_id": new_uuid7(),
    }
    with pytest.raises(ValidationError):
        Principal(
            **common,
            kind=PrincipalKind.HUMAN,
            organization_roles={Role.AGENT_SERVICE},
        )
    with pytest.raises(ValidationError):
        Principal(
            **common,
            kind=PrincipalKind.SERVICE_ACCOUNT,
            client_id="agent-service",
            organization_roles={Role.DATA_CURATOR},
        )
