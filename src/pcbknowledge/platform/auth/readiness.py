"""Credential-safe OIDC trust-source readiness probe."""

import json
from urllib.request import Request, urlopen

from jwt import PyJWK
from jwt.exceptions import PyJWTError

from pcbknowledge.platform.auth.oidc import is_usable_verification_jwk
from pcbknowledge.platform.config import OidcSettings

_MAXIMUM_JWKS_BYTES = 1024 * 1024


class OidcTrustUnavailableError(RuntimeError):
    """Raised without retaining provider response bodies or endpoint details."""


def probe_oidc_trust(settings: OidcSettings) -> None:
    """Fetch and minimally validate the pinned JWKS document."""

    request = Request(
        str(settings.jwks_url),
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read(_MAXIMUM_JWKS_BYTES + 1)
        if len(payload) > _MAXIMUM_JWKS_BYTES:
            raise ValueError("JWKS response is too large")
        document = json.loads(payload)
        keys = document.get("keys") if isinstance(document, dict) else None
        if not isinstance(keys, list) or not keys:
            raise ValueError("JWKS contains no keys")
        if not any(_is_usable_key(key, settings.allowed_algorithms) for key in keys):
            raise ValueError("JWKS contains no supported keyed signer")
    except OSError, PyJWTError, TypeError, ValueError:
        raise OidcTrustUnavailableError from None


def _is_usable_key(key: object, allowed_algorithms: tuple[str, ...]) -> bool:
    if not isinstance(key, dict):
        return False
    try:
        parsed_key = PyJWK.from_dict(key)
    except PyJWTError:
        return False
    return (
        is_usable_verification_jwk(
            key,
            allowed_algorithms=allowed_algorithms,
            required_algorithm=parsed_key.algorithm_name,
        )
        and parsed_key.algorithm_name in allowed_algorithms
    )
