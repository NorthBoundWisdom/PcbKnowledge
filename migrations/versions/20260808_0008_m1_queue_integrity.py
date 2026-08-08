"""Bind effect receipts to live leases and harden durable queue integrity.

Revision ID: 20260808_0008
Revises: 20260808_0007
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0008"
down_revision: str | None = "20260808_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install lease provenance, immutable identities, and least privilege."""

    op.add_column(
        "job_effect_receipt",
        sa.Column("lease_owner", sa.String(length=200), nullable=True),
        schema="platform",
    )
    _make_existing_receipts_unknown()
    _replace_receipt_guard()
    _install_immutable_queue_guards()
    _install_worker_outbox_policy()
    _normalize_queue_grants()


def downgrade() -> None:
    """Restore the 0007 contract without manufacturing historical provenance."""

    _require_no_verified_receipts_for_downgrade()
    _restore_0007_queue_grants()
    op.execute("DROP POLICY IF EXISTS outbox_worker_cleanup_only ON platform.outbox_event")
    _drop_immutable_queue_guards()
    _restore_0007_receipt_guard()
    op.drop_constraint(
        "ck_job_effect_lease_attempt",
        "job_effect_receipt",
        schema="platform",
        type_="check",
    )
    op.drop_column("job_effect_receipt", "lease_owner", schema="platform")
    op.create_check_constraint(
        "ck_job_effect_lease_attempt",
        "job_effect_receipt",
        "lease_attempt IS NULL OR lease_attempt > 0",
        schema="platform",
    )
    op.execute(
        "COMMENT ON COLUMN platform.job_effect_receipt.lease_attempt IS "
        "'NULL means the legacy lease attempt is unknown; new receipts require a positive value'"
    )


def _make_existing_receipts_unknown() -> None:
    op.execute(
        """
        -- Rows written before this revision did not persist the lease owner.
        -- Even a positive attempt is therefore incomplete provenance and must
        -- not be presented as a verified historical lease.
        UPDATE platform.job_effect_receipt
           SET lease_attempt = NULL,
               lease_owner = NULL;

        ALTER TABLE platform.job_effect_receipt
            DROP CONSTRAINT ck_job_effect_lease_attempt;
        ALTER TABLE platform.job_effect_receipt
            ADD CONSTRAINT ck_job_effect_lease_attempt
            CHECK (
                (lease_attempt IS NULL AND lease_owner IS NULL)
                OR (lease_attempt > 0 AND lease_owner IS NOT NULL)
            );

        COMMENT ON COLUMN platform.job_effect_receipt.lease_attempt IS
            'NULL with lease_owner NULL means pre-0008 lease provenance is UNKNOWN';
        COMMENT ON COLUMN platform.job_effect_receipt.lease_owner IS
            'NULL with lease_attempt NULL means pre-0008 lease provenance is UNKNOWN';
        """
    )


