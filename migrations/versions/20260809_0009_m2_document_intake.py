"""Add isolated document intake, immutable stored revisions, and verifier role.

Revision ID: 20260809_0009
Revises: 20260808_0008
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_0009"
down_revision: str | None = "20260808_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install the fail-closed M2 intake boundary."""

    _harden_verifier_role()
    op.execute("CREATE SCHEMA document")
    _create_tables()
    _extend_staging_lifecycle()
    _create_integrity_triggers()
    _create_immutable_triggers()
    _create_rls_policies()
    _create_verifier_discovery()
    _install_restrictive_verifier_queue_policies()
    _normalize_runtime_grants()


def downgrade() -> None:
    """Remove document metadata while leaving permanent S3 bytes untouched."""

    _revoke_runtime_grants()
    op.execute(
        """
        DROP POLICY IF EXISTS knowledge_job_verifier_only
            ON platform.knowledge_job;
        DROP POLICY IF EXISTS job_effect_receipt_verifier_only
            ON platform.job_effect_receipt;
        DROP POLICY IF EXISTS staging_upload_verifier_only
            ON platform.staging_upload_reservation;
        DROP POLICY IF EXISTS object_asset_verifier_only
            ON platform.object_asset;
        DROP POLICY IF EXISTS outbox_verifier_cleanup_only
            ON platform.outbox_event;
        DROP FUNCTION IF EXISTS platform.claimable_document_intake_scopes(integer);
        DROP SCHEMA document CASCADE;
        UPDATE platform.staging_upload_reservation
           SET state = 'PENDING'
         WHERE state = 'SUBMITTED';
        ALTER TABLE platform.staging_upload_reservation
            DROP CONSTRAINT ck_staging_upload_state,
            DROP CONSTRAINT ck_staging_upload_state_fields;
        ALTER TABLE platform.staging_upload_reservation
            ADD CONSTRAINT ck_staging_upload_state
                CHECK (state IN ('PENDING', 'FINALIZED', 'CLEANED', 'EXPIRED')),
            ADD CONSTRAINT ck_staging_upload_state_fields CHECK (
                (state = 'PENDING' AND asset_id IS NULL
                 AND finalized_at IS NULL AND cleaned_at IS NULL) OR
                (state = 'FINALIZED' AND asset_id IS NOT NULL
                 AND finalized_at IS NOT NULL AND cleaned_at IS NULL) OR
                (state = 'CLEANED' AND asset_id IS NOT NULL
                 AND finalized_at IS NOT NULL AND cleaned_at IS NOT NULL) OR
                (state = 'EXPIRED' AND asset_id IS NULL
                 AND finalized_at IS NULL AND cleaned_at IS NOT NULL)
            );
        ALTER ROLE pcbknowledge_verifier NOLOGIN;
        """
    )


def _harden_verifier_role() -> None:
    op.execute(
        """
        DO $block$
        DECLARE
            membership record;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles
                WHERE rolname = 'pcbknowledge_verifier'
            ) THEN
                CREATE ROLE pcbknowledge_verifier NOLOGIN;
            END IF;
            ALTER ROLE pcbknowledge_verifier
                NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
                NOREPLICATION NOBYPASSRLS;
            ALTER ROLE pcbknowledge_verifier SET row_security = on;

            FOR membership IN
                SELECT granted.rolname AS granted_role
                FROM pg_catalog.pg_auth_members AS member_map
                JOIN pg_catalog.pg_roles AS member_role
                  ON member_role.oid = member_map.member
                JOIN pg_catalog.pg_roles AS granted
                  ON granted.oid = member_map.roleid
                WHERE member_role.rolname = 'pcbknowledge_verifier'
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE %I FROM pcbknowledge_verifier',
                    membership.granted_role
                );
            END LOOP;
            FOR membership IN
                SELECT member_role.rolname AS member_role
                FROM pg_catalog.pg_auth_members AS member_map
                JOIN pg_catalog.pg_roles AS member_role
                  ON member_role.oid = member_map.member
                JOIN pg_catalog.pg_roles AS granted
                  ON granted.oid = member_map.roleid
                WHERE granted.rolname = 'pcbknowledge_verifier'
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE pcbknowledge_verifier FROM %I',
                    membership.member_role
                );
            END LOOP;
        END;
        $block$;
        """
    )


