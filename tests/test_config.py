import pytest
from pydantic import ValidationError

from pcbknowledge.platform.auth import OidcVerifierConfig
from pcbknowledge.platform.config import (
    ObjectStorageSettings,
    ObservabilitySettings,
    OidcSettings,
    Settings,
)


def test_database_dsn_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PCBKNOWLEDGE_DATABASE_DSN", raising=False)

    with pytest.raises(ValidationError):
        Settings()


def test_database_secret_is_masked() -> None:
    settings = Settings(database_dsn="postgresql+psycopg://knowledge:top-secret@db/knowledge")

    assert "top-secret" not in repr(settings)
    assert str(settings.database_dsn) == "**********"


@pytest.mark.parametrize(
    "dsn",
    [
        "sqlite+pysqlite:///:memory:",
        "postgresql://knowledge:secret@db/knowledge",
        "not-a-url",
    ],
)
def test_database_dsn_requires_psycopg_postgres(dsn: str) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(database_dsn=dsn)

    assert dsn not in str(error.value)


def test_production_database_requires_injected_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_dsn="postgresql+psycopg://db/knowledge",
        )


def test_production_runtime_database_rejects_known_owner_accounts() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_dsn="postgresql+psycopg://postgres:secret@db/knowledge",
        )

    migration = Settings(
        environment="production",
        database_access_mode="migration",
        database_dsn="postgresql+psycopg://postgres:secret@db/knowledge",
    )
    assert migration.database_access_mode == "migration"


def test_oidc_settings_require_distinct_known_clients() -> None:
    with pytest.raises(ValidationError):
        OidcSettings(
            issuer_url="https://identity.example/realms/pcbknowledge",
            jwks_url="https://identity-internal.example/keys",
            audience="pcbknowledge-api",
            browser_client_id="shared-client",
            service_client_id="shared-client",
        )


def test_oidc_allows_a_pinned_internal_jwks_origin_for_container_networks() -> None:
    settings = OidcSettings(
        issuer_url="http://localhost:8081/realms/pcbknowledge",
        jwks_url="http://keycloak:8080/realms/pcbknowledge/protocol/openid-connect/certs",
        audience="pcbknowledge-api",
        browser_client_id="pcbknowledge-curator-web",
        service_client_id="pcbknowledge-agent-service",
    )

    assert settings.jwks_url.host == "keycloak"


def test_production_oidc_rejects_plain_http() -> None:
    with pytest.raises(ValidationError):
        OidcSettings(
            environment="production",
            issuer_url="http://identity.example/realms/pcbknowledge",
            jwks_url="http://identity.example/realms/pcbknowledge/protocol/openid-connect/certs",
            audience="pcbknowledge-api",
            browser_client_id="pcbknowledge-curator-web",
            service_client_id="pcbknowledge-agent-service",
        )


def test_oidc_ps256_setting_is_supported_by_the_verifier_boundary() -> None:
    settings = OidcSettings(
        issuer_url="https://identity.example/realms/pcbknowledge",
        jwks_url="https://identity.example/realms/pcbknowledge/certs",
        audience="pcbknowledge-api",
        browser_client_id="pcbknowledge-curator-web",
        service_client_id="pcbknowledge-agent-service",
        allowed_algorithms=("PS256",),
    )

    verifier = OidcVerifierConfig(
        issuer=str(settings.issuer_url),
        audience=settings.audience,
        algorithms=settings.allowed_algorithms,
        human_client_ids={settings.browser_client_id},
        service_account_client_ids={settings.service_client_id},
    )
    assert verifier.algorithms == ("PS256",)


def test_object_storage_credentials_are_required_and_masked() -> None:
    settings = ObjectStorageSettings(
        endpoint_url="http://seaweedfs:8333",
        public_endpoint_url="http://localhost:8333",
        bucket="pcbknowledge-assets",
        staging_bucket="pcbknowledge-staging",
        access_key="a" * 16,
        secret_key="s" * 32,
    )

    assert "a" * 16 not in repr(settings)
    assert "s" * 32 not in repr(settings)


def test_object_storage_rejects_credentials_in_endpoint() -> None:
    with pytest.raises(ValidationError):
        ObjectStorageSettings(
            endpoint_url="http://user:password@seaweedfs:8333",
            public_endpoint_url="http://localhost:8333",
            bucket="pcbknowledge-assets",
            staging_bucket="pcbknowledge-staging",
            access_key="a" * 16,
            secret_key="s" * 32,
        )


def test_production_object_storage_requires_https_for_presigned_urls() -> None:
    with pytest.raises(ValidationError):
        ObjectStorageSettings(
            environment="production",
            endpoint_url="http://seaweedfs.internal:8333",
            public_endpoint_url="http://objects.example.test",
            bucket="pcbknowledge-assets",
            staging_bucket="pcbknowledge-staging",
            access_key="a" * 16,
            secret_key="s" * 32,
        )


def test_observability_accepts_standard_otel_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_SERVICE_NAME", "pcbknowledge-test")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")

    settings = ObservabilitySettings()

    assert settings.service_name == "pcbknowledge-test"
    assert str(settings.otel_exporter_otlp_endpoint) == "http://collector:4318/"
