#!/bin/sh
set -eu

source_directory=/run/secrets
target_directory=/run/pcbknowledge-postgres-secrets

stage_secret() {
  name=$1
  source_file=$source_directory/$name
  target_file=$target_directory/$name
  temporary_file=$target_directory/.$name.tmp.$$

  if [ ! -s "$source_file" ]; then
    echo "required PostgreSQL secret is missing or empty: $source_file" >&2
    exit 1
  fi
  cp "$source_file" "$temporary_file"
  chown root:postgres "$temporary_file"
  chmod 440 "$temporary_file"
  mv -f "$temporary_file" "$target_file"
}

if [ "$(id -u)" -ne 0 ]; then
  echo "PostgreSQL secret staging must start as root" >&2
  exit 1
fi

umask 077
mkdir -p "$target_directory"
chown root:root "$target_directory"
chmod 711 "$target_directory"
stage_secret postgres_password
stage_secret keycloak_db_password

export PCBKNOWLEDGE_SECRET_DIRECTORY=$target_directory
export POSTGRES_PASSWORD_FILE=$target_directory/postgres_password

exec docker-entrypoint.sh "$@"