def _create_tables() -> None:
    op.execute(
        r"""
        CREATE TABLE document.document (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            title varchar(500) NOT NULL,
            document_number varchar(255),
            created_by_subject_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            CONSTRAINT ck_document_id_uuid7
                CHECK (substring(id::text, 15, 1) = '7'),
            CONSTRAINT ck_document_title
                CHECK (length(btrim(title)) BETWEEN 1 AND 500),
            CONSTRAINT ck_document_number
                CHECK (
                    document_number IS NULL OR
                    length(btrim(document_number)) BETWEEN 1 AND 255
                ),
            CONSTRAINT uq_document_id_scope
                UNIQUE (id, organization_id, project_id),
            CONSTRAINT fk_document_project_organization
                FOREIGN KEY (project_id, organization_id)
                REFERENCES identity.project (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_document_creator_organization
                FOREIGN KEY (created_by_subject_id, organization_id)
                REFERENCES identity.external_subject (id, organization_id)
                ON DELETE RESTRICT
        );
        CREATE INDEX ix_document_scope_id
            ON document.document (organization_id, project_id, id);

        CREATE TABLE document.document_revision (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            document_id uuid NOT NULL,
            source_organization_id uuid NOT NULL,
            access_scope varchar(32) NOT NULL,
            access_scope_id uuid NOT NULL,
            license_policy_id uuid NOT NULL,
            revision_label varchar(128) NOT NULL,
            original_filename varchar(255) NOT NULL,
            media_type varchar(200) NOT NULL,
            state varchar(32) NOT NULL,
            created_by_subject_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            CONSTRAINT ck_document_revision_id_uuid7
                CHECK (substring(id::text, 15, 1) = '7'),
            CONSTRAINT ck_document_revision_project_scope
                CHECK (access_scope = 'PROJECT'),
            CONSTRAINT ck_document_revision_state CHECK (state = 'STORED'),
            CONSTRAINT ck_document_revision_label
                CHECK (length(btrim(revision_label)) BETWEEN 1 AND 128),
            CONSTRAINT ck_document_revision_original_filename
                CHECK (
                    length(btrim(original_filename)) BETWEEN 1 AND 255
                    AND original_filename !~ '[\r\n]'
                ),
            CONSTRAINT ck_document_revision_pdf_only
                CHECK (media_type = 'application/pdf'),
            CONSTRAINT uq_document_revision_id_organization
                UNIQUE (id, organization_id),
            CONSTRAINT uq_document_revision_id_scope
                UNIQUE (id, organization_id, project_id),
            CONSTRAINT uq_document_revision_document_label
                UNIQUE (document_id, revision_label),
            CONSTRAINT fk_document_revision_document_scope
                FOREIGN KEY (document_id, organization_id, project_id)
                REFERENCES document.document (id, organization_id, project_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_document_revision_source_organization
                FOREIGN KEY (source_organization_id, organization_id)
                REFERENCES source.source_organization (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_document_revision_access_scope
                FOREIGN KEY (access_scope_id, organization_id)
                REFERENCES source.access_scope (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_document_revision_license_policy
                FOREIGN KEY (license_policy_id, organization_id, access_scope_id)
                REFERENCES source.license_policy
                    (id, organization_id, access_scope_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_document_revision_creator_organization
                FOREIGN KEY (created_by_subject_id, organization_id)
                REFERENCES identity.external_subject (id, organization_id)
                ON DELETE RESTRICT
        );
        CREATE INDEX ix_document_revision_document
            ON document.document_revision (document_id, id);

        CREATE TABLE document.document_asset (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            revision_id uuid NOT NULL,
            object_asset_id uuid NOT NULL,
            asset_kind varchar(64) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            CONSTRAINT ck_document_asset_id_uuid7
                CHECK (substring(id::text, 15, 1) = '7'),
            CONSTRAINT ck_document_asset_kind CHECK (asset_kind = 'ORIGINAL'),
            CONSTRAINT uq_document_asset_revision_kind
                UNIQUE (revision_id, asset_kind),
            CONSTRAINT uq_document_asset_id_organization
                UNIQUE (id, organization_id),
            CONSTRAINT fk_document_asset_revision_scope
                FOREIGN KEY (revision_id, organization_id, project_id)
                REFERENCES document.document_revision
                    (id, organization_id, project_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_document_asset_object_organization
                FOREIGN KEY (object_asset_id, organization_id)
                REFERENCES platform.object_asset (id, organization_id)
                ON DELETE RESTRICT
        );

        CREATE TABLE document.upload_session (
            id uuid PRIMARY KEY,
            organization_id uuid NOT NULL,
            project_id uuid NOT NULL,
            access_scope varchar(32) NOT NULL,
            access_scope_id uuid NOT NULL,
            license_policy_id uuid NOT NULL,
            source_organization_id uuid NOT NULL,
            target_document_id uuid NOT NULL,
            target_revision_id uuid NOT NULL,
            creates_document boolean NOT NULL,
            title varchar(500) NOT NULL,
            document_number varchar(255),
            revision_label varchar(128) NOT NULL,
            original_filename varchar(255) NOT NULL,
            media_type varchar(200) NOT NULL,
            expected_byte_size bigint NOT NULL,
            idempotency_key varchar(200) NOT NULL,
            request_sha256 varchar(64) NOT NULL,
            state varchar(32) NOT NULL,
            expected_sha256 varchar(64) DEFAULT NULL,
            actual_sha256 varchar(64) DEFAULT NULL,
            completion_job_id uuid DEFAULT NULL,
            object_asset_id uuid DEFAULT NULL,
            failure_code varchar(128) DEFAULT NULL,
            created_by_subject_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
            completed_at timestamptz DEFAULT NULL,
            CONSTRAINT ck_upload_session_id_uuid7
                CHECK (substring(id::text, 15, 1) = '7'),
            CONSTRAINT ck_upload_session_document_id_uuid7
                CHECK (substring(target_document_id::text, 15, 1) = '7'),
            CONSTRAINT ck_upload_session_revision_id_uuid7
                CHECK (substring(target_revision_id::text, 15, 1) = '7'),
            CONSTRAINT ck_upload_session_project_scope
                CHECK (access_scope = 'PROJECT'),
            CONSTRAINT ck_upload_session_state
                CHECK (state IN ('RESERVED', 'QUEUED', 'STORED', 'FAILED')),
            CONSTRAINT ck_upload_session_byte_size
                CHECK (expected_byte_size BETWEEN 1 AND 268435456),
            CONSTRAINT ck_upload_session_pdf_only
                CHECK (media_type = 'application/pdf'),
            CONSTRAINT ck_upload_session_expected_sha256
                CHECK (
                    expected_sha256 IS NULL OR
                    expected_sha256 ~ '^[0-9a-f]{64}$'
                ),
            CONSTRAINT ck_upload_session_actual_sha256
                CHECK (
                    actual_sha256 IS NULL OR
                    actual_sha256 ~ '^[0-9a-f]{64}$'
                ),
            CONSTRAINT ck_upload_session_request_sha256
                CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_upload_session_idempotency_key
                CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 200),
            CONSTRAINT ck_upload_session_title
                CHECK (length(btrim(title)) BETWEEN 1 AND 500),
            CONSTRAINT ck_upload_session_document_number
                CHECK (
                    document_number IS NULL OR
                    length(btrim(document_number)) BETWEEN 1 AND 255
                ),
            CONSTRAINT ck_upload_session_revision_label
                CHECK (length(btrim(revision_label)) BETWEEN 1 AND 128),
            CONSTRAINT ck_upload_session_original_filename
                CHECK (
                    length(btrim(original_filename)) BETWEEN 1 AND 255
                    AND original_filename !~ '[\r\n]'
                ),
            CONSTRAINT ck_upload_session_state_fields CHECK (
                (
                    state = 'RESERVED' AND completion_job_id IS NULL
                    AND expected_sha256 IS NULL
                    AND actual_sha256 IS NULL AND object_asset_id IS NULL
                    AND completed_at IS NULL AND failure_code IS NULL
                ) OR (
                    state = 'QUEUED' AND completion_job_id IS NOT NULL
                    AND actual_sha256 IS NULL AND object_asset_id IS NULL
                    AND completed_at IS NULL AND failure_code IS NULL
                ) OR (
                    state = 'STORED' AND completion_job_id IS NOT NULL
                    AND actual_sha256 IS NOT NULL AND object_asset_id IS NOT NULL
                    AND completed_at IS NOT NULL AND failure_code IS NULL
                ) OR (
                    state = 'FAILED' AND completion_job_id IS NOT NULL
                    AND object_asset_id IS NULL AND completed_at IS NOT NULL
                    AND failure_code IS NOT NULL
                )
            ),
            CONSTRAINT ck_upload_session_failure_code
                CHECK (
                    failure_code IS NULL OR
                    failure_code ~ '^[A-Z0-9][A-Z0-9_.-]{0,127}$'
                ),
            CONSTRAINT uq_upload_session_id_organization
                UNIQUE (id, organization_id),
            CONSTRAINT uq_upload_session_actor_idempotency
                UNIQUE (organization_id, created_by_subject_id, idempotency_key),
            CONSTRAINT fk_upload_session_staging_reservation
                FOREIGN KEY (id, organization_id)
                REFERENCES platform.staging_upload_reservation
                    (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_project_organization
                FOREIGN KEY (project_id, organization_id)
                REFERENCES identity.project (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_access_scope_organization
                FOREIGN KEY (access_scope_id, organization_id)
                REFERENCES source.access_scope (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_license_policy_scope
                FOREIGN KEY (license_policy_id, organization_id, access_scope_id)
                REFERENCES source.license_policy
                    (id, organization_id, access_scope_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_source_organization
                FOREIGN KEY (source_organization_id, organization_id)
                REFERENCES source.source_organization (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_creator_organization
                FOREIGN KEY (created_by_subject_id, organization_id)
                REFERENCES identity.external_subject (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_completion_job
                FOREIGN KEY (completion_job_id, organization_id)
                REFERENCES platform.knowledge_job (id, organization_id)
                ON DELETE RESTRICT,
            CONSTRAINT fk_upload_session_object_asset
                FOREIGN KEY (object_asset_id, organization_id)
                REFERENCES platform.object_asset (id, organization_id)
                ON DELETE RESTRICT
        );
        CREATE INDEX ix_upload_session_scope_state
            ON document.upload_session (organization_id, project_id, state);
        CREATE UNIQUE INDEX uq_upload_session_active_document_revision
            ON document.upload_session (target_document_id, revision_label)
            WHERE state <> 'FAILED';
        """
    )


