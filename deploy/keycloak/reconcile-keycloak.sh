#!/bin/sh
set -eu
umask 077

realm=pcbknowledge
kcadm=/opt/keycloak/bin/kcadm.sh
config_file=/tmp/pcbknowledge-kcadm.config

read_secret() {
  if [ ! -s "$1" ]; then
    echo "required secret is missing or empty: $1" >&2
    exit 1
  fi
  tr -d '\r\n' <"$1"
}

secret_directory=${PCBKNOWLEDGE_SECRET_DIRECTORY:-/run/secrets}
admin_password=$(read_secret "$secret_directory/keycloak_admin_password")

export KC_CLI_PASSWORD=$admin_password
"$kcadm" config credentials \
  --config "$config_file" \
  --server http://keycloak:8080 \
  --realm master \
  --user pcbknowledge-admin >/dev/null
unset KC_CLI_PASSWORD admin_password

# Realm imports do not overwrite an existing database. Reapply the top-level
# login posture explicitly so drift cannot reopen self-service account paths.
# `external` keeps loopback/private-network HTTP usable for the local stack;
# reviewed production deployments terminate TLS at the trusted proxy.
"$kcadm" update "realms/$realm" --config "$config_file" \
  -s enabled=true \
  -s sslRequired=external \
  -s registrationAllowed=false \
  -s resetPasswordAllowed=false \
  -s rememberMe=false \
  -s bruteForceProtected=true >/dev/null

for role in DATA_CURATOR DOMAIN_REVIEWER KNOWLEDGE_ADMIN AUDITOR AGENT_SERVICE; do
  if ! "$kcadm" get "roles/$role" --config "$config_file" -r "$realm" >/dev/null 2>&1; then
    "$kcadm" create roles --config "$config_file" -r "$realm" -s "name=$role" >/dev/null
  fi
done

reconcile_client() {
  client_id=$1
  definition=$2
  client_uuid=$(
    "$kcadm" get clients --config "$config_file" -r "$realm" \
      -q "clientId=$client_id" --fields id --format csv --noquotes
  )
  if [ -z "$client_uuid" ]; then
    "$kcadm" create clients --config "$config_file" -r "$realm" -f "$definition" >/dev/null
  else
    "$kcadm" update "clients/$client_uuid" --config "$config_file" -r "$realm" \
      -f "$definition" >/dev/null
  fi
  "$kcadm" get clients --config "$config_file" -r "$realm" \
    -q "clientId=$client_id" --fields id --format csv --noquotes
}

api_uuid=$(reconcile_client pcbknowledge-api /opt/pcbknowledge/keycloak/pcbknowledge-api-client.json)
curator_uuid=$(reconcile_client pcbknowledge-curator-web /opt/pcbknowledge/keycloak/pcbknowledge-curator-client.json)
service_uuid=$(
  reconcile_client \
    pcbknowledge-agent-service \
    "$secret_directory/keycloak-agent-client.json"
)

test -n "$api_uuid"
test -n "$curator_uuid"
test -n "$service_uuid"

write_roles() {
  output=$1
  shift
  first=true
  printf '[' >"$output"
  for role in "$@"; do
    if [ "$first" = true ]; then
      first=false
    else
      printf ',' >>"$output"
    fi
    "$kcadm" get "roles/$role" --config "$config_file" -r "$realm" >>"$output"
  done
  printf ']\n' >>"$output"
}

write_roles /tmp/human-scope-roles.json DATA_CURATOR DOMAIN_REVIEWER KNOWLEDGE_ADMIN AUDITOR
write_roles /tmp/service-scope-roles.json AGENT_SERVICE

# Reconciliation is subtractive as well as additive: a previously widened client
# must not keep roles that cross the human/service boundary.
"$kcadm" delete "clients/$curator_uuid/scope-mappings/realm" \
  --config "$config_file" -r "$realm" -f /tmp/service-scope-roles.json >/dev/null
"$kcadm" delete "clients/$service_uuid/scope-mappings/realm" \
  --config "$config_file" -r "$realm" -f /tmp/human-scope-roles.json >/dev/null
"$kcadm" create "clients/$curator_uuid/scope-mappings/realm" \
  --config "$config_file" -r "$realm" -f /tmp/human-scope-roles.json >/dev/null
"$kcadm" create "clients/$service_uuid/scope-mappings/realm" \
  --config "$config_file" -r "$realm" -f /tmp/service-scope-roles.json >/dev/null

service_username=service-account-pcbknowledge-agent-service
service_user_id=$(
  "$kcadm" get users --config "$config_file" -r "$realm" \
    -q "username=$service_username" --fields id --format csv --noquotes
)
test -n "$service_user_id"
"$kcadm" remove-roles --config "$config_file" -r "$realm" \
  --uid "$service_user_id" \
  --rolename DATA_CURATOR \
  --rolename DOMAIN_REVIEWER \
  --rolename KNOWLEDGE_ADMIN \
  --rolename AUDITOR >/dev/null
"$kcadm" add-roles --config "$config_file" -r "$realm" \
  --uid "$service_user_id" --rolename AGENT_SERVICE >/dev/null

: >"$config_file"
echo "Keycloak realm security, clients, role scopes, and service identity are reconciled."
