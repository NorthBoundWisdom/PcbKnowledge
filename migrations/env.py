"""Alembic runtime bound to the same required application configuration."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from pcbknowledge.platform.config import get_settings
from pcbknowledge.platform.database import Base
from pcbknowledge.platform.database.metadata import load_platform_models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_platform_models()
target_metadata = Base.metadata

_TYPE_BOUND_ENUM_CHECKS = frozenset(
    {
        "ck_access_scope_kind",
        "ck_audit_event_actor_kind",
        "ck_audit_event_outcome",
        "ck_external_subject_kind",
        "ck_license_policy_class",
        "ck_membership_role",
    }
)


def _include_object(
    _object: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Ignore only reflected Enum CHECK duplicates misclassified as removals.

    A missing metadata-side constraint remains visible because ``reflected`` is
    false in that direction. The named checks are also asserted by PostgreSQL
    security integration tests.
    """

    return not (
        type_ == "check_constraint"
        and reflected
        and compare_to is None
        and name in _TYPE_BOUND_ENUM_CHECKS
    )


def _database_url() -> str:
    return get_settings().database_dsn.get_secret_value()


def run_migrations_offline() -> None:
    """Generate SQL without establishing a database connection."""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_schemas=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations transactionally against configured PostgreSQL."""

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            include_object=_include_object,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
