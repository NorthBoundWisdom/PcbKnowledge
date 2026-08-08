import asyncio
import json
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from pcbknowledge.platform.auth import OidcTrustUnavailableError, probe_oidc_trust
from pcbknowledge.platform.auth import readiness as oidc_readiness
from pcbknowledge.platform.config import ObjectStorageSettings, OidcSettings, Settings
from pcbknowledge.platform.storage import ObjectStoreUnavailableError
from pcbknowledge.readiness import ApplicationReadinessProbe


def _database_settings() -> Settings:
    return Settings(database_dsn="postgresql+psycopg://knowledge:secret@db/knowledge")


def _oidc_settings() -> OidcSettings:
    return OidcSettings(
        issuer_url="https://identity.example.test/realms/pcbknowledge",
        jwks_url="https://identity.example.test/realms/pcbknowledge/certs",
        audience="pcbknowledge-api",
        browser_client_id="pcbknowledge-curator-web",
        service_client_id="pcbknowledge-agent-service",
    )


def _storage_settings() -> ObjectStorageSettings:
    return ObjectStorageSettings(
        endpoint_url="https://objects.internal.test",
        public_endpoint_url="https://objects.example.test",
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
        access_key="a" * 16,
        secret_key="s" * 32,
    )


class _JwksResponse:
    def __init__(self, document: dict[str, object]) -> None:
        self._payload = json.dumps(document).encode()

    def __enter__(self) -> _JwksResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        del exc_info

    def read(self, maximum_bytes: int) -> bytes:
        return self._payload[:maximum_bytes]


def _install_jwks(
    monkeypatch: pytest.MonkeyPatch,
    key: dict[str, Any],
) -> None:
    response = _JwksResponse({"keys": [key]})
    monkeypatch.setattr(
        oidc_readiness,
        "urlopen",
        lambda _request, timeout: response,
    )


def test_oidc_readiness_accepts_explicit_rs256_verification_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    key.update(
        {
            "kid": "rsa-signing-key",
            "alg": "RS256",
            "use": "sig",
        }
    )
    _install_jwks(monkeypatch, key)

    probe_oidc_trust(_oidc_settings())


def test_oidc_readiness_rejects_ec_only_jwks_when_rs256_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    key = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    key.update(
        {
            "kid": "ec-signing-key",
            "alg": "ES256",
            "use": "sig",
            "key_ops": ["verify"],
        }
    )
    _install_jwks(monkeypatch, key)

    with pytest.raises(OidcTrustUnavailableError):
        probe_oidc_trust(_oidc_settings())


def test_readiness_requires_all_m1_dependencies() -> None:
    probe = ApplicationReadinessProbe(
        settings_loader=_database_settings,
        oidc_settings_loader=_oidc_settings,
        storage_settings_loader=_storage_settings,
        database_probe=lambda _settings: None,
        oidc_probe=lambda _settings: None,
        storage_probe=lambda _settings: None,
    )

    report = asyncio.run(probe.check())

    assert report.ready
    assert [(check.name, check.status) for check in report.checks] == [
        ("configuration", "ok"),
        ("database", "ok"),
        ("identity", "ok"),
        ("object_storage", "ok"),
    ]


def test_readiness_fails_closed_without_exposing_dependency_errors() -> None:
    def identity_unavailable(_settings: OidcSettings) -> None:
        raise OidcTrustUnavailableError("provider response contained a token")

    def storage_unavailable(_settings: ObjectStorageSettings) -> None:
        raise ObjectStoreUnavailableError()

    probe = ApplicationReadinessProbe(
        settings_loader=_database_settings,
        oidc_settings_loader=_oidc_settings,
        storage_settings_loader=_storage_settings,
        database_probe=lambda _settings: None,
        oidc_probe=identity_unavailable,
        storage_probe=storage_unavailable,
    )

    report = asyncio.run(probe.check())

    assert not report.ready
    assert {check.name for check in report.checks if check.status == "failed"} == {
        "identity",
        "object_storage",
    }
    assert "token" not in report.model_dump_json()
    assert "secret" not in report.model_dump_json()
