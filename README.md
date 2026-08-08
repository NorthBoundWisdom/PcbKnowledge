# PcbKnowledge

PcbKnowledge is an evidence-first engineering knowledge platform for PCB software and agents. It preserves source revisions and precise evidence anchors, turns reviewed evidence into typed knowledge, and serves explainable results without becoming a runtime dependency of PcbCore.

## Current state

The repository now has an executable M1 platform baseline: a modular FastAPI application with fail-closed PostgreSQL, OIDC, and private object-store readiness; bounded PostgreSQL job/outbox and storage primitives; a durable staging-cleanup worker; an OIDC Authorization Code + PKCE curator shell backed by the trusted `/session` projection; a committed OpenAPI artifact; and a Docker Compose development stack with Keycloak and baseline observability. This substrate is not the later document intake, extraction, review, publication, or retrieval workflow, and it is not production-ready.

The intended first-MVP domain scope remains an evidence-first path: immutable source bytes, document revisions, typed facts, two-role review, exact/FTS retrieval, audit, and repeatable evaluation. Those domain workflows are targets until their executable code and verification land. Vector retrieval, LLM extraction, MCP, KnowledgeSnapshot pinning, and PCB mutation are not MVP capabilities.

Authoritative project documents:

- [MVP execution plan](TODO_MVP_P0_EVIDENCE_FIRST.md)
- [architecture baseline](PcbKnowledge_ARCHITECTURE.md)
- [internal overview](PcbKnowledge_INTERNAL_OVERVIEW.md)
- [architecture decisions](docs/adr/README.md)

## Repository boundaries

- PcbKnowledge owns external documents, evidence, reviewed knowledge, search, and knowledge audit.
- PcbCore owns live board state, canonical identities, geometry, connectivity, and deterministic validation.
- PCBAtlas/PcbAgentHarness owns agent execution, approvals, and tool orchestration.
- PcbKnowledge never writes sibling repositories and is never a required dependency for opening, editing, or validating a board.

## Prerequisites

- Python 3.14 and `uv`
- Node.js 24 LTS, Corepack, and `pnpm`
- Docker Engine with Docker Compose v2
- `openssl` for local secret generation

## Canonical commands

Install and verify the source tree:

```bash
uv sync --frozen --all-groups
corepack enable
pnpm install --frozen-lockfile
uv run ruff format --check .
uv run ruff check .
uv run mypy src apps tests
uv run pytest
uv run pcbknowledge-openapi --check
pnpm check:generated
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Regenerate the canonical OpenAPI artifact and its browser client after changing
an API DTO or route:

```bash
uv run pcbknowledge-openapi
pnpm generate:api
```

`uv run pcbknowledge-openapi --check` verifies the Python-owned contract;
`pnpm check:generated` independently verifies the committed TypeScript client.
The browser transport is created only through the generated OpenAPI boundary;
route components do not maintain handwritten wire DTOs or call `fetch` directly.

`uv run pytest` is useful for a source-tree run, but PostgreSQL- and
SeaweedFS-gated tests can report skips when their explicit disposable-service
configuration is absent. It is therefore not, by itself, a zero-skip
integration receipt. The canonical M1 integration entry is the
[`M1 PostgreSQL and SeaweedFS integration` CI job](.github/workflows/ci.yml),
which provisions real disposable services, applies migrations, exercises the
separate application and worker database roles plus the cleanup worker, and
fails if either JUnit receipt contains a skipped case. The job runs on every
push to `main` and every pull request.

Start the local stack from an empty Docker volume set:

```bash
./deploy/scripts/dev-up.sh
```

The script generates untracked runtime credentials and two rendered Keycloak JSON files, validates the resolved Compose model, builds API/worker/web images, applies migrations before reconciling runtime database roles, reconciles identity configuration, initializes object-store buckets, and starts the stack. It never substitutes anonymous access or a known default password. See [local development](docs/operations/local-development.md) and [configuration](docs/operations/configuration.md).

Useful endpoints after startup:

- curator/Caddy: <http://localhost:8080>
- API liveness: <http://localhost:8080/healthz>
- API readiness: <http://localhost:8080/readyz>
- Keycloak: <http://localhost:8081>
- Grafana: <http://localhost:3000>
- Prometheus: <http://localhost:9090>

Stop services without deleting data:

```bash
./deploy/scripts/dev-down.sh
```

## Deployment posture

`compose.yaml` is a local-development and single-host reference skeleton, not a production manifest. Development defaults use explicit image tags so the stack is inspectable. Production operators must override every image with an immutable digest, inject secrets through the platform secret manager, configure TLS and trusted OIDC hostnames, isolate management ports, and complete backup/restore qualification before serving data.

## Security and licensing

Source documents are untrusted data. Missing identity, authorization, license policy, evidence, review, hash, schema, or audit checks fail closed. Never commit credentials, tokens, source PDFs, customer material, or generated local secret files. Report vulnerabilities according to [SECURITY.md](SECURITY.md).

Unless replaced by an explicit license from the legal owner, this repository is proprietary and all rights are reserved; see [LICENSE](LICENSE).
