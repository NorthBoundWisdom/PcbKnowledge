"""Repair M1 runtime-role, receipt, and object-registry security drift.

Revision ID: 20260808_0004
Revises: 20260808_0003
Create Date: 2026-08-08

The original 0002/0003 files were hardened while some databases were already
at revision 0003.  Every operation below is therefore idempotent against a
fresh database while also bringing an older 0003 database to the same schema.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_0004"
down_revision: str | None = "20260808_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the forward-only security repair and cleanup-worker boundary."""

    _harden_runtime_roles()
    _ensure_license_policy_scope_key()
    _repair_job_effect_receipts()
    _repair_object_asset_contract()
    _ensure_cleanup_scope_discovery()
    _normalize_application_privileges()
    _grant_cleanup_worker_privileges()


def downgrade() -> None:
    """Return to the current 0003 contract without restoring unsafe drift.

    The structural repairs and application-role restrictions already exist in
    the repository's canonical 0002/0003 definitions, so removing them would
    not represent revision 0003.  The only new 0004 behavior is the narrower
    cleanup-only worker grant set; restore the canonical 0003 worker grants.
    """

    _harden_runtime_roles()
    _normalize_application_privileges()
    _grant_current_0003_worker_privileges()


def _harden_runtime_roles() -> None:
    op.execute(
        """
        DO $block$
        DECLARE
            runtime_role text;
            membership record;
        BEGIN
            FOREACH runtime_role IN ARRAY ARRAY[
                'pcbknowledge_app', 'pcbknowledge_worker'
            ]
            LOOP
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_roles
                    WHERE rolname = runtime_role
                ) THEN
                    EXECUTE pg_catalog.format(
                        'CREATE ROLE %I NOLOGIN', runtime_role
                    );
                END IF;

                EXECUTE pg_catalog.format(
                    'ALTER ROLE %I '
                    'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT '
                    'NOREPLICATION NOBYPASSRLS',
                    runtime_role
                );

                -- NOINHERIT does not prevent SET ROLE.  A runtime principal
                -- must have no outgoing membership, including the first edge
                -- of a transitive escalation chain.  Reverse memberships are
                -- removed as well so unrelated logins cannot assume it.
                FOR membership IN
                    SELECT granted.rolname AS granted_role
                    FROM pg_catalog.pg_auth_members AS member_map
                    JOIN pg_catalog.pg_roles AS member_role
                      ON member_role.oid = member_map.member
                    JOIN pg_catalog.pg_roles AS granted
                      ON granted.oid = member_map.roleid
                    WHERE member_role.rolname = runtime_role
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE %I FROM %I',
                        membership.granted_role,
                        runtime_role
                    );
                END LOOP;

                FOR membership IN
                    SELECT member_role.rolname AS member_role
                    FROM pg_catalog.pg_auth_members AS member_map
                    JOIN pg_catalog.pg_roles AS member_role
                      ON member_role.oid = member_map.member
                    JOIN pg_catalog.pg_roles AS granted
                      ON granted.oid = member_map.roleid
                    WHERE granted.rolname = runtime_role
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE %I FROM %I',
                        runtime_role,
                        membership.member_role
                    );
                END LOOP;
            END LOOP;
        END;
        $block$;
        """
    )


