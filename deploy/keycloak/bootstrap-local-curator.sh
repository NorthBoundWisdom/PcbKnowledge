#!/bin/sh
set -eu
umask 077

realm=pcbknowledge
username=pcbknowledge-curator
managed_email=pcbknowledge-curator@local.invalid
action=${PCBKNOWLEDGE_LOCAL_CURATOR_ACTION:-}
kcadm=/opt/keycloak/bin/kcadm.sh
temporary_prefix=/tmp/pcbknowledge-local-curator.
temporary_directory=$(mktemp -d "${temporary_prefix}XXXXXX")
case "$temporary_directory" in
  "$temporary_prefix"*) ;;
  *)
    echo "temporary directory is outside the expected boundary" >&2
    exit 1
    ;;
esac
chmod 700 "$temporary_directory"
config_file=$temporary_directory/kcadm.config
password_payload=$temporary_directory/password.json
user_payload=$temporary_directory/user.json
group_payload=$temporary_directory/group.json

cleanup() {
  if [ -n "${temporary_directory:-}" ]; then
    case "$temporary_directory" in
      "$temporary_prefix"*)
        for temporary_file in \
          "$config_file" "$password_payload" "$user_payload" "$group_payload"
        do
          if [ -f "$temporary_file" ] && [ ! -L "$temporary_file" ]; then
            : >"$temporary_file"
            rm -f "$temporary_file"
          fi
        done
        rmdir "$temporary_directory" 2>/dev/null || true
        temporary_directory=
        ;;
    esac
  fi
}
trap cleanup EXIT HUP INT TERM

read_secret() {
  if [ ! -s "$1" ]; then
    echo "required secret is missing or empty: $1" >&2
    exit 1
  fi
  tr -d '\r\n' <"$1"
}

find_user_id() {
  ids=$(
    "$kcadm" get users --config "$config_file" -r "$realm" \
      -q "username=$username" -q exact=true \
      --fields id --format csv --noquotes
  )
  count=$(printf '%s\n' "$ids" | sed '/^$/d' | wc -l | tr -d ' ')
  case "$count" in
    0) return 1 ;;
    1) printf '%s\n' "$ids" ;;
    *)
      echo "multiple exact local curator users exist" >&2
      exit 1
      ;;
  esac
}

require_managed_user() {
  user_id=$1
  state=$(
    "$kcadm" get "users/$user_id" --config "$config_file" -r "$realm" \
      --fields username,email,emailVerified
  )
  printf '%s\n' "$state" |
    grep -Eq '"username"[[:space:]]*:[[:space:]]*"pcbknowledge-curator"' || {
      echo "local curator username does not match its managed identity" >&2
      exit 1
    }
  printf '%s\n' "$state" |
    grep -Eq '"email"[[:space:]]*:[[:space:]]*"pcbknowledge-curator@local.invalid"' || {
      echo "refusing to take over an unmanaged Keycloak user" >&2
      exit 1
    }
  printf '%s\n' "$state" |
    grep -Eq '"emailVerified"[[:space:]]*:[[:space:]]*true' || {
      echo "managed local curator email is not verified" >&2
      exit 1
    }
  group_ids=$(
    "$kcadm" get "users/$user_id/groups" --config "$config_file" -r "$realm" \
      --fields id --format csv --noquotes
  )
  group_count=$(printf '%s\n' "$group_ids" | sed '/^$/d' | wc -l | tr -d ' ')
  if [ "$group_count" -ne 1 ] || [ "$group_ids" != "$managed_group_id" ]; then
    echo "refusing to take over a local curator without its exact private managed marker" >&2
    exit 1
  fi
}

find_managed_group_id() {
  ids=$(
    "$kcadm" get groups --config "$config_file" -r "$realm" \
      -q "search=$managed_group_name" -q exact=true \
      --fields id --format csv --noquotes
  )
  count=$(printf '%s\n' "$ids" | sed '/^$/d' | wc -l | tr -d ' ')
  case "$count" in
    0) return 1 ;;
    1) printf '%s\n' "$ids" ;;
    *)
      echo "multiple private local bootstrap marker groups exist" >&2
      exit 1
      ;;
  esac
}

user_has_role() {
  user_id=$1
  role=$2
  "$kcadm" get "users/$user_id/role-mappings/realm" \
    --config "$config_file" -r "$realm" \
    --fields name --format csv --noquotes |
    grep -Fxq "$role"
}

assert_role_boundary() {
  user_id=$1
  user_has_role "$user_id" DATA_CURATOR || {
    echo "local curator is missing DATA_CURATOR" >&2
    exit 1
  }
  for forbidden_role in DOMAIN_REVIEWER KNOWLEDGE_ADMIN AUDITOR AGENT_SERVICE; do
    if user_has_role "$user_id" "$forbidden_role"; then
      echo "local curator has forbidden role: $forbidden_role" >&2
      exit 1
    fi
  done
}

