# Local development

The reference stack runs on one Docker host and is for development and qualification only. It starts PostgreSQL, SeaweedFS, Keycloak, the API, worker, curator web, Caddy, OpenTelemetry Collector, Prometheus, and Grafana.

## First start

From the repository root:

```bash
./deploy/scripts/dev-up.sh
```

The script requires Docker Compose v2 and OpenSSL. On first use it creates the required random credential files plus two rendered Keycloak JSON files under `deploy/secrets/`, sets owner-only permissions, and validates the resolved Compose model. It then starts PostgreSQL and SeaweedFS, starts and reconciles Keycloak, builds the application images, applies Alembic migrations, reconciles the constrained database logins after those migrations, initializes the object-store buckets, and waits for the API, durable worker, web, and Caddy health checks. These runtime files are ignored by Git.

No service substitutes anonymous access or a known password. If a required secret is missing or empty, startup stops. To supply secrets from another system, provision the same file paths before running the command.

## Daily commands

```bash
# Resolve and validate configuration without starting containers.
./deploy/scripts/compose-check.sh

# Show status and health.
docker compose ps

# Follow application logs.
docker compose logs --follow api worker web

# Stop while retaining volumes and secrets.
./deploy/scripts/dev-down.sh
```

The script deliberately has no automatic “delete all data” option. Removing volumes or rotating database/object-store credentials requires an explicit operator procedure and impact review.

## Health semantics

- API `/healthz` is process liveness.
- API `/readyz` verifies required configuration, the PostgreSQL runtime contract, OIDC verification keys, and private object-store access. It returns 503 when any required dependency is unavailable.
- Web `/healthz` proves that the built static artifact is being served.
- Worker health uses the explicit `python -m pcbknowledge.worker health-check` command and probes required configuration, the PostgreSQL runtime contract, and private object-store access. The Compose worker runs `python -m pcbknowledge.worker serve` as a durable supervisor. Each bounded cycle handles only tenant-scoped finalized or expired staging cleanup through the PostgreSQL outbox, then waits before probing again; a failed dependency check exits nonzero for Compose to restart. It does not implement document intake, extraction, review, or promotion handlers.

Caddy exposes browser traffic at port 8080 and proxies `/api/*` to the API. Keycloak is exposed separately on port 8081 so its issuer is stable in browser and container contexts. Infrastructure management ports bind to loopback by default.

## Source-only development

Run backend checks:

```bash
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src apps tests
uv run pytest
uv run pcbknowledge-openapi --check
```

Run frontend checks:

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm check:generated
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

See the root README for contract generation. Tests that claim persistence, authorization, job, or object-store behavior must exercise PostgreSQL and an S3-compatible service rather than a hidden SQLite or memory path.

## Full M1 integration receipt

A plain `uv run pytest` without explicit integration services may skip the
environment-gated PostgreSQL and SeaweedFS cases; do not report that as a full
integration pass. The canonical zero-skip entry is the
[`M1 PostgreSQL and SeaweedFS integration` job](../../.github/workflows/ci.yml)
on every pull request and push to `main`. It creates disposable real PostgreSQL
and SeaweedFS instances, migrates the database, reconciles and tests the
separate application/worker roles, exercises storage and cleanup behavior, and
parses both JUnit reports to fail the job if any selected integration case was
skipped.

Keep the hermetic backend job and this integration job distinct: the former
gives a fast source receipt, while only the latter owns the service lifecycle
and produces the required real-dependency, zero-skip receipt.
