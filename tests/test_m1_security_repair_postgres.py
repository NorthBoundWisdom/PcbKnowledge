import hashlib
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from pcbknowledge.platform.database.health import (
    UnsafeDatabaseRoleError,
    require_restricted_database_role,
)

pytestmark = pytest.mark.skipif(
    os.getenv("PCBKNOWLEDGE_RUN_POSTGRES_TESTS") != "1",
    reason="set PCBKNOWLEDGE_RUN_POSTGRES_TESTS=1 against disposable PostgreSQL",
)


def test_m1_security_repair_catalog_contract() -> None:
    engine = create_engine(os.environ["PCBKNOWLEDGE_DATABASE_DSN"])
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert isinstance(revision, str)
            assert revision >= "20260808_0004"

            roles = connection.execute(
                text(
                    "SELECT rolname, rolsuper, rolinherit, rolcreaterole, "
                    "rolcreatedb, rolreplication, rolbypassrls "
                    "FROM pg_catalog.pg_roles "
                    "WHERE rolname IN ('pcbknowledge_app', 'pcbknowledge_worker') "
                    "ORDER BY rolname"
                )
            ).all()
            assert [
                (
                    role.rolname,
                    role.rolsuper,
                    role.rolinherit,
                    role.rolcreaterole,
                    role.rolcreatedb,
                    role.rolreplication,
                    role.rolbypassrls,
                )
                for role in roles
            ] == [
                ("pcbknowledge_app", False, False, False, False, False, False),
                ("pcbknowledge_worker", False, False, False, False, False, False),
            ]
            membership_count = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_auth_members AS membership "
                    "JOIN pg_catalog.pg_roles AS member_role "
                    "ON member_role.oid = membership.member "
                    "JOIN pg_catalog.pg_roles AS granted_role "
                    "ON granted_role.oid = membership.roleid "
                    "WHERE member_role.rolname IN "
                    "('pcbknowledge_app', 'pcbknowledge_worker') "
                    "OR granted_role.rolname IN "
                    "('pcbknowledge_app', 'pcbknowledge_worker')"
                )
            )
            assert membership_count == 0

            app_policy_writes = connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM information_schema.role_table_grants "
                    "WHERE grantee = 'pcbknowledge_app' "
                    "AND table_schema IN ('identity', 'source') "
                    "AND privilege_type <> 'SELECT'"
                )
            )
            assert app_policy_writes == 0

            worker_grants = set(
                connection.execute(
                    text(
                        "SELECT table_schema, table_name, privilege_type "
                        "FROM information_schema.role_table_grants "
                        "WHERE grantee = 'pcbknowledge_worker'"
                    )
                ).all()
            )
            assert worker_grants == {
                ("platform", "outbox_event", "SELECT"),
                ("platform", "staging_upload_reservation", "SELECT"),
                ("public", "alembic_version", "SELECT"),
            }
            worker_outbox_updates = set(
                connection.execute(
                    text(
                        "SELECT column_name, privilege_type "
                        "FROM information_schema.role_column_grants "
                        "WHERE grantee = 'pcbknowledge_worker' "
                        "AND table_schema = 'platform' "
                        "AND table_name = 'outbox_event' "
                        "AND privilege_type = 'UPDATE'"
                    )
                ).all()
            )
            assert worker_outbox_updates == {
                ("attempts", "UPDATE"),
                ("available_at", "UPDATE"),
                ("last_failure_code", "UPDATE"),
                ("lease_expires_at", "UPDATE"),
                ("lease_owner", "UPDATE"),
                ("published_at", "UPDATE"),
                ("state", "UPDATE"),
                ("updated_at", "UPDATE"),
            }
            worker_reservation_updates = set(
                connection.execute(
                    text(
                        "SELECT column_name, privilege_type "
                        "FROM information_schema.role_column_grants "
                        "WHERE grantee = 'pcbknowledge_worker' "
                        "AND table_schema = 'platform' "
                        "AND table_name = 'staging_upload_reservation' "
                        "AND privilege_type = 'UPDATE'"
                    )
                ).all()
            )
            assert worker_reservation_updates == {
                ("cleaned_at", "UPDATE"),
                ("state", "UPDATE"),
            }
            assert connection.scalar(
                text(
                    "SELECT has_function_privilege("
                    "'pcbknowledge_worker', "
                    "'platform.claimable_storage_cleanup_scopes(integer)', "
                    "'EXECUTE')"
                )
            )
            assert not connection.scalar(
                text(
                    "SELECT has_function_privilege("
                    "'pcbknowledge_app', "
                    "'platform.claimable_storage_cleanup_scopes(integer)', "
                    "'EXECUTE')"
                )
            )

            lease_column = connection.execute(
                text(
                    "SELECT is_nullable, data_type "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'platform' "
                    "AND table_name = 'job_effect_receipt' "
                    "AND column_name = 'lease_attempt'"
                )
            ).one()
            assert lease_column == ("YES", "integer")
            owner_column = connection.execute(
                text(
                    "SELECT is_nullable, data_type, character_maximum_length "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'platform' "
                    "AND table_name = 'job_effect_receipt' "
                    "AND column_name = 'lease_owner'"
                )
            ).one()
            assert owner_column == ("YES", "character varying", 200)

            repaired_constraints = set(
                connection.scalars(
                    text(
                        "SELECT constraint_name "
                        "FROM information_schema.table_constraints "
                        "WHERE (table_schema = 'platform' "
                        "AND table_name IN ('job_effect_receipt', 'object_asset')) "
                        "OR (table_schema = 'source' "
                        "AND table_name = 'license_policy')"
                    )
                ).all()
            )
            assert {
                "ck_job_effect_lease_attempt",
                "ck_object_asset_bucket",
                "ck_object_asset_content_key",
                "fk_object_asset_license_policy_scope",
                "uq_license_policy_id_organization_scope",
            } <= repaired_constraints
            assert "ck_object_asset_organization_key" not in repaired_constraints
            assert "fk_object_asset_license_policy_organization" not in repaired_constraints

            assert connection.scalar(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_catalog.pg_trigger "
                    "WHERE tgrelid = 'platform.object_asset'::regclass "
                    "AND tgname = 'enforce_object_asset_policy_scope' "
                    "AND NOT tgisinternal)"
                )
            )
            integrity_triggers = set(
                connection.execute(
                    text(
                        "SELECT relation.relname, trigger.tgname, trigger.tgenabled "
                        "FROM pg_catalog.pg_trigger AS trigger "
                        "JOIN pg_catalog.pg_class AS relation "
                        "ON relation.oid = trigger.tgrelid "
                        "JOIN pg_catalog.pg_namespace AS namespace "
                        "ON namespace.oid = relation.relnamespace "
                        "WHERE namespace.nspname = 'platform' "
                        "AND NOT trigger.tgisinternal "
                        "AND trigger.tgname IN ("
                        "'enforce_job_effect_receipt_insert', "
                        "'enforce_knowledge_job_immutable_fields', "
                        "'enforce_outbox_event_immutable_fields')"
                    )
                ).all()
            )
            assert integrity_triggers == {
                ("job_effect_receipt", "enforce_job_effect_receipt_insert", "O"),
                ("knowledge_job", "enforce_knowledge_job_immutable_fields", "O"),
                ("outbox_event", "enforce_outbox_event_immutable_fields", "O"),
            }
            worker_policy = connection.execute(
                text(
                    "SELECT policy.polpermissive, policy.polcmd, "
                    "ARRAY(SELECT role.rolname "
                    "FROM unnest(policy.polroles) AS policy_role(role_oid) "
                    "JOIN pg_catalog.pg_roles AS role "
                    "ON role.oid = policy_role.role_oid), "
                    "pg_catalog.pg_get_expr(policy.polqual, policy.polrelid), "
                    "pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid) "
                    "FROM pg_catalog.pg_policy AS policy "
                    "WHERE policy.polrelid = 'platform.outbox_event'::regclass "
                    "AND policy.polname = 'outbox_worker_cleanup_only'"
                )
            ).one()
            expected_cleanup_expression = (
                "((event_type)::text = 'storage.staging_cleanup.requested'::text)"
            )
            assert worker_policy == (
                False,
                "*",
                ["pcbknowledge_worker"],
                expected_cleanup_expression,
                expected_cleanup_expression,
            )
    finally:
        engine.dispose()


