#!/bin/sh
set -eu

read_secret() {
  if [ ! -s "$2" ]; then
    echo "required secret is missing or empty: $2" >&2
    exit 1
  fi
  secret_value=$(tr -d '\r\n' <"$2")
  if [ -z "$secret_value" ]; then
    echo "required secret is empty: $2" >&2
    exit 1
  fi
  export "$1=$secret_value"
}

database_username=${PCBKNOWLEDGE_DATABASE_USERNAME:-pcbknowledge_app}
case "$database_username" in
  pcbknowledge_app)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD /run/secrets/application_db_password
    ;;
  pcbknowledge_worker)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD /run/secrets/worker_db_password
    ;;
  pcbknowledge_verifier)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD /run/secrets/verifier_db_password
    ;;
  pcbknowledge)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD /run/secrets/postgres_password
    ;;
  *)
    echo "unsupported database role: $database_username" >&2
    exit 1
    ;;
esac
read_secret PCBKNOWLEDGE_S3_ACCESS_KEY /run/secrets/seaweedfs_access_key
read_secret PCBKNOWLEDGE_S3_SECRET_KEY /run/secrets/seaweedfs_secret_key

export PCBKNOWLEDGE_DATABASE_DSN="postgresql+psycopg://${database_username}:${PCBKNOWLEDGE_DATABASE_PASSWORD}@postgres:5432/pcbknowledge"
export AWS_ACCESS_KEY_ID="$PCBKNOWLEDGE_S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$PCBKNOWLEDGE_S3_SECRET_KEY"

exec "$@"