def _extend_staging_lifecycle() -> None:
    """Make submission durable so cleanup cannot race accepted intake work."""

    op.execute(
        r"""
        ALTER TABLE platform.staging_upload_reservation
            DROP CONSTRAINT ck_staging_upload_state,
            DROP CONSTRAINT ck_staging_upload_state_fields;
        ALTER TABLE platform.staging_upload_reservation
            ADD CONSTRAINT ck_staging_upload_state CHECK (
                state IN (
                    'PENDING', 'SUBMITTED', 'FINALIZED', 'CLEANED', 'EXPIRED'
                )
            ),
            ADD CONSTRAINT ck_staging_upload_state_fields CHECK (
                (state = 'PENDING' AND asset_id IS NULL
                 AND finalized_at IS NULL AND cleaned_at IS NULL) OR
                (state = 'SUBMITTED' AND asset_id IS NULL
                 AND finalized_at IS NULL AND cleaned_at IS NULL) OR
                (state = 'FINALIZED' AND asset_id IS NOT NULL
                 AND finalized_at IS NOT NULL AND cleaned_at IS NULL) OR
                (state = 'CLEANED' AND asset_id IS NOT NULL
                 AND finalized_at IS NOT NULL AND cleaned_at IS NOT NULL) OR
                (state = 'EXPIRED' AND asset_id IS NULL
                 AND finalized_at IS NULL AND cleaned_at IS NOT NULL)
            );

        CREATE OR REPLACE FUNCTION platform.enforce_staging_upload_contract()
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
                    OLD.id, OLD.organization_id, OLD.project_id,
                    OLD.access_scope, OLD.access_scope_id,
                    OLD.license_policy_id, OLD.created_by_subject_id,
                    OLD.media_type, OLD.expected_byte_size,
                    OLD.created_at, OLD.expires_at
                ) IS DISTINCT FROM ROW(
                    NEW.id, NEW.organization_id, NEW.project_id,
                    NEW.access_scope, NEW.access_scope_id,
                    NEW.license_policy_id, NEW.created_by_subject_id,
                    NEW.media_type, NEW.expected_byte_size,
                    NEW.created_at, NEW.expires_at
                ) THEN
                    RAISE EXCEPTION 'staging upload binding is immutable'
                        USING ERRCODE = '55000';
                END IF;

                IF CURRENT_USER = 'pcbknowledge_worker' THEN
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
                    RETURN NEW;
                ELSIF CURRENT_USER = 'pcbknowledge_app' THEN
                    IF NOT (
                        (
                            OLD.state = 'PENDING'
                            AND NEW.state = 'FINALIZED'
                            AND NEW.asset_id IS NOT NULL
                            AND NEW.finalized_at IS NOT NULL
                            AND NEW.cleaned_at IS NULL
                        ) OR (
                            OLD.state = 'PENDING'
                            AND NEW.state = 'SUBMITTED'
                            AND NEW.asset_id IS NULL
                            AND NEW.finalized_at IS NULL
                            AND NEW.cleaned_at IS NULL
                            AND EXISTS (
                                SELECT 1
                                FROM document.upload_session AS upload
                                WHERE upload.id = NEW.id
                                  AND upload.organization_id =
                                      NEW.organization_id
                                  AND upload.project_id = NEW.project_id
                                  AND upload.access_scope = NEW.access_scope
                                  AND upload.access_scope_id =
                                      NEW.access_scope_id
                                  AND upload.license_policy_id =
                                      NEW.license_policy_id
                                  AND upload.created_by_subject_id =
                                      NEW.created_by_subject_id
                                  AND upload.media_type = NEW.media_type
                                  AND upload.expected_byte_size =
                                      NEW.expected_byte_size
                                  AND upload.state = 'RESERVED'
                            )
                        )
                    ) THEN
                        RAISE EXCEPTION 'application staging transition is not permitted'
                            USING ERRCODE = '42501';
                    END IF;
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
                SELECT project_id, access_scope, access_scope_id,
                       license_policy_id
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
        REVOKE ALL ON FUNCTION platform.enforce_staging_upload_contract()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        """
    )


