#!/bin/sh
set -eu

secret_directory=${PCBKNOWLEDGE_SECRET_DIRECTORY:-/run/secrets}
secret_file=$secret_directory/keycloak_db_password
if [ ! -s "$secret_file" ]; then
  echo "Keycloak database password secret is required" >&2
  exit 1
fi

keycloak_password=$(tr -d '\r\n' <"$secret_file")
if [ -z "$keycloak_password" ]; then
  echo "Keycloak database password secret is empty" >&2
  exit 1
fi

psql --set=ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=keycloak_password="$keycloak_password" <<'SQL'
SELECT 'CREATE ROLE keycloak LOGIN PASSWORD ' || quote_literal(:'keycloak_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'keycloak') \gexec

SELECT 'CREATE DATABASE keycloak OWNER keycloak'
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_database WHERE datname = 'keycloak') \gexec
SQL