def test_runtime_health_rejects_custom_non_super_protected_relation_owner() -> None:
    engine = create_engine(os.environ["PCBKNOWLEDGE_DATABASE_DSN"])
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("CREATE TABLE platform.health_owner_probe (id integer)"))
                connection.execute(
                    text("ALTER TABLE platform.health_owner_probe OWNER TO pcbknowledge_worker")
                )
                connection.execute(text("SET LOCAL ROLE pcbknowledge_worker"))

                with pytest.raises(UnsafeDatabaseRoleError):
                    require_restricted_database_role(connection)
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_worker_outbox_policy_hides_non_cleanup_events_in_the_same_scope() -> None:
    engine = create_engine(os.environ["PCBKNOWLEDGE_DATABASE_DSN"])
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                organization_id = connection.scalar(
                    text(
                        "INSERT INTO identity.organization "
                        "(id, slug, display_name) "
                        "VALUES (uuidv7(), "
                        "'worker-outbox-fence-' || uuidv7()::text, "
                        "'Worker outbox fence') RETURNING id"
                    )
                )
                assert organization_id is not None
                payload_digest = hashlib.sha256(b"{}").hexdigest()
                event_ids = connection.execute(
                    text(
                        "INSERT INTO platform.outbox_event "
                        "(organization_id, project_id, access_scope, event_type, "
                        "aggregate_type, aggregate_id, payload, payload_sha256, "
                        "idempotency_key) VALUES "
                        "(:organization_id, NULL, 'ORGANIZATION', "
                        "'storage.staging_cleanup.requested', 'storage.reservation', "
                        "uuidv7(), '{}'::jsonb, :digest, 'cleanup-visible'), "
                        "(:organization_id, NULL, 'ORGANIZATION', "
                        "'knowledge.publish', 'knowledge.entry', uuidv7(), "
                        "'{}'::jsonb, :digest, 'publish-hidden') "
                        "RETURNING id, event_type"
                    ),
                    {"organization_id": organization_id, "digest": payload_digest},
                ).all()
                event_id_by_type = {row.event_type: row.id for row in event_ids}

                connection.execute(text("SET LOCAL ROLE pcbknowledge_worker"))
                connection.execute(
                    text(
                        "SELECT set_config('pcbknowledge.organization_id', :organization_id, true)"
                    ),
                    {"organization_id": str(organization_id)},
                )
                connection.execute(text("SELECT set_config('pcbknowledge.project_ids', '', true)"))

                visible_types = set(
                    connection.scalars(
                        text(
                            "SELECT event_type FROM platform.outbox_event "
                            "WHERE organization_id = :organization_id"
                        ),
                        {"organization_id": organization_id},
                    ).all()
                )
                assert visible_types == {"storage.staging_cleanup.requested"}
                hidden_update = connection.execute(
                    text(
                        "UPDATE platform.outbox_event "
                        "SET state = 'DEAD_LETTER', "
                        "last_failure_code = 'FORGED_WORKER_UPDATE', "
                        "updated_at = clock_timestamp() "
                        "WHERE id = :event_id"
                    ),
                    {"event_id": event_id_by_type["knowledge.publish"]},
                )
                assert hidden_update.rowcount == 0
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_effect_receipt_trigger_requires_the_exact_live_job_lease() -> None:
    engine = create_engine(os.environ["PCBKNOWLEDGE_DATABASE_DSN"])
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                organization_id = connection.scalar(
                    text(
                        "INSERT INTO identity.organization "
                        "(id, slug, display_name) "
                        "VALUES (uuidv7(), "
                        "'repair-receipt-' || uuidv7()::text, "
                        "'Repair receipt') RETURNING id"
                    )
                )
                assert organization_id is not None
                connection.execute(text("SET LOCAL ROLE pcbknowledge_app"))
                connection.execute(
                    text(
                        "SELECT set_config('pcbknowledge.organization_id', :organization_id, true)"
                    ),
                    {"organization_id": str(organization_id)},
                )
                connection.execute(text("SELECT set_config('pcbknowledge.project_ids', '', true)"))
                job_id = connection.scalar(
                    text(
                        "INSERT INTO platform.knowledge_job "
                        "(organization_id, project_id, access_scope, job_type, "
                        "payload, payload_sha256, idempotency_key) "
                        "VALUES (:organization_id, NULL, 'ORGANIZATION', "
                        "'repair.receipt', '{}'::jsonb, :digest, "
                        "'repair-receipt') RETURNING id"
                    ),
                    {
                        "organization_id": organization_id,
                        "digest": hashlib.sha256(b"{}").hexdigest(),
                    },
                )
                assert job_id is not None
                connection.execute(
                    text(
                        "UPDATE platform.knowledge_job "
                        "SET state = 'RUNNING', attempts = 1, "
                        "lease_owner = 'repair-worker', "
                        "lease_expires_at = clock_timestamp() + interval '5 minutes', "
                        "updated_at = clock_timestamp() "
                        "WHERE id = :job_id"
                    ),
                    {"job_id": job_id},
                )

                def rejected(effect_name: str, *, attempt: int, owner: str) -> None:
                    savepoint = connection.begin_nested()
                    try:
                        with pytest.raises(DBAPIError):
                            connection.execute(
                                text(
                                    "INSERT INTO platform.job_effect_receipt "
                                    "(job_id, organization_id, project_id, access_scope, "
                                    "effect_name, effect_sha256, lease_attempt, lease_owner) "
                                    "VALUES (:job_id, :organization_id, NULL, "
                                    "'ORGANIZATION', :effect_name, :digest, :attempt, :owner)"
                                ),
                                {
                                    "job_id": job_id,
                                    "organization_id": organization_id,
                                    "effect_name": effect_name,
                                    "digest": hashlib.sha256(effect_name.encode()).hexdigest(),
                                    "attempt": attempt,
                                    "owner": owner,
                                },
                            )
                    finally:
                        savepoint.rollback()

                rejected("repair.receipt.wrong_owner", attempt=1, owner="other-worker")
                rejected("repair.receipt.wrong_attempt", attempt=2, owner="repair-worker")

                receipt = connection.execute(
                    text(
                        "INSERT INTO platform.job_effect_receipt "
                        "(job_id, organization_id, project_id, access_scope, "
                        "effect_name, effect_sha256, lease_attempt, lease_owner, recorded_at) "
                        "VALUES (:job_id, :organization_id, NULL, "
                        "'ORGANIZATION', 'repair.receipt.recorded', :digest, 1, "
                        "'repair-worker', '2000-01-01T00:00:00Z'::timestamptz) "
                        "RETURNING lease_attempt, lease_owner, recorded_at"
                    ),
                    {
                        "job_id": job_id,
                        "organization_id": organization_id,
                        "digest": "1" * 64,
                    },
                ).one()
                assert receipt.lease_attempt == 1
                assert receipt.lease_owner == "repair-worker"
                assert receipt.recorded_at.year >= 2026

                connection.execute(
                    text(
                        "UPDATE platform.knowledge_job "
                        "SET lease_expires_at = clock_timestamp() - interval '1 second' "
                        "WHERE id = :job_id"
                    ),
                    {"job_id": job_id},
                )
                rejected("repair.receipt.expired", attempt=1, owner="repair-worker")

                ready_job_id = connection.scalar(
                    text(
                        "INSERT INTO platform.knowledge_job "
                        "(organization_id, project_id, access_scope, job_type, "
                        "payload, payload_sha256, idempotency_key) "
                        "VALUES (:organization_id, NULL, 'ORGANIZATION', "
                        "'repair.ready', '{}'::jsonb, :digest, 'repair-ready') "
                        "RETURNING id"
                    ),
                    {
                        "organization_id": organization_id,
                        "digest": hashlib.sha256(b"{}").hexdigest(),
                    },
                )
                assert ready_job_id is not None
                savepoint = connection.begin_nested()
                try:
                    with pytest.raises(DBAPIError):
                        connection.execute(
                            text(
                                "INSERT INTO platform.job_effect_receipt "
                                "(job_id, organization_id, project_id, access_scope, "
                                "effect_name, effect_sha256, lease_attempt, lease_owner) "
                                "VALUES (:job_id, :organization_id, NULL, 'ORGANIZATION', "
                                "'repair.receipt.ready', :digest, 1, 'repair-worker')"
                            ),
                            {
                                "job_id": ready_job_id,
                                "organization_id": organization_id,
                                "digest": "2" * 64,
                            },
                        )
                finally:
                    savepoint.rollback()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
