"""Typed runtime configuration.

Configuration is read only from the process environment. In particular, the
database credential has no development fallback and is represented as a
``SecretStr`` so ordinary logging and repr calls cannot expose it.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Configuration shared by API, worker, and migration processes."""

    model_config = SettingsConfigDict(
        env_prefix="PCBKNOWLEDGE_",
        env_file=None,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    service_name: str = "pcbknowledge"
    database_dsn: SecretStr
    database_access_mode: Literal["runtime", "migration"] = "runtime"
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)

    @field_validator("database_dsn")
    @classmethod
    def require_psycopg_postgres(cls, value: SecretStr) -> SecretStr:
        """Reject accidental SQLite/in-memory fallbacks and non-psycopg drivers."""

        try:
            url = make_url(value.get_secret_value())
        except ArgumentError as exc:
            raise ValueError("database_dsn must be a valid SQLAlchemy URL") from exc
        if url.drivername != "postgresql+psycopg":
            raise ValueError("database_dsn must use the postgresql+psycopg driver")
        if url.database is None:
            raise ValueError("database_dsn must name a PostgreSQL database")
        return value

    @model_validator(mode="after")
    def reject_unsafe_production_endpoint(self) -> Self:
        """Disallow a credentials-free production DSN."""

        if self.environment != "production":
            return self
        url = make_url(self.database_dsn.get_secret_value())
        if url.username is None or url.password is None:
            raise ValueError("production database_dsn must include injected credentials")
        if self.database_access_mode == "runtime" and url.username.casefold() in {
            "admin",
            "pcbknowledge",
            "postgres",
            "root",
        }:
            raise ValueError("production runtime database_dsn must not use an owner account")
        return self


class OidcSettings(BaseSettings):
    """Required identity-provider trust anchors; none are inferred from a token."""

    model_config = SettingsConfigDict(
        env_prefix="PCBKNOWLEDGE_OIDC_",
        env_file=None,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"] = Field(
        default="local",
        validation_alias="PCBKNOWLEDGE_ENVIRONMENT",
    )
    issuer_url: AnyHttpUrl
    jwks_url: AnyHttpUrl
    audience: str = Field(min_length=1, max_length=200)
    browser_client_id: str = Field(min_length=1, max_length=200)
    service_client_id: str = Field(min_length=1, max_length=200)
    allowed_algorithms: tuple[Literal["RS256", "PS256", "ES256"], ...] = ("RS256",)
    clock_skew_seconds: int = Field(default=30, ge=0, le=120)
    jwks_cache_seconds: int = Field(default=300, ge=30, le=3600)

    @field_validator("issuer_url", "jwks_url")
    @classmethod
    def reject_url_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("OIDC URLs must not contain credentials")
        if value.query is not None or value.fragment is not None:
            raise ValueError("OIDC URLs must not contain query or fragment components")
        return value

    @model_validator(mode="after")
    def validate_trust_boundary(self) -> Self:
        if self.browser_client_id == self.service_client_id:
            raise ValueError("browser and service OIDC clients must be distinct")
        if self.environment in {"staging", "production"} and (
            self.issuer_url.scheme != "https" or self.jwks_url.scheme != "https"
        ):
            raise ValueError("staging and production OIDC endpoints must use HTTPS")
        return self


class ObjectStorageSettings(BaseSettings):
    """Required S3-compatible storage configuration with masked credentials."""

    model_config = SettingsConfigDict(
        env_prefix="PCBKNOWLEDGE_S3_",
        env_file=None,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"] = Field(
        default="local",
        validation_alias="PCBKNOWLEDGE_ENVIRONMENT",
    )
    endpoint_url: AnyHttpUrl
    public_endpoint_url: AnyHttpUrl
    bucket: str = Field(min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9.-]+[a-z0-9]$")
    staging_bucket: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z0-9][a-z0-9.-]+[a-z0-9]$",
    )
    access_mode: Literal["api", "worker", "admin"] = "api"
    region: str = Field(default="us-east-1", min_length=1, max_length=64)
    access_key: SecretStr
    secret_key: SecretStr
    presign_ttl_seconds: int = Field(default=300, ge=30, le=900)
    max_upload_bytes: int = Field(default=268_435_456, ge=1, le=2_147_483_648)

    @field_validator("endpoint_url", "public_endpoint_url")
    @classmethod
    def reject_storage_url_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("object-storage endpoint must not contain credentials")
        if value.query is not None or value.fragment is not None:
            raise ValueError(
                "object-storage endpoint must not contain query or fragment components"
            )
        return value

    @field_validator("access_key", "secret_key")
    @classmethod
    def reject_short_storage_credentials(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 16:
            raise ValueError("object-storage credentials must be at least 16 characters")
        return value

    @model_validator(mode="after")
    def require_tls_for_browser_presigned_urls(self) -> Self:
        if self.environment in {"staging", "production"} and (
            self.public_endpoint_url.scheme != "https"
        ):
            raise ValueError("staging and production public object storage must use HTTPS")
        if self.bucket == self.staging_bucket:
            raise ValueError("permanent and staging objects must use separate buckets")
        return self


class ObservabilitySettings(BaseSettings):
    """Telemetry export configuration; local collection may be disabled explicitly."""

    model_config = SettingsConfigDict(
        env_prefix="PCBKNOWLEDGE_",
        env_file=None,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    service_name: str = Field(
        default="pcbknowledge",
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("PCBKNOWLEDGE_SERVICE_NAME", "OTEL_SERVICE_NAME"),
    )
    otel_exporter_otlp_endpoint: AnyHttpUrl | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "PCBKNOWLEDGE_OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings for a process.

    Tests that mutate the environment must call ``get_settings.cache_clear()``.
    """

    return Settings()


@lru_cache(maxsize=1)
def get_oidc_settings() -> OidcSettings:
    """Load the trusted OIDC boundary independently from unverified requests."""

    return OidcSettings()


@lru_cache(maxsize=1)
def get_object_storage_settings() -> ObjectStorageSettings:
    """Load object-store configuration without exposing credential values."""

    return ObjectStorageSettings()


@lru_cache(maxsize=1)
def get_observability_settings() -> ObservabilitySettings:
    """Load process telemetry settings."""

    return ObservabilitySettings()
