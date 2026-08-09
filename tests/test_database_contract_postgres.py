import os

import pytest
from sqlalchemy import create_engine, text

from pcbknowledge.platform.config import Settings
from pcbknowledge.platform.database import (
    DatabaseContractError,
    UnsafeDatabaseRoleError,
    probe_database,
    require_database_contract,
    require_restricted_database_role,
)
from pcbknowledge.platform.database.health import EXPECTED_DATABASE_REVISION

_EXPECTED_ROLE_ENV = "PCBKNOWLEDGE_EXPECTED_RUNTIME_ROLE"
_RUNTIME_ROLES = frozenset({"pcbknowledge_app", "pcbknowledge_worker", "pcbknowledge_verifier"})


def _expected_runtime_role() -> str:
    expected_role = os.getenv(_EXPECTED_ROLE_ENV)
    if expected_role not in _RUNTIME_ROLES:
        pytest.fail(
            f"set {_EXPECTED_ROLE_ENV} to an actual runtime login role; skipping is forbidden",
            pytrace=False,
        )
    return expected_role


def test_actual_runtime_login_satisfies_database_contract() -> None:
    expected_role = _expected_runtime_role()
    dsn = os.environ["PCBKNOWLEDGE_DATABASE_DSN"]
    engine = create_engine(dsn)
    try:
        with engine.connect() as connection:
            identity = connection.execute(
                text(
                    "SELECT SESSION_USER AS session_user, CURRENT_USER AS current_user, "
                    "(SELECT version_num FROM public.alembic_version) AS revision, "
                    "has_table_privilege(CURRENT_USER, "
                    "(SELECT relation.oid FROM pg_catalog.pg_class AS relation "
                    "JOIN pg_catalog.pg_namespace AS namespace "
                    "ON namespace.oid = relation.relnamespace "
                    "WHERE namespace.nspname = 'public' "
                    "AND relation.relname = 'alembic_version'), 'SELECT') "
                    "AS can_read_revision"
                )
            ).one()
            assert identity.session_user == expected_role
            assert identity.current_user == expected_role
            assert identity.revision == EXPECTED_DATABASE_REVISION
            assert identity.can_read_revision

            objects = connection.execute(
                text(
                    "SELECT "
                    "EXISTS (SELECT 1 FROM pg_catalog.pg_class AS relation "
                    "JOIN pg_catalog.pg_namespace AS namespace "
                    "ON namespace.oid = relation.relnamespace "
                    "WHERE namespace.nspname = 'platform' "
                    "AND relation.relname = 'staging_upload_reservation' "
                    "AND relation.relrowsecurity AND relation.relforcerowsecurity) "
                    "AS has_forced_reservations, "
                    "EXISTS (SELECT 1 FROM pg_catalog.pg_proc AS routine "
                    "JOIN pg_catalog.pg_namespace AS namespace "
                    "ON namespace.oid = routine.pronamespace "
                    "WHERE namespace.nspname = 'platform' "
                    "AND routine.proname = 'claimable_storage_cleanup_scopes' "
                    "AND routine.proargtypes = '23'::pg_catalog.oidvector) "
                    "AS has_cleanup_discovery"
                )
            ).one()
            assert objects.has_forced_reservations
            assert objects.has_cleanup_discovery

            require_restricted_database_role(connection)
            require_database_contract(connection)
    finally:
        engine.dispose()

    probe_database(Settings(database_dsn=dsn))


def test_app_runtime_rejects_identity_and_grant_drift() -> None:
    if _expected_runtime_role() != "pcbknowledge_app":
        return
    admin_dsn = os.environ["PCBKNOWLEDGE_M1_TEST_DATABASE_DSN"]
    runtime_engine = create_engine(os.environ["PCBKNOWLEDGE_DATABASE_DSN"])
    admin_engine = create_engine(admin_dsn)

    def assert_rejected(*, drift: str, restore: str) -> None:
        with admin_engine.begin() as connection:
            connection.execute(text(drift))
        try:
            with (
                runtime_engine.connect() as connection,
                pytest.raises((DatabaseContractError, UnsafeDatabaseRoleError)),
            ):
                require_restricted_database_role(connection)
                require_database_contract(connection)
        finally:
            with admin_engine.begin() as connection:
                connection.execute(text(restore))

    try:
        with (
            admin_engine.connect() as connection,
            pytest.raises(DatabaseContractError),
        ):
            require_database_contract(connection)
        assert_rejected(
            drift="GRANT UPDATE ON source.license_policy TO pcbknowledge_app",
            restore="REVOKE UPDATE ON source.license_policy FROM pcbknowledge_app",
        )
        assert_rejected(
            drift="REVOKE SELECT ON source.license_policy FROM pcbknowledge_app",
            restore="GRANT SELECT ON source.license_policy TO pcbknowledge_app",
        )
        assert_rejected(
            drift="GRANT UPDATE ON public.alembic_version TO pcbknowledge_app",
            restore="REVOKE UPDATE ON public.alembic_version FROM pcbknowledge_app",
        )
        assert_rejected(
            drift=(
                "ALTER POLICY outbox_worker_cleanup_only "
                "ON platform.outbox_event USING (true) WITH CHECK (true)"
            ),
            restore=(
                "ALTER POLICY outbox_worker_cleanup_only ON platform.outbox_event "
                "USING (event_type = 'storage.staging_cleanup.requested') "
                "WITH CHECK (event_type = 'storage.staging_cleanup.requested')"
            ),
        )
        assert_rejected(
            drift=(
                "ALTER TABLE platform.outbox_event DISABLE TRIGGER "
                "enforce_outbox_event_immutable_fields"
            ),
            restore=(
                "ALTER TABLE platform.outbox_event ENABLE TRIGGER "
                "enforce_outbox_event_immutable_fields"
            ),
        )
        with admin_engine.begin() as connection:
            connection.execute(text("CREATE ROLE pcbknowledge_contract_rogue NOLOGIN"))
        try:
            assert_rejected(
                drift="GRANT pcbknowledge_app TO pcbknowledge_contract_rogue",
                restore="REVOKE pcbknowledge_app FROM pcbknowledge_contract_rogue",
            )
        finally:
            with admin_engine.begin() as connection:
                connection.execute(text("DROP ROLE pcbknowledge_contract_rogue"))
    finally:
        runtime_engine.dispose()
        admin_engine.dispose()
