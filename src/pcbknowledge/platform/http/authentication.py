"""Bearer authentication joined to the request's single database transaction."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Protocol, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy.orm import Session

from pcbknowledge.platform.auth import (
    AuthenticationError,
    AuthenticationFailure,
    JwksSigningKeyResolver,
    OidcTokenVerifier,
    OidcVerifierConfig,
    VerifiedOidcClaims,
)
from pcbknowledge.platform.config import OidcSettings, get_oidc_settings
from pcbknowledge.platform.database import DatabaseRuntime, get_database_runtime
from pcbknowledge.platform.identity.resolver import PrincipalResolver
from pcbknowledge.platform.identity.types import Principal
from pcbknowledge.platform.observability import current_request_context, enrich_request_context
from pcbknowledge.platform.observability.metrics import AUTHENTICATION_FAILURES
from pcbknowledge.shared.errors import ProblemException

_bearer = HTTPBearer(auto_error=False)


class TokenVerifier(Protocol):
    def verify(self, token: str) -> VerifiedOidcClaims: ...


class IdentityResolver(Protocol):
    def resolve(self, session: Session, claims: VerifiedOidcClaims) -> Principal: ...


def request_database_session(request: Request) -> Iterator[Session]:
    """Yield the one explicit transaction shared by auth, audit, and route work."""

    runtime = cast(
        DatabaseRuntime,
        getattr(request.app.state, "database_runtime", None) or get_database_runtime(),
    )
    with runtime.transaction() as session:
        yield session


# The transaction must commit before FastAPI starts the response. Request-scoped
# yield dependencies finalize after the response has already been sent and can
# therefore report success for a failed business/audit commit.
SessionDependency = Annotated[
    Session,
    Depends(request_database_session, scope="function"),
]
CredentialsDependency = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(_bearer),
]


def authenticate_request(
    request: Request,
    session: SessionDependency,
    credentials: CredentialsDependency,
) -> Principal:
    """Verify the token before installing its exact trusted DB identity mapping."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        AUTHENTICATION_FAILURES.labels(AuthenticationFailure.MALFORMED_TOKEN.value).inc()
        raise _authentication_problem()

    try:
        verifier = cast(
            TokenVerifier,
            getattr(request.app.state, "oidc_verifier", None) or get_oidc_verifier(),
        )
        resolver = cast(
            IdentityResolver,
            getattr(request.app.state, "principal_resolver", None) or PrincipalResolver(),
        )
        claims = verifier.verify(credentials.credentials)
        principal = resolver.resolve(session, claims)
    except ValidationError as exc:
        raise ProblemException(
            status=503,
            title="Service unavailable",
            detail="The authentication boundary is not configured.",
            type_uri="urn:pcbknowledge:problem:authentication-unavailable",
        ) from exc
    except AuthenticationError as exc:
        AUTHENTICATION_FAILURES.labels(exc.reason.value).inc()
        if exc.reason is AuthenticationFailure.SIGNING_KEY_UNAVAILABLE:
            raise ProblemException(
                status=503,
                title="Service unavailable",
                detail="The identity provider trust keys are unavailable.",
                type_uri="urn:pcbknowledge:problem:authentication-unavailable",
            ) from exc
        raise _authentication_problem() from exc

    if current_request_context() is not None:
        enrich_request_context(
            subject_id=principal.subject_id,
            organization_id=principal.organization_id,
            project_id=None,
        )
    return principal


PrincipalDependency = Annotated[Principal, Depends(authenticate_request)]


@lru_cache(maxsize=1)
def get_oidc_verifier() -> OidcTokenVerifier:
    """Build one verifier from pinned configuration without fetching keys eagerly."""

    settings: OidcSettings = get_oidc_settings()
    return OidcTokenVerifier(
        OidcVerifierConfig(
            issuer=str(settings.issuer_url).rstrip("/"),
            audience=settings.audience,
            algorithms=settings.allowed_algorithms,
            human_client_ids=frozenset({settings.browser_client_id}),
            service_account_client_ids=frozenset({settings.service_client_id}),
            leeway_seconds=settings.clock_skew_seconds,
        ),
        JwksSigningKeyResolver(
            str(settings.jwks_url),
            timeout_seconds=5.0,
            lifespan_seconds=settings.jwks_cache_seconds,
        ),
    )


def _authentication_problem() -> ProblemException:
    return ProblemException(
        status=401,
        title="Authentication required",
        detail="A valid bearer access token is required.",
        type_uri="urn:pcbknowledge:problem:authentication-required",
        headers={"WWW-Authenticate": "Bearer"},
    )
