"""Typed runtime configuration.

Configuration is read only from the process environment. In particular, the
database credential has no development fallback and is represented as a
``SecretStr`` so ordinary logging and repr calls cannot expose it.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
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
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    service_name: str = "pcbknowledge"
    database_dsn: SecretStr
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
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings for a process.

    Tests that mutate the environment must call ``get_settings.cache_clear()``.
    """

    return Settings()
