#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$repo_root"

if ! docker compose ps --status running --services | grep -Fxq keycloak; then
  echo "a running local Compose Keycloak service is required" >&2
  exit 1
fi
if ! docker compose ps --status running --services | grep -Fxq postgres; then
  echo "a running local Compose PostgreSQL service is required" >&2
  exit 1
fi

file_permissions() {
  path=$1
  if stat -f '%Lp' "$path" >/dev/null 2>&1; then
    stat -f '%Lp' "$path"
  else
    stat -c '%a' "$path"
  fi
}

permissions=$(file_permissions deploy/secrets/local_curator_password)
if [ "$permissions" != 600 ]; then
  echo "local curator password is not owner-only" >&2
  exit 1
fi
marker_permissions=$(file_permissions deploy/secrets/local_curator_marker)
if [ "$marker_permissions" != 600 ]; then
  echo "local curator managed marker is not owner-only" >&2
  exit 1
fi

"$script_dir/bootstrap-local-development.sh" >/dev/null
"$script_dir/bootstrap-local-development.sh" >/dev/null

set +e
negative_output=$(
  PCBKNOWLEDGE_LOCAL_CURATOR_SUBJECT=00000000-0000-0000-0000-000000000000 \
  PCBKNOWLEDGE_LOCAL_OIDC_ISSUER="http://localhost:${PCBKNOWLEDGE_KEYCLOAK_PORT:-8081}/realms/pcbknowledge" \
    docker compose --profile tools run --rm --no-deps -T local-development-data 2>&1
)
negative_result=$?
set -e
if [ "$negative_result" -eq 0 ]; then
  echo "a mismatched Keycloak subject was incorrectly accepted" >&2
  exit 1
fi
printf '%s\n' "$negative_output" |
  grep -Fq 'local curator subject mapping conflicts with Keycloak' || {
    echo "subject mismatch did not fail at the trusted mapping boundary" >&2
    exit 1
  }
unset negative_output

managed_subject=$(
  PCBKNOWLEDGE_LOCAL_CURATOR_ACTION=assert \
    docker compose --profile tools run --rm --no-deps -T local-curator-keycloak
)
for invalid_issuer in \
  'http://localhost:8081@evil.example/realms/pcbknowledge' \
  'http://localhost:not-a-port/realms/pcbknowledge' \
  'http://localhost:0/realms/pcbknowledge' \
  'http://localhost:65536/realms/pcbknowledge' \
  'http://localhost:8081/realms/pcbknowledge/extra' \
  'http://localhost:8081/realms/pcbknowledge?unexpected=true'
do
  set +e
  issuer_output=$(
    PCBKNOWLEDGE_LOCAL_CURATOR_SUBJECT=$managed_subject \
    PCBKNOWLEDGE_LOCAL_OIDC_ISSUER=$invalid_issuer \
      docker compose --profile tools run --rm --no-deps -T local-development-data 2>&1
  )
  issuer_result=$?
  set -e
  if [ "$issuer_result" -eq 0 ]; then
    echo "an invalid local issuer was incorrectly accepted" >&2
    exit 1
  fi
  case "$invalid_issuer" in
    *'@evil.example'* | *':not-a-port/'*)
      expected_issuer_error='local OIDC issuer port must be numeric'
      ;;
    *':0/'* | *':65536/'*)
      expected_issuer_error='local OIDC issuer port is outside 1..65535'
      ;;
    *)
      expected_issuer_error='local OIDC issuer must be the exact loopback pcbknowledge realm'
      ;;
  esac
  printf '%s\n' "$issuer_output" |
    grep -Fq "$expected_issuer_error" || {
      echo "invalid issuer did not fail at the exact local issuer boundary" >&2
      exit 1
    }
done

set +e
custom_port_output=$(
  PCBKNOWLEDGE_LOCAL_CURATOR_SUBJECT=$managed_subject \
  PCBKNOWLEDGE_LOCAL_OIDC_ISSUER=http://localhost:49152/realms/pcbknowledge \
    docker compose --profile tools run --rm --no-deps -T local-development-data 2>&1
)
custom_port_result=$?
set -e
if [ "$custom_port_result" -eq 0 ]; then
  echo "a different issuer unexpectedly replaced the trusted mapping" >&2
  exit 1
fi
printf '%s\n' "$custom_port_output" |
  grep -Fq 'local curator subject mapping conflicts with Keycloak' || {
    echo "a valid custom loopback port did not reach exact subject validation" >&2
    exit 1
  }
unset custom_port_output
unset expected_issuer_error issuer_output managed_subject

drift_installed=false
cleanup_membership_drift() {
  if [ "$drift_installed" = true ]; then
    docker compose exec -T postgres /bin/sh -s <<'CONTAINER_SH' >/dev/null
set -eu
PGPASSWORD=$(tr -d '\r\n' </run/secrets/postgres_password)
export PGPASSWORD
psql --host 127.0.0.1 --username pcbknowledge --dbname pcbknowledge \
  --no-psqlrc --quiet --set ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DELETE FROM identity.membership
 WHERE id IN (
   '019fe5df-728a-7581-99be-e456cd730fec',
   '019fe5df-728a-7581-99be-e46100000002'
 );
DELETE FROM identity.project
 WHERE id = '019fe5df-728a-7581-99be-e46000000001';
COMMIT;
SQL
CONTAINER_SH
    drift_installed=false
    "$script_dir/bootstrap-local-development.sh" >/dev/null || true
  fi
}
trap cleanup_membership_drift EXIT HUP INT TERM

