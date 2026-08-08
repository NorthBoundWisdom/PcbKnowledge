"""Process-scoped SQLAlchemy engine and explicit transaction boundary."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from pcbknowledge.platform.config import Settings, get_settings
from pcbknowledge.platform.database.health import (
    require_database_contract,
    require_restricted_database_role,
)


@dataclass(frozen=True, slots=True)
class DatabaseRuntime:
    """Own the connection pool; repositories receive only an explicit Session."""

    engine: Engine
    session_factory: sessionmaker[Session]

    @classmethod
    def from_settings(cls, settings: Settings) -> DatabaseRuntime:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        engine = create_engine(
            settings.database_dsn.get_secret_value(),
            connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
            pool_pre_ping=True,
        )
        try:
            with engine.connect() as connection:
                require_restricted_database_role(connection)
                require_database_contract(connection)
        except Exception:
            engine.dispose()
            raise
        SQLAlchemyInstrumentor().instrument(engine=engine)
        return cls(
            engine=engine,
            session_factory=sessionmaker(
                bind=engine,
                autoflush=False,
                expire_on_commit=False,
            ),
        )

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Provide exactly one transaction and close the Session on every path."""

        with self.session_factory() as session, session.begin():
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


@lru_cache(maxsize=1)
def get_database_runtime() -> DatabaseRuntime:
    """Create one bounded connection pool per process after configuration loads."""

    return DatabaseRuntime.from_settings(get_settings())


def reset_database_runtime() -> None:
    """Dispose the cached pool, primarily for process shutdown and isolated tests."""

    if get_database_runtime.cache_info().currsize:
        get_database_runtime().dispose()
    get_database_runtime.cache_clear()
