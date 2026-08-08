"""Add durable, tenant-bound staging upload reservations.

Revision ID: 20260808_0005
Revises: 20260808_0004
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0005"
down_revision: str | None = "20260808_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_POLICY = """
organization_id = identity.current_organization_id()
AND (project_id IS NULL OR identity.can_access_project(project_id))
"""


def upgrade() -> None:
    _ensure_asset_composite_identity()
    op.create_table(
        "staging_upload_reservation",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("access_scope", sa.String(length=32), nullable=False),
        sa.Column("access_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("license_policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("expected_byte_size", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("cleaned_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "substring(id::text, 15, 1) = '7'",
            name="ck_staging_upload_id_uuid7",
        ),
        sa.CheckConstraint(
            "access_scope IN ('ORGANIZATION', 'PROJECT')",
            name="ck_staging_upload_access_scope",
        ),
        sa.CheckConstraint(
            "(access_scope = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(access_scope = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_staging_upload_scope_project",
        ),
        sa.CheckConstraint(
            "state IN ('PENDING', 'FINALIZED', 'CLEANED', 'EXPIRED')",
            name="ck_staging_upload_state",
        ),
        sa.CheckConstraint(
            "(state = 'PENDING' AND asset_id IS NULL AND finalized_at IS NULL "
            "AND cleaned_at IS NULL) OR "
            "(state = 'FINALIZED' AND asset_id IS NOT NULL AND finalized_at IS NOT NULL "
            "AND cleaned_at IS NULL) OR "
            "(state = 'CLEANED' AND asset_id IS NOT NULL AND finalized_at IS NOT NULL "
            "AND cleaned_at IS NOT NULL) OR "
            "(state = 'EXPIRED' AND asset_id IS NULL AND finalized_at IS NULL "
            "AND cleaned_at IS NOT NULL)",
            name="ck_staging_upload_state_fields",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_staging_upload_expiry",
        ),
        sa.CheckConstraint(
            "length(btrim(media_type)) > 0 AND octet_length(media_type) <= 200",
            name="ck_staging_upload_media_type",
        ),
        sa.CheckConstraint(
            "expected_byte_size BETWEEN 1 AND 2147483648",
            name="ck_staging_upload_expected_byte_size",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            name="fk_staging_upload_project_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            name="fk_staging_upload_creator_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            name="fk_staging_upload_access_scope_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["license_policy_id", "organization_id", "access_scope_id"],
            [
                "source.license_policy.id",
                "source.license_policy.organization_id",
                "source.license_policy.access_scope_id",
            ],
            name="fk_staging_upload_license_policy_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id", "organization_id"],
            ["platform.object_asset.id", "platform.object_asset.organization_id"],
            name="fk_staging_upload_asset_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_staging_upload_id_organization",
        ),
        schema="platform",
    )
    op.create_index(
        "ix_staging_upload_scope_state",
        "staging_upload_reservation",
        ["organization_id", "project_id", "state", "expires_at"],
        schema="platform",
    )
    _create_reservation_guard()
    _install_rls_and_grants()
    _replace_scope_discovery(include_expired_reservations=True)


def downgrade() -> None:
    _replace_scope_discovery(include_expired_reservations=False)
    op.execute(
        "DROP TRIGGER IF EXISTS enforce_staging_upload_contract "
        "ON platform.staging_upload_reservation"
    )
    op.execute("DROP FUNCTION IF EXISTS platform.enforce_staging_upload_contract()")
    op.drop_table("staging_upload_reservation", schema="platform")
    op.execute(
        "ALTER TABLE platform.object_asset "
        "DROP CONSTRAINT IF EXISTS uq_object_asset_id_organization"
    )


def _ensure_asset_composite_identity() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_constraint
                WHERE conrelid = 'platform.object_asset'::pg_catalog.regclass
                  AND conname = 'uq_object_asset_id_organization'
            ) THEN
                ALTER TABLE platform.object_asset
                    ADD CONSTRAINT uq_object_asset_id_organization
                    UNIQUE (id, organization_id);
            END IF;
        END;
        $block$;
        """
    )


