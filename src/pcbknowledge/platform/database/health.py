"""Real PostgreSQL connectivity checks shared by API and worker."""

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.pool import NullPool

from pcbknowledge.platform.config import Settings


class UnsafeDatabaseRoleError(RuntimeError):
    """Raised when a request-path connection can own or bypass tenant policy."""


class DatabaseContractError(RuntimeError):
    """Raised when the connected database is not at the executable M1 contract."""


EXPECTED_DATABASE_REVISION = "20260808_0008"


def require_restricted_database_role(connection: Connection) -> None:
    """Reject roles that can own, bypass, or switch around tenant policy."""

    role = connection.execute(
        text(
            "SELECT role.rolsuper, role.rolinherit, role.rolcreaterole, "
            "role.rolcreatedb, role.rolreplication, role.rolbypassrls, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_auth_members AS membership "
            "WHERE membership.member = role.oid"
            ") AS has_role_membership, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_auth_members AS membership "
            "WHERE membership.roleid = role.oid"
            ") AS has_role_assumers, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_namespace AS namespace "
            "WHERE namespace.nspowner = role.oid "
            "AND namespace.nspname IN ('identity', 'source', 'audit', 'platform')"
            ") AS owns_protected_schema, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_class AS relation "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = relation.relnamespace "
            "WHERE relation.relowner = role.oid "
            "AND namespace.nspname IN ('identity', 'source', 'audit', 'platform')"
            ") AS owns_protected_relation, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_proc AS routine "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = routine.pronamespace "
            "WHERE routine.proowner = role.oid "
            "AND namespace.nspname IN ('identity', 'source', 'audit', 'platform')"
            ") AS owns_protected_function "
            "FROM pg_catalog.pg_roles AS role "
            "WHERE role.rolname = CURRENT_USER"
        )
    ).one_or_none()
    if (
        role is None
        or role.rolsuper
        or role.rolinherit
        or role.rolcreaterole
        or role.rolcreatedb
        or role.rolreplication
        or role.rolbypassrls
        or role.has_role_membership
        or role.has_role_assumers
        or role.owns_protected_schema
        or role.owns_protected_relation
        or role.owns_protected_function
    ):
        raise UnsafeDatabaseRoleError("runtime database role is privileged")


