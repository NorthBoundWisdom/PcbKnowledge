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
generate_hex "$secret_dir/application_db_password" 32
generate_hex "$secret_dir/worker_db_password" 32
generate_hex "$secret_dir/keycloak_db_password" 32
generate_hex "$secret_dir/keycloak_admin_password" 32
generate_hex "$secret_dir/agent_service_client_secret" 32
generate_hex "$secret_dir/seaweedfs_access_key" 16
generate_hex "$secret_dir/seaweedfs_secret_key" 32
generate_hex "$secret_dir/seaweedfs_admin_access_key" 16
generate_hex "$secret_dir/seaweedfs_admin_secret_key" 32
generate_hex "$secret_dir/seaweedfs_worker_access_key" 16
generate_hex "$secret_dir/seaweedfs_worker_secret_key" 32
generate_hex "$secret_dir/grafana_admin_password" 32

render_secret_template() {
  template=$1
  output=$2
  placeholder=$3
  replacement_file=$4
  if ! grep -q "$placeholder" "$template"; then
    echo "secret template placeholder is missing: $template" >&2
    exit 1
  fi
  replacement=$(tr -d '\r\n' <"$replacement_file")
  if [ -z "$replacement" ]; then
    echo "template replacement secret is empty: $replacement_file" >&2
    exit 1
  fi
  temporary="$output.tmp"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      *"$placeholder"*)
        prefix=${line%%"$placeholder"*}
        suffix=${line#*"$placeholder"}
        printf '%s%s%s\n' "$prefix" "$replacement" "$suffix"
        ;;
      *) printf '%s\n' "$line" ;;
    esac
  done <"$template" >"$temporary"
  chmod 600 "$temporary"
  mv "$temporary" "$output"
}

render_secret_template \
  "$script_dir/../keycloak/pcbknowledge-realm.template.json" \
  "$secret_dir/keycloak-realm.json" \
  __PCBKNOWLEDGE_AGENT_SERVICE_SECRET__ \
  "$secret_dir/agent_service_client_secret"
render_secret_template \
  "$script_dir/../keycloak/pcbknowledge-agent-client.template.json" \
  "$secret_dir/keycloak-agent-client.json" \
  __PCBKNOWLEDGE_AGENT_SERVICE_SECRET__ \
  "$secret_dir/agent_service_client_secret"

echo "Local secret files and rendered Keycloak configuration are present with owner-only permissions."
