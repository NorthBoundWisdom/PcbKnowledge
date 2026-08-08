"""Create M1 identity, source policy, RLS, and append-only audit spine.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0002"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID7_CHECK = "substring(id::text, 15, 1) = '7'"


def upgrade() -> None:
    """Install tenant identity, default-deny policies, RLS, and immutable audit."""

    op.execute("CREATE SCHEMA identity")
    op.execute("CREATE SCHEMA source")
    op.execute("CREATE SCHEMA audit")
    _ensure_application_role()
    _create_rls_context_functions()
    _create_identity_tables()
    _create_membership_boundary_trigger()
    _create_source_policy_tables()
    _create_audit_table()
    _create_audit_immutability_trigger()
    _enable_row_level_security()
    _grant_application_privileges()


def downgrade() -> None:
    """Remove M1 security objects in strict reverse dependency order."""

    op.execute("DROP TRIGGER IF EXISTS reject_audit_event_mutation ON audit.audit_event")
    op.execute("DROP FUNCTION IF EXISTS audit.reject_audit_event_mutation()")
    op.execute("DROP TRIGGER IF EXISTS enforce_membership_subject_kind ON identity.membership")
    op.execute("DROP FUNCTION IF EXISTS identity.enforce_membership_subject_kind()")
    op.drop_table("audit_event", schema="audit")
    op.drop_table("license_policy", schema="source")
    op.drop_table("access_scope", schema="source")
    op.drop_table("source_organization", schema="source")
    op.drop_table("membership", schema="identity")
    op.drop_table("external_subject", schema="identity")
    op.drop_table("project", schema="identity")
    op.drop_table("organization", schema="identity")
    op.execute("DROP FUNCTION IF EXISTS identity.current_external_subject_id()")
    op.execute("DROP FUNCTION IF EXISTS identity.can_access_project(uuid)")
    op.execute("DROP FUNCTION IF EXISTS identity.current_organization_id()")
    op.execute("DROP SCHEMA audit")
    op.execute("DROP SCHEMA source")
    op.execute("DROP SCHEMA identity")


def _ensure_application_role() -> None:
    op.execute(
        """
        DO $block$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'pcbknowledge_app')
            THEN
                EXECUTE 'CREATE ROLE pcbknowledge_app NOLOGIN';
            END IF;
            EXECUTE 'ALTER ROLE pcbknowledge_app '
                'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS';

            -- NOINHERIT still permits SET ROLE. Remove both directions so a
            -- drifted runtime role cannot assume an owner/super role and no
            -- unrelated login can assume the application role.
            DECLARE
                membership record;
            BEGIN
                FOR membership IN
                    SELECT granted.rolname AS granted_role
                    FROM pg_catalog.pg_auth_members AS member_map
                    JOIN pg_catalog.pg_roles AS member_role
                      ON member_role.oid = member_map.member
                    JOIN pg_catalog.pg_roles AS granted
                      ON granted.oid = member_map.roleid
                    WHERE member_role.rolname = 'pcbknowledge_app'
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE %I FROM pcbknowledge_app', membership.granted_role
                    );
                END LOOP;
                FOR membership IN
                    SELECT member_role.rolname AS member_role
                    FROM pg_catalog.pg_auth_members AS member_map
                    JOIN pg_catalog.pg_roles AS member_role
                      ON member_role.oid = member_map.member
                    JOIN pg_catalog.pg_roles AS granted
                      ON granted.oid = member_map.roleid
                    WHERE granted.rolname = 'pcbknowledge_app'
                LOOP
                    EXECUTE pg_catalog.format(
                        'REVOKE pcbknowledge_app FROM %I', membership.member_role
                    );
                END LOOP;
            END;
        END;
        $block$;
        """
    )


def _create_rls_context_functions() -> None:
    op.execute(
        r"""
        CREATE FUNCTION identity.current_organization_id()
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            raw_value text;
        BEGIN
            raw_value := pg_catalog.current_setting('pcbknowledge.organization_id', true);
            IF raw_value IS NULL OR raw_value = '' OR raw_value !~
                '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            THEN
                RETURN NULL;
            END IF;
            RETURN raw_value::uuid;
        EXCEPTION
            WHEN invalid_text_representation THEN
                RETURN NULL;
        END;
        $function$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION identity.can_access_project(requested_project_id uuid)
        RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            raw_value text;
            project_value text;
            matched boolean := false;
        BEGIN
            IF requested_project_id IS NULL THEN
                RETURN false;
            END IF;
            raw_value := pg_catalog.current_setting('pcbknowledge.project_ids', true);
            IF raw_value IS NULL OR raw_value = '' THEN
                RETURN false;
            END IF;
            FOREACH project_value IN ARRAY pg_catalog.string_to_array(raw_value, ',')
            LOOP
                IF project_value !~
                    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                THEN
                    RETURN false;
                END IF;
                IF project_value::uuid = requested_project_id THEN
                    matched := true;
                END IF;
            END LOOP;
            RETURN matched;
        EXCEPTION
            WHEN invalid_text_representation THEN
                RETURN false;
        END;
        $function$
        """
    )
    op.execute(
        r"""
        CREATE FUNCTION identity.current_external_subject_id()
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        PARALLEL SAFE
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            raw_value text;
        BEGIN
            raw_value := pg_catalog.current_setting(
                'pcbknowledge.external_subject_id', true
            );
            IF raw_value IS NULL OR raw_value = '' OR raw_value !~
                '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            THEN
                RETURN NULL;
            END IF;
            RETURN raw_value::uuid;
        EXCEPTION
            WHEN invalid_text_representation THEN
                RETURN NULL;
        END;
        $function$
        """
    )


def _create_identity_tables() -> None:
    op.create_table(
        "organization",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(_UUID7_CHECK, name="ck_organization_id_uuid7"),
        sa.PrimaryKeyConstraint("id", name="pk_organization"),
        sa.UniqueConstraint("slug", name="uq_organization_slug"),
        schema="identity",
    )
    op.create_table(
        "project",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(_UUID7_CHECK, name="ck_project_id_uuid7"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            name="fk_project_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project"),
        sa.UniqueConstraint("id", "organization_id", name="uq_project_id_organization"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_project_organization_slug"),
        schema="identity",
    )
    op.create_table(
        "external_subject",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer", sa.String(length=2048), nullable=False),
        sa.Column("external_subject", sa.String(length=512), nullable=False),
        sa.Column(
            "subject_kind",
            sa.Enum(
                "HUMAN",
                "SERVICE_ACCOUNT",
                name="ck_external_subject_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint(_UUID7_CHECK, name="ck_external_subject_id_uuid7"),
        sa.CheckConstraint(
            "(subject_kind = 'HUMAN' AND client_id IS NULL) OR "
            "(subject_kind = 'SERVICE_ACCOUNT' AND client_id IS NOT NULL "
            "AND length(btrim(client_id)) > 0)",
            name="ck_external_subject_service_client",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            name="fk_external_subject_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_external_subject"),
        sa.UniqueConstraint("id", "organization_id", name="uq_external_subject_id_organization"),
        sa.UniqueConstraint(
            "issuer", "external_subject", name="uq_external_subject_issuer_subject"
        ),
        schema="identity",
    )
    op.create_table(
        "membership",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "DATA_CURATOR",
                "DOMAIN_REVIEWER",
                "KNOWLEDGE_ADMIN",
                "AUDITOR",
                "AGENT_SERVICE",
                name="ck_membership_role",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(_UUID7_CHECK, name="ck_membership_id_uuid7"),
        sa.ForeignKeyConstraint(
            ["external_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            name="fk_membership_subject_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            name="fk_membership_project_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_membership"),
        sa.UniqueConstraint(
            "external_subject_id",
            "organization_id",
            "project_id",
            "role",
            name="uq_membership_subject_scope_role",
            postgresql_nulls_not_distinct=True,
        ),
        schema="identity",
    )


def _create_membership_boundary_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION identity.enforce_membership_subject_kind()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            mapped_kind text;
        BEGIN
            SELECT subject_kind
              INTO mapped_kind
              FROM identity.external_subject
             WHERE id = NEW.external_subject_id
               AND organization_id = NEW.organization_id;
            IF mapped_kind IS NULL THEN
                RAISE EXCEPTION 'membership subject mapping is unavailable'
                    USING ERRCODE = '23514';
            END IF;
            IF (mapped_kind = 'SERVICE_ACCOUNT' AND NEW.role <> 'AGENT_SERVICE')
               OR (mapped_kind = 'HUMAN' AND NEW.role = 'AGENT_SERVICE')
            THEN
                RAISE EXCEPTION 'membership role is incompatible with subject kind'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;

        CREATE TRIGGER enforce_membership_subject_kind
        BEFORE INSERT OR UPDATE ON identity.membership
        FOR EACH ROW EXECUTE FUNCTION identity.enforce_membership_subject_kind();
        """
    )