def require_database_contract(connection: Connection) -> None:
    """Reject stale schemas and runtime grants before serving or consuming work."""

    identity = connection.execute(
        text("SELECT SESSION_USER AS session_user, CURRENT_USER AS current_user")
    ).one()
    if (
        identity.session_user not in {"pcbknowledge_app", "pcbknowledge_worker"}
        or identity.current_user != identity.session_user
    ):
        raise DatabaseContractError("database runtime identity is not supported")

    revision = connection.scalar(
        text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
    )
    if revision != EXPECTED_DATABASE_REVISION:
        raise DatabaseContractError("database schema revision is not supported")
    contract = connection.execute(
        text(
            "WITH contract_relations AS ("
            "SELECT namespace.nspname AS schema_name, relation.relname, "
            "relation.oid, relation.relrowsecurity, relation.relforcerowsecurity "
            "FROM pg_catalog.pg_class AS relation "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = relation.relnamespace "
            "WHERE (namespace.nspname, relation.relname) IN ("
            "('identity', 'organization'), ('identity', 'project'), "
            "('identity', 'external_subject'), ('identity', 'membership'), "
            "('source', 'source_organization'), ('source', 'access_scope'), "
            "('source', 'license_policy'), ('audit', 'audit_event'), "
            "('platform', 'job_effect_receipt'), ('platform', 'knowledge_job'), "
            "('platform', 'outbox_event'), ('platform', 'object_asset'), "
            "('platform', 'staging_upload_reservation'))), "
            "contract_routines AS ("
            "SELECT routine.oid, routine.proname "
            "FROM pg_catalog.pg_proc AS routine "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = routine.pronamespace "
            "WHERE namespace.nspname = 'platform' "
            "AND routine.proname = 'claimable_storage_cleanup_scopes' "
            "AND routine.proargtypes = '23'::pg_catalog.oidvector), "
            "contract_triggers AS ("
            "SELECT trigger.tgname "
            "FROM pg_catalog.pg_trigger AS trigger "
            "JOIN pg_catalog.pg_class AS relation "
            "ON relation.oid = trigger.tgrelid "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = relation.relnamespace "
            "WHERE NOT trigger.tgisinternal "
            "AND trigger.tgenabled = 'O' "
            "AND (namespace.nspname, relation.relname, trigger.tgname) IN ("
            "('platform', 'job_effect_receipt', "
            "'enforce_job_effect_receipt_insert'), "
            "('platform', 'knowledge_job', "
            "'enforce_knowledge_job_immutable_fields'), "
            "('platform', 'outbox_event', "
            "'enforce_outbox_event_immutable_fields'))), "
            "worker_outbox_policy AS ("
            "SELECT policy.oid "
            "FROM pg_catalog.pg_policy AS policy "
            "JOIN pg_catalog.pg_class AS relation "
            "ON relation.oid = policy.polrelid "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = relation.relnamespace "
            "WHERE namespace.nspname = 'platform' "
            "AND relation.relname = 'outbox_event' "
            "AND policy.polname = 'outbox_worker_cleanup_only' "
            "AND NOT policy.polpermissive "
            "AND policy.polcmd = '*' "
            "AND policy.polroles = ARRAY[(SELECT role.oid "
            "FROM pg_catalog.pg_roles AS role "
            "WHERE role.rolname = 'pcbknowledge_worker')]::pg_catalog.oid[] "
            "AND pg_catalog.pg_get_expr(policy.polqual, policy.polrelid) = "
            "'((event_type)::text = ''storage.staging_cleanup.requested''::text)' "
            "AND pg_catalog.pg_get_expr(policy.polwithcheck, policy.polrelid) = "
            "'((event_type)::text = ''storage.staging_cleanup.requested''::text)') "
            "SELECT "
            "EXISTS (SELECT 1 FROM contract_relations "
            "WHERE schema_name = 'platform' "
            "AND relname = 'staging_upload_reservation') AS has_reservations, "
            "EXISTS (SELECT 1 FROM contract_routines) AS has_discovery, "
            "(SELECT count(*) = 3 FROM contract_triggers) AS has_integrity_triggers, "
            "EXISTS (SELECT 1 FROM worker_outbox_policy) AS has_worker_outbox_fence, "
            "(SELECT count(*) = 13 "
            "AND bool_and(relrowsecurity AND relforcerowsecurity) "
            "FROM contract_relations) AS rls_forced, "
            "has_function_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_routines), 'EXECUTE') AS is_cleanup_worker, "
            "has_table_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'SELECT') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'state', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'available_at', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'lease_owner', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'lease_expires_at', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'attempts', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'last_failure_code', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'updated_at', 'UPDATE') AND "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations "
            "WHERE schema_name = 'platform' AND relname = 'outbox_event'), "
            "'published_at', 'UPDATE') AS can_process_outbox, "
            "has_table_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'platform' "
            "AND relname = 'staging_upload_reservation'), "
            "'SELECT') AS can_read_reservations, "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'platform' "
            "AND relname = 'staging_upload_reservation'), "
            "'state', 'UPDATE') AS can_update_reservation_state, "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'platform' "
            "AND relname = 'staging_upload_reservation'), "
            "'cleaned_at', 'UPDATE') AS can_record_cleanup, "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'platform' "
            "AND relname = 'staging_upload_reservation'), "
            "'id', 'INSERT') AS can_reserve_upload, "
            "has_column_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'platform' "
            "AND relname = 'staging_upload_reservation'), "
            "'asset_id', 'UPDATE') AS can_finalize_upload, "
            "has_table_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'platform' "
            "AND relname = 'object_asset'), "
            "'SELECT,INSERT') AS can_register_asset, "
            "has_table_privilege(CURRENT_USER, "
            "(SELECT oid FROM contract_relations WHERE schema_name = 'audit' "
            "AND relname = 'audit_event'), "
            "'SELECT,INSERT') AS can_append_audit"
        )
    ).one()
    base_ready = (
        contract.has_reservations
        and contract.has_discovery
        and contract.has_integrity_triggers
        and contract.has_worker_outbox_fence
        and contract.rls_forced
    )
    if contract.is_cleanup_worker:
        ready = (
            base_ready
            and contract.can_process_outbox
            and contract.can_read_reservations
            and contract.can_update_reservation_state
            and contract.can_record_cleanup
            and not contract.can_reserve_upload
            and not contract.can_register_asset
        )
    else:
        ready = (
            base_ready
            and contract.can_read_reservations
            and contract.can_update_reservation_state
            and contract.can_reserve_upload
            and contract.can_finalize_upload
            and contract.can_register_asset
            and contract.can_append_audit
            and not contract.can_record_cleanup
        )
    if not ready:
        raise DatabaseContractError("database runtime grants do not match the M1 contract")
    _require_exact_runtime_grants(connection, role_name=identity.current_user)