docker compose exec -T postgres /bin/sh -s <<'CONTAINER_SH' >/dev/null
set -eu
PGPASSWORD=$(tr -d '\r\n' </run/secrets/postgres_password)
export PGPASSWORD
psql --host 127.0.0.1 --username pcbknowledge --dbname pcbknowledge \
  --no-psqlrc --quiet --set ON_ERROR_STOP=1 <<'SQL'
BEGIN;
INSERT INTO identity.project (id, organization_id, slug, display_name, active)
VALUES (
  '019fe5df-728a-7581-99be-e46000000001',
  '019fe5df-728a-7581-99be-e452971c8ff6',
  'bootstrap-drift-project',
  'Bootstrap Drift Project',
  true
);
INSERT INTO identity.membership (
  id, organization_id, external_subject_id, project_id, role
)
VALUES
  (
    '019fe5df-728a-7581-99be-e456cd730fec',
    '019fe5df-728a-7581-99be-e452971c8ff6',
    '019fe5df-728a-7581-99be-e454bb06ac4c',
    '019fe5df-728a-7581-99be-e4539921e503',
    'KNOWLEDGE_ADMIN'
  ),
  (
    '019fe5df-728a-7581-99be-e46100000002',
    '019fe5df-728a-7581-99be-e452971c8ff6',
    '019fe5df-728a-7581-99be-e454bb06ac4c',
    '019fe5df-728a-7581-99be-e46000000001',
    'DATA_CURATOR'
  );
COMMIT;
SQL
CONTAINER_SH
drift_installed=true

set +e
membership_output=$("$script_dir/bootstrap-local-development.sh" 2>&1)
membership_result=$?
set -e
if [ "$membership_result" -eq 0 ]; then
  echo "extra local curator memberships were incorrectly accepted" >&2
  exit 1
fi
printf '%s\n' "$membership_output" |
  grep -Fq 'local curator has membership outside its managed default project role' || {
    echo "membership drift did not fail at the exact-set boundary" >&2
    exit 1
  }
unset membership_output

set +e
disabled_output=$(
  PCBKNOWLEDGE_LOCAL_CURATOR_ACTION=assert \
    docker compose --profile tools run --rm --no-deps -T local-curator-keycloak 2>&1
)
disabled_result=$?
set -e
if [ "$disabled_result" -eq 0 ]; then
  echo "the local curator remained enabled after membership drift" >&2
  exit 1
fi
printf '%s\n' "$disabled_output" | grep -Fq 'managed local curator is disabled' || {
  echo "membership drift did not leave the local curator disabled" >&2
  exit 1
}
unset disabled_output

cleanup_membership_drift
trap - EXIT HUP INT TERM

database_state=$(docker compose exec -T postgres /bin/sh -s <<'CONTAINER_SH'
set -eu
PGPASSWORD=$(tr -d '\r\n' </run/secrets/postgres_password)
export PGPASSWORD
psql \
  --host 127.0.0.1 \
  --username pcbknowledge \
  --dbname pcbknowledge \
  --no-psqlrc \
  --tuples-only \
  --no-align \
  --set ON_ERROR_STOP=1 <<'SQL'
SELECT
  (SELECT count(*) = 1
     FROM identity.organization
    WHERE id = '019fe5df-728a-7581-99be-e452971c8ff6'
      AND slug = 'local-development'
      AND active)
  AND (SELECT count(*) = 1
         FROM identity.project
        WHERE id = '019fe5df-728a-7581-99be-e4539921e503'
          AND organization_id = '019fe5df-728a-7581-99be-e452971c8ff6'
          AND slug = 'default-project'
          AND active)
  AND (SELECT count(*) = 1
         FROM identity.external_subject
        WHERE id = '019fe5df-728a-7581-99be-e454bb06ac4c'
          AND subject_kind = 'HUMAN'
          AND active)
  AND (SELECT count(*) = 1
         FROM identity.membership
        WHERE external_subject_id = '019fe5df-728a-7581-99be-e454bb06ac4c'
          AND project_id = '019fe5df-728a-7581-99be-e4539921e503'
          AND role = 'DATA_CURATOR')
  AND (SELECT count(*) = 1
         FROM identity.membership
        WHERE external_subject_id = '019fe5df-728a-7581-99be-e454bb06ac4c')
  AND (SELECT count(*) = 1
         FROM source.source_organization
        WHERE id = '019fe5df-728a-7581-99be-e458c5032fb9')
  AND (SELECT count(*) = 1
         FROM source.access_scope
        WHERE id = '019fe5df-728a-7581-99be-e459279f1318'
          AND project_id = '019fe5df-728a-7581-99be-e4539921e503'
          AND scope_kind = 'PROJECT')
  AND (SELECT count(*) = 1
         FROM source.license_policy
        WHERE id = '019fe5df-728a-7581-99be-e45a23bb832e'
          AND allow_metadata_read
          AND allow_human_raw_access
          AND NOT allow_parse
          AND NOT allow_external_model
          AND NOT allow_local_model
          AND NOT allow_embedding
          AND NOT allow_agent_raw_access
          AND NOT allow_redistribution);
SQL
CONTAINER_SH
)
if [ "$database_state" != t ]; then
  echo "local development identity or intake policy state is not exact" >&2
  exit 1
fi

echo "Local identity bootstrap passed exact marker, issuer, subject, membership, and policy checks."
