"""Independent worker process and dependency-health boundary.

M1 starts a durable supervisor without inventing M2 document handlers. Concrete
job handlers are registered only alongside their domain implementations.
"""

import argparse
import json
import signal
import threading
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from pcbknowledge.platform.config import (
    ObjectStorageSettings,
    Settings,
    get_object_storage_settings,
    get_settings,
)
from pcbknowledge.platform.database import (
    DatabaseContractError,
    UnsafeDatabaseRoleError,
    probe_database,
)
from pcbknowledge.platform.database.runtime import get_database_runtime
from pcbknowledge.platform.ids import new_uuid7
from pcbknowledge.platform.outbox.worker import WorkerOutboxDispatcher
from pcbknowledge.platform.storage import ObjectStoreUnavailableError, probe_object_storage
from pcbknowledge.platform.storage.runtime import get_object_storage_adapter


class WorkerHealth(BaseModel):
    """Stable, credential-free worker health output."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "failed"]]
    reason: str | None = None


def run_health_check(
    *,
    settings_loader: Callable[[], Settings] = get_settings,
    storage_settings_loader: Callable[[], ObjectStorageSettings] = get_object_storage_settings,
    database_probe: Callable[[Settings], None] = probe_database,
    storage_probe: Callable[[ObjectStorageSettings], None] = probe_object_storage,
) -> WorkerHealth:
    """Return a deterministic health result without leaking connection errors."""

    try:
        settings = settings_loader()
        storage_settings = storage_settings_loader()
    except ValidationError:
        return WorkerHealth(
            status="not_ready",
            checks={"configuration": "failed"},
            reason="required runtime configuration is missing or invalid",
        )

    try:
        database_probe(settings)
    except DatabaseContractError, SQLAlchemyError, UnsafeDatabaseRoleError, OSError:
        return WorkerHealth(
            status="not_ready",
            checks={"configuration": "ok", "database": "failed"},
            reason="PostgreSQL is unavailable",
        )
    try:
        storage_probe(storage_settings)
    except ObjectStoreUnavailableError, OSError:
        return WorkerHealth(
            status="not_ready",
            checks={
                "configuration": "ok",
                "database": "ok",
                "object_storage": "failed",
            },
            reason="Object storage is unavailable",
        )
    return WorkerHealth(
        status="ready",
        checks={
            "configuration": "ok",
            "database": "ok",
            "object_storage": "ok",
        },
    )


def run_service(
    *,
    health_interval_seconds: float,
    stop_event: threading.Event,
    health_check: Callable[[], WorkerHealth] = run_health_check,
    work_cycle: Callable[[], int] = lambda: 0,
) -> int:
    """Run bounded outbox work and continuously surface dependency health."""

    while not stop_event.is_set():
        result = health_check()
        print(json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True))
        if result.status != "ready":
            return 1
        processed = work_cycle()
        print(
            json.dumps(
                {"event": "worker_cycle", "published_events": processed},
                sort_keys=True,
            )
        )
        stop_event.wait(health_interval_seconds)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcbknowledge-worker")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "health-check",
        help="validate runtime configuration, PostgreSQL, and private object storage",
    )
    serve = subcommands.add_parser(
        "serve",
        help="run the durable worker supervisor; domain handlers are registered separately",
    )
    serve.add_argument(
        "--health-interval-seconds",
        type=float,
        default=30,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a worker command and return a process exit code."""

    arguments = _build_parser().parse_args(argv)
    if arguments.command == "health-check":
        result = run_health_check()
        print(json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True))
        return 0 if result.status == "ready" else 1
    if arguments.command == "serve":
        interval = arguments.health_interval_seconds
        if not 5 <= interval <= 300:
            _build_parser().error("health interval must be between 5 and 300 seconds")
        stop_event = threading.Event()

        def request_stop(_signal_number: int, _frame: object) -> None:
            stop_event.set()

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        dispatcher = WorkerOutboxDispatcher(
            database=get_database_runtime(),
            adapter=get_object_storage_adapter(),
            worker_id=f"storage-cleanup-{new_uuid7()}",
        )
        return run_service(
            health_interval_seconds=interval,
            stop_event=stop_event,
            work_cycle=dispatcher.run_once,
        )
    raise AssertionError("argparse accepted an unknown worker command")


if __name__ == "__main__":
    raise SystemExit(main())
