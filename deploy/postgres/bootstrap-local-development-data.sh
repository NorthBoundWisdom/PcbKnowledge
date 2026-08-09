#!/bin/sh
set -eu
umask 077

issuer=${PCBKNOWLEDGE_LOCAL_OIDC_ISSUER:-}
external_subject=${PCBKNOWLEDGE_LOCAL_CURATOR_SUBJECT:-}

issuer_prefix=http://localhost:
issuer_suffix=/realms/pcbknowledge
case "$issuer" in
  "$issuer_prefix"*"$issuer_suffix") ;;
  *)
    echo "local OIDC issuer must be the exact loopback pcbknowledge realm" >&2
    exit 1
    ;;
esac
issuer_port=${issuer#"$issuer_prefix"}
issuer_port=${issuer_port%"$issuer_suffix"}
case "$issuer_port" in
  "" | *[!0-9]*)
    echo "local OIDC issuer port must be numeric" >&2
    exit 1
    ;;
esac
normalized_port=$(printf '%s\n' "$issuer_port" | sed 's/^0*//')
normalized_port=${normalized_port:-0}
if [ "${#normalized_port}" -gt 5 ] || \
  [ "$normalized_port" -lt 1 ] || [ "$normalized_port" -gt 65535 ]; then
  echo "local OIDC issuer port is outside 1..65535" >&2
  exit 1
fi
if [ "$issuer" != "$issuer_prefix$issuer_port$issuer_suffix" ]; then
  echo "local OIDC issuer contains an unexpected authority or path" >&2
  exit 1
fi
unset normalized_port issuer_port
case "$external_subject" in
  ????????-????-????-????-????????????) ;;
  *)
    echo "local curator subject is not a UUID" >&2
    exit 1
    ;;
esac
case "$external_subject" in
  *[!0-9a-f-]*)
    echo "local curator subject contains invalid characters" >&2
    exit 1
    ;;
esac

if [ ! -s /run/secrets/postgres_password ]; then
  echo "PostgreSQL owner password is missing or empty" >&2
  exit 1
fi
PGPASSWORD=$(tr -d '\r\n' </run/secrets/postgres_password)
if [ -z "$PGPASSWORD" ]; then
  echo "PostgreSQL owner password is empty" >&2
  exit 1
fi
export PGPASSWORD

psql \
  --host postgres \
  --username pcbknowledge \
  --dbname pcbknowledge \
  --no-psqlrc \
  --quiet \
  --set ON_ERROR_STOP=1 \
  --set issuer="$issuer" \
  --set external_subject="$external_subject" <<'SQL'
BEGIN;

CREATE TEMPORARY TABLE local_bootstrap_input (
  issuer text NOT NULL,
  external_subject text NOT NULL
) ON COMMIT DROP;
INSERT INTO local_bootstrap_input (issuer, external_subject)
VALUES (:'issuer', :'external_subject');

INSERT INTO identity.organization (id, slug, display_name, active)
VALUES (
  '019fe5df-728a-7581-99be-e452971c8ff6',
  'local-development',
  'Local Development',
  true
)
ON CONFLICT DO NOTHING;

INSERT INTO identity.project (id, organization_id, slug, display_name, active)
VALUES (
  '019fe5df-728a-7581-99be-e4539921e503',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  'default-project',
  'Default Project',
  true
)
ON CONFLICT DO NOTHING;

INSERT INTO identity.external_subject (
  id,
  organization_id,
  issuer,
  external_subject,
  subject_kind,
  client_id,
  display_name,
  active
)
SELECT
  '019fe5df-728a-7581-99be-e454bb06ac4c',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  input.issuer,
  input.external_subject,
  'HUMAN',
  NULL,
  'Local Curator',
  true
FROM local_bootstrap_input AS input
ON CONFLICT DO NOTHING;

INSERT INTO identity.membership (
  id,
  organization_id,
  external_subject_id,
  project_id,
  role
)
VALUES (
  '019fe5df-728a-7581-99be-e45524732aa5',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  '019fe5df-728a-7581-99be-e454bb06ac4c',
  '019fe5df-728a-7581-99be-e4539921e503',
  'DATA_CURATOR'
)
ON CONFLICT DO NOTHING;

INSERT INTO source.source_organization (
  id,
  organization_id,
  name,
  authority_tier
)
VALUES (
  '019fe5df-728a-7581-99be-e458c5032fb9',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  'Internal Development',
  'INTERNAL'
)
ON CONFLICT DO NOTHING;

