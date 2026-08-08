"""Application and database authorization interfaces."""

from pcbknowledge.platform.authorization.models import (
    AccessScope,
    AccessScopeKind,
    LicenseClass,
    LicensePolicy,
    SourceOrganization,
)
from pcbknowledge.platform.authorization.policy import (
    AccessScopeRef,
    AuthorizationDecision,
    AuthorizationDeniedError,
    Capability,
    DenialReason,
    LicenseAction,
    LicensePolicySnapshot,
    ResourceAuthorization,
    authorize,
    require_authorized,
)
from pcbknowledge.platform.authorization.session_context import (
    RlsContextError,
    install_principal_context,
    install_verified_identity_context,
)

__all__ = [
    "AccessScope",
    "AccessScopeKind",
    "AccessScopeRef",
    "AuthorizationDecision",
    "AuthorizationDeniedError",
    "Capability",
    "DenialReason",
    "LicenseAction",
    "LicenseClass",
    "LicensePolicy",
    "LicensePolicySnapshot",
    "ResourceAuthorization",
    "RlsContextError",
    "SourceOrganization",
    "authorize",
    "install_principal_context",
    "install_verified_identity_context",
    "require_authorized",
]
