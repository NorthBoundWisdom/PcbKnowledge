#!/bin/sh
set -eu

read_required_secret() {
  if [ ! -s "$2" ]; then
    echo "required secret is missing or empty: $2" >&2
    exit 1
  fi
  value=$(tr -d '\r\n' <"$2")
  if [ -z "$value" ]; then
    echo "required secret is empty: $2" >&2
    exit 1
  fi
  export "$1=$value"
}

read_required_secret KC_DB_PASSWORD /run/secrets/keycloak_db_password
read_required_secret KC_BOOTSTRAP_ADMIN_PASSWORD /run/secrets/keycloak_admin_password

exec /opt/keycloak/bin/kc.sh "$@"
