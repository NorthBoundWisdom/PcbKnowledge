"""Real PostgreSQL connectivity checks shared by API and worker."""

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.pool import NullPool

from pcbknowledge.platform.config import Settings


class UnsafeDatabaseRoleError(RuntimeError):
    """Raised when a request-path connection can own or bypass tenant policy."""


class DatabaseContractError(RuntimeError):
    """Raised when the connected database is not at the executable M1 contract."""


EXPECTED_DATABASE_REVISION = "20260809_0009"


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
            "AND namespace.nspname IN "
            "('identity', 'source', 'audit', 'platform', 'document')"
            ") AS owns_protected_schema, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_class AS relation "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = relation.relnamespace "
            "WHERE relation.relowner = role.oid "
            "AND namespace.nspname IN "
            "('identity', 'source', 'audit', 'platform', 'document')"
            ") AS owns_protected_relation, "
            "EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_proc AS routine "
            "JOIN pg_catalog.pg_namespace AS namespace "
            "ON namespace.oid = routine.pronamespace "
            "WHERE routine.proowner = role.oid "
            "AND namespace.nspname IN "
            "('identity', 'source', 'audit', 'platform', 'document')"
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
        identity.session_user
        not in {"pcbknowledge_app", "pcbknowledge_worker", "pcbknowledge_verifier"}
        or identity.current_user != identity.session_user
    ):
        raise DatabaseContractError("database runtime identity is not supported")

    revision = connection.scalar(
        text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1")
    )
    if revision != EXPECTED_DATABASE_REVISION:
        raise DatabaseContractError("database schema revision is not supported")
    _require_document_database_contract(connection)
    if identity.current_user == "pcbknowledge_verifier":
        _require_verifier_database_contract(connection)
        _require_exact_runtime_grants(connection, role_name=identity.current_user)
        return
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