def _create_integrity_triggers() -> None:
    op.execute(
        r"""
        CREATE FUNCTION document.enforce_verifier_staging_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF CURRENT_USER = 'pcbknowledge_verifier' THEN
                IF ROW(
                    OLD.id, OLD.organization_id, OLD.project_id,
                    OLD.access_scope, OLD.access_scope_id,
                    OLD.license_policy_id, OLD.created_by_subject_id,
                    OLD.media_type, OLD.expected_byte_size,
                    OLD.created_at, OLD.expires_at, OLD.cleaned_at
                ) IS DISTINCT FROM ROW(
                    NEW.id, NEW.organization_id, NEW.project_id,
                    NEW.access_scope, NEW.access_scope_id,
                    NEW.license_policy_id, NEW.created_by_subject_id,
                    NEW.media_type, NEW.expected_byte_size,
                    NEW.created_at, NEW.expires_at, NEW.cleaned_at
                ) THEN
                    RAISE EXCEPTION 'verifier staging binding is immutable'
                        USING ERRCODE = '23514';
                END IF;
                IF NOT (
                    (
                        OLD.state = 'SUBMITTED'
                        AND NEW.state = 'FINALIZED'
                        AND OLD.asset_id IS NULL
                        AND OLD.finalized_at IS NULL
                        AND NEW.asset_id IS NOT NULL
                        AND NEW.finalized_at IS NOT NULL
                    ) OR (
                        OLD.state = 'SUBMITTED'
                        AND NEW.state = 'PENDING'
                        AND OLD.asset_id IS NULL
                        AND OLD.finalized_at IS NULL
                        AND NEW.asset_id IS NULL
                        AND NEW.finalized_at IS NULL
                    )
                ) THEN
                    RAISE EXCEPTION 'verifier staging transition is invalid'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_verifier_staging_transition
        BEFORE UPDATE ON platform.staging_upload_reservation
        FOR EACH ROW EXECUTE FUNCTION
            document.enforce_verifier_staging_transition();

        CREATE FUNCTION document.enforce_upload_reservation_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            upload_state text;
            reservation_state text;
            required_id uuid;
            required_organization_id uuid;
        BEGIN
            required_id := NEW.id;
            required_organization_id := NEW.organization_id;
            SELECT upload.state, reservation.state
              INTO upload_state, reservation_state
              FROM document.upload_session AS upload
              JOIN platform.staging_upload_reservation AS reservation
                ON reservation.id = upload.id
               AND reservation.organization_id = upload.organization_id
             WHERE upload.id = required_id
               AND upload.organization_id = required_organization_id;
            IF NOT FOUND THEN
                RETURN NULL;
            END IF;
            IF NOT (
                (upload_state = 'RESERVED'
                 AND reservation_state IN ('PENDING', 'EXPIRED')) OR
                (upload_state = 'QUEUED'
                 AND reservation_state = 'SUBMITTED') OR
                (upload_state = 'STORED'
                 AND reservation_state IN ('FINALIZED', 'CLEANED')) OR
                (upload_state = 'FAILED'
                 AND reservation_state IN ('PENDING', 'EXPIRED'))
            ) THEN
                RAISE EXCEPTION 'upload and staging lifecycle are inconsistent'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $function$;
        CREATE CONSTRAINT TRIGGER require_upload_reservation_lifecycle
        AFTER INSERT OR UPDATE ON document.upload_session
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION
            document.enforce_upload_reservation_lifecycle();
        CREATE CONSTRAINT TRIGGER require_document_upload_lifecycle
        AFTER INSERT OR UPDATE ON platform.staging_upload_reservation
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION
            document.enforce_upload_reservation_lifecycle();

        CREATE FUNCTION document.enforce_upload_session_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            staging record;
            scope record;
            job record;
            object record;
        BEGIN
            SELECT reservation.organization_id, reservation.project_id,
                   reservation.access_scope, reservation.access_scope_id,
                   reservation.license_policy_id,
                   reservation.created_by_subject_id,
                   reservation.media_type, reservation.expected_byte_size,
                   reservation.state
              INTO staging
              FROM platform.staging_upload_reservation AS reservation
             WHERE reservation.id = NEW.id
               AND reservation.organization_id = NEW.organization_id;
            IF NOT FOUND OR ROW(
                staging.project_id, staging.access_scope,
                staging.access_scope_id, staging.license_policy_id,
                staging.created_by_subject_id, staging.media_type,
                staging.expected_byte_size
            ) IS DISTINCT FROM ROW(
                NEW.project_id, NEW.access_scope,
                NEW.access_scope_id, NEW.license_policy_id,
                NEW.created_by_subject_id, NEW.media_type,
                NEW.expected_byte_size
            ) THEN
                RAISE EXCEPTION 'upload session does not match its reservation'
                    USING ERRCODE = '23514';
            END IF;
            IF (NEW.state = 'RESERVED' AND staging.state <> 'PENDING')
               OR (NEW.state = 'QUEUED' AND staging.state <> 'SUBMITTED')
               OR (NEW.state = 'STORED'
                   AND staging.state NOT IN ('FINALIZED', 'CLEANED'))
               OR (NEW.state = 'FAILED'
                   AND staging.state NOT IN ('PENDING', 'EXPIRED'))
            THEN
                RAISE EXCEPTION 'upload session staging lifecycle is invalid'
                    USING ERRCODE = '23514';
            END IF;

            SELECT access.project_id, access.scope_kind::text
              INTO scope
              FROM source.access_scope AS access
             WHERE access.id = NEW.access_scope_id
               AND access.organization_id = NEW.organization_id;
            IF NOT FOUND OR scope.project_id <> NEW.project_id
               OR scope.scope_kind <> NEW.access_scope THEN
                RAISE EXCEPTION 'upload access scope does not match project'
                    USING ERRCODE = '23514';
            END IF;

            IF NEW.creates_document
               AND NEW.state IN ('RESERVED', 'QUEUED') THEN
                IF EXISTS (
                    SELECT 1 FROM document.document AS stored_document
                    WHERE stored_document.id = NEW.target_document_id
                ) THEN
                    RAISE EXCEPTION 'new upload target document already exists'
                        USING ERRCODE = '23514';
                END IF;
            ELSIF NOT NEW.creates_document AND NOT EXISTS (
                SELECT 1 FROM document.document AS stored_document
                WHERE stored_document.id = NEW.target_document_id
                  AND stored_document.organization_id = NEW.organization_id
                  AND stored_document.project_id = NEW.project_id
                  AND stored_document.title = NEW.title
                  AND stored_document.document_number IS NOT DISTINCT FROM
                      NEW.document_number
            ) THEN
                RAISE EXCEPTION 'existing upload target document is invalid'
                    USING ERRCODE = '23514';
            END IF;

            IF NEW.completion_job_id IS NOT NULL THEN
                SELECT queued.organization_id, queued.project_id,
                       queued.access_scope, queued.job_type,
                       queued.payload ->> 'upload_session_id' AS upload_session_id,
                       queued.state, queued.lease_owner,
                       queued.lease_expires_at, queued.attempts
                  INTO job
                  FROM platform.knowledge_job AS queued
                 WHERE queued.id = NEW.completion_job_id;
                IF NOT FOUND OR ROW(
                    job.organization_id, job.project_id, job.access_scope,
                    job.job_type, job.upload_session_id
                ) IS DISTINCT FROM ROW(
                    NEW.organization_id, NEW.project_id, NEW.access_scope,
                    'document.intake.verify', NEW.id::text
                ) THEN
                    RAISE EXCEPTION 'upload completion job binding is invalid'
                        USING ERRCODE = '23514';
                END IF;
                IF NEW.state IN ('STORED', 'FAILED') AND (
                    job.state <> 'RUNNING' OR job.lease_owner IS NULL
                    OR job.lease_expires_at <= pg_catalog.clock_timestamp()
                    OR job.attempts < 1
                ) THEN
                    RAISE EXCEPTION 'terminal upload transition lacks active lease'
                        USING ERRCODE = '23514';
                END IF;
            END IF;

            IF NEW.state = 'STORED' THEN
                SELECT asset.project_id, asset.access_scope,
                       asset.access_scope_id, asset.license_policy_id,
                       asset.asset_kind, asset.sha256, asset.byte_size,
                       asset.media_type, asset.state
                  INTO object
                  FROM platform.object_asset AS asset
                 WHERE asset.id = NEW.object_asset_id
                   AND asset.organization_id = NEW.organization_id;
                IF NOT FOUND OR ROW(
                    object.project_id, object.access_scope,
                    object.access_scope_id, object.license_policy_id,
                    object.asset_kind, object.sha256, object.byte_size,
                    object.media_type, object.state
                ) IS DISTINCT FROM ROW(
                    NEW.project_id, NEW.access_scope,
                    NEW.access_scope_id, NEW.license_policy_id,
                    'DOCUMENT_ORIGINAL', NEW.actual_sha256,
                    NEW.expected_byte_size, NEW.media_type, 'AVAILABLE'
                ) THEN
                    RAISE EXCEPTION 'stored upload object binding is invalid'
                        USING ERRCODE = '23514';
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM document.document AS stored_document
                    JOIN document.document_revision AS revision
                      ON revision.document_id = stored_document.id
                     AND revision.organization_id = stored_document.organization_id
                     AND revision.project_id = stored_document.project_id
                    JOIN document.document_asset AS relation
                      ON relation.revision_id = revision.id
                     AND relation.organization_id = revision.organization_id
                     AND relation.project_id = revision.project_id
                    JOIN platform.job_effect_receipt AS receipt
                      ON receipt.job_id = NEW.completion_job_id
                     AND receipt.organization_id = NEW.organization_id
                     AND receipt.effect_name = 'document-original-promotion'
                     AND receipt.effect_sha256 = NEW.actual_sha256
                     AND receipt.lease_attempt = job.attempts
                     AND receipt.lease_owner = job.lease_owner
                    WHERE stored_document.id = NEW.target_document_id
                      AND stored_document.organization_id = NEW.organization_id
                      AND stored_document.project_id = NEW.project_id
                      AND stored_document.title = NEW.title
                      AND stored_document.document_number IS NOT DISTINCT FROM
                          NEW.document_number
                      AND revision.id = NEW.target_revision_id
                      AND revision.source_organization_id =
                          NEW.source_organization_id
                      AND revision.access_scope = NEW.access_scope
                      AND revision.access_scope_id = NEW.access_scope_id
                      AND revision.license_policy_id = NEW.license_policy_id
                      AND revision.revision_label = NEW.revision_label
                      AND revision.original_filename = NEW.original_filename
                      AND revision.media_type = NEW.media_type
                      AND revision.state = 'STORED'
                      AND relation.object_asset_id = NEW.object_asset_id
                      AND relation.asset_kind = 'ORIGINAL'
                ) THEN
                    RAISE EXCEPTION 'stored upload lacks immutable document records'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $function$;

        CREATE TRIGGER enforce_upload_session_binding
        BEFORE INSERT OR UPDATE ON document.upload_session
        FOR EACH ROW EXECUTE FUNCTION document.enforce_upload_session_binding();

        CREATE FUNCTION document.enforce_revision_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            scope record;
        BEGIN
            SELECT access.project_id, access.scope_kind::text
              INTO scope
              FROM source.access_scope AS access
             WHERE access.id = NEW.access_scope_id
               AND access.organization_id = NEW.organization_id;
            IF NOT FOUND OR scope.project_id <> NEW.project_id
               OR scope.scope_kind <> NEW.access_scope THEN
                RAISE EXCEPTION 'revision access scope does not match project'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_revision_scope
        BEFORE INSERT ON document.document_revision
        FOR EACH ROW EXECUTE FUNCTION document.enforce_revision_scope();

        CREATE FUNCTION document.enforce_document_asset_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            revision record;
            object record;
        BEGIN
            SELECT stored.organization_id, stored.project_id,
                   stored.access_scope, stored.access_scope_id,
                   stored.license_policy_id, stored.media_type, stored.state
              INTO revision
              FROM document.document_revision AS stored
             WHERE stored.id = NEW.revision_id;
            SELECT asset.organization_id, asset.project_id,
                   asset.access_scope, asset.access_scope_id,
                   asset.license_policy_id, asset.asset_kind,
                   asset.media_type, asset.state
              INTO object
              FROM platform.object_asset AS asset
             WHERE asset.id = NEW.object_asset_id;
            IF revision IS NULL THEN
                RAISE EXCEPTION 'document revision binding is unavailable'
                    USING ERRCODE = '23514';
            END IF;
            IF object IS NULL THEN
                RAISE EXCEPTION 'document object binding is unavailable'
                    USING ERRCODE = '23514';
            END IF;
            IF ROW(
                revision.organization_id, revision.project_id,
                revision.access_scope, revision.access_scope_id,
                revision.license_policy_id, revision.media_type,
                revision.state, object.organization_id, object.project_id,
                object.access_scope, object.access_scope_id,
                object.license_policy_id, object.asset_kind,
                object.media_type, object.state, NEW.asset_kind
            ) IS DISTINCT FROM ROW(
                NEW.organization_id, NEW.project_id,
                'PROJECT', object.access_scope_id,
                object.license_policy_id, 'application/pdf',
                'STORED', NEW.organization_id, NEW.project_id,
                'PROJECT', revision.access_scope_id,
                revision.license_policy_id, 'DOCUMENT_ORIGINAL',
                'application/pdf', 'AVAILABLE', 'ORIGINAL'
            ) THEN
                RAISE EXCEPTION 'document asset crosses a protected boundary'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_document_asset_binding
        BEFORE INSERT ON document.document_asset
        FOR EACH ROW EXECUTE FUNCTION document.enforce_document_asset_binding();

        CREATE FUNCTION document.enforce_document_insert_upload_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                WHERE upload.target_document_id = NEW.id
                  AND upload.organization_id = NEW.organization_id
                  AND upload.project_id = NEW.project_id
                  AND upload.creates_document
                  AND upload.title = NEW.title
                  AND upload.document_number IS NOT DISTINCT FROM
                      NEW.document_number
                  AND upload.created_by_subject_id = NEW.created_by_subject_id
                  AND upload.state = 'QUEUED'
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'RUNNING'
                  AND job.lease_owner IS NOT NULL
                  AND job.lease_expires_at > pg_catalog.clock_timestamp()
                  AND job.attempts > 0
            ) THEN
                RAISE EXCEPTION 'document insert lacks an active upload lease'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_document_insert_upload_binding
        BEFORE INSERT ON document.document
        FOR EACH ROW EXECUTE FUNCTION
            document.enforce_document_insert_upload_binding();

        CREATE FUNCTION document.enforce_revision_insert_upload_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                WHERE upload.target_document_id = NEW.document_id
                  AND upload.target_revision_id = NEW.id
                  AND upload.organization_id = NEW.organization_id
                  AND upload.project_id = NEW.project_id
                  AND upload.source_organization_id =
                      NEW.source_organization_id
                  AND upload.access_scope = NEW.access_scope
                  AND upload.access_scope_id = NEW.access_scope_id
                  AND upload.license_policy_id = NEW.license_policy_id
                  AND upload.revision_label = NEW.revision_label
                  AND upload.original_filename = NEW.original_filename
                  AND upload.media_type = NEW.media_type
                  AND upload.created_by_subject_id = NEW.created_by_subject_id
                  AND upload.state = 'QUEUED'
                  AND NEW.state = 'STORED'
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'RUNNING'
                  AND job.lease_owner IS NOT NULL
                  AND job.lease_expires_at > pg_catalog.clock_timestamp()
                  AND job.attempts > 0
            ) THEN
                RAISE EXCEPTION 'revision insert lacks an active upload lease'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_revision_insert_upload_binding
        BEFORE INSERT ON document.document_revision
        FOR EACH ROW EXECUTE FUNCTION
            document.enforce_revision_insert_upload_binding();

        CREATE FUNCTION document.enforce_asset_insert_upload_binding()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                JOIN platform.object_asset AS object
                  ON object.id = NEW.object_asset_id
                 AND object.organization_id = NEW.organization_id
                JOIN platform.job_effect_receipt AS receipt
                  ON receipt.job_id = job.id
                 AND receipt.organization_id = job.organization_id
                 AND receipt.effect_name = 'document-original-promotion'
                 AND receipt.effect_sha256 = object.sha256
                 AND receipt.lease_attempt = job.attempts
                 AND receipt.lease_owner = job.lease_owner
                WHERE upload.target_revision_id = NEW.revision_id
                  AND upload.organization_id = NEW.organization_id
                  AND upload.project_id = NEW.project_id
                  AND upload.state = 'QUEUED'
                  AND NEW.asset_kind = 'ORIGINAL'
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'RUNNING'
                  AND job.lease_owner IS NOT NULL
                  AND job.lease_expires_at > pg_catalog.clock_timestamp()
                  AND job.attempts > 0
            ) THEN
                RAISE EXCEPTION 'document asset insert lacks a verified effect'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_asset_insert_upload_binding
        BEFORE INSERT ON document.document_asset
        FOR EACH ROW EXECUTE FUNCTION
            document.enforce_asset_insert_upload_binding();

        CREATE FUNCTION document.has_closed_stored_upload(
            required_document_id uuid,
            required_revision_id uuid,
            required_relation_id uuid,
            required_object_asset_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
            SELECT EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN document.document AS stored_document
                  ON stored_document.id = upload.target_document_id
                 AND stored_document.organization_id = upload.organization_id
                 AND stored_document.project_id = upload.project_id
                JOIN document.document_revision AS revision
                  ON revision.id = upload.target_revision_id
                 AND revision.document_id = stored_document.id
                 AND revision.organization_id = upload.organization_id
                 AND revision.project_id = upload.project_id
                JOIN document.document_asset AS relation
                  ON relation.revision_id = revision.id
                 AND relation.organization_id = upload.organization_id
                 AND relation.project_id = upload.project_id
                 AND relation.asset_kind = 'ORIGINAL'
                JOIN platform.object_asset AS object
                  ON object.id = relation.object_asset_id
                 AND object.organization_id = upload.organization_id
                 AND object.project_id = upload.project_id
                JOIN platform.staging_upload_reservation AS reservation
                  ON reservation.id = upload.id
                 AND reservation.organization_id = upload.organization_id
                 AND reservation.project_id = upload.project_id
                 AND reservation.access_scope = upload.access_scope
                 AND reservation.access_scope_id = upload.access_scope_id
                 AND reservation.license_policy_id = upload.license_policy_id
                 AND reservation.created_by_subject_id =
                     upload.created_by_subject_id
                 AND reservation.media_type = upload.media_type
                 AND reservation.expected_byte_size =
                     upload.expected_byte_size
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                JOIN platform.job_effect_receipt AS receipt
                  ON receipt.job_id = job.id
                 AND receipt.organization_id = job.organization_id
                 AND receipt.effect_name = 'document-original-promotion'
                 AND receipt.effect_sha256 = object.sha256
                 AND receipt.lease_attempt = job.attempts
                 AND receipt.lease_owner IS NOT NULL
                JOIN audit.audit_event AS audit_receipt
                  ON audit_receipt.organization_id = upload.organization_id
                 AND audit_receipt.project_id = upload.project_id
                 AND audit_receipt.actor_subject_id IS NULL
                 AND audit_receipt.actor_kind IS NULL
                 AND audit_receipt.action = 'document.revision.stored'
                 AND audit_receipt.resource_type = 'document_revision'
                 AND audit_receipt.resource_id = revision.id
                 AND audit_receipt.outcome = 'SUCCEEDED'
                WHERE upload.state = 'STORED'
                  AND upload.actual_sha256 = object.sha256
                  AND upload.object_asset_id = object.id
                  AND upload.expected_byte_size = object.byte_size
                  AND upload.media_type = object.media_type
                  AND upload.access_scope = object.access_scope
                  AND upload.access_scope_id = object.access_scope_id
                  AND upload.license_policy_id = object.license_policy_id
                  AND upload.created_by_subject_id =
                      object.created_by_subject_id
                  AND stored_document.title = upload.title
                  AND stored_document.document_number IS NOT DISTINCT FROM
                      upload.document_number
                  AND revision.source_organization_id =
                      upload.source_organization_id
                  AND revision.access_scope = upload.access_scope
                  AND revision.access_scope_id = upload.access_scope_id
                  AND revision.license_policy_id = upload.license_policy_id
                  AND revision.revision_label = upload.revision_label
                  AND revision.original_filename = upload.original_filename
                  AND revision.media_type = upload.media_type
                  AND revision.state = 'STORED'
                  AND object.asset_kind = 'DOCUMENT_ORIGINAL'
                  AND object.state = 'AVAILABLE'
                  AND reservation.state IN ('FINALIZED', 'CLEANED')
                  AND reservation.asset_id = object.id
                  AND reservation.finalized_at IS NOT NULL
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'COMPLETED'
                  AND audit_receipt.detail ->> 'upload_session_id' =
                      upload.id::text
                  AND audit_receipt.detail ->> 'job_id' = job.id::text
                  AND audit_receipt.detail ->> 'object_asset_id' =
                      object.id::text
                  AND audit_receipt.detail ->> 'sha256' = object.sha256
                  AND audit_receipt.detail ->> 'byte_size' =
                      object.byte_size::text
                  AND (
                      required_document_id IS NULL OR
                      stored_document.id = required_document_id
                  )
                  AND (
                      required_revision_id IS NULL OR
                      revision.id = required_revision_id
                  )
                  AND (
                      required_relation_id IS NULL OR
                      relation.id = required_relation_id
                  )
                  AND (
                      required_object_asset_id IS NULL OR
                      object.id = required_object_asset_id
                  )
            )
        $function$;

        CREATE FUNCTION document.enforce_closed_stored_upload()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        DECLARE
            closed boolean;
        BEGIN
            IF TG_TABLE_SCHEMA = 'platform' THEN
                closed := document.has_closed_stored_upload(
                    NULL, NULL, NULL, NEW.id
                );
            ELSIF TG_TABLE_NAME = 'document' THEN
                closed := document.has_closed_stored_upload(
                    NEW.id, NULL, NULL, NULL
                );
            ELSIF TG_TABLE_NAME = 'document_revision' THEN
                closed := document.has_closed_stored_upload(
                    NULL, NEW.id, NULL, NULL
                );
            ELSE
                closed := document.has_closed_stored_upload(
                    NULL, NULL, NEW.id, NULL
                );
            END IF;
            IF NOT closed THEN
                RAISE EXCEPTION 'stored document transaction is incomplete'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $function$;

        CREATE CONSTRAINT TRIGGER require_closed_document_insert
        AFTER INSERT ON document.document
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION document.enforce_closed_stored_upload();
        CREATE CONSTRAINT TRIGGER require_closed_revision_insert
        AFTER INSERT ON document.document_revision
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION document.enforce_closed_stored_upload();
        CREATE CONSTRAINT TRIGGER require_closed_document_asset_insert
        AFTER INSERT ON document.document_asset
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION document.enforce_closed_stored_upload();
        CREATE CONSTRAINT TRIGGER require_closed_object_asset_insert
        AFTER INSERT ON platform.object_asset
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        WHEN (NEW.asset_kind = 'DOCUMENT_ORIGINAL')
        EXECUTE FUNCTION document.enforce_closed_stored_upload();
        """
    )


