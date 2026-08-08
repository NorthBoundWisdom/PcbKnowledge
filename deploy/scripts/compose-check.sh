#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

"$script_dir/bootstrap-secrets.sh"
cd "$repo_root"
docker compose config --quiet
echo "Compose configuration is valid."