def _require_exact_runtime_grants(connection: Connection, *, role_name: str) -> None:
    unexpected = connection.scalar(
        text(
            """
            WITH protected_relations AS (
                SELECT
                    namespace.nspname AS schema_name,
                    relation.relname,
                    relation.oid
                FROM pg_catalog.pg_class AS relation
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = relation.relnamespace
                WHERE (
                    namespace.nspname IN ('identity', 'source', 'audit', 'platform')
                    OR (
                        namespace.nspname = 'public'
                        AND relation.relname = 'alembic_version'
                    )
                )
                  AND relation.relkind IN ('r', 'p')
            ),
            relation_privileges(privilege) AS (
                VALUES
                    ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'),
                    ('TRUNCATE'), ('REFERENCES'), ('TRIGGER')
            ),
            column_privileges(privilege) AS (
                VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('REFERENCES')
            ),
            allowed_tables(role_name, schema_name, table_name, privilege) AS (
                VALUES
                    ('pcbknowledge_app', 'identity', 'organization', 'SELECT'),
                    ('pcbknowledge_app', 'identity', 'project', 'SELECT'),
                    ('pcbknowledge_app', 'identity', 'external_subject', 'SELECT'),
                    ('pcbknowledge_app', 'identity', 'membership', 'SELECT'),
                    ('pcbknowledge_app', 'source', 'source_organization', 'SELECT'),
                    ('pcbknowledge_app', 'source', 'access_scope', 'SELECT'),
                    ('pcbknowledge_app', 'source', 'license_policy', 'SELECT'),
                    ('pcbknowledge_app', 'audit', 'audit_event', 'SELECT'),
                    ('pcbknowledge_app', 'audit', 'audit_event', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job', 'SELECT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event', 'SELECT'),
                    ('pcbknowledge_app', 'platform', 'job_effect_receipt', 'SELECT'),
                    ('pcbknowledge_app', 'platform', 'job_effect_receipt', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'object_asset', 'SELECT'),
                    ('pcbknowledge_app', 'platform', 'object_asset', 'INSERT'),
                    ('pcbknowledge_app', 'public', 'alembic_version', 'SELECT'),
                    (
                        'pcbknowledge_app', 'platform',
                        'staging_upload_reservation', 'SELECT'
                    ),
                    ('pcbknowledge_worker', 'platform', 'outbox_event', 'SELECT'),
                    ('pcbknowledge_worker', 'public', 'alembic_version', 'SELECT'),
                    (
                        'pcbknowledge_worker', 'platform',
                        'staging_upload_reservation', 'SELECT'
                    )
            ),
            allowed_columns(
                role_name, schema_name, table_name, column_name, privilege
            ) AS (
                VALUES
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'organization_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'project_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'access_scope', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'job_type', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'payload', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'payload_sha256', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'idempotency_key', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'priority', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'state', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'available_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'attempts', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'max_attempts', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'created_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'updated_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'state', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'available_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'lease_owner', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'lease_expires_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'attempts', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'last_failure_code', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'updated_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'completed_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'knowledge_job',
                     'cancelled_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'organization_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'project_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'access_scope', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'event_type', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'aggregate_type', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'aggregate_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'payload', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'payload_sha256', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'idempotency_key', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'state', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'available_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'attempts', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'max_attempts', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'created_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'updated_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'state', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'available_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'lease_owner', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'lease_expires_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'attempts', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'last_failure_code', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'updated_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'outbox_event',
                     'published_at', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'state', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'available_at', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'lease_owner', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'lease_expires_at', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'attempts', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'last_failure_code', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'updated_at', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'outbox_event',
                     'published_at', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'organization_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'project_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'access_scope', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'access_scope_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'license_policy_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'created_by_subject_id', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'media_type', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'expected_byte_size', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'state', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'created_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'expires_at', 'INSERT'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'state', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'asset_id', 'UPDATE'),
                    ('pcbknowledge_app', 'platform', 'staging_upload_reservation',
                     'finalized_at', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'staging_upload_reservation',
                     'state', 'UPDATE'),
                    ('pcbknowledge_worker', 'platform', 'staging_upload_reservation',
                     'cleaned_at', 'UPDATE')
            ),
            allowed_schemas(role_name, schema_name, privilege) AS (
                VALUES
                    ('pcbknowledge_app', 'identity', 'USAGE'),
                    ('pcbknowledge_app', 'source', 'USAGE'),
                    ('pcbknowledge_app', 'audit', 'USAGE'),
                    ('pcbknowledge_app', 'platform', 'USAGE'),
                    ('pcbknowledge_app', 'public', 'USAGE'),
                    ('pcbknowledge_worker', 'identity', 'USAGE'),
                    ('pcbknowledge_worker', 'platform', 'USAGE'),
                    ('pcbknowledge_worker', 'public', 'USAGE')
            ),
            allowed_functions(
                role_name, schema_name, function_name, argument_types
            ) AS (
                VALUES
                    ('pcbknowledge_app', 'identity', 'current_organization_id', ''),
                    ('pcbknowledge_app', 'identity', 'can_access_project', '2950'),
                    (
                        'pcbknowledge_app', 'identity',
                        'current_external_subject_id', ''
                    ),
                    (
                        'pcbknowledge_worker', 'identity',
                        'current_organization_id', ''
                    ),
                    (
                        'pcbknowledge_worker', 'identity',
                        'can_access_project', '2950'
                    ),
                    (
                        'pcbknowledge_worker', 'platform',
                        'claimable_storage_cleanup_scopes', '23'
                    )
            )
            SELECT EXISTS (
                SELECT 1
                FROM protected_relations AS relation
                CROSS JOIN relation_privileges AS held
                WHERE pg_catalog.has_table_privilege(
                    CURRENT_USER, relation.oid, held.privilege
                )
                  AND NOT EXISTS (
                    SELECT 1 FROM allowed_tables AS allowed
                    WHERE allowed.role_name = :role_name
                      AND allowed.schema_name = relation.schema_name
                      AND allowed.table_name = relation.relname
                      AND allowed.privilege = held.privilege
                  )
                UNION ALL
                SELECT 1
                FROM protected_relations AS relation
                JOIN pg_catalog.pg_attribute AS attribute
                  ON attribute.attrelid = relation.oid
                 AND attribute.attnum > 0
                 AND NOT attribute.attisdropped
                CROSS JOIN column_privileges AS held
                WHERE pg_catalog.has_column_privilege(
                    CURRENT_USER, relation.oid, attribute.attnum, held.privilege
                )
                  AND NOT EXISTS (
                    SELECT 1 FROM allowed_tables AS allowed
                    WHERE allowed.role_name = :role_name
                      AND allowed.schema_name = relation.schema_name
                      AND allowed.table_name = relation.relname
                      AND allowed.privilege = held.privilege
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM allowed_columns AS allowed
                    WHERE allowed.role_name = :role_name
                      AND allowed.schema_name = relation.schema_name
                      AND allowed.table_name = relation.relname
                      AND allowed.column_name = attribute.attname
                      AND allowed.privilege = held.privilege
                  )
                UNION ALL
                SELECT 1
                FROM allowed_tables AS allowed
                JOIN protected_relations AS relation
                  ON relation.schema_name = allowed.schema_name
                 AND relation.relname = allowed.table_name
                WHERE allowed.role_name = :role_name
                  AND NOT pg_catalog.has_table_privilege(
                    CURRENT_USER, relation.oid, allowed.privilege
                  )
                UNION ALL
                SELECT 1
                FROM allowed_columns AS allowed
                JOIN protected_relations AS relation
                  ON relation.schema_name = allowed.schema_name
                 AND relation.relname = allowed.table_name
                JOIN pg_catalog.pg_attribute AS attribute
                  ON attribute.attrelid = relation.oid
                 AND attribute.attname = allowed.column_name
                 AND attribute.attnum > 0
                 AND NOT attribute.attisdropped
                WHERE allowed.role_name = :role_name
                  AND NOT pg_catalog.has_column_privilege(
                    CURRENT_USER, relation.oid, attribute.attnum, allowed.privilege
                  )
                UNION ALL
                SELECT 1
                FROM allowed_schemas AS allowed
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.nspname = allowed.schema_name
                WHERE allowed.role_name = :role_name
                  AND NOT pg_catalog.has_schema_privilege(
                    CURRENT_USER, namespace.oid, allowed.privilege
                  )
                UNION ALL
                SELECT 1
                FROM allowed_functions AS allowed
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.nspname = allowed.schema_name
                JOIN pg_catalog.pg_proc AS routine
                  ON routine.pronamespace = namespace.oid
                 AND routine.proname = allowed.function_name
                 AND routine.proargtypes::text = allowed.argument_types
                WHERE allowed.role_name = :role_name
                  AND NOT pg_catalog.has_function_privilege(
                    CURRENT_USER, routine.oid, 'EXECUTE'
                  )
                UNION ALL
                SELECT 1
                FROM pg_catalog.pg_namespace AS namespace
                CROSS JOIN (VALUES ('USAGE'), ('CREATE')) AS held(privilege)
                WHERE namespace.nspname IN (
                    'identity', 'source', 'audit', 'platform', 'public'
                )
                  AND pg_catalog.has_schema_privilege(
                    CURRENT_USER, namespace.oid, held.privilege
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM allowed_schemas AS allowed
                    WHERE allowed.role_name = :role_name
                      AND allowed.schema_name = namespace.nspname
                      AND allowed.privilege = held.privilege
                  )
                UNION ALL
                SELECT 1
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname IN ('identity', 'source', 'audit', 'platform')
                  AND pg_catalog.has_function_privilege(
                    CURRENT_USER, routine.oid, 'EXECUTE'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM allowed_functions AS allowed
                    WHERE allowed.role_name = :role_name
                      AND allowed.schema_name = namespace.nspname
                      AND allowed.function_name = routine.proname
                      AND allowed.argument_types = routine.proargtypes::text
                  )
            )
            """
        ),
        {"role_name": role_name},
    )
    if unexpected:
        raise DatabaseContractError("database runtime grants do not exactly match the M1 contract")


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
            require_restricted_database_role(connection)
            require_database_contract(connection)
    finally:
        engine.dispose()