def _create_source_policy_tables() -> None:
    op.create_table(
        "source_organization",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("authority_tier", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(_UUID7_CHECK, name="ck_source_organization_id_uuid7"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            name="fk_source_organization_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_organization"),
        sa.UniqueConstraint("id", "organization_id", name="uq_source_organization_id_organization"),
        sa.UniqueConstraint("organization_id", "name", name="uq_source_organization_name"),
        schema="source",
    )
    op.create_table(
        "access_scope",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "scope_kind",
            sa.Enum(
                "ORGANIZATION",
                "PROJECT",
                name="ck_access_scope_kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(_UUID7_CHECK, name="ck_access_scope_id_uuid7"),
        sa.CheckConstraint(
            "(scope_kind = 'ORGANIZATION' AND project_id IS NULL) OR "
            "(scope_kind = 'PROJECT' AND project_id IS NOT NULL)",
            name="ck_access_scope_kind_project",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            name="fk_access_scope_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            name="fk_access_scope_project_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_access_scope"),
        sa.UniqueConstraint("id", "organization_id", name="uq_access_scope_id_organization"),
        sa.UniqueConstraint("organization_id", "name", name="uq_access_scope_organization_name"),
        schema="source",
    )
    op.create_table(
        "license_policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "license_class",
            sa.Enum(
                "OPEN_LICENSE",
                "PUBLIC_REFERENCE",
                "LICENSED",
                "LICENSED_BLOCKED_FOR_AI",
                "INTERNAL",
                "PROJECT_CONFIDENTIAL",
                name="ck_license_policy_class",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("allow_metadata_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_human_raw_access", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_parse", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_external_model", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_local_model", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_embedding", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_agent_raw_access", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allow_redistribution", sa.Boolean(), server_default="false", nullable=False),
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
        sa.CheckConstraint(_UUID7_CHECK, name="ck_license_policy_id_uuid7"),
        sa.CheckConstraint(
            "license_class <> 'LICENSED_BLOCKED_FOR_AI' OR "
            "(NOT allow_parse AND NOT allow_external_model AND NOT allow_local_model "
            "AND NOT allow_embedding AND NOT allow_agent_raw_access)",
            name="ck_license_policy_blocked_ai_deny",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            name="fk_license_policy_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["access_scope_id", "organization_id"],
            ["source.access_scope.id", "source.access_scope.organization_id"],
            name="fk_license_policy_scope_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_license_policy"),
        sa.UniqueConstraint("id", "organization_id", name="uq_license_policy_id_organization"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "access_scope_id",
            name="uq_license_policy_id_organization_scope",
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_license_policy_organization_name"),
        schema="source",
    )


def _create_audit_table() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("actor_subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "actor_kind",
            sa.Enum(
                "HUMAN",
                "SERVICE_ACCOUNT",
                name="ck_audit_event_actor_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "SUCCEEDED",
                "DENIED",
                "FAILED",
                name="ck_audit_event_outcome",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(_UUID7_CHECK, name="ck_audit_event_id_uuid7"),
        sa.CheckConstraint(
            "resource_id IS NULL OR substring(resource_id::text, 15, 1) = '7'",
            name="ck_audit_event_resource_id_uuid7",
        ),
        sa.CheckConstraint(
            "(actor_subject_id IS NULL AND actor_kind IS NULL) OR "
            "(actor_subject_id IS NOT NULL AND actor_kind IS NOT NULL)",
            name="ck_audit_event_actor_pair",
        ),
        sa.CheckConstraint("jsonb_typeof(detail) = 'object'", name="ck_audit_event_detail_object"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["identity.organization.id"],
            name="fk_audit_event_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "organization_id"],
            ["identity.project.id", "identity.project.organization_id"],
            name="fk_audit_event_project_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_subject_id", "organization_id"],
            ["identity.external_subject.id", "identity.external_subject.organization_id"],
            name="fk_audit_event_actor_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_event"),
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_time",
        "audit_event",
        ["organization_id", "project_id", sa.text("occurred_at DESC")],
        schema="audit",
    )


def _create_audit_immutability_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION audit.reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            RAISE EXCEPTION 'audit_event is append-only'
                USING ERRCODE = '55000';
        END;
        $function$;

        CREATE TRIGGER reject_audit_event_mutation
        BEFORE UPDATE OR DELETE ON audit.audit_event
        FOR EACH ROW EXECUTE FUNCTION audit.reject_audit_event_mutation();
        """
    )


def _enable_row_level_security() -> None:
    for qualified_table in (
        "identity.organization",
        "identity.project",
        "identity.external_subject",
        "identity.membership",
        "source.source_organization",
        "source.access_scope",
        "source.license_policy",
        "audit.audit_event",
    ):
        op.execute(f"ALTER TABLE {qualified_table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {qualified_table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY organization_tenant_policy ON identity.organization
        FOR ALL
        USING (id = identity.current_organization_id())
        WITH CHECK (id = identity.current_organization_id());

        CREATE POLICY project_select_policy ON identity.project
        FOR SELECT
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(id)
        );
        CREATE POLICY project_insert_policy ON identity.project
        FOR INSERT
        WITH CHECK (organization_id = identity.current_organization_id());
        CREATE POLICY project_update_policy ON identity.project
        FOR UPDATE
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(id)
        )
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(id)
        );
        CREATE POLICY project_delete_policy ON identity.project
        FOR DELETE
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(id)
        );

        CREATE POLICY external_subject_select_policy ON identity.external_subject
        FOR SELECT
        USING (
            organization_id = identity.current_organization_id()
            OR (
                issuer = nullif(
                    pg_catalog.current_setting('pcbknowledge.external_issuer', true), ''
                )
                AND external_subject = nullif(
                    pg_catalog.current_setting('pcbknowledge.external_subject', true), ''
                )
            )
        );
        CREATE POLICY external_subject_insert_policy ON identity.external_subject
        FOR INSERT
        WITH CHECK (organization_id = identity.current_organization_id());
        CREATE POLICY external_subject_update_policy ON identity.external_subject
        FOR UPDATE
        USING (organization_id = identity.current_organization_id())
        WITH CHECK (organization_id = identity.current_organization_id());
        CREATE POLICY external_subject_delete_policy ON identity.external_subject
        FOR DELETE
        USING (organization_id = identity.current_organization_id());

        CREATE POLICY membership_select_tenant_scope_policy ON identity.membership
        FOR SELECT
        USING (
            organization_id = identity.current_organization_id()
            AND (
                external_subject_id = identity.current_external_subject_id()
                OR project_id IS NULL
                OR identity.can_access_project(project_id)
            )
        );
        CREATE POLICY membership_insert_policy ON identity.membership
        FOR INSERT
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        );
        CREATE POLICY membership_update_policy ON identity.membership
        FOR UPDATE
        USING (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        )
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        );
        CREATE POLICY membership_delete_policy ON identity.membership
        FOR DELETE
        USING (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        );

        CREATE POLICY source_organization_tenant_policy ON source.source_organization
        FOR ALL
        USING (organization_id = identity.current_organization_id())
        WITH CHECK (organization_id = identity.current_organization_id());

        CREATE POLICY access_scope_tenant_policy ON source.access_scope
        FOR ALL
        USING (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        )
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        );

        CREATE POLICY license_policy_tenant_policy ON source.license_policy
        FOR ALL
        USING (
            organization_id = identity.current_organization_id()
            AND EXISTS (
                SELECT 1
                FROM source.access_scope AS scope
                WHERE scope.id = access_scope_id
                  AND scope.organization_id = license_policy.organization_id
            )
        )
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND EXISTS (
                SELECT 1
                FROM source.access_scope AS scope
                WHERE scope.id = access_scope_id
                  AND scope.organization_id = license_policy.organization_id
            )
        );

        CREATE POLICY audit_event_select_policy ON audit.audit_event
        FOR SELECT
        USING (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        );
        CREATE POLICY audit_event_insert_policy ON audit.audit_event
        FOR INSERT
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND (project_id IS NULL OR identity.can_access_project(project_id))
        );
        """
    )


def _grant_application_privileges() -> None:
    op.execute(
        """
        REVOKE ALL ON SCHEMA identity, source, audit FROM PUBLIC;
        REVOKE ALL ON ALL TABLES IN SCHEMA identity, source, audit FROM PUBLIC;

        GRANT USAGE ON SCHEMA identity, source, audit TO pcbknowledge_app;
        GRANT SELECT ON ALL TABLES IN SCHEMA identity, source TO pcbknowledge_app;
        GRANT SELECT, INSERT ON TABLE audit.audit_event TO pcbknowledge_app;

        REVOKE ALL ON FUNCTION identity.current_organization_id() FROM PUBLIC;
        REVOKE ALL ON FUNCTION identity.can_access_project(uuid) FROM PUBLIC;
        REVOKE ALL ON FUNCTION identity.current_external_subject_id() FROM PUBLIC;
        REVOKE ALL ON FUNCTION identity.enforce_membership_subject_kind() FROM PUBLIC;
        REVOKE ALL ON FUNCTION audit.reject_audit_event_mutation() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION identity.current_organization_id()
            TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid)
            TO pcbknowledge_app;
        GRANT EXECUTE ON FUNCTION identity.current_external_subject_id()
            TO pcbknowledge_app;
        """
    )
