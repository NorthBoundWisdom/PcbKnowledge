#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
secret_dir=$(CDPATH= cd -- "$script_dir/../secrets" && pwd)

command -v openssl >/dev/null 2>&1 || {
  echo "openssl is required to generate local development secrets" >&2
  exit 1
}

umask 077

generate_hex() {
  target=$1
  bytes=$2
  if [ ! -e "$target" ]; then
    openssl rand -hex "$bytes" >"$target"
  fi
  if [ ! -s "$target" ]; then
    echo "required secret is empty: $target" >&2
    exit 1
  fi
  chmod 600 "$target"
}

generate_hex "$secret_dir/postgres_password" 32
generate_hex "$secret_dir/keycloak_db_password" 32
generate_hex "$secret_dir/keycloak_admin_password" 32
generate_hex "$secret_dir/seaweedfs_access_key" 16
generate_hex "$secret_dir/seaweedfs_secret_key" 32
generate_hex "$secret_dir/grafana_admin_password" 32

echo "Local secret files are present with owner-only permissions."
