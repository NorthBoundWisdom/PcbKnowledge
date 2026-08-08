"""Strict OIDC access-token verification with injectable signing-key resolution."""

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, Self
from urllib.parse import urlsplit

import jwt
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError, PyJWKError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pcbknowledge.platform.auth.errors import (
    AuthenticationError,
    AuthenticationFailure,
    MalformedSigningTokenError,
    SigningKeyResolutionError,
)
from pcbknowledge.platform.identity.types import PrincipalKind

AsymmetricJwtAlgorithm = Literal[
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
]

_ALGORITHM_KEY_TYPES: dict[str, str] = {
    "RS256": "RSA",
    "RS384": "RSA",
    "RS512": "RSA",
    "PS256": "RSA",
    "ES256": "EC",
    "ES384": "EC",
    "ES512": "EC",
    "EdDSA": "OKP",
}


def is_usable_verification_jwk(
    jwk: Mapping[str, object],
    *,
    allowed_algorithms: Collection[str],
    required_algorithm: str | None = None,
) -> bool:
    """Validate JWK intent and key type under RFC 7517 optional metadata."""

    key_id = jwk.get("kid")
    algorithm = jwk.get("alg")
    key_use = jwk.get("use")
    key_operations = jwk.get("key_ops")
    if not isinstance(key_id, str) or not key_id:
        return False
    if algorithm is not None and (
        not isinstance(algorithm, str) or algorithm not in allowed_algorithms
    ):
        return False
    if required_algorithm is not None and algorithm is not None and algorithm != required_algorithm:
        return False
    effective_algorithm = algorithm or required_algorithm
    if effective_algorithm is None or jwk.get("kty") != _ALGORITHM_KEY_TYPES.get(
        effective_algorithm
    ):
        return False
    if key_use is not None and key_use != "sig":
        return False
    return key_operations is None or (
        isinstance(key_operations, list)
        and all(isinstance(operation, str) for operation in key_operations)
        and "verify" in key_operations
    )


