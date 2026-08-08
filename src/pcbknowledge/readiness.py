"""Readiness model and the default configuration/PostgreSQL probe."""

from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from pcbknowledge.platform.config import get_settings
from pcbknowledge.platform.database import probe_database


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
    """Load required settings and verify a real PostgreSQL round trip."""

    async def check(self) -> ReadinessReport:
        try:
            settings = get_settings()
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

        try:
            await run_in_threadpool(probe_database, settings)
        except SQLAlchemyError, OSError:
            return ReadinessReport(
                ready=False,
                checks=(
                    ReadinessCheck(name="configuration", status="ok"),
                    ReadinessCheck(
                        name="database",
                        status="failed",
                        detail="PostgreSQL is unavailable",
                    ),
                ),
            )
        return ReadinessReport(
            ready=True,
            checks=(
                ReadinessCheck(name="configuration", status="ok"),
                ReadinessCheck(name="database", status="ok"),
            ),
        )