def _create_immutable_triggers() -> None:
    op.execute(
        r"""
        CREATE FUNCTION document.reject_immutable_record_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            RAISE EXCEPTION 'stored document records are immutable'
                USING ERRCODE = '55000';
        END;
        $function$;
        CREATE TRIGGER reject_document_mutation
            BEFORE UPDATE OR DELETE ON document.document
            FOR EACH ROW EXECUTE FUNCTION document.reject_immutable_record_mutation();
        CREATE TRIGGER reject_document_revision_mutation
            BEFORE UPDATE OR DELETE ON document.document_revision
            FOR EACH ROW EXECUTE FUNCTION document.reject_immutable_record_mutation();
        CREATE TRIGGER reject_document_asset_mutation
            BEFORE UPDATE OR DELETE ON document.document_asset
            FOR EACH ROW EXECUTE FUNCTION document.reject_immutable_record_mutation();

        CREATE FUNCTION document.enforce_upload_session_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, pg_temp
        AS $function$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'upload sessions cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF ROW(
                OLD.id, OLD.organization_id, OLD.project_id, OLD.access_scope,
                OLD.access_scope_id, OLD.license_policy_id,
                OLD.source_organization_id, OLD.target_document_id,
                OLD.target_revision_id, OLD.creates_document, OLD.title,
                OLD.document_number, OLD.revision_label, OLD.original_filename,
                OLD.media_type, OLD.expected_byte_size, OLD.idempotency_key,
                OLD.request_sha256, OLD.created_by_subject_id, OLD.created_at
            ) IS DISTINCT FROM ROW(
                NEW.id, NEW.organization_id, NEW.project_id, NEW.access_scope,
                NEW.access_scope_id, NEW.license_policy_id,
                NEW.source_organization_id, NEW.target_document_id,
                NEW.target_revision_id, NEW.creates_document, NEW.title,
                NEW.document_number, NEW.revision_label, NEW.original_filename,
                NEW.media_type, NEW.expected_byte_size, NEW.idempotency_key,
                NEW.request_sha256, NEW.created_by_subject_id, NEW.created_at
            ) THEN
                RAISE EXCEPTION 'upload session identity and metadata are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NOT (
                (OLD.state = 'RESERVED' AND NEW.state = 'QUEUED') OR
                (OLD.state = 'QUEUED' AND NEW.state IN ('STORED', 'FAILED'))
            ) THEN
                RAISE EXCEPTION 'invalid upload session state transition'
                    USING ERRCODE = '23514';
            END IF;
            IF OLD.state = 'RESERVED' AND (
                NEW.actual_sha256 IS NOT NULL OR NEW.object_asset_id IS NOT NULL
                OR NEW.completed_at IS NOT NULL OR NEW.failure_code IS NOT NULL
            ) THEN
                RAISE EXCEPTION 'API cannot finalize an upload session'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $function$;
        CREATE TRIGGER enforce_upload_session_transition
        BEFORE UPDATE OR DELETE ON document.upload_session
        FOR EACH ROW EXECUTE FUNCTION document.enforce_upload_session_transition();

        REVOKE ALL ON FUNCTION document.reject_immutable_record_mutation()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION document.enforce_upload_session_transition()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION document.enforce_upload_session_binding()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION document.enforce_revision_scope()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION document.enforce_document_asset_binding()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION
            document.enforce_document_insert_upload_binding()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION
            document.enforce_revision_insert_upload_binding()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION
            document.enforce_asset_insert_upload_binding()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION
            document.enforce_verifier_staging_transition()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION
            document.enforce_upload_reservation_lifecycle()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION
            document.has_closed_stored_upload(uuid, uuid, uuid, uuid)
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON FUNCTION document.enforce_closed_stored_upload()
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        """
    )


