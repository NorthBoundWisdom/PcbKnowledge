"""Resolve verified OIDC claims through trusted database mappings and grants."""

from collections import defaultdict
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from pcbknowledge.platform.auth import (
    AuthenticationError,
    AuthenticationFailure,
    VerifiedOidcClaims,
)
from pcbknowledge.platform.authorization.session_context import (
    ResolvedIdentityContext,
    install_principal_context,
    install_resolved_identity_context,
    install_verified_identity_context,
)
from pcbknowledge.platform.identity.models import ExternalSubject, Membership, Organization, Project
from pcbknowledge.platform.identity.types import Principal, PrincipalKind, Role


class PrincipalResolver:
    """Build a Principal only from verified claims and active trusted DB rows."""

    def resolve(self, session: Session, claims: VerifiedOidcClaims) -> Principal:
        install_verified_identity_context(session, claims)
        mapping = session.scalar(
            select(ExternalSubject).where(
                ExternalSubject.issuer == claims.issuer,
                ExternalSubject.external_subject == claims.subject,
            )
        )
        if mapping is None:
            raise AuthenticationError(AuthenticationFailure.SUBJECT_NOT_MAPPED)
        if not mapping.active:
            raise AuthenticationError(AuthenticationFailure.SUBJECT_DISABLED)
        if mapping.subject_kind is not claims.subject_kind:
            raise AuthenticationError(AuthenticationFailure.SUBJECT_MAPPING_MISMATCH)
        if (
            mapping.subject_kind is PrincipalKind.SERVICE_ACCOUNT
            and mapping.client_id != claims.authorized_party
        ):
            raise AuthenticationError(AuthenticationFailure.SUBJECT_MAPPING_MISMATCH)

        install_resolved_identity_context(
            session,
            ResolvedIdentityContext(
                organization_id=mapping.organization_id,
                external_subject_id=mapping.id,
                issuer=mapping.issuer,
                subject=mapping.external_subject,
            ),
        )
        organization = session.get(Organization, mapping.organization_id)
        if organization is None or not organization.active:
            raise AuthenticationError(AuthenticationFailure.SUBJECT_DISABLED)
        memberships = session.scalars(
            select(Membership).where(Membership.external_subject_id == mapping.id)
        ).all()
        if not memberships:
            raise AuthenticationError(AuthenticationFailure.MEMBERSHIP_MISSING)

        candidate_project_ids = frozenset(
            membership.project_id for membership in memberships if membership.project_id is not None
        )
        install_resolved_identity_context(
            session,
            ResolvedIdentityContext(
                organization_id=mapping.organization_id,
                external_subject_id=mapping.id,
                issuer=mapping.issuer,
                subject=mapping.external_subject,
            ),
            candidate_project_ids=candidate_project_ids,
        )
        active_project_ids = set(
            session.scalars(
                select(Project.id).where(
                    Project.id.in_(candidate_project_ids),
                    Project.active.is_(True),
                )
            ).all()
        )

        organization_roles: set[Role] = set()
        project_roles: defaultdict[UUID, set[Role]] = defaultdict(set)
        for membership in memberships:
            if membership.project_id is None:
                organization_roles.add(membership.role)
            elif membership.project_id in active_project_ids:
                project_roles[membership.project_id].add(membership.role)
        if not organization_roles and not project_roles:
            raise AuthenticationError(AuthenticationFailure.MEMBERSHIP_MISSING)
        try:
            principal = Principal(
                subject_id=mapping.id,
                issuer=mapping.issuer,
                subject=mapping.external_subject,
                kind=mapping.subject_kind,
                client_id=mapping.client_id,
                organization_id=mapping.organization_id,
                organization_roles=frozenset(organization_roles),
                project_roles={
                    project_id: frozenset(roles) for project_id, roles in project_roles.items()
                },
            )
        except ValidationError as exc:
            raise AuthenticationError(AuthenticationFailure.SUBJECT_MAPPING_MISMATCH) from exc
        install_principal_context(session, principal)
        return principal