def _create_reservation_guard() -> None:
    op.execute(
        """
        CREATE FUNCTION platform.enforce_staging_upload_contract()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            stored_scope_kind text;
            stored_project_id uuid;
            stored_policy_scope_id uuid;
            stored_asset record;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF ROW(
                    OLD.id, OLD.organization_id, OLD.project_id, OLD.access_scope,
                    OLD.access_scope_id, OLD.license_policy_id,
                    OLD.created_by_subject_id, OLD.media_type,
                    OLD.expected_byte_size, OLD.created_at, OLD.expires_at
                ) IS DISTINCT FROM ROW(
                    NEW.id, NEW.organization_id, NEW.project_id, NEW.access_scope,
                    NEW.access_scope_id, NEW.license_policy_id,
                    NEW.created_by_subject_id, NEW.media_type,
                    NEW.expected_byte_size, NEW.created_at, NEW.expires_at
                ) THEN
                    RAISE EXCEPTION 'staging upload binding is immutable'
                        USING ERRCODE = '55000';
                END IF;

                IF current_user = 'pcbknowledge_worker' THEN
                    IF NOT (
                        (
                            OLD.state = 'FINALIZED'
                            AND NEW.state = 'CLEANED'
                            AND NEW.asset_id = OLD.asset_id
                            AND NEW.finalized_at = OLD.finalized_at
                            AND NEW.cleaned_at IS NOT NULL
                        ) OR (
                            OLD.state = 'PENDING'
                            AND NEW.state = 'EXPIRED'
                            AND NEW.asset_id IS NULL
                            AND NEW.finalized_at IS NULL
                            AND NEW.cleaned_at IS NOT NULL
                            AND OLD.expires_at <= pg_catalog.clock_timestamp()
                        )
                    ) THEN
                        RAISE EXCEPTION 'worker staging transition is not permitted'
                            USING ERRCODE = '42501';
                    END IF;
                    -- The worker can validate only immutable row state.  The
                    -- insert/finalize paths already proved source/asset FKs;
                    -- do not widen worker grants just to repeat those reads.
                    RETURN NEW;
                ELSIF current_user = 'pcbknowledge_app' AND NOT (
                    OLD.state = 'PENDING'
                    AND NEW.state = 'FINALIZED'
                    AND NEW.asset_id IS NOT NULL
                    AND NEW.finalized_at IS NOT NULL
                    AND NEW.cleaned_at IS NULL
                ) THEN
                    RAISE EXCEPTION 'application staging transition is not permitted'
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT scope_kind, project_id
                  INTO stored_scope_kind, stored_project_id
                  FROM source.access_scope
                 WHERE id = NEW.access_scope_id
                   AND organization_id = NEW.organization_id;
                IF NOT FOUND
                   OR stored_scope_kind <> NEW.access_scope
                   OR stored_project_id IS DISTINCT FROM NEW.project_id
                THEN
                    RAISE EXCEPTION 'staging upload access scope is incoherent'
                        USING ERRCODE = '23514';
                END IF;

                SELECT access_scope_id
                  INTO stored_policy_scope_id
                  FROM source.license_policy
                 WHERE id = NEW.license_policy_id
                   AND organization_id = NEW.organization_id;
                IF NOT FOUND OR stored_policy_scope_id <> NEW.access_scope_id THEN
                    RAISE EXCEPTION 'staging upload license policy is incoherent'
                        USING ERRCODE = '23514';
                END IF;
            END IF;

            IF NEW.asset_id IS NOT NULL THEN
                SELECT project_id, access_scope, access_scope_id, license_policy_id
                  INTO stored_asset
                  FROM platform.object_asset
                 WHERE id = NEW.asset_id
                   AND organization_id = NEW.organization_id;
                IF NOT FOUND
                   OR stored_asset.project_id IS DISTINCT FROM NEW.project_id
                   OR stored_asset.access_scope <> NEW.access_scope
                   OR stored_asset.access_scope_id <> NEW.access_scope_id
                   OR stored_asset.license_policy_id <> NEW.license_policy_id
                THEN
                    RAISE EXCEPTION 'staging upload asset binding is incoherent'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $function$;

        CREATE TRIGGER enforce_staging_upload_contract
        BEFORE INSERT OR UPDATE ON platform.staging_upload_reservation
        FOR EACH ROW EXECUTE FUNCTION platform.enforce_staging_upload_contract();

        REVOKE ALL ON FUNCTION platform.enforce_staging_upload_contract()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        """
    )


def _install_rls_and_grants() -> None:
    op.execute(
        f"""
        ALTER TABLE platform.staging_upload_reservation ENABLE ROW LEVEL SECURITY;
        ALTER TABLE platform.staging_upload_reservation FORCE ROW LEVEL SECURITY;
        CREATE POLICY staging_upload_reservation_tenant_isolation
        ON platform.staging_upload_reservation
        USING ({_TENANT_POLICY})
        WITH CHECK ({_TENANT_POLICY});

        REVOKE ALL ON TABLE platform.staging_upload_reservation FROM PUBLIC;
        GRANT SELECT ON TABLE platform.staging_upload_reservation
            TO pcbknowledge_app;
        GRANT INSERT (
            id, organization_id, project_id, access_scope, access_scope_id,
            license_policy_id, created_by_subject_id, media_type,
            expected_byte_size, state, created_at, expires_at
        ) ON platform.staging_upload_reservation TO pcbknowledge_app;
        GRANT UPDATE (state, asset_id, finalized_at)
            ON platform.staging_upload_reservation TO pcbknowledge_app;

        GRANT SELECT ON TABLE platform.staging_upload_reservation
            TO pcbknowledge_worker;
        GRANT UPDATE (state, cleaned_at)
            ON platform.staging_upload_reservation TO pcbknowledge_worker;
        """
    )


def _replace_scope_discovery(*, include_expired_reservations: bool) -> None:
    reservation_union = (
        """
                UNION ALL
                SELECT
                    upload.organization_id,
                    upload.project_id,
                    upload.access_scope
                FROM platform.staging_upload_reservation AS upload
                WHERE upload.state = 'PENDING'
                  AND upload.expires_at <=
                      pg_catalog.clock_timestamp() - interval '1 minute'
    """
        if include_expired_reservations
        else ""
    )
    op.execute(
        f"""
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
                candidate.organization_id,
                candidate.project_id,
                candidate.access_scope
            FROM (
                SELECT
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
                {reservation_union}
            ) AS candidate
            ORDER BY candidate.organization_id, candidate.project_id NULLS FIRST
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
        GRANT EXECUTE ON FUNCTION
            platform.claimable_storage_cleanup_scopes(integer)
            TO pcbknowledge_worker;
        """
    )
