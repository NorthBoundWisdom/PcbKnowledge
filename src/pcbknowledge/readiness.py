"""Readiness model for all M1 request-path dependencies."""

import asyncio
from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from pcbknowledge.platform.auth import OidcTrustUnavailableError, probe_oidc_trust
from pcbknowledge.platform.config import (
    ObjectStorageSettings,
    OidcSettings,
    Settings,
    get_object_storage_settings,
    get_oidc_settings,
    get_settings,
)
from pcbknowledge.platform.database import (
    DatabaseContractError,
    UnsafeDatabaseRoleError,
    probe_database,
)
from pcbknowledge.platform.storage import ObjectStoreUnavailableError, probe_object_storage


class ReadinessCheck(BaseModel):
    """A single dependency result safe to return to unauthenticated probes."""

    name: str
    status: Literal["ok", "failed"]
    detail: str | None = None


class ReadinessReport(BaseModel):
    """Aggregate readiness; false if any required dependency is unavailable."""

    ready: bool
    checks: tuple[ReadinessCheck, ...]


class ReadinessProbe(Protocol):
    """Injectable readiness contract used by the HTTP boundary."""

    async def check(self) -> ReadinessReport: ...


class ApplicationReadinessProbe:
    """Load required settings and probe PostgreSQL, OIDC JWKS, and private S3."""

    def __init__(
        self,
        *,
        settings_loader: Callable[[], Settings] = get_settings,
        oidc_settings_loader: Callable[[], OidcSettings] = get_oidc_settings,
        storage_settings_loader: Callable[[], ObjectStorageSettings] = (
            get_object_storage_settings
        ),
        database_probe: Callable[[Settings], None] = probe_database,
        oidc_probe: Callable[[OidcSettings], None] = probe_oidc_trust,
        storage_probe: Callable[[ObjectStorageSettings], None] = probe_object_storage,
    ) -> None:
        self._settings_loader = settings_loader
        self._oidc_settings_loader = oidc_settings_loader
        self._storage_settings_loader = storage_settings_loader
        self._database_probe = database_probe
        self._oidc_probe = oidc_probe
        self._storage_probe = storage_probe

    async def check(self) -> ReadinessReport:
        try:
            settings = self._settings_loader()
            oidc_settings = self._oidc_settings_loader()
            storage_settings = self._storage_settings_loader()
        except ValidationError:
            return ReadinessReport(
                ready=False,
                checks=(
                    ReadinessCheck(
                        name="configuration",
                        status="failed",
                        detail="required runtime configuration is missing or invalid",
                    ),
                ),
            )

        database, identity, object_storage = await asyncio.gather(
            self._check_database(settings),
            self._check_identity(oidc_settings),
            self._check_object_storage(storage_settings),
        )
        checks = (
            ReadinessCheck(name="configuration", status="ok"),
            database,
            identity,
            object_storage,
        )
        return ReadinessReport(
            ready=all(check.status == "ok" for check in checks),
            checks=checks,
        )

    async def _check_database(self, settings: Settings) -> ReadinessCheck:
        try:
            await run_in_threadpool(self._database_probe, settings)
        except DatabaseContractError, SQLAlchemyError, UnsafeDatabaseRoleError, OSError:
            return ReadinessCheck(
                name="database",
                status="failed",
                detail="PostgreSQL is unavailable",
            )
        return ReadinessCheck(name="database", status="ok")

    async def _check_identity(self, settings: OidcSettings) -> ReadinessCheck:
        try:
            await run_in_threadpool(self._oidc_probe, settings)
        except OidcTrustUnavailableError, OSError:
            return ReadinessCheck(
                name="identity",
                status="failed",
                detail="OIDC trust keys are unavailable",
            )
        return ReadinessCheck(name="identity", status="ok")

    async def _check_object_storage(
        self,
        settings: ObjectStorageSettings,
    ) -> ReadinessCheck:
        try:
            await run_in_threadpool(self._storage_probe, settings)
        except ObjectStoreUnavailableError, OSError:
            return ReadinessCheck(
                name="object_storage",
                status="failed",
                detail="Object storage is unavailable",
            )
        return ReadinessCheck(name="object_storage", status="ok")
