"""Application-layer RBAC, project isolation, access-scope, and license guards."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from pcbknowledge.platform.authorization.models import AccessScopeKind, LicenseClass
from pcbknowledge.platform.identity.types import Principal, PrincipalKind, Role
from pcbknowledge.platform.ids import UUID7


class Capability(StrEnum):
    """Operations authorized by trusted roles rather than token claims."""

    DOCUMENT_INGEST = "DOCUMENT_INGEST"
    DOCUMENT_METADATA_WRITE = "DOCUMENT_METADATA_WRITE"
    EVIDENCE_VERIFY = "EVIDENCE_VERIFY"
    REVIEW_APPROVE = "REVIEW_APPROVE"
    KNOWLEDGE_PUBLISH = "KNOWLEDGE_PUBLISH"
    CONFLICT_RESOLVE = "CONFLICT_RESOLVE"
    POLICY_MANAGE = "POLICY_MANAGE"
    AUDIT_READ = "AUDIT_READ"
    TYPED_QUERY = "TYPED_QUERY"
    RAW_EVIDENCE_READ = "RAW_EVIDENCE_READ"
    BULK_EXPORT = "BULK_EXPORT"


class LicenseAction(StrEnum):
    """Actions controlled independently by each source license policy."""

    READ_METADATA = "READ_METADATA"
    HUMAN_READ_RAW = "HUMAN_READ_RAW"
    PARSE = "PARSE"
    USE_EXTERNAL_MODEL = "USE_EXTERNAL_MODEL"
    USE_LOCAL_MODEL = "USE_LOCAL_MODEL"
    EMBED = "EMBED"
    AGENT_READ_RAW = "AGENT_READ_RAW"
    REDISTRIBUTE = "REDISTRIBUTE"


class AccessScopeRef(BaseModel):
    """Immutable access-scope projection for authorization checks."""

    model_config = ConfigDict(frozen=True)

    id: UUID7
    organization_id: UUID7
    project_id: UUID7 | None = None
    kind: AccessScopeKind

    @model_validator(mode="after")
    def require_matching_kind(self) -> Self:
        if self.kind is AccessScopeKind.ORGANIZATION and self.project_id is not None:
            raise ValueError("organization access scope cannot name a project")
        if self.kind is AccessScopeKind.PROJECT and self.project_id is None:
            raise ValueError("project access scope must name a project")
        return self


class LicensePolicySnapshot(BaseModel):
    """Policy projection whose permission flags default to deny."""

    model_config = ConfigDict(frozen=True)

    id: UUID7
    organization_id: UUID7
    access_scope_id: UUID7
    license_class: LicenseClass
    allow_metadata_read: bool = False
    allow_human_raw_access: bool = False
    allow_parse: bool = False
    allow_external_model: bool = False
    allow_local_model: bool = False
    allow_embedding: bool = False
    allow_agent_raw_access: bool = False
    allow_redistribution: bool = False

    @model_validator(mode="after")
    def enforce_blocked_ai_class(self) -> Self:
        if self.license_class is LicenseClass.LICENSED_BLOCKED_FOR_AI and any(
            (
                self.allow_parse,
                self.allow_external_model,
                self.allow_local_model,
                self.allow_embedding,
                self.allow_agent_raw_access,
            )
        ):
            raise ValueError("LICENSED_BLOCKED_FOR_AI cannot enable automated processing")
        return self

    def allows(self, action: LicenseAction, *, principal_kind: PrincipalKind) -> bool:
        if action is LicenseAction.READ_METADATA:
            return self.allow_metadata_read
        if action is LicenseAction.HUMAN_READ_RAW:
            return principal_kind is PrincipalKind.HUMAN and self.allow_human_raw_access
        if action is LicenseAction.PARSE:
            return self.allow_parse
        if action is LicenseAction.USE_EXTERNAL_MODEL:
            return self.allow_external_model
        if action is LicenseAction.USE_LOCAL_MODEL:
            return self.allow_local_model
        if action is LicenseAction.EMBED:
            return self.allow_embedding
        if action is LicenseAction.AGENT_READ_RAW:
            return principal_kind is PrincipalKind.SERVICE_ACCOUNT and self.allow_agent_raw_access
        if action is LicenseAction.REDISTRIBUTE:
            return self.allow_redistribution
        return False


class ResourceAuthorization(BaseModel):
    """All ABAC attributes needed to authorize one protected operation."""

    model_config = ConfigDict(frozen=True)

    organization_id: UUID7
    project_id: UUID7 | None = None
    access_scope: AccessScopeRef
    license_policy: LicensePolicySnapshot | None = None
    license_action: LicenseAction | None = None

    @model_validator(mode="after")
    def require_coherent_scope_and_policy(self) -> Self:
        if self.access_scope.organization_id != self.organization_id:
            raise ValueError("access scope belongs to another organization")
        if self.project_id is not None and self.access_scope.project_id not in {
            None,
            self.project_id,
        }:
            raise ValueError("access scope belongs to another project")
        if self.license_action is not None and self.license_policy is None:
            return self
        if self.license_policy is not None:
            if self.license_policy.organization_id != self.organization_id:
                raise ValueError("license policy belongs to another organization")
            if self.license_policy.access_scope_id != self.access_scope.id:
                raise ValueError("license policy belongs to another access scope")
        return self


class DenialReason(StrEnum):
    """Non-sensitive authorization denial categories."""

    ORGANIZATION_MISMATCH = "ORGANIZATION_MISMATCH"
    PROJECT_ACCESS_REQUIRED = "PROJECT_ACCESS_REQUIRED"
    ACCESS_SCOPE_MISMATCH = "ACCESS_SCOPE_MISMATCH"
    CAPABILITY_MISSING = "CAPABILITY_MISSING"
    LICENSE_POLICY_MISSING = "LICENSE_POLICY_MISSING"
    LICENSE_ACTION_DENIED = "LICENSE_ACTION_DENIED"


class AuthorizationDecision(BaseModel):
    """Explicit allow/deny result; no implicit truthy fallback."""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: DenialReason | None = None


class AuthorizationDeniedError(PermissionError):
    """Raised when a caller requires an allowed decision."""

    def __init__(self, reason: DenialReason) -> None:
        super().__init__("access denied")
        self.reason = reason


_ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.DATA_CURATOR: frozenset(
        {
            Capability.DOCUMENT_INGEST,
            Capability.DOCUMENT_METADATA_WRITE,
            Capability.EVIDENCE_VERIFY,
            Capability.RAW_EVIDENCE_READ,
        }
    ),
    Role.DOMAIN_REVIEWER: frozenset(
        {
            Capability.REVIEW_APPROVE,
            Capability.KNOWLEDGE_PUBLISH,
            Capability.CONFLICT_RESOLVE,
            Capability.RAW_EVIDENCE_READ,
        }
    ),
    Role.KNOWLEDGE_ADMIN: frozenset(
        {
            Capability.DOCUMENT_INGEST,
            Capability.DOCUMENT_METADATA_WRITE,
            Capability.EVIDENCE_VERIFY,
            Capability.REVIEW_APPROVE,
            Capability.KNOWLEDGE_PUBLISH,
            Capability.CONFLICT_RESOLVE,
            Capability.POLICY_MANAGE,
            Capability.AUDIT_READ,
            Capability.RAW_EVIDENCE_READ,
            Capability.BULK_EXPORT,
        }
    ),
    Role.AUDITOR: frozenset({Capability.AUDIT_READ, Capability.RAW_EVIDENCE_READ}),
    Role.AGENT_SERVICE: frozenset({Capability.TYPED_QUERY, Capability.RAW_EVIDENCE_READ}),
}


def authorize(
    principal: Principal,
    capability: Capability,
    resource: ResourceAuthorization,
) -> AuthorizationDecision:
    """Apply organization, project, scope, role, then license guards in that order."""

    if principal.organization_id != resource.organization_id:
        return AuthorizationDecision(allowed=False, reason=DenialReason.ORGANIZATION_MISMATCH)

    effective_project_id = resource.project_id or resource.access_scope.project_id
    if effective_project_id is not None and effective_project_id not in principal.project_ids:
        return AuthorizationDecision(allowed=False, reason=DenialReason.PROJECT_ACCESS_REQUIRED)
    if (
        resource.access_scope.kind is AccessScopeKind.PROJECT
        and resource.access_scope.project_id != effective_project_id
    ):
        return AuthorizationDecision(allowed=False, reason=DenialReason.ACCESS_SCOPE_MISMATCH)

    effective_roles = principal.roles_for_project(effective_project_id)
    if not any(capability in _ROLE_CAPABILITIES[role] for role in effective_roles):
        return AuthorizationDecision(allowed=False, reason=DenialReason.CAPABILITY_MISSING)

    if resource.license_action is not None:
        if resource.license_policy is None:
            return AuthorizationDecision(
                allowed=False,
                reason=DenialReason.LICENSE_POLICY_MISSING,
            )
        if not resource.license_policy.allows(
            resource.license_action,
            principal_kind=principal.kind,
        ):
            return AuthorizationDecision(
                allowed=False,
                reason=DenialReason.LICENSE_ACTION_DENIED,
            )
    return AuthorizationDecision(allowed=True)


def require_authorized(
    principal: Principal,
    capability: Capability,
    resource: ResourceAuthorization,
) -> None:
    """Raise a non-disclosing error unless authorization explicitly succeeds."""

    decision = authorize(principal, capability, resource)
    if not decision.allowed:
        assert decision.reason is not None
        raise AuthorizationDeniedError(decision.reason)
