#!/bin/sh
set -eu

repository_dir=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
cd "$repository_dir"

exec python3 configs/pcbknowledge_workflow.py open
