from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pcbknowledge.api import create_app
from pcbknowledge.platform.auth import VerifiedOidcClaims
from pcbknowledge.platform.http.authentication import request_database_session
from pcbknowledge.platform.identity.types import Principal, PrincipalKind, Role
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.time import utc_now


class StubVerifier:
    def __init__(self, principal: Principal) -> None:
        now = utc_now()
        self.claims = VerifiedOidcClaims(
            issuer=principal.issuer,
            subject=principal.subject,
            audience="pcbknowledge-api",
            authorized_party="pcbknowledge-curator-web",
            subject_kind=principal.kind,
            expires_at=now,
            issued_at=now,
            not_before=None,
            token_id=None,
        )

    def verify(self, token: str) -> VerifiedOidcClaims:
        assert token == "opaque-access-token"
        return self.claims


class StubResolver:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    def resolve(self, session: Session, claims: VerifiedOidcClaims) -> Principal:
        return self.principal


class StubAuditWriter:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[object] = []

    def append(self, session: Session, draft: object, *, principal: Principal) -> object:
        if self.fail:
            raise RuntimeError("simulated audit failure")
        self.events.append(draft)
        return object()


class CommitFailingRuntime:
    @contextmanager
    def transaction(self) -> Iterator[Session]:
        yield cast(Session, object())
        raise RuntimeError("simulated database commit failure with secret detail")


def _principal() -> Principal:
    project_id = new_uuid7()
    return Principal(
        subject_id=new_uuid7(),
        issuer="https://identity.example/realms/pcbknowledge",
        subject="user-1",
        kind=PrincipalKind.HUMAN,
        organization_id=new_uuid7(),
        organization_roles=frozenset({Role.AUDITOR}),
        project_roles={project_id: frozenset({Role.DOMAIN_REVIEWER})},
    )


def _application(principal: Principal, audit_writer: StubAuditWriter) -> FastAPI:
    application = create_app()
    application.state.oidc_verifier = StubVerifier(principal)
    application.state.principal_resolver = StubResolver(principal)
    application.state.audit_writer = audit_writer

    def fake_session() -> Iterator[Session]:
        yield cast(Session, object())

    application.dependency_overrides[request_database_session] = fake_session
    return application


def test_session_returns_only_trusted_mapping_and_writes_audit() -> None:
    principal = _principal()
    auditor = StubAuditWriter()
    with TestClient(_application(principal, auditor)) as client:
        response = client.get(
            "/session",
            headers={"Authorization": "Bearer opaque-access-token"},
        )

    assert response.status_code == 200
    assert response.json()["subject_id"] == str(principal.subject_id)
    assert response.json()["organization_id"] == str(principal.organization_id)
    assert response.json()["subject_kind"] == "HUMAN"
    assert response.json()["organization_roles"] == ["AUDITOR"]
    assert response.json()["authenticated_at"].endswith("Z")
    assert "token" not in response.text.lower()
    assert len(auditor.events) == 1


def test_session_fails_when_required_audit_write_fails() -> None:
    principal = _principal()
    with TestClient(
        _application(principal, StubAuditWriter(fail=True)),
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/session",
            headers={"Authorization": "Bearer opaque-access-token"},
        )

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert "simulated" not in response.text


def test_session_does_not_send_success_before_transaction_commit() -> None:
    principal = _principal()
    application = create_app()
    application.state.database_runtime = CommitFailingRuntime()
    application.state.oidc_verifier = StubVerifier(principal)
    application.state.principal_resolver = StubResolver(principal)
    application.state.audit_writer = StubAuditWriter()

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get(
            "/session",
            headers={"Authorization": "Bearer opaque-access-token"},
        )

    assert response.status_code == 500
    assert "secret detail" not in response.text


def test_session_requires_bearer_authentication() -> None:
    principal = _principal()
    with TestClient(_application(principal, StubAuditWriter())) as client:
        response = client.get("/session")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
