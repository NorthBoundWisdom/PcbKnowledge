#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

run_config=true
case ${1:-} in
  "") ;;
  --skip-config) run_config=false ;;
  *)
    echo "usage: $0 [--skip-config]" >&2
    exit 2
    ;;
esac

command -v docker >/dev/null 2>&1 || {
  echo "docker is required" >&2
  exit 1
}
docker compose version >/dev/null

if [ "$run_config" = true ]; then
  "$script_dir/compose-check.sh"
fi
cd "$repo_root"

docker compose up --detach --wait postgres
docker compose up --detach --wait --force-recreate seaweedfs
docker compose up --detach --wait --force-recreate keycloak
docker compose run --rm keycloak-reconcile
docker compose up --detach --force-recreate otel-collector prometheus grafana
docker compose build api worker verifier web migrate storage-init
docker compose run --rm migrate
docker compose run --rm postgres-reconcile
"$script_dir/bootstrap-local-development.sh"
docker compose run --rm storage-init
docker compose up --detach --wait api worker verifier web caddy

docker compose ps
echo "PcbKnowledge is available at http://localhost:${PCBKNOWLEDGE_HTTP_PORT:-8080}"
