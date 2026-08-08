"""Real PostgreSQL connectivity checks shared by API and worker."""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from pcbknowledge.platform.config import Settings


def probe_database(settings: Settings) -> None:
    """Connect to the configured PostgreSQL database and execute a trivial query.

    The caller owns error classification and must never return the raw exception
    because database exceptions may contain connection credentials.
    """

    engine = create_engine(
        settings.database_dsn.get_secret_value(),
        connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
        poolclass=NullPool,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()