def _create_rls_policies() -> None:
    op.execute(
        r"""
        ALTER TABLE document.upload_session ENABLE ROW LEVEL SECURITY;
        ALTER TABLE document.upload_session FORCE ROW LEVEL SECURITY;
        ALTER TABLE document.document ENABLE ROW LEVEL SECURITY;
        ALTER TABLE document.document FORCE ROW LEVEL SECURITY;
        ALTER TABLE document.document_revision ENABLE ROW LEVEL SECURITY;
        ALTER TABLE document.document_revision FORCE ROW LEVEL SECURITY;
        ALTER TABLE document.document_asset ENABLE ROW LEVEL SECURITY;
        ALTER TABLE document.document_asset FORCE ROW LEVEL SECURITY;

        CREATE POLICY upload_session_app_select
        ON document.upload_session FOR SELECT TO pcbknowledge_app
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY upload_session_app_insert
        ON document.upload_session FOR INSERT TO pcbknowledge_app
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND created_by_subject_id = identity.current_external_subject_id()
            AND state = 'RESERVED'
        );
        CREATE POLICY upload_session_app_update
        ON document.upload_session FOR UPDATE TO pcbknowledge_app
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND created_by_subject_id = identity.current_external_subject_id()
            AND state IN ('RESERVED', 'QUEUED', 'STORED', 'FAILED')
        )
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND created_by_subject_id = identity.current_external_subject_id()
            AND state = 'QUEUED'
        );

        CREATE POLICY upload_session_verifier_select
        ON document.upload_session FOR SELECT TO pcbknowledge_verifier
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY upload_session_verifier_update
        ON document.upload_session FOR UPDATE TO pcbknowledge_verifier
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND state = 'QUEUED'
        )
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND state IN ('STORED', 'FAILED')
        );

        CREATE POLICY document_app_select
        ON document.document FOR SELECT TO pcbknowledge_app
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY document_verifier_select
        ON document.document FOR SELECT TO pcbknowledge_verifier
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY document_verifier_insert
        ON document.document FOR INSERT TO pcbknowledge_verifier
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );

        CREATE POLICY revision_app_select
        ON document.document_revision FOR SELECT TO pcbknowledge_app
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY revision_verifier_select
        ON document.document_revision FOR SELECT TO pcbknowledge_verifier
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY revision_verifier_insert
        ON document.document_revision FOR INSERT TO pcbknowledge_verifier
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND state = 'STORED'
        );

        CREATE POLICY document_asset_app_select
        ON document.document_asset FOR SELECT TO pcbknowledge_app
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY document_asset_verifier_select
        ON document.document_asset FOR SELECT TO pcbknowledge_verifier
        USING (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
        );
        CREATE POLICY document_asset_verifier_insert
        ON document.document_asset FOR INSERT TO pcbknowledge_verifier
        WITH CHECK (
            organization_id = identity.current_organization_id()
            AND identity.can_access_project(project_id)
            AND asset_kind = 'ORIGINAL'
        );
        """
    )


