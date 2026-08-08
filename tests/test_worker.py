import json
import threading

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from pcbknowledge.platform.config import ObjectStorageSettings, Settings
from pcbknowledge.platform.database import DatabaseContractError
from pcbknowledge.platform.storage import ObjectStoreUnavailableError
from pcbknowledge.worker import WorkerHealth, run_health_check, run_service


def _settings() -> Settings:
    return Settings(database_dsn="postgresql+psycopg://knowledge:secret@db/knowledge")


def _storage_settings() -> ObjectStorageSettings:
    return ObjectStorageSettings(
        endpoint_url="https://objects.internal.test",
        public_endpoint_url="https://objects.example.test",
        bucket="pcbknowledge-test",
        staging_bucket="pcbknowledge-test-staging",
        access_mode="worker",
        access_key="a" * 16,
        secret_key="s" * 32,
    )


def test_worker_health_check_is_deterministic_when_ready() -> None:
    result = run_health_check(
        settings_loader=_settings,
        storage_settings_loader=_storage_settings,
        database_probe=lambda _settings: None,
        storage_probe=lambda _settings: None,
    )

    rendered_once = json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True)
    rendered_twice = json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True)
    assert rendered_once == rendered_twice
    assert result.status == "ready"


def test_worker_health_check_fails_closed_on_missing_configuration() -> None:
    def missing_settings() -> Settings:
        raise ValidationError.from_exception_data("Settings", [])

    result = run_health_check(
        settings_loader=missing_settings,
        storage_settings_loader=_storage_settings,
    )

    assert result.status == "not_ready"
    assert result.checks == {"configuration": "failed"}


def test_worker_health_check_does_not_expose_database_exception() -> None:
    def unavailable(settings: Settings) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("secret connection detail"))

    result = run_health_check(
        settings_loader=_settings,
        storage_settings_loader=_storage_settings,
        database_probe=unavailable,
        storage_probe=lambda _settings: None,
    )

    assert result.status == "not_ready"
    assert result.reason == "PostgreSQL is unavailable"
    assert "secret" not in result.model_dump_json()


def test_worker_health_check_fails_closed_on_database_contract_mismatch() -> None:
    def stale_contract(_settings: Settings) -> None:
        raise DatabaseContractError("unexpected object and role detail")

    result = run_health_check(
        settings_loader=_settings,
        storage_settings_loader=_storage_settings,
        database_probe=stale_contract,
        storage_probe=lambda _settings: None,
    )

    assert result.status == "not_ready"
    assert result.checks == {"configuration": "ok", "database": "failed"}
    assert result.reason == "PostgreSQL is unavailable"
    assert "unexpected" not in result.model_dump_json()


def test_worker_health_check_requires_object_storage() -> None:
    def unavailable(_settings: ObjectStorageSettings) -> None:
        raise ObjectStoreUnavailableError()

    result = run_health_check(
        settings_loader=_settings,
        storage_settings_loader=_storage_settings,
        database_probe=lambda _settings: None,
        storage_probe=unavailable,
    )

    assert result.status == "not_ready"
    assert result.checks["object_storage"] == "failed"


def test_worker_service_stops_without_claiming_unregistered_domain_jobs() -> None:
    stop_event = threading.Event()
    calls = 0
    work_calls = 0

    def healthy() -> WorkerHealth:
        nonlocal calls
        calls += 1
        stop_event.set()
        return WorkerHealth(
            status="ready",
            checks={
                "configuration": "ok",
                "database": "ok",
                "object_storage": "ok",
            },
        )

    def work_cycle() -> int:
        nonlocal work_calls
        work_calls += 1
        return 2

    assert (
        run_service(
            health_interval_seconds=5,
            stop_event=stop_event,
            health_check=healthy,
            work_cycle=work_cycle,
        )
        == 0
    )
    assert calls == 1
    assert work_calls == 1
