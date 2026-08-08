"""Make legacy receipt provenance explicit and pin runtime grants.

Revision ID: 20260808_0007
Revises: 20260808_0006
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260808_0007"
down_revision: str | None = "20260808_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Represent unverifiable legacy attempts as unknown and reset grants."""

    _make_legacy_receipt_attempts_unknown()
    _normalize_runtime_grants()
    op.execute(
        """
        REVOKE ALL ON FUNCTION platform.enforce_job_effect_receipt_insert()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        """
    )


def downgrade() -> None:
    """Restore the 0006 shape only when no unknown history would be forged."""

    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM platform.job_effect_receipt
                WHERE lease_attempt IS NULL
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade: legacy receipt lease attempts are unknown'
                    USING ERRCODE = '23514';
            END IF;
        END;
        $block$;

        DROP TRIGGER IF EXISTS enforce_job_effect_receipt_insert
            ON platform.job_effect_receipt;
        DROP FUNCTION IF EXISTS platform.enforce_job_effect_receipt_insert();
        ALTER TABLE platform.job_effect_receipt
            DROP CONSTRAINT IF EXISTS ck_job_effect_lease_attempt;
        ALTER TABLE platform.job_effect_receipt
            ADD CONSTRAINT ck_job_effect_lease_attempt
            CHECK (lease_attempt > 0);
        ALTER TABLE platform.job_effect_receipt
            ALTER COLUMN lease_attempt SET NOT NULL;
        """
    )
    _normalize_runtime_grants()


def _make_legacy_receipt_attempts_unknown() -> None:
    op.execute(
        """
        ALTER TABLE platform.job_effect_receipt
            ALTER COLUMN lease_attempt DROP NOT NULL;
        ALTER TABLE platform.job_effect_receipt
            DROP CONSTRAINT IF EXISTS ck_job_effect_lease_attempt;

        -- 0004 had no evidence from which to recover the historical lease
        -- attempt and used the job's then-current attempt count.  Conservatively
        -- mark every receipt that predates this repair as unknown instead of
        -- retaining a value that may describe a later retry.
        UPDATE platform.job_effect_receipt
           SET lease_attempt = NULL;

        ALTER TABLE platform.job_effect_receipt
            ADD CONSTRAINT ck_job_effect_lease_attempt
            CHECK (lease_attempt IS NULL OR lease_attempt > 0);
        COMMENT ON COLUMN platform.job_effect_receipt.lease_attempt IS
            'NULL means the legacy lease attempt is unknown; new receipts require a positive value';

        CREATE OR REPLACE FUNCTION platform.enforce_job_effect_receipt_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF NEW.lease_attempt IS NULL OR NEW.lease_attempt <= 0 THEN
                RAISE EXCEPTION 'new effect receipt requires a verified lease attempt'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;

        DROP TRIGGER IF EXISTS enforce_job_effect_receipt_insert
            ON platform.job_effect_receipt;
        CREATE TRIGGER enforce_job_effect_receipt_insert
        BEFORE INSERT ON platform.job_effect_receipt
        FOR EACH ROW EXECUTE FUNCTION platform.enforce_job_effect_receipt_insert();
        """
    )


def _normalize_runtime_grants() -> None:
    op.execute(
        """
        REVOKE ALL ON SCHEMA identity, source, audit, platform
            FROM pcbknowledge_app, pcbknowledge_worker;
        REVOKE ALL ON ALL TABLES IN SCHEMA identity, source, audit, platform
            FROM pcbknowledge_app, pcbknowledge_worker;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA identity, source, audit, platform
            FROM pcbknowledge_app, pcbknowledge_worker;

        GRANT USAGE ON SCHEMA identity, source, audit, platform
            TO pcbknowledge_app;
        GRANT SELECT ON ALL TABLES IN SCHEMA identity, source
            TO pcbknowledge_app;
        GRANT SELECT, INSERT ON TABLE audit.audit_event
            TO pcbknowledge_app;
        GRANT SELECT, INSERT, UPDATE ON TABLE
            platform.knowledge_job, platform.outbox_event
            TO pcbknowledge_app;
        GRANT SELECT, INSERT ON TABLE
            platform.job_effect_receipt, platform.object_asset
            TO pcbknowledge_app;
        GRANT SELECT ON TABLE platform.staging_upload_reservation
            TO pcbknowledge_app;
        GRANT INSERT (
            id, organization_id, project_id, access_scope, access_scope_id,
            license_policy_id, created_by_subject_id, media_type,
            expected_byte_size, state, created_at, expires_at
        ) ON platform.staging_upload_reservation TO pcbknowledge_app;
        GRANT UPDATE (state, asset_id, finalized_at)
            ON platform.staging_upload_reservation TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.current_organization_id()
            TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid)
            TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.current_external_subject_id()
            TO pcbknowledge_app;

        GRANT USAGE ON SCHEMA identity, platform TO pcbknowledge_worker;
        GRANT SELECT, UPDATE ON TABLE platform.outbox_event
            TO pcbknowledge_worker;
        GRANT SELECT ON TABLE platform.staging_upload_reservation
            TO pcbknowledge_worker;
        GRANT UPDATE (state, cleaned_at)
            ON platform.staging_upload_reservation TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION identity.current_organization_id()
            TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid)
            TO pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION
            platform.claimable_storage_cleanup_scopes(integer)
            TO pcbknowledge_worker;

        """
    )