def _ensure_license_policy_scope_key() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_constraint
                WHERE conrelid = 'source.license_policy'::pg_catalog.regclass
                  AND conname = 'uq_license_policy_id_organization_scope'
            ) THEN
                ALTER TABLE source.license_policy
                    ADD CONSTRAINT uq_license_policy_id_organization_scope
                    UNIQUE (id, organization_id, access_scope_id);
            END IF;
        END;
        $block$;
        """
    )


def _repair_job_effect_receipts() -> None:
    op.execute(
        """
        ALTER TABLE platform.job_effect_receipt
            ADD COLUMN IF NOT EXISTS lease_attempt integer;

        UPDATE platform.job_effect_receipt AS receipt
           SET lease_attempt = greatest(job.attempts, 1)
          FROM platform.knowledge_job AS job
         WHERE receipt.job_id = job.id
           AND receipt.organization_id = job.organization_id
           AND receipt.lease_attempt IS NULL;

        ALTER TABLE platform.job_effect_receipt
            ALTER COLUMN lease_attempt SET NOT NULL;
        ALTER TABLE platform.job_effect_receipt
            DROP CONSTRAINT IF EXISTS ck_job_effect_lease_attempt;
        ALTER TABLE platform.job_effect_receipt
            ADD CONSTRAINT ck_job_effect_lease_attempt
            CHECK (lease_attempt > 0) NOT VALID;
        ALTER TABLE platform.job_effect_receipt
            VALIDATE CONSTRAINT ck_job_effect_lease_attempt;
        """
    )


def _repair_object_asset_contract() -> None:
    op.execute(
        """
        ALTER TABLE platform.object_asset
            DROP CONSTRAINT IF EXISTS ck_object_asset_content_key;
        ALTER TABLE platform.object_asset
            ADD CONSTRAINT ck_object_asset_content_key
            CHECK (
                object_key = 'organizations/' || organization_id::text ||
                    '/sha256/' || left(sha256, 2) || '/' || sha256
            ) NOT VALID;
        ALTER TABLE platform.object_asset
            VALIDATE CONSTRAINT ck_object_asset_content_key;
        ALTER TABLE platform.object_asset
            DROP CONSTRAINT IF EXISTS ck_object_asset_organization_key;

        ALTER TABLE platform.object_asset
            DROP CONSTRAINT IF EXISTS ck_object_asset_bucket;
        ALTER TABLE platform.object_asset
            ADD CONSTRAINT ck_object_asset_bucket
            CHECK (bucket ~ '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$')
            NOT VALID;
        ALTER TABLE platform.object_asset
            VALIDATE CONSTRAINT ck_object_asset_bucket;

        ALTER TABLE platform.object_asset
            DROP CONSTRAINT IF EXISTS fk_object_asset_license_policy_scope;
        ALTER TABLE platform.object_asset
            ADD CONSTRAINT fk_object_asset_license_policy_scope
            FOREIGN KEY (license_policy_id, organization_id, access_scope_id)
            REFERENCES source.license_policy (
                id, organization_id, access_scope_id
            )
            ON DELETE RESTRICT
            NOT VALID;
        ALTER TABLE platform.object_asset
            VALIDATE CONSTRAINT fk_object_asset_license_policy_scope;
        ALTER TABLE platform.object_asset
            DROP CONSTRAINT IF EXISTS
                fk_object_asset_license_policy_organization;
        """
    )
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM platform.object_asset AS asset
                LEFT JOIN source.access_scope AS scope
                  ON scope.id = asset.access_scope_id
                 AND scope.organization_id = asset.organization_id
                LEFT JOIN source.license_policy AS policy
                  ON policy.id = asset.license_policy_id
                 AND policy.organization_id = asset.organization_id
                 AND policy.access_scope_id = asset.access_scope_id
                WHERE scope.id IS NULL
                   OR policy.id IS NULL
                   OR scope.scope_kind::text <> asset.access_scope
                   OR scope.project_id IS DISTINCT FROM asset.project_id
            ) THEN
                RAISE EXCEPTION
                    'existing object assets violate their policy scope'
                    USING ERRCODE = '23514';
            END IF;
        END;
        $block$;

        CREATE OR REPLACE FUNCTION platform.enforce_object_asset_policy_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            stored_scope_kind text;
            stored_project_id uuid;
            stored_policy_scope_id uuid;
        BEGIN
            SELECT scope_kind, project_id
              INTO stored_scope_kind, stored_project_id
              FROM source.access_scope
             WHERE id = NEW.access_scope_id
               AND organization_id = NEW.organization_id;
            IF NOT FOUND
               OR stored_scope_kind <> NEW.access_scope
               OR stored_project_id IS DISTINCT FROM NEW.project_id
            THEN
                RAISE EXCEPTION 'object asset access scope is incoherent'
                    USING ERRCODE = '23514';
            END IF;

            SELECT access_scope_id
              INTO stored_policy_scope_id
              FROM source.license_policy
             WHERE id = NEW.license_policy_id
               AND organization_id = NEW.organization_id;
            IF NOT FOUND OR stored_policy_scope_id <> NEW.access_scope_id THEN
                RAISE EXCEPTION 'object asset license policy is incoherent'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;

        DROP TRIGGER IF EXISTS enforce_object_asset_policy_scope
            ON platform.object_asset;
        CREATE TRIGGER enforce_object_asset_policy_scope
        BEFORE INSERT OR UPDATE ON platform.object_asset
        FOR EACH ROW EXECUTE FUNCTION
            platform.enforce_object_asset_policy_scope();

        REVOKE ALL ON FUNCTION
            platform.enforce_object_asset_policy_scope()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        """
    )


