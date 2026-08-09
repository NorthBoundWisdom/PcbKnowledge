#!/bin/sh
set -eu
umask 077

read_secret() {
  if [ ! -s "$1" ]; then
    echo "required database secret is missing or empty: $1" >&2
    exit 1
  fi
  tr -d '\r\n' <"$1"
}

admin_password=$(read_secret /run/secrets/postgres_password)
application_password=$(read_secret /run/secrets/application_db_password)
worker_password=$(read_secret /run/secrets/worker_db_password)
verifier_password=$(read_secret /run/secrets/verifier_db_password)
export PGPASSWORD=$admin_password

psql \
  --host postgres \
  --username pcbknowledge \
  --dbname pcbknowledge \
  --set ON_ERROR_STOP=1 \
  --set application_password="$application_password" \
  --set worker_password="$worker_password" \
  --set verifier_password="$verifier_password" <<'SQL'
SELECT 'CREATE ROLE pcbknowledge_app'
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pcbknowledge_app'
) \gexec

ALTER ROLE pcbknowledge_app
  WITH LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'application_password';
ALTER ROLE pcbknowledge_app SET row_security = on;

SELECT pg_catalog.format('REVOKE %I FROM pcbknowledge_app', granted.rolname)
FROM pg_catalog.pg_auth_members AS member_map
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
WHERE member_role.rolname = 'pcbknowledge_app'
\gexec

SELECT pg_catalog.format('REVOKE pcbknowledge_app FROM %I', member_role.rolname)
FROM pg_catalog.pg_auth_members AS member_map
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
WHERE granted.rolname = 'pcbknowledge_app'
\gexec

SELECT 'CREATE ROLE pcbknowledge_worker'
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pcbknowledge_worker'
) \gexec

ALTER ROLE pcbknowledge_worker
  WITH LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'worker_password';
ALTER ROLE pcbknowledge_worker SET row_security = on;

SELECT pg_catalog.format('REVOKE %I FROM pcbknowledge_worker', granted.rolname)
FROM pg_catalog.pg_auth_members AS member_map
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
WHERE member_role.rolname = 'pcbknowledge_worker'
\gexec

SELECT pg_catalog.format('REVOKE pcbknowledge_worker FROM %I', member_role.rolname)
FROM pg_catalog.pg_auth_members AS member_map
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
WHERE granted.rolname = 'pcbknowledge_worker'
\gexec

SELECT 'CREATE ROLE pcbknowledge_verifier'
WHERE NOT EXISTS (
  SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pcbknowledge_verifier'
) \gexec

ALTER ROLE pcbknowledge_verifier
  WITH LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  PASSWORD :'verifier_password';
ALTER ROLE pcbknowledge_verifier SET row_security = on;

SELECT pg_catalog.format('REVOKE %I FROM pcbknowledge_verifier', granted.rolname)
FROM pg_catalog.pg_auth_members AS member_map
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
WHERE member_role.rolname = 'pcbknowledge_verifier'
\gexec

SELECT pg_catalog.format('REVOKE pcbknowledge_verifier FROM %I', member_role.rolname)
FROM pg_catalog.pg_auth_members AS member_map
JOIN pg_catalog.pg_roles AS member_role ON member_role.oid = member_map.member
JOIN pg_catalog.pg_roles AS granted ON granted.oid = member_map.roleid
WHERE granted.rolname = 'pcbknowledge_verifier'
\gexec
SQL

unset PGPASSWORD admin_password application_password worker_password verifier_password
echo "PostgreSQL application, worker, and verifier roles are present without owner or RLS-bypass privileges."
