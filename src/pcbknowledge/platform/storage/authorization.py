"""Concrete RBAC/ABAC/license authorization for object storage."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from pcbknowledge.platform.authorization import (
    AccessScope,
    AccessScopeKind,
    AccessScopeRef,
    AuthorizationDeniedError,
    Capability,
    LicenseAction,
    LicensePolicy,
    LicensePolicySnapshot,
    ResourceAuthorization,
    require_authorized,
)
from pcbknowledge.platform.identity.types import Principal, PrincipalKind
from pcbknowledge.platform.jobs.repository import TenantScope
from pcbknowledge.platform.storage.errors import ObjectAccessDeniedError
from pcbknowledge.platform.storage.models import ObjectAsset
from pcbknowledge.platform.storage.service import StorageRequestContext


class PolicyStorageAuthorizer:
    """Resolve trusted source policy rows before every upload or raw download."""

    def __init__(self, principal: Principal) -> None:
        self._principal = principal

    def authorize_upload(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        scope: TenantScope,
        access_scope_id: UUID,
        license_policy_id: UUID,
    ) -> None:
        self._require_context(context)
        resource = self._load_resource(
            session,
            organization_id=scope.organization_id,
            project_id=scope.project_id,
            access_scope_id=access_scope_id,
            license_policy_id=license_policy_id,
            license_action=None,
        )
        self._require(Capability.DOCUMENT_INGEST, resource)

    def authorize_download(
        self,
        session: Session,
        *,
        context: StorageRequestContext,
        asset: ObjectAsset,
    ) -> None:
        self._require_context(context)
        action = (
            LicenseAction.AGENT_READ_RAW
            if self._principal.kind is PrincipalKind.SERVICE_ACCOUNT
            else LicenseAction.HUMAN_READ_RAW
        )
        resource = self._load_resource(
            session,
            organization_id=asset.organization_id,
            project_id=asset.project_id,
            access_scope_id=asset.access_scope_id,
            license_policy_id=asset.license_policy_id,
            license_action=action,
        )
        self._require(Capability.RAW_EVIDENCE_READ, resource)

    def _load_resource(
        self,
        session: Session,
        *,
        organization_id: UUID,
        project_id: UUID | None,
        access_scope_id: UUID,
        license_policy_id: UUID,
        license_action: LicenseAction | None,
    ) -> ResourceAuthorization:
        access_scope = session.scalar(
            select(AccessScope).where(
                AccessScope.id == access_scope_id,
                AccessScope.organization_id == organization_id,
            )
        )
        license_policy = session.scalar(
            select(LicensePolicy).where(
                LicensePolicy.id == license_policy_id,
                LicensePolicy.organization_id == organization_id,
                LicensePolicy.access_scope_id == access_scope_id,
            )
        )
        if access_scope is None or license_policy is None:
            raise ObjectAccessDeniedError()
        expected_scope_kind = (
            AccessScopeKind.PROJECT if project_id is not None else AccessScopeKind.ORGANIZATION
        )
        if (
            access_scope.scope_kind is not expected_scope_kind
            or access_scope.project_id != project_id
        ):
            raise ObjectAccessDeniedError()
        return ResourceAuthorization(
            organization_id=organization_id,
            project_id=project_id,
            access_scope=AccessScopeRef(
                id=access_scope.id,
                organization_id=access_scope.organization_id,
                project_id=access_scope.project_id,
                kind=access_scope.scope_kind,
            ),
            license_policy=LicensePolicySnapshot(
                id=license_policy.id,
                organization_id=license_policy.organization_id,
                access_scope_id=license_policy.access_scope_id,
                license_class=license_policy.license_class,
                allow_metadata_read=license_policy.allow_metadata_read,
                allow_human_raw_access=license_policy.allow_human_raw_access,
                allow_parse=license_policy.allow_parse,
                allow_external_model=license_policy.allow_external_model,
                allow_local_model=license_policy.allow_local_model,
                allow_embedding=license_policy.allow_embedding,
                allow_agent_raw_access=license_policy.allow_agent_raw_access,
                allow_redistribution=license_policy.allow_redistribution,
            ),
            license_action=license_action,
        )

    def _require_context(self, context: StorageRequestContext) -> None:
        if (
            context.organization_id != self._principal.organization_id
            or context.actor_subject_id != self._principal.subject_id
            or context.project_ids != self._principal.project_ids
        ):
            raise ObjectAccessDeniedError()

    def _require(self, capability: Capability, resource: ResourceAuthorization) -> None:
        try:
            require_authorized(self._principal, capability, resource)
        except AuthorizationDeniedError:
            raise ObjectAccessDeniedError() from None