def _ensure_cleanup_scope_discovery() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            platform.claimable_storage_cleanup_scopes(maximum_scopes integer)
        RETURNS TABLE (
            organization_id uuid,
            project_id uuid,
            access_scope text
        )
        LANGUAGE sql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $function$
            SELECT DISTINCT
                event.organization_id,
                event.project_id,
                event.access_scope
            FROM platform.outbox_event AS event
            WHERE event.event_type = 'storage.staging_cleanup.requested'
              AND (
                  (
                      event.state = 'READY'
                      AND event.available_at <= pg_catalog.clock_timestamp()
                  )
                  OR (
                      event.state = 'RUNNING'
                      AND event.lease_expires_at <= pg_catalog.clock_timestamp()
                  )
              )
            ORDER BY event.organization_id, event.project_id NULLS FIRST
            LIMIT CASE
                WHEN maximum_scopes IS NULL THEN 100
                WHEN maximum_scopes < 1 THEN 1
                WHEN maximum_scopes > 1000 THEN 1000
                ELSE maximum_scopes
            END
        $function$;

        REVOKE ALL ON FUNCTION
            platform.claimable_storage_cleanup_scopes(integer)
            FROM PUBLIC, pcbknowledge_app;
        """
    )


def _normalize_application_privileges() -> None:
    op.execute(
        """
        REVOKE ALL ON SCHEMA identity, source, audit, platform
            FROM pcbknowledge_app;
        REVOKE ALL ON ALL TABLES IN SCHEMA identity, source, audit, platform
            FROM pcbknowledge_app;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA identity, source, audit, platform
            FROM pcbknowledge_app;

        GRANT USAGE ON SCHEMA identity, source, audit, platform
            TO pcbknowledge_app;
        GRANT SELECT ON ALL TABLES IN SCHEMA identity, source
            TO pcbknowledge_app;
        GRANT SELECT, INSERT ON TABLE audit.audit_event
            TO pcbknowledge_app;
        GRANT SELECT, INSERT, UPDATE
            ON TABLE platform.knowledge_job, platform.outbox_event
            TO pcbknowledge_app;
        GRANT SELECT, INSERT ON TABLE
            platform.job_effect_receipt, platform.object_asset
            TO pcbknowledge_app;

        GRANT EXECUTE ON FUNCTION identity.current_organization_id()
            TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid)
            TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.current_external_subject_id()
            TO pcbknowledge_app;
        """
    )


def _reset_worker_privileges() -> None:
    op.execute(
        """
        REVOKE ALL ON SCHEMA identity, source, audit, platform
            FROM pcbknowledge_worker;
        REVOKE ALL ON ALL TABLES IN SCHEMA identity, source, audit, platform
            FROM pcbknowledge_worker;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA identity, source, audit, platform
            FROM pcbknowledge_worker;

        GRANT USAGE ON SCHEMA identity, platform TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION identity.current_organization_id()
            TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid)
            TO pcbknowledge_worker;
        """
    )


def _grant_cleanup_worker_privileges() -> None:
    _reset_worker_privileges()
    op.execute(
        """
        GRANT SELECT, UPDATE ON TABLE platform.outbox_event
            TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION
            platform.claimable_storage_cleanup_scopes(integer)
            TO pcbknowledge_worker;
        """
    )


def _grant_current_0003_worker_privileges() -> None:
    _reset_worker_privileges()
    op.execute(
        """
        GRANT SELECT, UPDATE ON TABLE
            platform.knowledge_job, platform.outbox_event
            TO pcbknowledge_worker;
        GRANT SELECT, INSERT ON TABLE platform.job_effect_receipt
            TO pcbknowledge_worker;
        GRANT SELECT ON TABLE platform.object_asset TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION
            platform.claimable_storage_cleanup_scopes(integer)
            TO pcbknowledge_worker;
        """
    )
