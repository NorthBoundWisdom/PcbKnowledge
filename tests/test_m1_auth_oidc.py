import json
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt import PyJWK
from jwt.algorithms import ECAlgorithm, RSAAlgorithm
from pydantic import ValidationError

from pcbknowledge.platform.auth import (
    AuthenticationError,
    AuthenticationFailure,
    JwksSigningKeyResolver,
    OidcTokenVerifier,
    OidcVerifierConfig,
)
from pcbknowledge.platform.identity import PrincipalKind


class StaticKeyResolver:
    def __init__(self, key: PyJWK) -> None:
        self.key = key
        self.calls = 0

    def resolve(self, *, token: str, key_id: str, algorithm: str) -> PyJWK:
        self.calls += 1
        assert token
        assert key_id == "test-key"
        assert algorithm == "RS256"
        return self.key


@pytest.fixture(scope="module")
def signing_material() -> tuple[Any, PyJWK]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk_document = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk_document.update(
        {
            "kid": "test-key",
            "alg": "RS256",
            "use": "sig",
            "key_ops": ["verify"],
        }
    )
    return private_key, PyJWK.from_dict(jwk_document)


def _config() -> OidcVerifierConfig:
    return OidcVerifierConfig(
        issuer="https://id.example.test/realms/pcbknowledge",
        audience="pcbknowledge-api",
        human_client_ids={"pcbknowledge-curator-web"},
        service_account_client_ids={"pcbknowledge-agent-service"},
        leeway_seconds=0,
    )


def _payload(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": "https://id.example.test/realms/pcbknowledge",
        "aud": "pcbknowledge-api",
        "sub": "human-123",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "iat": int((now - timedelta(seconds=1)).timestamp()),
        "azp": "pcbknowledge-curator-web",
        "pcbknowledge_subject_kind": "HUMAN",
        "jti": "token-123",
    }
    payload.update(overrides)
    return payload


def _token(private_key: Any, payload: dict[str, Any], *, algorithm: str = "RS256") -> str:
    return jwt.encode(
        payload,
        private_key,
        algorithm=algorithm,
        headers={"kid": "test-key"},
    )


def test_verifier_accepts_only_fully_verified_human_claims(
    signing_material: tuple[Any, PyJWK],
) -> None:
    private_key, public_jwk = signing_material
    resolver = StaticKeyResolver(public_jwk)

    claims = OidcTokenVerifier(_config(), resolver).verify(_token(private_key, _payload()))

    assert claims.subject == "human-123"
    assert claims.subject_kind is PrincipalKind.HUMAN
    assert claims.authorized_party == "pcbknowledge-curator-web"
    assert resolver.calls == 1


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"iss": "https://wrong.example.test"}, AuthenticationFailure.INVALID_TOKEN),
        ({"aud": "another-api"}, AuthenticationFailure.INVALID_TOKEN),
        ({"exp": 1}, AuthenticationFailure.INVALID_TOKEN),
        ({"pcbknowledge_subject_kind": "ROBOT"}, AuthenticationFailure.INVALID_CLAIMS),
        (
            {
                "pcbknowledge_subject_kind": "HUMAN",
                "azp": "pcbknowledge-agent-service",
            },
            AuthenticationFailure.CLIENT_KIND_MISMATCH,
        ),
        (
            {
                "pcbknowledge_subject_kind": "SERVICE_ACCOUNT",
                "azp": "pcbknowledge-curator-web",
            },
            AuthenticationFailure.CLIENT_KIND_MISMATCH,
        ),
        ({"sub": "x" * 513}, AuthenticationFailure.INVALID_CLAIMS),
    ],
)
def test_verifier_rejects_authority_lifetime_kind_and_client_mismatch(
    signing_material: tuple[Any, PyJWK],
    overrides: dict[str, Any],
    reason: AuthenticationFailure,
) -> None:
    private_key, public_jwk = signing_material
    verifier = OidcTokenVerifier(_config(), StaticKeyResolver(public_jwk))

    with pytest.raises(AuthenticationError) as error:
        verifier.verify(_token(private_key, _payload(**overrides)))

    assert error.value.reason is reason
    assert str(error.value) == "authentication failed"