def _require_document_database_contract(connection: Connection) -> None:
    """Require immutable FORCE-RLS document relations and isolated verifier fences.

    Policy fingerprints are over PostgreSQL 18's ``pg_get_expr`` normalized
    output. Exact fingerprints intentionally reject seemingly harmless extra
    branches such as ``OR true`` on this security boundary.
    """

    contract = connection.execute(
        text(
            """
            WITH document_relations AS (
                SELECT relation.relname, relation.relrowsecurity,
                       relation.relforcerowsecurity
                FROM pg_catalog.pg_class AS relation
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'document'
                  AND relation.relname IN (
                      'upload_session', 'document',
                      'document_revision', 'document_asset'
                  )
            ), required_triggers(schema_name, table_name, trigger_name) AS (
                VALUES
                    ('document', 'upload_session',
                     'enforce_upload_session_binding'),
                    ('document', 'upload_session',
                     'enforce_upload_session_transition'),
                    ('document', 'upload_session',
                     'require_upload_reservation_lifecycle'),
                    ('document', 'document', 'reject_document_mutation'),
                    ('document', 'document',
                     'enforce_document_insert_upload_binding'),
                    ('document', 'document', 'require_closed_document_insert'),
                    ('document', 'document_revision',
                     'reject_document_revision_mutation'),
                    ('document', 'document_revision', 'enforce_revision_scope'),
                    ('document', 'document_revision',
                     'enforce_revision_insert_upload_binding'),
                    ('document', 'document_revision',
                     'require_closed_revision_insert'),
                    ('document', 'document_asset',
                     'reject_document_asset_mutation'),
                    ('document', 'document_asset',
                     'enforce_document_asset_binding'),
                    ('document', 'document_asset',
                     'enforce_asset_insert_upload_binding'),
                    ('document', 'document_asset',
                     'require_closed_document_asset_insert'),
                    ('platform', 'object_asset',
                     'require_closed_object_asset_insert'),
                    ('platform', 'staging_upload_reservation',
                     'enforce_verifier_staging_transition'),
                    ('platform', 'staging_upload_reservation',
                     'require_document_upload_lifecycle')
            ), installed_triggers AS (
                SELECT namespace.nspname AS schema_name,
                       relation.relname AS table_name,
                       trigger.tgname AS trigger_name
                FROM pg_catalog.pg_trigger AS trigger
                JOIN pg_catalog.pg_class AS relation
                  ON relation.oid = trigger.tgrelid
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = relation.relnamespace
                WHERE NOT trigger.tgisinternal AND trigger.tgenabled = 'O'
            ), required_policies(
                table_name, policy_name,
                expected_using_md5, expected_check_md5
            ) AS (
                VALUES
                    (
                        'knowledge_job', 'knowledge_job_verifier_only',
                        '259d3ab37c236d5915d3ca85b2860724',
                        '259d3ab37c236d5915d3ca85b2860724'
                    ),
                    ('job_effect_receipt',
                     'job_effect_receipt_verifier_only',
                     '125cff282e125222e96489ad27c5a7bc',
                     '125cff282e125222e96489ad27c5a7bc'),
                    ('staging_upload_reservation',
                     'staging_upload_verifier_only',
                     '1604016d275877430628f263579fbd9d',
                     '1604016d275877430628f263579fbd9d'),
                    ('object_asset', 'object_asset_verifier_only',
                     '214ca1a2c65e535920de9008ccecf9cb',
                     'b69028fcfcaf6f4ad2a645c62324e9fb'),
                    ('outbox_event', 'outbox_verifier_cleanup_only',
                     '2d19fbb288c08f33eefb078da9dd839b',
                     '2d19fbb288c08f33eefb078da9dd839b')
            ), installed_policies AS (
                SELECT relation.relname AS table_name,
                       policy.polname AS policy_name,
                       policy.polpermissive,
                       policy.polroles,
                       policy.polcmd,
                       pg_catalog.pg_get_expr(
                           policy.polqual, policy.polrelid
                       ) AS using_expression,
                       pg_catalog.pg_get_expr(
                           policy.polwithcheck, policy.polrelid
                       ) AS check_expression
                FROM pg_catalog.pg_policy AS policy
                JOIN pg_catalog.pg_class AS relation
                  ON relation.oid = policy.polrelid
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'platform'
            ), discovery AS (
                SELECT routine.oid, routine.prosecdef,
                       routine.proconfig
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname = 'platform'
                  AND routine.proname =
                      'claimable_document_intake_scopes'
                  AND routine.proargtypes = '23'::pg_catalog.oidvector
            ), closure AS (
                SELECT routine.oid, routine.prosecdef,
                       routine.proconfig, routine.proacl, routine.proowner
                FROM pg_catalog.pg_proc AS routine
                JOIN pg_catalog.pg_namespace AS namespace
                  ON namespace.oid = routine.pronamespace
                WHERE namespace.nspname = 'document'
                  AND routine.proname = 'enforce_closed_stored_upload'
                  AND routine.proargtypes = ''::pg_catalog.oidvector
            )
            SELECT
                (SELECT count(*) = 4
                   AND bool_and(relrowsecurity AND relforcerowsecurity)
                 FROM document_relations) AS relations_ready,
                NOT EXISTS (
                    SELECT 1 FROM required_triggers AS required
                    WHERE NOT EXISTS (
                        SELECT 1 FROM installed_triggers AS installed
                        WHERE installed.schema_name = required.schema_name
                          AND installed.table_name = required.table_name
                          AND installed.trigger_name = required.trigger_name
                    )
                ) AS triggers_ready,
                NOT EXISTS (
                    SELECT 1 FROM required_policies AS required
                    WHERE NOT EXISTS (
                        SELECT 1 FROM installed_policies AS installed
                        WHERE installed.table_name = required.table_name
                          AND installed.policy_name = required.policy_name
                          AND NOT installed.polpermissive
                          AND installed.polcmd = '*'
                          AND installed.polroles = ARRAY[(
                              SELECT oid FROM pg_catalog.pg_roles
                              WHERE rolname = 'pcbknowledge_verifier'
                          )]::pg_catalog.oid[]
                          AND installed.using_expression IS NOT NULL
                          AND installed.check_expression IS NOT NULL
                          AND pg_catalog.md5(
                              installed.using_expression
                          ) = required.expected_using_md5
                          AND pg_catalog.md5(
                              installed.check_expression
                          ) = required.expected_check_md5
                    )
                ) AS policies_ready,
                EXISTS (
                    SELECT 1 FROM discovery
                    WHERE prosecdef
                      AND proconfig = ARRAY[
                          'search_path=pg_catalog, pg_temp'
                      ]::text[]
                ) AS discovery_ready,
                NOT has_function_privilege(
                    'pcbknowledge_app', (SELECT oid FROM discovery), 'EXECUTE'
                )
                AND NOT has_function_privilege(
                    'pcbknowledge_worker', (SELECT oid FROM discovery), 'EXECUTE'
                )
                AND has_function_privilege(
                    'pcbknowledge_verifier', (SELECT oid FROM discovery),
                    'EXECUTE'
                ) AS discovery_acl_ready,
                EXISTS (
                    SELECT 1 FROM closure
                    WHERE prosecdef
                      AND proconfig = ARRAY[
                          'search_path=pg_catalog, pg_temp'
                      ]::text[]
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM closure,
                         pg_catalog.aclexplode(
                             COALESCE(
                                 closure.proacl,
                                 pg_catalog.acldefault(
                                     'f', closure.proowner
                                 )
                             )
                         ) AS acl
                    WHERE acl.grantee = 0
                      AND acl.privilege_type = 'EXECUTE'
                )
                AND NOT has_function_privilege(
                    'pcbknowledge_verifier', (SELECT oid FROM closure),
                    'EXECUTE'
                ) AS closure_ready
            """
        )
    ).one()
    if not all(contract):
        raise DatabaseContractError("document database contract is incomplete")


