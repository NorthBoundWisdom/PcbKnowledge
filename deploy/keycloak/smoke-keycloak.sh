#!/bin/sh
set -eu
umask 077

issuer=${PCBKNOWLEDGE_KEYCLOAK_ISSUER_URL:-http://localhost:8081/realms/pcbknowledge}
secret_file=${PCBKNOWLEDGE_AGENT_SERVICE_SECRET_FILE:-deploy/secrets/agent_service_client_secret}

for dependency in curl jq openssl; do
  command -v "$dependency" >/dev/null 2>&1 || {
    echo "$dependency is required for the Keycloak smoke check" >&2
    exit 1
  }
done

if [ ! -s "$secret_file" ]; then
  echo "service client secret is missing or empty: $secret_file" >&2
  exit 1
fi

temporary_directory=$(mktemp -d "${TMPDIR:-/tmp}/pcbknowledge-keycloak-smoke.XXXXXX")
cleanup() {
  rm -f \
    "$temporary_directory/discovery.json" \
    "$temporary_directory/service-secret" \
    "$temporary_directory/token-response.json" \
    "$temporary_directory/token-payload.json"
  rmdir "$temporary_directory"
}
trap cleanup EXIT HUP INT TERM

discovery_file=$temporary_directory/discovery.json
curl --fail --silent --show-error \
  "$issuer/.well-known/openid-configuration" \
  --output "$discovery_file"

jq --exit-status \
  --arg issuer "$issuer" \
  '.issuer == $issuer
   and (.response_types_supported | index("code") != null)
   and (.code_challenge_methods_supported | index("S256") != null)
   and (.grant_types_supported | index("client_credentials") != null)' \
  "$discovery_file" >/dev/null

authorization_endpoint=$(jq --exit-status --raw-output '.authorization_endpoint' "$discovery_file")
token_endpoint=$(jq --exit-status --raw-output '.token_endpoint' "$discovery_file")

verifier=pcbknowledge-pkce-smoke-verifier-000000000000000000000000
challenge=$(
  printf '%s' "$verifier" |
    openssl dgst -sha256 -binary |
    openssl base64 -A |
    tr '+/' '-_' |
    tr -d '='
)
authorization_status=$(
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --get "$authorization_endpoint" \
    --data-urlencode client_id=pcbknowledge-curator-web \
    --data-urlencode response_type=code \
    --data-urlencode scope='openid profile email roles' \
    --data-urlencode redirect_uri=http://localhost:8080/auth/callback \
    --data-urlencode code_challenge="$challenge" \
    --data-urlencode code_challenge_method=S256 \
    --data-urlencode state=nonsecret-smoke-state \
    --data-urlencode nonce=nonsecret-smoke-nonce \
    --data-urlencode prompt=none
)
case "$authorization_status" in
  302 | 303) ;;
  *)
    echo "PKCE authorization request was not accepted (HTTP $authorization_status)" >&2
    exit 1
    ;;
esac

tr -d '\r\n' <"$secret_file" >"$temporary_directory/service-secret"
chmod 600 "$temporary_directory/service-secret"
curl --fail --silent --show-error \
  --request POST "$token_endpoint" \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=client_credentials \
  --data-urlencode client_id=pcbknowledge-agent-service \
  --data-urlencode "client_secret@$temporary_directory/service-secret" \
  --output "$temporary_directory/token-response.json"

jq --exit-status '.access_token | type == "string" and length > 0' \
  "$temporary_directory/token-response.json" >/dev/null

encoded_payload=$(jq --exit-status --raw-output '.access_token' "$temporary_directory/token-response.json" | cut -d. -f2)
case $((${#encoded_payload} % 4)) in
  2) encoded_payload="${encoded_payload}==" ;;
  3) encoded_payload="${encoded_payload}=" ;;
esac
printf '%s' "$encoded_payload" |
  tr '_-' '/+' |
  openssl base64 -d -A >"$temporary_directory/token-payload.json"

jq --exit-status \
  --arg issuer "$issuer" \
  '.iss == $issuer
   and .azp == "pcbknowledge-agent-service"
   and .pcbknowledge_subject_kind == "SERVICE_ACCOUNT"
   and ((if (.aud | type) == "array" then .aud else [.aud] end) | index("pcbknowledge-api") != null)
   and .realm_access.roles == ["AGENT_SERVICE"]' \
  "$temporary_directory/token-payload.json" >/dev/null

echo "Keycloak discovery, PKCE metadata/request, and service token claims are valid."
jq '{
  iss,
  aud,
  azp,
  pcbknowledge_subject_kind,
  realm_roles: .realm_access.roles
}' "$temporary_directory/token-payload.json"
