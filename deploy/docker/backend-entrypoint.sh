#!/bin/sh
set -eu

# Root-only secret loading must not resolve utilities from the application-owned
# virtual environment. Restore that path only after setpriv has dropped the
# command to the dedicated runtime account.
trusted_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
application_path=/workspace/.venv/bin:$trusted_path
PATH=$trusted_path
export PATH

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

secret_directory=${PCBKNOWLEDGE_SECRET_DIRECTORY:-/run/secrets}
database_username=${PCBKNOWLEDGE_DATABASE_USERNAME:-pcbknowledge_app}
case "$database_username" in
  pcbknowledge_app)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD "$secret_directory/application_db_password"
    ;;
  pcbknowledge_worker)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD "$secret_directory/worker_db_password"
    ;;
  pcbknowledge_verifier)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD "$secret_directory/verifier_db_password"
    ;;
  pcbknowledge)
    read_secret PCBKNOWLEDGE_DATABASE_PASSWORD "$secret_directory/postgres_password"
    ;;
  *)
    echo "unsupported database role: $database_username" >&2
    exit 1
    ;;
esac
read_secret PCBKNOWLEDGE_S3_ACCESS_KEY "$secret_directory/seaweedfs_access_key"
read_secret PCBKNOWLEDGE_S3_SECRET_KEY "$secret_directory/seaweedfs_secret_key"

export PCBKNOWLEDGE_DATABASE_DSN="postgresql+psycopg://${database_username}:${PCBKNOWLEDGE_DATABASE_PASSWORD}@postgres:5432/pcbknowledge"
export AWS_ACCESS_KEY_ID="$PCBKNOWLEDGE_S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$PCBKNOWLEDGE_S3_SECRET_KEY"

if [ "$(id -u)" -eq 0 ]; then
  PATH=$application_path
  export PATH
  exec /usr/bin/setpriv \
    --reuid=pcbknowledge \
    --regid=pcbknowledge \
    --init-groups \
    -- "$@"
fi
if [ "$(id -un)" != pcbknowledge ]; then
  echo "backend entrypoint must run as root or pcbknowledge" >&2
  exit 1
fi
PATH=$application_path
export PATH
exec "$@"