def _require_verifier_database_contract(connection: Connection) -> None:
    """Require the verifier's narrow write surface before it can claim work."""

    ready = connection.scalar(
        text(
            """
            SELECT
                has_schema_privilege(
                    CURRENT_USER, 'document', 'USAGE'
                )
                AND has_function_privilege(
                    CURRENT_USER,
                    'platform.claimable_document_intake_scopes(integer)',
                    'EXECUTE'
                )
                AND has_table_privilege(
                    CURRENT_USER, 'platform.knowledge_job', 'SELECT'
                )
                AND has_column_privilege(
                    CURRENT_USER, 'platform.knowledge_job',
                    'state', 'UPDATE'
                )
                AND has_table_privilege(
                    CURRENT_USER, 'platform.staging_upload_reservation',
                    'SELECT'
                )
                AND has_column_privilege(
                    CURRENT_USER, 'platform.staging_upload_reservation',
                    'asset_id', 'UPDATE'
                )
                AND has_table_privilege(
                    CURRENT_USER, 'platform.object_asset', 'SELECT'
                )
                AND has_column_privilege(
                    CURRENT_USER, 'platform.object_asset', 'id', 'INSERT'
                )
                AND has_table_privilege(
                    CURRENT_USER, 'document.upload_session', 'SELECT'
                )
                AND has_column_privilege(
                    CURRENT_USER, 'document.upload_session',
                    'state', 'UPDATE'
                )
                AND has_table_privilege(
                    CURRENT_USER, 'document.document', 'SELECT'
                )
                AND has_column_privilege(
                    CURRENT_USER, 'document.document', 'id', 'INSERT'
                )
                AND NOT has_table_privilege(
                    CURRENT_USER, 'document.document', 'UPDATE,DELETE'
                )
            """
        )
    )
    if not ready:
        raise DatabaseContractError("verifier database grants are incomplete")


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
                    namespace.nspname IN (
                        'identity', 'source', 'audit', 'platform', 'document'
                    )
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
                    ('pcbknowledge_app', 'document', 'upload_session', 'SELECT'),
                    ('pcbknowledge_app', 'document', 'document', 'SELECT'),
                    (
                        'pcbknowledge_app', 'document',
                        'document_revision', 'SELECT'
                    ),
                    (
                        'pcbknowledge_app', 'document',
                        'document_asset', 'SELECT'
                    ),
                    (
                        'pcbknowledge_app', 'platform',
                        'staging_upload_reservation', 'SELECT'
                    ),
                    ('pcbknowledge_worker', 'platform', 'outbox_event', 'SELECT'),
                    ('pcbknowledge_worker', 'public', 'alembic_version', 'SELECT'),
                    (
                        'pcbknowledge_worker', 'platform',
                        'staging_upload_reservation', 'SELECT'
                    ),
                    ('pcbknowledge_verifier', 'public',
                     'alembic_version', 'SELECT'),
                    ('pcbknowledge_verifier', 'source',
                     'access_scope', 'SELECT'),
                    ('pcbknowledge_verifier', 'source',
                     'license_policy', 'SELECT'),
                    ('pcbknowledge_verifier', 'platform',
                     'knowledge_job', 'SELECT'),
                    ('pcbknowledge_verifier', 'platform',
                     'job_effect_receipt', 'SELECT'),
                    ('pcbknowledge_verifier', 'platform',
                     'staging_upload_reservation', 'SELECT'),
                    ('pcbknowledge_verifier', 'platform',
                     'object_asset', 'SELECT'),
                    ('pcbknowledge_verifier', 'platform',
                     'outbox_event', 'SELECT'),
                    ('pcbknowledge_verifier', 'document',
                     'upload_session', 'SELECT'),
                    ('pcbknowledge_verifier', 'document',
                     'document', 'SELECT'),
                    ('pcbknowledge_verifier', 'document',
                     'document_revision', 'SELECT'),
                    ('pcbknowledge_verifier', 'document',
                     'document_asset', 'SELECT')
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
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'organization_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'project_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'access_scope', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'access_scope_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'license_policy_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'source_organization_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'target_document_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'target_revision_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'creates_document', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'title', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'document_number', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'revision_label', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'original_filename', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'media_type', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'expected_byte_size', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'idempotency_key', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'request_sha256', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'state', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'created_by_subject_id', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'created_at', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'updated_at', 'INSERT')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'state', 'UPDATE')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'expected_sha256', 'UPDATE')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'completion_job_id', 'UPDATE')
                    ,('pcbknowledge_app', 'document', 'upload_session',
                      'updated_at', 'UPDATE')

                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'state', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'available_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'lease_owner', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'lease_expires_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'attempts', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'last_failure_code', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'updated_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'completed_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'knowledge_job',
                      'cancelled_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'job_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'access_scope', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'effect_name', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'effect_sha256', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'lease_attempt', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'lease_owner', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'job_effect_receipt', 'recorded_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform',
                      'staging_upload_reservation', 'state', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform',
                      'staging_upload_reservation', 'asset_id', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform',
                      'staging_upload_reservation', 'finalized_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'access_scope', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'access_scope_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'license_policy_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'asset_kind', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'bucket', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'object_key', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'sha256', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'byte_size', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'media_type', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'state', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'created_by_subject_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'object_asset',
                      'created_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'access_scope', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'event_type', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'aggregate_type', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'aggregate_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'payload', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'payload_sha256', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'idempotency_key', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'state', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'available_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'attempts', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'max_attempts', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'created_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'platform', 'outbox_event',
                      'updated_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'occurred_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'actor_subject_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'actor_kind', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'action', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'resource_type', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'resource_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'outcome', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'request_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'detail', 'INSERT')
                    ,('pcbknowledge_verifier', 'audit', 'audit_event',
                      'occurred_at', 'SELECT')
                    ,('pcbknowledge_verifier', 'document', 'upload_session',
                      'state', 'UPDATE')
                    ,('pcbknowledge_verifier', 'document', 'upload_session',
                      'actual_sha256', 'UPDATE')
                    ,('pcbknowledge_verifier', 'document', 'upload_session',
                      'object_asset_id', 'UPDATE')
                    ,('pcbknowledge_verifier', 'document', 'upload_session',
                      'failure_code', 'UPDATE')
                    ,('pcbknowledge_verifier', 'document', 'upload_session',
                      'updated_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'document', 'upload_session',
                      'completed_at', 'UPDATE')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'title', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'document_number', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'created_by_subject_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document',
                      'created_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'document_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'source_organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'access_scope', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'access_scope_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'license_policy_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'revision_label', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'original_filename', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'media_type', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'state', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'created_by_subject_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document',
                      'document_revision', 'created_at', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'organization_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'project_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'revision_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'object_asset_id', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'asset_kind', 'INSERT')
                    ,('pcbknowledge_verifier', 'document', 'document_asset',
                      'created_at', 'INSERT')
            ),
            allowed_schemas(role_name, schema_name, privilege) AS (
                VALUES
                    ('pcbknowledge_app', 'identity', 'USAGE'),
                    ('pcbknowledge_app', 'source', 'USAGE'),
                    ('pcbknowledge_app', 'audit', 'USAGE'),
                    ('pcbknowledge_app', 'platform', 'USAGE'),
                    ('pcbknowledge_app', 'document', 'USAGE'),
                    ('pcbknowledge_app', 'public', 'USAGE'),
                    ('pcbknowledge_worker', 'identity', 'USAGE'),
                    ('pcbknowledge_worker', 'platform', 'USAGE'),
                    ('pcbknowledge_worker', 'public', 'USAGE'),
                    ('pcbknowledge_verifier', 'public', 'USAGE'),
                    ('pcbknowledge_verifier', 'identity', 'USAGE'),
                    ('pcbknowledge_verifier', 'source', 'USAGE'),
                    ('pcbknowledge_verifier', 'audit', 'USAGE'),
                    ('pcbknowledge_verifier', 'platform', 'USAGE'),
                    ('pcbknowledge_verifier', 'document', 'USAGE')
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
                    ),
                    (
                        'pcbknowledge_verifier', 'identity',
                        'current_organization_id', ''
                    ),
                    (
                        'pcbknowledge_verifier', 'identity',
                        'can_access_project', '2950'
                    ),
                    (
                        'pcbknowledge_verifier', 'platform',
                        'claimable_document_intake_scopes', '23'
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
                    'identity', 'source', 'audit', 'platform',
                    'document', 'public'
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
                WHERE namespace.nspname IN (
                    'identity', 'source', 'audit', 'platform', 'document'
                )
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
