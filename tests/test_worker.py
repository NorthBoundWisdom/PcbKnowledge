import json

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from pcbknowledge.platform.config import Settings
from pcbknowledge.worker import run_health_check


def _settings() -> Settings:
    return Settings(database_dsn="postgresql+psycopg://knowledge:secret@db/knowledge")


def test_worker_health_check_is_deterministic_when_ready() -> None:
    result = run_health_check(settings_loader=_settings, database_probe=lambda settings: None)

    rendered_once = json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True)
    rendered_twice = json.dumps(result.model_dump(mode="json", exclude_none=True), sort_keys=True)
    assert rendered_once == rendered_twice
    assert result.status == "ready"


def test_worker_health_check_fails_closed_on_missing_configuration() -> None:
    def missing_settings() -> Settings:
        raise ValidationError.from_exception_data("Settings", [])

    result = run_health_check(settings_loader=missing_settings)

    assert result.status == "not_ready"
    assert result.checks == {"configuration": "failed"}


def test_worker_health_check_does_not_expose_database_exception() -> None:
    def unavailable(settings: Settings) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("secret connection detail"))

    result = run_health_check(settings_loader=_settings, database_probe=unavailable)

    assert result.status == "not_ready"
    assert result.reason == "PostgreSQL is unavailable"
    assert "secret" not in result.model_dump_json()
