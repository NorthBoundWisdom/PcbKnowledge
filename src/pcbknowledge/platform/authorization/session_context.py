"""Transaction-local PostgreSQL GUCs used by row-level security policies."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from pcbknowledge.platform.auth import VerifiedOidcClaims
from pcbknowledge.platform.identity.types import Principal


class RlsContextError(RuntimeError):
    """Raised if callers try to install RLS context outside a transaction."""


@dataclass(frozen=True, slots=True)
class ResolvedIdentityContext:
    """Internal identity mapping result used while constructing a Principal."""

    organization_id: UUID
    external_subject_id: UUID
    issuer: str
    subject: str


def install_verified_identity_context(session: Session, claims: VerifiedOidcClaims) -> None:
    """Install bootstrap issuer/subject only after token verification."""

    _require_transaction(session)
    _set_local(session, "pcbknowledge.external_issuer", claims.issuer)
    _set_local(session, "pcbknowledge.external_subject", claims.subject)
    _set_local(session, "pcbknowledge.external_subject_id", "")
    _set_local(session, "pcbknowledge.organization_id", "")
    _set_local(session, "pcbknowledge.project_ids", "")


def install_resolved_identity_context(
    session: Session,
    context: ResolvedIdentityContext,
    *,
    candidate_project_ids: frozenset[UUID] = frozenset(),
) -> None:
    """Install trusted mapping values before membership resolution."""

    _require_transaction(session)
    _set_local(session, "pcbknowledge.external_issuer", context.issuer)
    _set_local(session, "pcbknowledge.external_subject", context.subject)
    _set_local(session, "pcbknowledge.external_subject_id", str(context.external_subject_id))
    _set_local(session, "pcbknowledge.organization_id", str(context.organization_id))
    projects = ",".join(sorted(str(project_id) for project_id in candidate_project_ids))
    _set_local(session, "pcbknowledge.project_ids", projects)


def install_principal_context(session: Session, principal: Principal) -> None:
    """Install the complete, trusted tenant context for one request transaction."""

    _require_transaction(session)
    project_ids = ",".join(sorted(str(project_id) for project_id in principal.project_ids))
    _set_local(session, "pcbknowledge.external_issuer", principal.issuer)
    _set_local(session, "pcbknowledge.external_subject", principal.subject)
    _set_local(session, "pcbknowledge.external_subject_id", str(principal.subject_id))
    _set_local(session, "pcbknowledge.organization_id", str(principal.organization_id))
    _set_local(session, "pcbknowledge.project_ids", project_ids)


def _require_transaction(session: Session) -> None:
    if not session.in_transaction():
        raise RlsContextError("RLS context requires an active transaction")


def _set_local(session: Session, name: str, value: str) -> None:
    session.execute(
        text("SELECT pg_catalog.set_config(:name, :value, true)"),
        {"name": name, "value": value},
    )