def _create_verifier_discovery() -> None:
    op.execute(
        r"""
        CREATE FUNCTION platform.claimable_document_intake_scopes(
            maximum_scopes integer
        )
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
                job.organization_id,
                job.project_id,
                job.access_scope
            FROM platform.knowledge_job AS job
            WHERE job.job_type = 'document.intake.verify'
              AND (
                  (
                      job.state = 'READY'
                      AND job.available_at <= pg_catalog.clock_timestamp()
                      AND job.attempts < job.max_attempts
                  ) OR (
                      job.state = 'RUNNING'
                      AND job.lease_expires_at <=
                          pg_catalog.clock_timestamp()
                  )
              )
            ORDER BY job.organization_id, job.project_id
            LIMIT CASE
                WHEN maximum_scopes IS NULL THEN 100
                WHEN maximum_scopes < 1 THEN 1
                WHEN maximum_scopes > 1000 THEN 1000
                ELSE maximum_scopes
            END
        $function$;
        REVOKE ALL ON FUNCTION
            platform.claimable_document_intake_scopes(integer)
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker;
        GRANT EXECUTE ON FUNCTION
            platform.claimable_document_intake_scopes(integer)
            TO pcbknowledge_verifier;
        """
    )


def _install_restrictive_verifier_queue_policies() -> None:
    op.execute(
        r"""
        CREATE POLICY knowledge_job_verifier_only
        ON platform.knowledge_job
        AS RESTRICTIVE FOR ALL TO pcbknowledge_verifier
        USING (job_type = 'document.intake.verify')
        WITH CHECK (job_type = 'document.intake.verify');

        CREATE POLICY job_effect_receipt_verifier_only
        ON platform.job_effect_receipt
        AS RESTRICTIVE FOR ALL TO pcbknowledge_verifier
        USING (
            EXISTS (
                SELECT 1 FROM platform.knowledge_job AS job
                WHERE job.id = job_effect_receipt.job_id
                  AND job.organization_id = job_effect_receipt.organization_id
                  AND job.job_type = 'document.intake.verify'
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM platform.knowledge_job AS job
                WHERE job.id = job_effect_receipt.job_id
                  AND job.organization_id = job_effect_receipt.organization_id
                  AND job.job_type = 'document.intake.verify'
            )
        );

        CREATE POLICY staging_upload_verifier_only
        ON platform.staging_upload_reservation
        AS RESTRICTIVE FOR ALL TO pcbknowledge_verifier
        USING (
            EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                WHERE upload.id = staging_upload_reservation.id
                  AND upload.organization_id =
                      staging_upload_reservation.organization_id
                  AND upload.project_id = staging_upload_reservation.project_id
                  AND upload.state = 'QUEUED'
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'RUNNING'
                  AND job.lease_owner IS NOT NULL
                  AND job.lease_expires_at > pg_catalog.clock_timestamp()
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                WHERE upload.id = staging_upload_reservation.id
                  AND upload.organization_id =
                      staging_upload_reservation.organization_id
                  AND upload.project_id = staging_upload_reservation.project_id
                  AND upload.state = 'QUEUED'
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'RUNNING'
                  AND job.lease_owner IS NOT NULL
                  AND job.lease_expires_at > pg_catalog.clock_timestamp()
            )
        );

        CREATE POLICY object_asset_verifier_only
        ON platform.object_asset
        AS RESTRICTIVE FOR ALL TO pcbknowledge_verifier
        USING (
            asset_kind = 'DOCUMENT_ORIGINAL'
            AND EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                JOIN platform.job_effect_receipt AS receipt
                  ON receipt.job_id = job.id
                 AND receipt.organization_id = job.organization_id
                 AND receipt.effect_name = 'document-original-promotion'
                 AND receipt.effect_sha256 = object_asset.sha256
                 AND receipt.lease_attempt = job.attempts
                WHERE upload.organization_id = object_asset.organization_id
                  AND upload.project_id = object_asset.project_id
                  AND upload.access_scope = object_asset.access_scope
                  AND upload.access_scope_id = object_asset.access_scope_id
                  AND upload.license_policy_id = object_asset.license_policy_id
                  AND upload.created_by_subject_id =
                      object_asset.created_by_subject_id
                  AND upload.media_type = object_asset.media_type
                  AND upload.expected_byte_size = object_asset.byte_size
                  AND upload.state IN ('QUEUED', 'STORED')
                  AND job.job_type = 'document.intake.verify'
                  AND (
                      (
                          job.state = 'RUNNING'
                          AND receipt.lease_owner = job.lease_owner
                          AND job.lease_owner IS NOT NULL
                          AND job.lease_expires_at >
                              pg_catalog.clock_timestamp()
                      ) OR (
                          job.state = 'COMPLETED'
                          AND receipt.lease_owner IS NOT NULL
                      )
                  )
            )
        )
        WITH CHECK (
            asset_kind = 'DOCUMENT_ORIGINAL'
            AND EXISTS (
                SELECT 1
                FROM document.upload_session AS upload
                JOIN platform.knowledge_job AS job
                  ON job.id = upload.completion_job_id
                 AND job.organization_id = upload.organization_id
                JOIN platform.job_effect_receipt AS receipt
                  ON receipt.job_id = job.id
                 AND receipt.organization_id = job.organization_id
                 AND receipt.effect_name = 'document-original-promotion'
                 AND receipt.effect_sha256 = object_asset.sha256
                 AND receipt.lease_attempt = job.attempts
                 AND receipt.lease_owner = job.lease_owner
                WHERE upload.organization_id = object_asset.organization_id
                  AND upload.project_id = object_asset.project_id
                  AND upload.access_scope = object_asset.access_scope
                  AND upload.access_scope_id = object_asset.access_scope_id
                  AND upload.license_policy_id = object_asset.license_policy_id
                  AND upload.created_by_subject_id =
                      object_asset.created_by_subject_id
                  AND upload.media_type = object_asset.media_type
                  AND upload.expected_byte_size = object_asset.byte_size
                  AND upload.state = 'QUEUED'
                  AND job.job_type = 'document.intake.verify'
                  AND job.state = 'RUNNING'
                  AND job.lease_owner IS NOT NULL
                  AND job.lease_expires_at > pg_catalog.clock_timestamp()
            )
        );

        CREATE POLICY outbox_verifier_cleanup_only
        ON platform.outbox_event
        AS RESTRICTIVE FOR ALL TO pcbknowledge_verifier
        USING (event_type = 'storage.staging_cleanup.requested')
        WITH CHECK (event_type = 'storage.staging_cleanup.requested');
        """
    )