def _replace_receipt_guard() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION platform.enforce_job_effect_receipt_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            leased_job record;
        BEGIN
            IF NEW.lease_attempt IS NULL
               OR NEW.lease_attempt <= 0
               OR NEW.lease_owner IS NULL
               OR length(btrim(NEW.lease_owner)) = 0
            THEN
                RAISE EXCEPTION 'new effect receipt requires verified lease provenance'
                    USING ERRCODE = '23514';
            END IF;

            SELECT
                job.organization_id,
                job.project_id,
                job.access_scope,
                job.state,
                job.attempts,
                job.lease_owner,
                job.lease_expires_at
              INTO leased_job
              FROM platform.knowledge_job AS job
             WHERE job.id = NEW.job_id
               AND job.organization_id = NEW.organization_id
             FOR UPDATE;

            IF NOT FOUND
               OR leased_job.organization_id <> NEW.organization_id
               OR leased_job.project_id IS DISTINCT FROM NEW.project_id
               OR leased_job.access_scope <> NEW.access_scope
               OR leased_job.state <> 'RUNNING'
               OR leased_job.attempts <> NEW.lease_attempt
               OR leased_job.lease_owner IS DISTINCT FROM NEW.lease_owner
               OR leased_job.lease_expires_at IS NULL
               OR leased_job.lease_expires_at <= pg_catalog.clock_timestamp()
            THEN
                RAISE EXCEPTION 'effect receipt does not match an active job lease'
                    USING ERRCODE = '55000';
            END IF;
            NEW.recorded_at := pg_catalog.clock_timestamp();
            RETURN NEW;
        END;
        $function$;

        REVOKE ALL ON FUNCTION platform.enforce_job_effect_receipt_insert()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        """
    )


def _install_immutable_queue_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION platform.enforce_knowledge_job_immutable_fields()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'READY'
                   OR NEW.attempts <> 0
                   OR NEW.lease_owner IS NOT NULL
                   OR NEW.lease_expires_at IS NOT NULL
                   OR NEW.last_failure_code IS NOT NULL
                   OR NEW.completed_at IS NOT NULL
                   OR NEW.cancelled_at IS NOT NULL
                THEN
                    RAISE EXCEPTION 'knowledge job must begin in the READY state'
                        USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;
            IF ROW(
                OLD.id, OLD.organization_id, OLD.project_id, OLD.access_scope,
                OLD.job_type, OLD.payload, OLD.payload_sha256,
                OLD.idempotency_key, OLD.priority, OLD.max_attempts,
                OLD.created_at
            ) IS DISTINCT FROM ROW(
                NEW.id, NEW.organization_id, NEW.project_id, NEW.access_scope,
                NEW.job_type, NEW.payload, NEW.payload_sha256,
                NEW.idempotency_key, NEW.priority, NEW.max_attempts,
                NEW.created_at
            ) THEN
                RAISE EXCEPTION 'knowledge job identity and payload are immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $function$;

        CREATE TRIGGER enforce_knowledge_job_immutable_fields
        BEFORE INSERT OR UPDATE ON platform.knowledge_job
        FOR EACH ROW EXECUTE FUNCTION platform.enforce_knowledge_job_immutable_fields();

        CREATE FUNCTION platform.enforce_outbox_event_immutable_fields()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'READY'
                   OR NEW.attempts <> 0
                   OR NEW.lease_owner IS NOT NULL
                   OR NEW.lease_expires_at IS NOT NULL
                   OR NEW.last_failure_code IS NOT NULL
                   OR NEW.published_at IS NOT NULL
                THEN
                    RAISE EXCEPTION 'outbox event must begin in the READY state'
                        USING ERRCODE = '55000';
                END IF;
                RETURN NEW;
            END IF;
            IF ROW(
                OLD.id, OLD.organization_id, OLD.project_id, OLD.access_scope,
                OLD.event_type, OLD.aggregate_type, OLD.aggregate_id,
                OLD.payload, OLD.payload_sha256, OLD.idempotency_key,
                OLD.max_attempts, OLD.created_at
            ) IS DISTINCT FROM ROW(
                NEW.id, NEW.organization_id, NEW.project_id, NEW.access_scope,
                NEW.event_type, NEW.aggregate_type, NEW.aggregate_id,
                NEW.payload, NEW.payload_sha256, NEW.idempotency_key,
                NEW.max_attempts, NEW.created_at
            ) THEN
                RAISE EXCEPTION 'outbox identity and payload are immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $function$;

        CREATE TRIGGER enforce_outbox_event_immutable_fields
        BEFORE INSERT OR UPDATE ON platform.outbox_event
        FOR EACH ROW EXECUTE FUNCTION platform.enforce_outbox_event_immutable_fields();

        REVOKE ALL ON FUNCTION platform.enforce_knowledge_job_immutable_fields()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        REVOKE ALL ON FUNCTION platform.enforce_outbox_event_immutable_fields()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        """
    )


def _drop_immutable_queue_guards() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS enforce_knowledge_job_immutable_fields
            ON platform.knowledge_job;
        DROP TRIGGER IF EXISTS enforce_outbox_event_immutable_fields
            ON platform.outbox_event;
        DROP FUNCTION IF EXISTS platform.enforce_knowledge_job_immutable_fields();
        DROP FUNCTION IF EXISTS platform.enforce_outbox_event_immutable_fields();
        """
    )


def _install_worker_outbox_policy() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS outbox_worker_cleanup_only
            ON platform.outbox_event;
        CREATE POLICY outbox_worker_cleanup_only
        ON platform.outbox_event
        AS RESTRICTIVE
        FOR ALL
        TO pcbknowledge_worker
        USING (event_type = 'storage.staging_cleanup.requested')
        WITH CHECK (event_type = 'storage.staging_cleanup.requested');
        """
    )


