# Local development

The reference stack runs on one Docker host and is for development and qualification only. It starts PostgreSQL, SeaweedFS, Keycloak, the API, cleanup worker, isolated document verifier, curator web, Caddy, OpenTelemetry Collector, Prometheus, and Grafana.

## First start

From the repository root:

```bash
./deploy/scripts/dev-up.sh
```

The script requires Docker Compose v2 and OpenSSL. On first use it creates the required random credential files plus two rendered Keycloak JSON files under `deploy/secrets/`, sets owner-only permissions, and validates the resolved Compose model. It then starts PostgreSQL and SeaweedFS, starts and reconciles Keycloak, builds the application images, applies Alembic migrations, reconciles the constrained database logins after those migrations, bootstraps the fail-closed local Curator identity and its default project data, initializes the object-store buckets, and waits for the API, cleanup worker, verifier, web, and Caddy health checks. These runtime files are ignored by Git.

No service substitutes anonymous access or a known password. If a required secret is missing or empty, startup stops. To supply secrets from another system, provision the same file paths before running the command.

The local login username is `pcbknowledge-curator`. Its random password is retained in the
owner-only `deploy/secrets/local_curator_password` file and is not printed by startup. The
account has only `DATA_CURATOR` access to `Local Development / Default Project`. It cannot
act as a domain reviewer or global administrator.

## First usable intake flow

After the stack is healthy, open <http://localhost:8080>, sign in with the managed local
Curator, and use **Intake → New intake**. Select the default project and the server-provided
source organization, access scope, and license policy; choose a PDF no larger than 256
MiB; enter its document identity and revision; then confirm and submit. The browser sends
the bytes only to the short-lived staging URL. The isolated verifier reads the staged
object, checks its declared size and `%PDF-` magic, computes the authoritative SHA-256,
promotes it under an organization-scoped content-addressed key, and atomically records the
immutable document revision and audit receipt. The UI polls the durable job and exposes a
stable failure code instead of presenting an unverified upload as stored.

Stored revisions appear under **Documents**. Opening an original is a separate authorized
POST that writes an audit event before returning a short-lived private download URL.
Current scope stops there: page parsing, thumbnails, extracted text, entity matching,
evidence anchors, review, publication, and search have not yet been implemented.

## Daily commands

```bash
# Resolve and validate configuration without starting containers.
./deploy/scripts/compose-check.sh

# Show status and health.
docker compose ps

# Follow application logs.
docker compose logs --follow api worker verifier web

# Stop while retaining volumes and secrets.
./deploy/scripts/dev-down.sh
```

The script deliberately has no automatic “delete all data” option. Removing volumes or rotating database/object-store credentials requires an explicit operator procedure and impact review.

## Health semantics

- API `/healthz` is process liveness.
- API `/readyz` verifies required configuration, the PostgreSQL runtime contract, OIDC verification keys, and private object-store access. It returns 503 when any required dependency is unavailable.
- Web `/healthz` proves that the built static artifact is being served.
- Worker health uses the explicit `python -m pcbknowledge.worker health-check` command and probes required configuration, the PostgreSQL runtime contract, and private object-store access. The Compose worker runs `python -m pcbknowledge.worker serve` as a durable supervisor. Each bounded cycle handles only tenant-scoped finalized or expired staging cleanup through the PostgreSQL outbox, then waits before probing again; a failed dependency check exits nonzero for Compose to restart. It does not implement document intake, extraction, review, or promotion handlers.
- Verifier health uses `python -m pcbknowledge.document.verifier health-check` through the same fail-closed secret entrypoint. Its durable `serve` process is the only runtime with the `pcbknowledge_verifier` database login and the independent SeaweedFS identity permitted to read/write staging and permanent content. It has no SeaweedFS Admin or List action; the API and cleanup-worker credentials remain unchanged.

After Build has reconciled the verifier login and recreated SeaweedFS with its generated
identity policy, qualify the real allow/deny boundary with:

```bash
./deploy/scripts/test-verifier-runtime-boundary.sh
```

The probe uses and removes only its own random object keys. It requires verifier staging
and permanent read/write, denies verifier List/Admin operations, and proves API and cleanup
worker credentials still cannot write permanent content.

SeaweedFS 3.85 exposes browser staging CORS through a process-level origin allow-list. The
reference stack pins only the documented local origins and the browser upload adapter uses
`withCredentials=false` plus a single `Content-Type` request header. SeaweedFS 3.85 still
responds to an allowed preflight with wildcard allow-method/header response fields and has
a defective rejected-preflight response, so this is a qualified local-development path,
not a production CORS policy. Production must use a storage service or ingress that has
passed the exact origin/method/header and denial tests.

The verifier is trusted in this reference stack: SeaweedFS 3.85 cannot express
create-only/no-overwrite permission for its permanent bucket. Application code prevents
normal-path overwrite with digest verification, a PostgreSQL advisory lock, and
read-before-create behavior, while API and cleanup-worker credentials cannot write the
bucket. A compromised verifier credential is therefore outside the local qualification;
production requires a bounded promotion broker or a qualified object-lock/conditional-
create backend.

Caddy exposes browser traffic at port 8080 and proxies `/api/*` to the API. Keycloak is exposed separately on port 8081 so its issuer is stable in browser and container contexts. Infrastructure management ports bind to loopback by default.

## Source-only development

Repository-owned orchestration with branching, timeouts, receipts, or subprocess
lifecycle belongs in typed Python so it can be unit tested. Shell remains a thin boundary
for container entrypoints, Docker secret loading, and direct `psql`, `kcadm`, or service
CLI invocation; do not grow those wrappers into a second workflow engine.

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

## Full persistence integration receipt

A plain `uv run pytest` without explicit integration services may skip the
environment-gated PostgreSQL and SeaweedFS cases; do not report that as a full
integration pass. The canonical zero-skip entry is the
[`Platform and document PostgreSQL/SeaweedFS integration` job](../../.github/workflows/ci.yml)
on every pull request and push to `main`. It creates disposable real PostgreSQL
and SeaweedFS instances, migrates the database, reconciles and tests the separate
application, cleanup-worker, and document-verifier roles, exercises storage,
promotion, and cleanup behavior, and
parses both JUnit reports to fail the job if any selected integration case was
skipped.

Keep the hermetic backend job and this integration job distinct: the former
gives a fast source receipt, while only the latter owns the service lifecycle
and produces the required real-dependency, zero-skip receipt.
