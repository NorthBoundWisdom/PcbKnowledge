#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
secret_dir=$(CDPATH= cd -- "$script_dir/../secrets" && pwd)

command -v openssl >/dev/null 2>&1 || {
  echo "openssl is required to rotate local development secrets" >&2
  exit 1
}

umask 077
temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/pcbknowledge-db-secrets.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM

openssl rand -hex 32 >"$temporary_dir/application_db_password"
openssl rand -hex 32 >"$temporary_dir/worker_db_password"
chmod 600 \
  "$temporary_dir/application_db_password" \
  "$temporary_dir/worker_db_password"
mv "$temporary_dir/application_db_password" "$secret_dir/application_db_password"
mv "$temporary_dir/worker_db_password" "$secret_dir/worker_db_password"

echo "Local application and worker database credentials were rotated."
echo "Run the PostgreSQL role reconciler and recreate API/worker processes next."
