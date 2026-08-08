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

read_secret PCBKNOWLEDGE_POSTGRES_PASSWORD /run/secrets/postgres_password
read_secret PCBKNOWLEDGE_S3_ACCESS_KEY /run/secrets/seaweedfs_access_key
read_secret PCBKNOWLEDGE_S3_SECRET_KEY /run/secrets/seaweedfs_secret_key

export PCBKNOWLEDGE_DATABASE_DSN="postgresql+psycopg://pcbknowledge:${PCBKNOWLEDGE_POSTGRES_PASSWORD}@postgres:5432/pcbknowledge"
export AWS_ACCESS_KEY_ID="$PCBKNOWLEDGE_S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$PCBKNOWLEDGE_S3_SECRET_KEY"

exec "$@"