class OidcVerifierConfig(BaseModel):
    """Pinned token authority and allowed browser/service clients."""

    model_config = ConfigDict(frozen=True)

    issuer: str = Field(min_length=1, max_length=2048)
    audience: str = Field(min_length=1, max_length=255)
    algorithms: tuple[AsymmetricJwtAlgorithm, ...] = ("RS256",)
    human_client_ids: frozenset[str] = frozenset()
    service_account_client_ids: frozenset[str] = frozenset()
    leeway_seconds: int = Field(default=30, ge=0, le=300)
    maximum_token_bytes: int = Field(default=16_384, ge=1024, le=131_072)

    @field_validator("issuer")
    @classmethod
    def require_absolute_issuer(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("issuer must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("issuer must not contain query or fragment components")
        return value.rstrip("/")

    @field_validator("algorithms")
    @classmethod
    def require_algorithms(cls, value: tuple[AsymmetricJwtAlgorithm, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one asymmetric JWT algorithm is required")
        if len(set(value)) != len(value):
            raise ValueError("JWT algorithms must not contain duplicates")
        return value

    @model_validator(mode="after")
    def require_disjoint_client_classes(self) -> Self:
        if not self.human_client_ids or not self.service_account_client_ids:
            raise ValueError("both human and service-account client allowlists are required")
        overlap = self.human_client_ids.intersection(self.service_account_client_ids)
        if overlap:
            raise ValueError("human and service-account client IDs must be disjoint")
        return self


@dataclass(frozen=True, slots=True)
class VerifiedOidcClaims:
    """Claims returned only after cryptographic and semantic verification."""

    issuer: str
    subject: str
    audience: str
    authorized_party: str
    subject_kind: PrincipalKind
    expires_at: datetime
    issued_at: datetime
    not_before: datetime | None
    token_id: str | None


class SigningKeyResolver(Protocol):
    """Resolve only keys from a caller-configured trust source."""

    def resolve(self, *, token: str, key_id: str, algorithm: str) -> PyJWK: ...


class JwksSigningKeyResolver:
    """Resolve signing keys from one pinned JWKS endpoint."""

    def __init__(
        self,
        jwks_url: str,
        *,
        timeout_seconds: float = 5.0,
        lifespan_seconds: int = 300,
    ) -> None:
        parsed = urlsplit(jwks_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("jwks_url must be an absolute HTTP(S) URL")
        self._client = PyJWKClient(
            jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=lifespan_seconds,
            timeout=timeout_seconds,
        )

    def resolve(self, *, token: str, key_id: str, algorithm: str) -> PyJWK:
        try:
            key = self._client.get_signing_key_from_jwt(token)
        except InvalidTokenError as exc:
            raise MalformedSigningTokenError from exc
        except (PyJWKClientError, PyJWKError, OSError) as exc:
            raise SigningKeyResolutionError from exc
        if key.key_id != key_id or key.algorithm_name != algorithm:
            raise SigningKeyResolutionError
        return key


class OidcTokenVerifier:
    """Verify signature, authority, lifetime, audience, algorithm, and actor class."""

    def __init__(self, config: OidcVerifierConfig, key_resolver: SigningKeyResolver) -> None:
        self._config = config
        self._key_resolver = key_resolver

    def verify(self, token: str) -> VerifiedOidcClaims:
        if not token or len(token.encode("utf-8")) > self._config.maximum_token_bytes:
            raise AuthenticationError(AuthenticationFailure.MALFORMED_TOKEN)
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise AuthenticationError(AuthenticationFailure.MALFORMED_TOKEN) from exc

        algorithm = header.get("alg")
        key_id = header.get("kid")
        critical = header.get("crit")
        if not isinstance(algorithm, str) or algorithm not in self._config.algorithms:
            raise AuthenticationError(AuthenticationFailure.DISALLOWED_ALGORITHM)
        if not isinstance(key_id, str) or not key_id:
            raise AuthenticationError(AuthenticationFailure.MALFORMED_TOKEN)
        if critical not in (None, []):
            raise AuthenticationError(AuthenticationFailure.MALFORMED_TOKEN)

        try:
            key = self._key_resolver.resolve(
                token=token,
                key_id=key_id,
                algorithm=algorithm,
            )
        except MalformedSigningTokenError as exc:
            raise AuthenticationError(AuthenticationFailure.MALFORMED_TOKEN) from exc
        except SigningKeyResolutionError as exc:
            raise AuthenticationError(AuthenticationFailure.SIGNING_KEY_UNAVAILABLE) from exc
        raw_jwk = getattr(key, "_jwk_data", None)
        if (
            key.key_id != key_id
            or key.algorithm_name != algorithm
            or not isinstance(raw_jwk, dict)
            or not is_usable_verification_jwk(
                raw_jwk,
                allowed_algorithms=self._config.algorithms,
                required_algorithm=algorithm,
            )
        ):
            raise AuthenticationError(AuthenticationFailure.SIGNING_KEY_UNAVAILABLE)

        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "exp",
                        "iat",
                        "azp",
                        "pcbknowledge_subject_kind",
                    ],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except InvalidTokenError as exc:
            raise AuthenticationError(AuthenticationFailure.INVALID_TOKEN) from exc
        return self._map_verified_payload(payload)

    def _map_verified_payload(self, payload: dict[str, Any]) -> VerifiedOidcClaims:
        issuer = _required_string(payload, "iss", maximum_length=2048)
        subject = _required_string(payload, "sub", maximum_length=512)
        authorized_party = _required_string(payload, "azp", maximum_length=255)
        kind_value = _required_string(
            payload,
            "pcbknowledge_subject_kind",
            maximum_length=32,
        )
        try:
            subject_kind = PrincipalKind(kind_value)
        except ValueError as exc:
            raise AuthenticationError(AuthenticationFailure.INVALID_CLAIMS) from exc

        allowed_clients = (
            self._config.human_client_ids
            if subject_kind is PrincipalKind.HUMAN
            else self._config.service_account_client_ids
        )
        if authorized_party not in allowed_clients:
            raise AuthenticationError(AuthenticationFailure.CLIENT_KIND_MISMATCH)

        expires_at = _numeric_date(payload, "exp")
        issued_at = _numeric_date(payload, "iat")
        not_before = _numeric_date(payload, "nbf") if "nbf" in payload else None
        token_id_value = payload.get("jti")
        if token_id_value is not None and (
            not isinstance(token_id_value, str) or not token_id_value or len(token_id_value) > 255
        ):
            raise AuthenticationError(AuthenticationFailure.INVALID_CLAIMS)

        return VerifiedOidcClaims(
            issuer=issuer,
            subject=subject,
            audience=self._config.audience,
            authorized_party=authorized_party,
            subject_kind=subject_kind,
            expires_at=expires_at,
            issued_at=issued_at,
            not_before=not_before,
            token_id=token_id_value,
        )


def _required_string(payload: dict[str, Any], name: str, *, maximum_length: int) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value or len(value) > maximum_length:
        raise AuthenticationError(AuthenticationFailure.INVALID_CLAIMS)
    return value


def _numeric_date(payload: dict[str, Any], name: str) -> datetime:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise AuthenticationError(AuthenticationFailure.INVALID_CLAIMS)
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise AuthenticationError(AuthenticationFailure.INVALID_CLAIMS) from exc
