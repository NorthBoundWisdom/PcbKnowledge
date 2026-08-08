"""Add durable jobs, transactional outbox, and object asset registry.

Revision ID: 20260808_0003
Revises: 20260808_0002
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0003"
down_revision: str | None = "20260808_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"
_TENANT_POLICY = """
organization_id = identity.current_organization_id()
AND (project_id IS NULL OR identity.can_access_project(project_id))
"""


def upgrade() -> None:
    _ensure_worker_role()
    op.execute("CREATE SCHEMA IF NOT EXISTS platform")

    op.create_table(
        "knowledge_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("job_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state", sa.String(length=32), server_default="READY", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("lease_owner", sa.String(length=200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("last_failure_code", sa.String(length=128)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_job_id_uuid7"),
        sa.CheckConstraint("priority BETWEEN -1000 AND 1000", name="ck_job_priority"),
        sa.CheckConstraint("attempts >= 0", name="ck_job_attempts_nonnegative"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 100", name="ck_job_max_attempts"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_job_payload_object"),
        sa.CheckConstraint("octet_length(payload::text) <= 8192", name="ck_job_payload_small"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_job_payload_sha256"),
        sa.CheckConstraint("length(btrim(job_type)) > 0", name="ck_job_type_nonempty"),
        sa.CheckConstraint(
            "length(btrim(idempotency_key)) > 0", name="ck_job_idempotency_nonempty"
        ),
        sa.CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')", name="ck_job_access_scope"
        ),
        sa.CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_job_scope_project",
        ),
        sa.CheckConstraint(
            "state IN ('READY', 'RUNNING', 'COMPLETED', 'DEAD_LETTER', 'CANCELLED')",
            name="ck_job_state",
        ),
        sa.CheckConstraint(
            "(state = 'RUNNING' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (state <> 'RUNNING' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_job_lease_state",
        ),
        sa.CheckConstraint(
            "last_failure_code IS NULL OR last_failure_code ~ '^[A-Z0-9][A-Z0-9_.-]{0,127}$'",
            name="ck_job_failure_code",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["identity.organization.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_job_project_organization",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_job_id_organization"),
        schema="platform",
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_job_scope_type_idempotency
        ON platform.knowledge_job (
            organization_id,
            COALESCE(project_id, '{_ZERO_UUID}'::uuid),
            access_scope,
            job_type,
            idempotency_key
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_job_claim
        ON platform.knowledge_job (
            organization_id, state, available_at, priority DESC, created_at
        )
        """
    )

    op.create_table(
        "job_effect_receipt",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("effect_name", sa.String(length=128), nullable=False),
        sa.Column("effect_sha256", sa.String(length=64), nullable=False),
        sa.Column("lease_attempt", sa.Integer(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_job_effect_id_uuid7"),
        sa.CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')", name="ck_job_effect_access_scope"
        ),
        sa.CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_job_effect_scope_project",
        ),
        sa.CheckConstraint("length(btrim(effect_name)) > 0", name="ck_job_effect_name_nonempty"),
        sa.CheckConstraint("effect_sha256 ~ '^[0-9a-f]{64}$'", name="ck_job_effect_sha256"),
        sa.CheckConstraint("lease_attempt > 0", name="ck_job_effect_lease_attempt"),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["platform.knowledge_job.id", "platform.knowledge_job.organization_id"],
            ondelete="RESTRICT",
            name="fk_job_effect_job_organization",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_job_effect_project_organization",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "effect_name", name="uq_job_effect_once"),
        schema="platform",
    )

    op.create_table(
        "outbox_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="READY", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("lease_owner", sa.String(length=200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="10", nullable=False),
        sa.Column("last_failure_code", sa.String(length=128)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_outbox_id_uuid7"),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_attempts_nonnegative"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 100", name="ck_outbox_max_attempts"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_outbox_payload_object"),
        sa.CheckConstraint("octet_length(payload::text) <= 8192", name="ck_outbox_payload_small"),
        sa.CheckConstraint("payload_sha256 ~ '^[0-9a-f]{64}$'", name="ck_outbox_payload_sha256"),
        sa.CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')", name="ck_outbox_access_scope"
        ),
        sa.CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_outbox_scope_project",
        ),
        sa.CheckConstraint(
            "state IN ('READY', 'RUNNING', 'PUBLISHED', 'DEAD_LETTER')",
            name="ck_outbox_state",
        ),
        sa.CheckConstraint(
            "(state = 'RUNNING' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL) "
            "OR (state <> 'RUNNING' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name="ck_outbox_lease_state",
        ),
        sa.CheckConstraint(
            "last_failure_code IS NULL OR last_failure_code ~ '^[A-Z0-9][A-Z0-9_.-]{0,127}$'",
            name="ck_outbox_failure_code",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["identity.organization.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_outbox_project_organization",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="platform",
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_outbox_scope_type_idempotency
        ON platform.outbox_event (
            organization_id,
            COALESCE(project_id, '{_ZERO_UUID}'::uuid),
            access_scope,
            event_type,
            idempotency_key
        )
        """
    )
    op.create_index(
        "ix_outbox_claim",
        "outbox_event",
        ["organization_id", "state", "available_at", "created_at"],
        schema="platform",
    )

    op.create_table(
        "object_asset",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("access_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("license_policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_kind", sa.String(length=64), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="AVAILABLE", nullable=False),
        sa.Column("created_by_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("substring(id::text, 15, 1) = '7'", name="ck_object_asset_id_uuid7"),
        sa.CheckConstraint("byte_size >= 0", name="ck_object_asset_byte_size"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_object_asset_sha256"),
        sa.CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_object_asset_access_scope",
        ),
        sa.CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_object_asset_scope_project",
        ),
        sa.CheckConstraint(
            "state IN ('AVAILABLE', 'QUARANTINED', 'TOMBSTONED')",
            name="ck_object_asset_state",
        ),
        sa.CheckConstraint(
            "object_key = 'organizations/' || organization_id::text || '/sha256/' || "
            "left(sha256, 2) || '/' || sha256",
            name="ck_object_asset_content_key",
        ),
        sa.CheckConstraint(
            "bucket ~ '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$'",
            name="ck_object_asset_bucket",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["identity.organization.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            ondelete="RESTRICT",
            name="fk_object_asset_project_organization",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            ondelete="RESTRICT",
            name="fk_object_asset_creator_organization",
        ),
        sa.ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            ondelete="RESTRICT",
            name="fk_object_asset_access_scope_organization",
        ),
        sa.ForeignKeyConstraint(
            ["license_policy_id", "organization_id", "access_scope_id"],
            [
                "source.license_policy.id",
                "source.license_policy.organization_id",
                "source.license_policy.access_scope_id",
            ],
            ondelete="RESTRICT",
            name="fk_object_asset_license_policy_scope",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="platform",
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_object_asset_logical_scope
        ON platform.object_asset (
            organization_id,
            COALESCE(project_id, '{_ZERO_UUID}'::uuid),
            access_scope,
            asset_kind,
            sha256
        )
        """
    )
    op.create_index(
        "ix_object_asset_scope",
        "object_asset",
        ["organization_id", "project_id", "state"],
        schema="platform",
    )

    _create_object_asset_policy_scope_trigger()
    _create_storage_cleanup_scope_function()

    for table_name in (
        "knowledge_job",
        "job_effect_receipt",
        "outbox_event",
        "object_asset",
    ):
        op.execute(f"ALTER TABLE platform.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE platform.{table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON platform.{table_name}
            USING ({_TENANT_POLICY})
            WITH CHECK ({_TENANT_POLICY})
            """
        )

    # The API role is intentionally neither the migration owner nor a schema
    # owner. Table grants permit operations while FORCE RLS constrains rows.
    op.execute("REVOKE ALL ON SCHEMA platform FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA platform TO pcbknowledge_app")
    for table_name in ("knowledge_job", "outbox_event"):
        op.execute(f"REVOKE ALL ON TABLE platform.{table_name} FROM PUBLIC")
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON TABLE platform.{table_name} TO pcbknowledge_app"
        )
    op.execute("REVOKE ALL ON TABLE platform.job_effect_receipt FROM PUBLIC")
    op.execute("GRANT SELECT, INSERT ON TABLE platform.job_effect_receipt TO pcbknowledge_app")
    op.execute("REVOKE ALL ON TABLE platform.object_asset FROM PUBLIC")
    op.execute("GRANT SELECT, INSERT ON TABLE platform.object_asset TO pcbknowledge_app")

    op.execute("GRANT USAGE ON SCHEMA identity, platform TO pcbknowledge_worker")
    op.execute(
        "GRANT EXECUTE ON FUNCTION identity.current_organization_id() TO pcbknowledge_worker"
    )
    op.execute("GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid) TO pcbknowledge_worker")
    op.execute(
        "GRANT SELECT, UPDATE ON TABLE platform.knowledge_job, platform.outbox_event "
        "TO pcbknowledge_worker"
    )
    op.execute("GRANT SELECT, INSERT ON TABLE platform.job_effect_receipt TO pcbknowledge_worker")
    op.execute("GRANT SELECT ON TABLE platform.object_asset TO pcbknowledge_worker")
    op.execute(
        "GRANT EXECUTE ON FUNCTION "
        "platform.claimable_storage_cleanup_scopes(integer) TO pcbknowledge_worker"
    )


def _ensure_worker_role() -> None:
    op.execute(
        """
        DO $block$
        DECLARE
            membership record;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'pcbknowledge_worker'
            ) THEN
                EXECUTE 'CREATE ROLE pcbknowledge_worker NOLOGIN';
            END IF;
            EXECUTE 'ALTER ROLE pcbknowledge_worker '
                'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS';

            FOR membership IN
                SELECT granted.rolname AS granted_role
                FROM pg_catalog.pg_auth_members AS member_map
                JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
                JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
                WHERE member_role.rolname = 'pcbknowledge_worker'
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE %I FROM pcbknowledge_worker', membership.granted_role
                );
            END LOOP;
            FOR membership IN
                SELECT member_role.rolname AS member_role
                FROM pg_catalog.pg_auth_members AS member_map
                JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
                JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
                WHERE granted.rolname = 'pcbknowledge_worker'
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE pcbknowledge_worker FROM %I', membership.member_role
                );
            END LOOP;
        END;
        $block$;
        """
    )


def _create_object_asset_policy_scope_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION platform.enforce_object_asset_policy_scope()
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

        CREATE TRIGGER enforce_object_asset_policy_scope
        BEFORE INSERT OR UPDATE ON platform.object_asset
        FOR EACH ROW EXECUTE FUNCTION platform.enforce_object_asset_policy_scope();
        """
    )


def _create_storage_cleanup_scope_function() -> None:
    op.execute(
        """
        CREATE FUNCTION platform.claimable_storage_cleanup_scopes(maximum_scopes integer)
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
            platform.claimable_storage_cleanup_scopes(integer) FROM PUBLIC;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS enforce_object_asset_policy_scope ON platform.object_asset")
    op.execute("DROP FUNCTION IF EXISTS platform.enforce_object_asset_policy_scope()")
    op.execute("DROP FUNCTION IF EXISTS platform.claimable_storage_cleanup_scopes(integer)")
    op.drop_table("object_asset", schema="platform")
    op.drop_table("outbox_event", schema="platform")
    op.drop_table("job_effect_receipt", schema="platform")
    op.drop_table("knowledge_job", schema="platform")
    op.execute("DROP SCHEMA IF EXISTS platform")
