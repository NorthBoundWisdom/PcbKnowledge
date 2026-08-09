#!/bin/sh
set -eu

pnpm check:generated
pnpm lint
pnpm typecheck
pnpm test
pnpm build
