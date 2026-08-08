# Local development

The reference stack runs on one Docker host and is for development and qualification only. It starts PostgreSQL, SeaweedFS, Keycloak, the API, worker, curator web, Caddy, OpenTelemetry Collector, Prometheus, and Grafana.

## First start

From the repository root:

```bash
./deploy/scripts/dev-up.sh
```

The script requires Docker Compose v2 and OpenSSL. On first use it creates six random files under `deploy/secrets/`, sets owner-only permissions, validates the resolved Compose model, builds application images, starts infrastructure, applies Alembic migrations, runs the worker readiness probe, then starts application and observability services. The secret files are ignored by Git.

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
- API `/readyz` verifies required configuration and PostgreSQL reachability and must return 503 when dependencies are unavailable.
- Web `/healthz` proves that the built static artifact is being served.
- Worker health uses the explicit `python -m pcbknowledge.worker health-check` command and probes configuration plus PostgreSQL. M0 intentionally has no pretend long-running job loop; the Compose `worker` service is a one-shot profile until the real PostgreSQL queue consumer is implemented.

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
```

See the root README for contract generation. Tests that claim persistence, authorization, job, or object-store behavior must exercise PostgreSQL and an S3-compatible service rather than a hidden SQLite or memory path.
