from typing import cast

import pytest
from fastapi import FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from pcbknowledge.platform.auth import VerifiedOidcClaims
from pcbknowledge.platform.http.authentication import authenticate_request
from pcbknowledge.platform.identity.types import Principal, PrincipalKind, Role
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.time import utc_now
from pcbknowledge.shared.errors import ProblemException


def _principal() -> Principal:
    return Principal(
        subject_id=new_uuid7(),
        issuer="https://identity.example/realms/pcbknowledge",
        subject="user-1",
        kind=PrincipalKind.HUMAN,
        organization_id=new_uuid7(),
        organization_roles=frozenset({Role.DATA_CURATOR}),
    )


class StubVerifier:
    def __init__(self, claims: VerifiedOidcClaims) -> None:
        self.claims = claims

    def verify(self, token: str) -> VerifiedOidcClaims:
        assert token == "opaque-access-token"
        return self.claims


class StubResolver:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    def resolve(self, session: Session, claims: VerifiedOidcClaims) -> Principal:
        assert claims.subject == self.principal.subject
        return self.principal


def _request(app: FastAPI) -> Request:
    return Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/session",
            "headers": [],
            "query_string": b"",
            "scheme": "https",
            "server": ("test", 443),
            "client": ("test", 1),
            "root_path": "",
        }
    )


def test_authentication_uses_injected_verified_claims_and_mapping() -> None:
    principal = _principal()
    now = utc_now()
    claims = VerifiedOidcClaims(
        issuer=principal.issuer,
        subject=principal.subject,
        audience="pcbknowledge-api",
        authorized_party="pcbknowledge-curator-web",
        subject_kind=PrincipalKind.HUMAN,
        expires_at=now,
        issued_at=now,
        not_before=None,
        token_id=None,
    )
    app = FastAPI()
    app.state.oidc_verifier = StubVerifier(claims)
    app.state.principal_resolver = StubResolver(principal)

    result = authenticate_request(
        _request(app),
        cast(Session, object()),
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="opaque-access-token",
        ),
    )

    assert result == principal


@pytest.mark.parametrize(
    "credentials",
    [
        None,
        HTTPAuthorizationCredentials(scheme="Basic", credentials="opaque-access-token"),
    ],
)
def test_authentication_missing_or_wrong_scheme_fails_with_bearer_challenge(
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    app = FastAPI()

    with pytest.raises(ProblemException) as error:
        authenticate_request(_request(app), cast(Session, object()), credentials)

    assert error.value.status == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}
    assert "opaque-access-token" not in str(error.value)
