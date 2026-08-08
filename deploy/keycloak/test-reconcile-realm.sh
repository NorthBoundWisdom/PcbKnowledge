#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
cd "$repo_root"

command -v docker >/dev/null 2>&1 || {
  echo "docker is required for the live Keycloak reconciliation test" >&2
  exit 1
}

if ! docker compose ps --status running --services | grep -Fxq keycloak; then
  echo "a running Compose Keycloak service is required" >&2
  exit 1
fi

admin_action() {
  mode=$1
  docker compose --profile tools run --rm --no-deps --quiet-pull -T \
    --entrypoint /bin/sh keycloak-reconcile -s "$mode" <<'CONTAINER_SH'
set -eu
umask 077

mode=$1
realm=pcbknowledge
kcadm=/opt/keycloak/bin/kcadm.sh
config_file=/tmp/pcbknowledge-kcadm-test.config

if [ ! -s /run/secrets/keycloak_admin_password ]; then
  echo "Keycloak admin secret is missing" >&2
  exit 1
fi
admin_password=$(tr -d '\r\n' </run/secrets/keycloak_admin_password)
export KC_CLI_PASSWORD=$admin_password
"$kcadm" config credentials \
  --config "$config_file" \
  --server http://keycloak:8080 \
  --realm master \
  --user pcbknowledge-admin >/dev/null
unset KC_CLI_PASSWORD admin_password

assert_value() {
  state=$1
  property=$2
  expected=$3
  printf '%s\n' "$state" |
    grep -Eq '"'"$property"'"[[:space:]]*:[[:space:]]*'"$expected"'([,}]|$)'
}

case "$mode" in
  drift)
    "$kcadm" update "realms/$realm" --config "$config_file" \
      -s sslRequired=none \
      -s registrationAllowed=true \
      -s resetPasswordAllowed=true \
      -s rememberMe=true \
      -s bruteForceProtected=false >/dev/null
    ;;
  assert-drifted)
    state=$("$kcadm" get "realms/$realm" --config "$config_file" \
      --fields sslRequired,registrationAllowed,resetPasswordAllowed,rememberMe,bruteForceProtected)
    assert_value "$state" sslRequired '"none"'
    assert_value "$state" registrationAllowed true
    assert_value "$state" resetPasswordAllowed true
    assert_value "$state" rememberMe true
    assert_value "$state" bruteForceProtected false
    ;;
  assert-secure)
    state=$("$kcadm" get "realms/$realm" --config "$config_file" \
      --fields sslRequired,registrationAllowed,resetPasswordAllowed,rememberMe,bruteForceProtected)
    assert_value "$state" sslRequired '"external"'
    assert_value "$state" registrationAllowed false
    assert_value "$state" resetPasswordAllowed false
    assert_value "$state" rememberMe false
    assert_value "$state" bruteForceProtected true
    ;;
  *)
    echo "unknown reconciliation test action" >&2
    exit 1
    ;;
esac

: >"$config_file"
CONTAINER_SH
}

reconcile() {
  docker compose --profile tools run --rm keycloak-reconcile
}

drifted=false
restore_if_needed() {
  if [ "$drifted" = true ]; then
    echo "Restoring Keycloak realm security after interrupted drift test." >&2
    reconcile
  fi
}
trap restore_if_needed EXIT

admin_action drift
drifted=true
admin_action assert-drifted
reconcile
admin_action assert-secure
reconcile
admin_action assert-secure
drifted=false

echo "Keycloak realm drift converged and a second reconciliation was idempotent."
