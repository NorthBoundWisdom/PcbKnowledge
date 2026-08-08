"""Independent worker process command line boundary.

M0 intentionally ships no pretend job consumer. The health check is suitable for
container probes and verifies the same required PostgreSQL dependency as the API.
"""

import argparse
import json
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from pcbknowledge.platform.config import Settings, get_settings
from pcbknowledge.platform.database import probe_database


class WorkerHealth(BaseModel):
    """Stable, credential-free worker health output."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "failed"]]
    reason: str | None = None


def run_health_check(
    *,
    settings_loader: Callable[[], Settings] = get_settings,
    database_probe: Callable[[Settings], None] = probe_database,
) -> WorkerHealth:
    """Return a deterministic health result without leaking connection errors."""

    try:
        settings = settings_loader()
    except ValidationError:
        return WorkerHealth(
            status="not_ready",
            checks={"configuration": "failed"},
            reason="required runtime configuration is missing or invalid",
        )

    try:
        database_probe(settings)
    except SQLAlchemyError, OSError:
        return WorkerHealth(
            status="not_ready",
            checks={"configuration": "ok", "database": "failed"},
            reason="PostgreSQL is unavailable",
        )
    return WorkerHealth(
        status="ready",
        checks={"configuration": "ok", "database": "ok"},
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcbknowledge-worker")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "health-check",
        help="validate runtime configuration and execute SELECT 1 against PostgreSQL",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a worker command and return a process exit code."""

    arguments = _build_parser().parse_args(argv)
    if arguments.command != "health-check":
        raise AssertionError("argparse accepted an unknown worker command")
    result = run_health_check()
    print(json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True))
    return 0 if result.status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