def _normalize_runtime_grants() -> None:
    _revoke_runtime_grants()
    op.execute(
        r"""
        GRANT USAGE ON SCHEMA document TO pcbknowledge_app;
        GRANT SELECT ON TABLE
            document.upload_session, document.document,
            document.document_revision, document.document_asset
            TO pcbknowledge_app;
        GRANT INSERT (
            id, organization_id, project_id, access_scope,
            access_scope_id, license_policy_id, source_organization_id,
            target_document_id, target_revision_id, creates_document,
            title, document_number, revision_label, original_filename,
            media_type, expected_byte_size, idempotency_key,
            request_sha256, state, created_by_subject_id,
            created_at, updated_at
        ) ON document.upload_session TO pcbknowledge_app;
        GRANT UPDATE (
            state, expected_sha256, completion_job_id, updated_at
        ) ON document.upload_session TO pcbknowledge_app;

        GRANT USAGE ON SCHEMA
            public, identity, source, audit, platform, document
            TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE public.alembic_version
            TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE source.access_scope, source.license_policy
            TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE platform.knowledge_job
            TO pcbknowledge_verifier;
        GRANT UPDATE (
            state, available_at, lease_owner, lease_expires_at,
            attempts, last_failure_code, updated_at,
            completed_at, cancelled_at
        ) ON platform.knowledge_job TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE platform.job_effect_receipt
            TO pcbknowledge_verifier;
        GRANT INSERT (
            id, job_id, organization_id, project_id, access_scope,
            effect_name, effect_sha256, lease_attempt, lease_owner,
            recorded_at
        ) ON platform.job_effect_receipt TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE platform.staging_upload_reservation
            TO pcbknowledge_verifier;
        GRANT UPDATE (state, asset_id, finalized_at)
            ON platform.staging_upload_reservation
            TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE platform.object_asset
            TO pcbknowledge_verifier;
        GRANT INSERT (
            id, organization_id, project_id, access_scope,
            access_scope_id, license_policy_id, asset_kind, bucket,
            object_key, sha256, byte_size, media_type, state,
            created_by_subject_id, created_at
        ) ON platform.object_asset TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE platform.outbox_event
            TO pcbknowledge_verifier;
        GRANT INSERT (
            id, organization_id, project_id, access_scope,
            event_type, aggregate_type, aggregate_id, payload,
            payload_sha256, idempotency_key, state, available_at,
            attempts, max_attempts, created_at, updated_at
        ) ON platform.outbox_event TO pcbknowledge_verifier;
        GRANT INSERT (
            id, organization_id, project_id, occurred_at,
            actor_subject_id, actor_kind, action, resource_type,
            resource_id, outcome, request_id, detail
        ) ON audit.audit_event TO pcbknowledge_verifier;
        GRANT SELECT (occurred_at)
            ON audit.audit_event TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE document.upload_session
            TO pcbknowledge_verifier;
        GRANT UPDATE (
            state, actual_sha256, object_asset_id,
            failure_code, updated_at, completed_at
        ) ON document.upload_session TO pcbknowledge_verifier;
        GRANT SELECT ON TABLE
            document.document, document.document_revision,
            document.document_asset TO pcbknowledge_verifier;
        GRANT INSERT (
            id, organization_id, project_id, title, document_number,
            created_by_subject_id, created_at
        ) ON document.document TO pcbknowledge_verifier;
        GRANT INSERT (
            id, organization_id, project_id, document_id,
            source_organization_id, access_scope, access_scope_id,
            license_policy_id, revision_label, original_filename,
            media_type, state, created_by_subject_id, created_at
        ) ON document.document_revision TO pcbknowledge_verifier;
        GRANT INSERT (
            id, organization_id, project_id, revision_id,
            object_asset_id, asset_kind, created_at
        ) ON document.document_asset TO pcbknowledge_verifier;
        GRANT EXECUTE ON FUNCTION identity.current_organization_id()
            TO pcbknowledge_verifier;
        GRANT EXECUTE ON FUNCTION identity.can_access_project(uuid)
            TO pcbknowledge_verifier;
        GRANT EXECUTE ON FUNCTION
            platform.claimable_document_intake_scopes(integer)
            TO pcbknowledge_verifier;
        """
    )


def _revoke_runtime_grants() -> None:
    op.execute(
        r"""
        REVOKE ALL ON SCHEMA document
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON ALL TABLES IN SCHEMA document
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA document
            FROM PUBLIC, pcbknowledge_app, pcbknowledge_worker,
                 pcbknowledge_verifier;

        REVOKE ALL ON SCHEMA public, identity, source, audit, platform
            FROM pcbknowledge_verifier;
        REVOKE ALL ON ALL TABLES IN SCHEMA
            public, identity, source, audit, platform
            FROM pcbknowledge_verifier;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA
            identity, source, audit, platform
            FROM pcbknowledge_verifier;
        """
    )
