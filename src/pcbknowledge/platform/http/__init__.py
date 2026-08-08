"""FastAPI dependencies for authenticated, transaction-scoped platform requests."""

from pcbknowledge.platform.http.authentication import (
    PrincipalDependency,
    SessionDependency,
    authenticate_request,
    request_database_session,
)

__all__ = [
    "PrincipalDependency",
    "SessionDependency",
    "authenticate_request",
    "request_database_session",
]
