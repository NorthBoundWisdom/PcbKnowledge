# PcbKnowledge

PcbKnowledge is an evidence-first engineering knowledge platform for PCB software and agents. It preserves source revisions and precise evidence anchors, turns reviewed evidence into typed knowledge, and serves explainable results without becoming a runtime dependency of PcbCore.

## Current state

The repository now has a first usable local intake slice on top of the M1 platform. A
managed development Curator can sign in with OIDC Authorization Code + PKCE, upload a PDF
directly to private staging, let an isolated verifier compute the authoritative SHA-256
and byte size, store one content-addressed original, browse the resulting immutable
document revision, and request a short-lived audited original-file download. PostgreSQL
RLS, bounded jobs/outbox, the cleanup worker, generated OpenAPI browser transport, and
real PostgreSQL/SeaweedFS integration tests protect that path.

This is an M2 intake subset, not the completed evidence-first MVP and not a production
deployment. Page parsing, thumbnails, extracted text, entity resolution, evidence
anchors, typed facts, two-person review, publication, and retrieval remain targets.
Vector retrieval, LLM extraction, MCP, KnowledgeSnapshot pinning, and PCB mutation are
not current capabilities.

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

Initialize the repository-pinned FreeCM tooling after cloning:

```bash
git submodule update --init --recursive FreeCM
```

## FreeCM plugin workflow

The repository declares Config, Build, Run, Test, and Package actions in
`configs/freecm.commands.jsonc`. In the FreeCM workflow view, run **Config** once, run
**Build → Prepare Runtime** whenever the source or runtime contract changes, and then use
**Run → Start Built Apps** for the normal edit/run cycle. Build owns the slower work: it
builds the images, starts and warms infrastructure, applies migrations, reconciles roles
and Keycloak, bootstraps the explicitly managed local Curator, and initializes storage.
Run never builds or migrates; it only starts the already-created API, cleanup worker,
document verifier, web, and gateway containers and attaches their logs.

The curator is available at <http://localhost:18080>. Press Ctrl+C in the Run terminal to
stop those five application containers. PostgreSQL, Keycloak, SeaweedFS, and observability
services stay warm, so the next Run avoids their cold-start delay. To explicitly stop the
entire prepared FreeCM environment while preserving its volumes, run:

```bash
COMPOSE_PROJECT_NAME=pcbknowledge-freecm ./deploy/scripts/dev-down.sh
```

Build creates one fail-closed local human identity for development. Sign in as
`pcbknowledge-curator` and read its random password from the owner-only, ignored
`deploy/secrets/local_curator_password` file at the interactive login boundary. It has
only `DATA_CURATOR` access to the managed default project; it is neither a reviewer nor an
administrator. The Keycloak bootstrap administrator is not an application user. See
[authentication operations](docs/operations/authentication.md#local-development-human).

For the first end-to-end use, open **Intake → New intake**, select the managed default
project and its source/scope/license options, choose an `application/pdf` file of at most
256 MiB, confirm the metadata, and submit. The UI uploads directly to staging and polls
the durable verifier until the revision is `STORED` or reports a stable failure. A stored
revision appears under **Documents**, where **Open authorized original** performs a fresh
authorization and audit before navigating to the short-lived object URL.

The plugin actions are deliberately isolated under the `pcbknowledge-freecm` Compose
project, so they do not reuse or stop a stack started with `deploy/scripts/dev-up.sh`.
Their fixed local endpoints are:

- curator/Caddy: <http://localhost:18080>
- Keycloak: <http://localhost:18081>
- S3: <http://localhost:18333>
- Prometheus: <http://localhost:19090>
- Grafana: <http://localhost:13000>

The other actions use the same pinned workflow:

- **Config** generates untracked development secrets, validates the resolved Compose
  model, and writes an input-bound receipt under `.freecm/`.
- **Build** builds the repository-owned images, prepares migrations and external-service
  state, creates the stopped application containers, and leaves infrastructure running.
- **Run** fails quickly with an instruction to run Build if that prepared environment is
  missing, stopped, or stale. It passes `--no-build` and never performs setup work.
- **Test** runs backend formatting/lint/type/unit/OpenAPI checks and frontend generated
  client/lint/type/unit/build checks in the repository-pinned containers.
- **Package** verifies and exports the exact six images recorded by Build as a
  gzip-compressed, `docker image load`-compatible archive, SHA-256 sidecar, and JSON
  manifest under `build/package/`. It never rebuilds or retags them, and fails if the
  prepared runtime receipt is stale.

The same actions can be reproduced without the UI:

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py run
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_workflow.py package
```

After editing the FreeCM command manifest or its workflow, validate it against the pinned
plugin checkout:

```bash
npm ci --no-audit --prefix FreeCM/vscode-extension
python3 configs/validate_freecm_repo_commands.py
```

## Canonical commands

Install and verify the source tree:

```bash
uv sync --frozen --all-groups
corepack enable
pnpm install --frozen-lockfile
uv run ruff format --check .
uv run ruff check .
uv run mypy src apps tests configs
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
integration receipt. The canonical persistence integration entry is the
[`Platform and document PostgreSQL/SeaweedFS integration` CI job](.github/workflows/ci.yml),
which provisions real disposable services, applies migrations, exercises the
separate application, cleanup-worker, and document-verifier database roles, and
fails if either JUnit receipt contains a skipped case. The job runs on every
push to `main` and every pull request.

Start the local stack from an empty Docker volume set:

```bash
./deploy/scripts/dev-up.sh
```

The script generates untracked runtime credentials and two rendered Keycloak JSON files,
validates the resolved Compose model, builds API/worker/verifier/web images, applies
migrations before reconciling runtime database roles, bootstraps the managed local
Curator, initializes object-store buckets, and starts the stack. It never substitutes
anonymous access or a known default password. See
[local development](docs/operations/local-development.md) and
[configuration](docs/operations/configuration.md).

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