INSERT INTO source.access_scope (
  id,
  organization_id,
  project_id,
  name,
  scope_kind
)
VALUES (
  '019fe5df-728a-7581-99be-e459279f1318',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  '019fe5df-728a-7581-99be-e4539921e503',
  'Default Project',
  'PROJECT'
)
ON CONFLICT DO NOTHING;

INSERT INTO source.license_policy (
  id,
  organization_id,
  access_scope_id,
  name,
  license_class,
  allow_metadata_read,
  allow_human_raw_access,
  allow_parse,
  allow_external_model,
  allow_local_model,
  allow_embedding,
  allow_agent_raw_access,
  allow_redistribution
)
VALUES (
  '019fe5df-728a-7581-99be-e45a23bb832e',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  '019fe5df-728a-7581-99be-e459279f1318',
  'Local Internal Human Intake',
  'INTERNAL',
  true,
  true,
  false,
  false,
  false,
  false,
  false,
  false
)
ON CONFLICT DO NOTHING;

DO $validation$
DECLARE
  expected_issuer text;
  expected_subject text;
BEGIN
  SELECT issuer, external_subject
    INTO STRICT expected_issuer, expected_subject
    FROM local_bootstrap_input;

  IF NOT EXISTS (
    SELECT 1
      FROM identity.organization
     WHERE id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND slug = 'local-development'
       AND display_name = 'Local Development'
       AND active
  ) THEN
    RAISE EXCEPTION 'local development organization conflicts with managed bootstrap data'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM identity.project
     WHERE id = '019fe5df-728a-7581-99be-e4539921e503'
       AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND slug = 'default-project'
       AND display_name = 'Default Project'
       AND active
  ) THEN
    RAISE EXCEPTION 'default project conflicts with managed bootstrap data'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM identity.external_subject
     WHERE id = '019fe5df-728a-7581-99be-e454bb06ac4c'
       AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND issuer = expected_issuer
       AND external_subject = expected_subject
       AND subject_kind = 'HUMAN'
       AND client_id IS NULL
       AND display_name = 'Local Curator'
       AND active
  ) THEN
    RAISE EXCEPTION 'local curator subject mapping conflicts with Keycloak'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM identity.membership
     WHERE id = '019fe5df-728a-7581-99be-e45524732aa5'
       AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND external_subject_id = '019fe5df-728a-7581-99be-e454bb06ac4c'
       AND project_id = '019fe5df-728a-7581-99be-e4539921e503'
       AND role = 'DATA_CURATOR'
  ) THEN
    RAISE EXCEPTION 'local curator membership conflicts with managed bootstrap data'
      USING ERRCODE = '23514';
  END IF;

  IF (
    SELECT count(*)
      FROM identity.membership
     WHERE external_subject_id = '019fe5df-728a-7581-99be-e454bb06ac4c'
  ) <> 1 THEN
    RAISE EXCEPTION 'local curator has membership outside its managed default project role'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM source.source_organization
     WHERE id = '019fe5df-728a-7581-99be-e458c5032fb9'
       AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND name = 'Internal Development'
       AND authority_tier = 'INTERNAL'
  ) THEN
    RAISE EXCEPTION 'local source organization conflicts with managed bootstrap data'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM source.access_scope
     WHERE id = '019fe5df-728a-7581-99be-e459279f1318'
       AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND project_id = '019fe5df-728a-7581-99be-e4539921e503'
       AND name = 'Default Project'
       AND scope_kind = 'PROJECT'
  ) THEN
    RAISE EXCEPTION 'local access scope conflicts with managed bootstrap data'
      USING ERRCODE = '23514';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM source.license_policy
     WHERE id = '019fe5df-728a-7581-99be-e45a23bb832e'
       AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
       AND access_scope_id = '019fe5df-728a-7581-99be-e459279f1318'
       AND name = 'Local Internal Human Intake'
       AND license_class = 'INTERNAL'
       AND allow_metadata_read
       AND allow_human_raw_access
       AND NOT allow_parse
       AND NOT allow_external_model
       AND NOT allow_local_model
       AND NOT allow_embedding
       AND NOT allow_agent_raw_access
       AND NOT allow_redistribution
  ) THEN
    RAISE EXCEPTION 'local license policy conflicts with managed bootstrap data'
      USING ERRCODE = '23514';
  END IF;
END;
$validation$;

COMMIT;
SQL

unset PGPASSWORD
