#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)
caddyfile=$repo_root/deploy/caddy/Caddyfile
nginx_config=$repo_root/deploy/docker/nginx.conf

grep -Fq '@oidc_callbacks path /auth/callback /auth/logout/callback' "$caddyfile"
grep -Fq 'log_skip @oidc_callbacks' "$caddyfile"

location_disables_access_log() {
  target=$1
  awk -v target="$target" '
    $1 == "location" && $2 == "=" && $3 == target && $4 == "{" {
      seen = 1
      inside = 1
      next
    }
    inside && $1 == "access_log" && $2 == "off;" { disabled = 1 }
    inside && $1 == "}" { inside = 0 }
    END { exit !(seen && disabled) }
  ' "$nginx_config"
}

location_disables_access_log /auth/callback
location_disables_access_log /auth/logout/callback

echo "OIDC callback access logging is disabled at both HTTP proxy layers."