def test_verifier_rejects_unsigned_or_symmetric_algorithm_before_key_lookup(
    signing_material: tuple[Any, PyJWK],
) -> None:
    _, public_jwk = signing_material
    resolver = StaticKeyResolver(public_jwk)
    token = jwt.encode(
        _payload(),
        "not-a-trusted-asymmetric-key-at-least-32-bytes",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )

    with pytest.raises(AuthenticationError) as error:
        OidcTokenVerifier(_config(), resolver).verify(token)

    assert error.value.reason is AuthenticationFailure.DISALLOWED_ALGORITHM
    assert resolver.calls == 0


def test_jwks_resolver_maps_malformed_payload_to_safe_authentication_failure() -> None:
    token = "eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3Qta2V5In0.eA.eA"
    verifier = OidcTokenVerifier(
        _config(),
        JwksSigningKeyResolver("https://identity.invalid.example/jwks"),
    )

    with pytest.raises(AuthenticationError) as error:
        verifier.verify(token)

    assert error.value.reason is AuthenticationFailure.MALFORMED_TOKEN
    assert str(error.value) == "authentication failed"


def test_verifier_rejects_ec_only_key_for_rs256_token(
    signing_material: tuple[Any, PyJWK],
) -> None:
    rsa_private_key, _ = signing_material
    ec_private_key = ec.generate_private_key(ec.SECP256R1())
    ec_document = json.loads(ECAlgorithm.to_jwk(ec_private_key.public_key()))
    ec_document.update(
        {
            "kid": "test-key",
            "alg": "ES256",
            "use": "sig",
            "key_ops": ["verify"],
        }
    )

    with pytest.raises(AuthenticationError) as error:
        OidcTokenVerifier(
            _config(),
            StaticKeyResolver(PyJWK.from_dict(ec_document)),
        ).verify(_token(rsa_private_key, _payload()))

    assert error.value.reason is AuthenticationFailure.SIGNING_KEY_UNAVAILABLE


@pytest.mark.parametrize(
    "metadata",
    [
        {"use": "enc", "key_ops": ["verify"]},
        {"use": "sig", "key_ops": ["sign"]},
    ],
)
def test_verifier_rejects_jwk_without_verification_only_metadata(
    signing_material: tuple[Any, PyJWK],
    metadata: dict[str, Any],
) -> None:
    private_key, _ = signing_material
    document = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    document.update({"kid": "test-key", "alg": "RS256", **metadata})

    with pytest.raises(AuthenticationError) as error:
        OidcTokenVerifier(
            _config(),
            StaticKeyResolver(PyJWK.from_dict(document)),
        ).verify(_token(private_key, _payload()))

    assert error.value.reason is AuthenticationFailure.SIGNING_KEY_UNAVAILABLE


def test_verifier_accepts_optional_use_and_key_ops_metadata(
    signing_material: tuple[Any, PyJWK],
) -> None:
    private_key, _ = signing_material
    document = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    document.update({"kid": "test-key", "alg": "RS256"})

    claims = OidcTokenVerifier(
        _config(),
        StaticKeyResolver(PyJWK.from_dict(document)),
    ).verify(_token(private_key, _payload()))

    assert claims.subject == "human-123"


def test_verifier_requires_actor_kind_claim(
    signing_material: tuple[Any, PyJWK],
) -> None:
    private_key, public_jwk = signing_material
    payload = _payload()
    del payload["pcbknowledge_subject_kind"]

    with pytest.raises(AuthenticationError) as error:
        OidcTokenVerifier(_config(), StaticKeyResolver(public_jwk)).verify(
            _token(private_key, payload)
        )

    assert error.value.reason is AuthenticationFailure.INVALID_TOKEN


def test_verifier_configuration_requires_both_disjoint_client_classes() -> None:
    with pytest.raises(ValidationError):
        OidcVerifierConfig(
            issuer="https://id.example.test/realms/pcbknowledge",
            audience="pcbknowledge-api",
            human_client_ids={"web"},
            service_account_client_ids=set(),
        )
    with pytest.raises(ValidationError):
        OidcVerifierConfig(
            issuer="https://id.example.test/realms/pcbknowledge",
            audience="pcbknowledge-api",
            human_client_ids={"same"},
            service_account_client_ids={"same"},
        )