assert_enabled() {
  user_id=$1
  state=$(
    "$kcadm" get "users/$user_id" --config "$config_file" -r "$realm" \
      --fields enabled
  )
  printf '%s\n' "$state" |
    grep -Eq '"enabled"[[:space:]]*:[[:space:]]*true' || {
      echo "managed local curator is disabled" >&2
      exit 1
    }
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

managed_marker=$(read_secret "$secret_directory/local_curator_marker")
case "$managed_marker" in
  *[!0-9a-f]* | "")
    echo "local curator managed marker must be random lowercase hexadecimal" >&2
    exit 1
    ;;
esac
if [ "${#managed_marker}" -ne 64 ]; then
  echo "local curator managed marker must contain exactly 64 hexadecimal characters" >&2
  exit 1
fi
managed_group_name=pcbknowledge-local-bootstrap-$managed_marker
unset managed_marker
if ! managed_group_id=$(find_managed_group_id); then
  printf '{"name":"%s"}\n' "$managed_group_name" >"$group_payload"
  "$kcadm" create groups --config "$config_file" -r "$realm" \
    -f "$group_payload" >/dev/null
  : >"$group_payload"
  managed_group_id=$(find_managed_group_id)
fi

case "$action" in
  prepare)
    if ! user_id=$(find_user_id); then
      printf '%s\n' \
        '{' \
        '  "username": "pcbknowledge-curator",' \
        '  "enabled": false,' \
        '  "firstName": "Local",' \
        '  "lastName": "Curator",' \
        '  "email": "pcbknowledge-curator@local.invalid",' \
        '  "emailVerified": true' \
        '}' >"$user_payload"
      "$kcadm" create users --config "$config_file" -r "$realm" \
        -f "$user_payload" >/dev/null
      user_id=$(find_user_id)
      "$kcadm" update "users/$user_id/groups/$managed_group_id" \
        --config "$config_file" -r "$realm" -n >/dev/null
    fi
    require_managed_user "$user_id"

    # Disable first: a partially reconciled cross-system identity must never log in.
    "$kcadm" update "users/$user_id" --config "$config_file" -r "$realm" \
      -s enabled=false \
      -s firstName=Local \
      -s lastName=Curator \
      -s "email=$managed_email" \
      -s emailVerified=true \
      -s 'requiredActions=[]' >/dev/null

    local_password=$(read_secret "$secret_directory/local_curator_password")
    case "$local_password" in
      *[!0-9a-f]* | "")
        echo "local curator password must be random lowercase hexadecimal" >&2
        exit 1
        ;;
    esac
    if [ "${#local_password}" -ne 64 ]; then
      echo "local curator password must contain exactly 64 hexadecimal characters" >&2
      exit 1
    fi
    printf '{"type":"password","value":"%s","temporary":false}\n' \
      "$local_password" >"$password_payload"
    unset local_password
    "$kcadm" update "users/$user_id/reset-password" \
      --config "$config_file" -r "$realm" -f "$password_payload" >/dev/null
    : >"$password_payload"

    "$kcadm" remove-roles --config "$config_file" -r "$realm" \
      --uid "$user_id" \
      --rolename DOMAIN_REVIEWER \
      --rolename KNOWLEDGE_ADMIN \
      --rolename AUDITOR \
      --rolename AGENT_SERVICE >/dev/null
    "$kcadm" add-roles --config "$config_file" -r "$realm" \
      --uid "$user_id" --rolename DATA_CURATOR >/dev/null
    assert_role_boundary "$user_id"
    printf '%s\n' "$user_id"
    ;;
  enable)
    user_id=$(find_user_id) || {
      echo "managed local curator is missing" >&2
      exit 1
    }
    require_managed_user "$user_id"
    assert_role_boundary "$user_id"
    "$kcadm" update "users/$user_id" --config "$config_file" -r "$realm" \
      -s enabled=true >/dev/null
    assert_role_boundary "$user_id"
    assert_enabled "$user_id"
    printf '%s\n' "$user_id"
    ;;
  disable)
    if user_id=$(find_user_id); then
      require_managed_user "$user_id"
      "$kcadm" update "users/$user_id" --config "$config_file" -r "$realm" \
        -s enabled=false >/dev/null
    fi
    ;;
  assert)
    user_id=$(find_user_id) || {
      echo "managed local curator is missing" >&2
      exit 1
    }
    require_managed_user "$user_id"
    assert_role_boundary "$user_id"
    assert_enabled "$user_id"
    printf '%s\n' "$user_id"
    ;;
  *)
    echo "PCBKNOWLEDGE_LOCAL_CURATOR_ACTION must be prepare, enable, disable, or assert" >&2
    exit 2
    ;;
esac
