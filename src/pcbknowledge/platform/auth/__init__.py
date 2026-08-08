"""OIDC authentication public interface."""

from pcbknowledge.platform.auth.errors import AuthenticationError, AuthenticationFailure
from pcbknowledge.platform.auth.oidc import (
    JwksSigningKeyResolver,
    OidcTokenVerifier,
    OidcVerifierConfig,
    SigningKeyResolver,
    VerifiedOidcClaims,
)
from pcbknowledge.platform.auth.readiness import OidcTrustUnavailableError, probe_oidc_trust

__all__ = [
    "AuthenticationError",
    "AuthenticationFailure",
    "JwksSigningKeyResolver",
    "OidcTokenVerifier",
    "OidcTrustUnavailableError",
    "OidcVerifierConfig",
    "SigningKeyResolver",
    "VerifiedOidcClaims",
    "probe_oidc_trust",
]
