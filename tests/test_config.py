import pytest
from pydantic import ValidationError

from pcbknowledge.platform.config import Settings


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
