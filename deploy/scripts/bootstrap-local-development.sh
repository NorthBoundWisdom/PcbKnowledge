#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$repo_root"

command -v docker >/dev/null 2>&1 || {
  echo "docker is required for local identity bootstrap" >&2
  exit 1
}
docker compose version >/dev/null
for required_service in postgres keycloak; do
  if ! docker compose ps --status running --services | grep -Fxq "$required_service"; then
    echo "a running $required_service service is required for local identity bootstrap" >&2
    exit 1
  fi
done

password_file=deploy/secrets/local_curator_password
if [ ! -s "$password_file" ]; then
  echo "local curator password is missing; run Config first" >&2
  exit 1
fi

prepared_subject=
completed=false
disable_incomplete_identity() {
  if [ -n "$prepared_subject" ] && [ "$completed" != true ]; then
    echo "Local identity bootstrap did not complete; keeping the curator disabled." >&2
    PCBKNOWLEDGE_LOCAL_CURATOR_ACTION=disable \
      docker compose --profile tools run --rm --no-deps -T \
      local-curator-keycloak >/dev/null || true
  fi
}
trap disable_incomplete_identity EXIT HUP INT TERM

prepared_subject=$(
  PCBKNOWLEDGE_LOCAL_CURATOR_ACTION=prepare \
    docker compose --profile tools run --rm --no-deps -T local-curator-keycloak
)
case "$prepared_subject" in
  ????????-????-????-????-????????????) ;;
  *)
    echo "Keycloak returned an invalid local curator subject" >&2
    exit 1
    ;;
esac
case "$prepared_subject" in
  *[!0-9a-f-]*)
    echo "Keycloak returned an invalid local curator subject" >&2
    exit 1
    ;;
esac

local_issuer="http://localhost:${PCBKNOWLEDGE_KEYCLOAK_PORT:-8081}/realms/pcbknowledge"
PCBKNOWLEDGE_LOCAL_CURATOR_SUBJECT=$prepared_subject \
PCBKNOWLEDGE_LOCAL_OIDC_ISSUER=$local_issuer \
  docker compose --profile tools run --rm --no-deps -T local-development-data >/dev/null

enabled_subject=$(
  PCBKNOWLEDGE_LOCAL_CURATOR_ACTION=enable \
    docker compose --profile tools run --rm --no-deps -T local-curator-keycloak
)
if [ "$enabled_subject" != "$prepared_subject" ]; then
  echo "Keycloak curator subject changed during bootstrap" >&2
  exit 1
fi

completed=true
trap - EXIT HUP INT TERM

printf '%s\n' \
  'Local development identity is ready.' \
  'Username: pcbknowledge-curator' \
  'Password file: deploy/secrets/local_curator_password (owner-only; value not printed)' \
  'Organization: Local Development' \
  'Project: Default Project'