def _normalize_queue_grants() -> None:
    op.execute(
        """
        REVOKE ALL ON TABLE platform.knowledge_job, platform.outbox_event
            FROM pcbknowledge_app, pcbknowledge_worker;

        REVOKE INSERT (
            id, organization_id, project_id, access_scope, job_type,
            payload, payload_sha256, idempotency_key, priority, state,
            available_at, lease_owner, lease_expires_at, attempts,
            max_attempts, last_failure_code, created_at, updated_at,
            completed_at, cancelled_at
        ) ON platform.knowledge_job FROM pcbknowledge_app, pcbknowledge_worker;
        REVOKE UPDATE (
            id, organization_id, project_id, access_scope, job_type,
            payload, payload_sha256, idempotency_key, priority, state,
            available_at, lease_owner, lease_expires_at, attempts,
            max_attempts, last_failure_code, created_at, updated_at,
            completed_at, cancelled_at
        ) ON platform.knowledge_job FROM pcbknowledge_app, pcbknowledge_worker;
        REVOKE INSERT (
            id, organization_id, project_id, access_scope, event_type,
            aggregate_type, aggregate_id, payload, payload_sha256,
            idempotency_key, state, available_at, lease_owner,
            lease_expires_at, attempts, max_attempts, last_failure_code,
            created_at, updated_at, published_at
        ) ON platform.outbox_event FROM pcbknowledge_app, pcbknowledge_worker;
        REVOKE UPDATE (
            id, organization_id, project_id, access_scope, event_type,
            aggregate_type, aggregate_id, payload, payload_sha256,
            idempotency_key, state, available_at, lease_owner,
            lease_expires_at, attempts, max_attempts, last_failure_code,
            created_at, updated_at, published_at
        ) ON platform.outbox_event FROM pcbknowledge_app, pcbknowledge_worker;

        GRANT SELECT ON TABLE platform.knowledge_job TO pcbknowledge_app;
        GRANT INSERT (
            id, organization_id, project_id, access_scope, job_type,
            payload, payload_sha256, idempotency_key, priority, state,
            available_at, attempts, max_attempts, created_at, updated_at
        ) ON platform.knowledge_job TO pcbknowledge_app;
        GRANT UPDATE (
            state, available_at, lease_owner, lease_expires_at, attempts,
            last_failure_code, updated_at, completed_at, cancelled_at
        ) ON platform.knowledge_job TO pcbknowledge_app;

        GRANT SELECT ON TABLE platform.outbox_event TO pcbknowledge_app;
        GRANT INSERT (
            id, organization_id, project_id, access_scope, event_type,
            aggregate_type, aggregate_id, payload, payload_sha256,
            idempotency_key, state, available_at, attempts, max_attempts,
            created_at, updated_at
        ) ON platform.outbox_event TO pcbknowledge_app;
        GRANT UPDATE (
            state, available_at, lease_owner, lease_expires_at, attempts,
            last_failure_code, updated_at, published_at
        ) ON platform.outbox_event TO pcbknowledge_app;

        GRANT SELECT ON TABLE platform.outbox_event TO pcbknowledge_worker;
        GRANT UPDATE (
            state, available_at, lease_owner, lease_expires_at, attempts,
            last_failure_code, updated_at, published_at
        ) ON platform.outbox_event TO pcbknowledge_worker;
        """
    )


def _restore_0007_queue_grants() -> None:
    op.execute(
        """
        REVOKE ALL ON TABLE platform.knowledge_job, platform.outbox_event
            FROM pcbknowledge_app, pcbknowledge_worker;
        GRANT SELECT, INSERT, UPDATE ON TABLE
            platform.knowledge_job, platform.outbox_event
            TO pcbknowledge_app;
        GRANT SELECT, UPDATE ON TABLE platform.outbox_event
            TO pcbknowledge_worker;
        """
    )


def _restore_0007_receipt_guard() -> None:
    op.execute(
        """
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

        REVOKE ALL ON FUNCTION platform.enforce_job_effect_receipt_insert()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        """
    )


def _require_no_verified_receipts_for_downgrade() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM platform.job_effect_receipt
                WHERE lease_owner IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade: verified receipt lease owners would be lost'
                    USING ERRCODE = '23514';
            END IF;
        END;
        $block$;
        """
    )
