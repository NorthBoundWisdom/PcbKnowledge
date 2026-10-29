# Architecture decision records

ADRs record durable choices from the architecture baseline. `Accepted` decisions govern the current executable architecture. `Deferred` decisions describe constrained targets whose implementation is outside the current phase; deferred capability must not be advertised as current.

| ADR | Status | Decision |
|---|---|---|
| [001](ADR-001-pcbknowledge-pcbcore-isolation.md) | Accepted | PcbKnowledge and PcbCore remain physically and dependency isolated |
| [002](ADR-002-modular-monolith-worker.md) | Superseded | Historical modular monolith plus worker design |
| [003](ADR-003-postgresql-transaction-source.md) | Superseded | Historical PostgreSQL transaction-source design |
| [004](ADR-004-content-addressed-assets.md) | Accepted | Original assets use SHA-256 content addressing |
| [005](ADR-005-seaweedfs-reference-store.md) | Superseded | Historical SeaweedFS reference-store design |
| [006](ADR-006-frontend-stack.md) | Superseded | Historical React/Vite frontend design |
| [007](ADR-007-backend-stack.md) | Superseded | Historical FastAPI backend design |
| [008](ADR-008-postgresql-job-queue.md) | Superseded | Historical PostgreSQL queue design |
| [009](ADR-009-postgresql-fts.md) | Superseded | Historical PostgreSQL FTS design |
| [010](ADR-010-p1-hybrid-retrieval.md) | Deferred | Hybrid/vector retrieval requires evaluation evidence |
| [011](ADR-011-model-gateway.md) | Deferred | Model access is mediated if PcbKnowledge later owns model calls |
| [012](ADR-012-immutable-publication.md) | Superseded by 022 for v2 | Per-record immutability; v2 pins a whole commit instead |
| [013](ADR-013-evidence-anchor-coordinates.md) | Accepted | Evidence anchors use page plus normalized PDF coordinates |
| [014](ADR-014-knowledge-snapshot.md) | Superseded by 022 | Replaced by bundles pinned to one validated commit |
| [015](ADR-015-ipc-license-default.md) | Accepted | IPC defaults to AI-processing blocked |
| [016](ADR-016-mcp-adapter-only.md) | Deferred | MCP is an adapter, not the domain protocol |
| [017](ADR-017-two-role-review.md) | Superseded | Historical shared-service role model; human review intent remains |
| [018](ADR-018-git-native-local-editor.md) | Accepted; review workflow superseded by 022 | Git-native local product supersedes the service-platform MVP decisions |
| [019](ADR-019-git-publication-boundary.md) | Accepted; APPROVED-state parts superseded by 022 | Git commit is publication; data and policy/contract changes use separate commits |
| [020](ADR-020-knowledge-workspace-boundary.md) | Partly superseded by 021 | Explicit workspaces and pinned schemas remain; public data-empty rule retired |
| [021](ADR-021-lightweight-curation-local-evidence.md) | Accepted; intake lane superseded by 022 | Original evidence in ignored local cache; the intake queue is frozen |
| [022](ADR-022-board-generation-knowledge.md) | Accepted | Consumer-driven v2 knowledge for board generation; one model; golden designs |
| [023](ADR-023-design-intent-handoff.md) | Accepted | D3/D4 design-intent JSON handoff and PcbAtlas synthesis ownership |
| [024](ADR-024-terminals-packages-selection.md) | Accepted | Two-terminal numbering convention, package drawing dimensions as authority, range-aware selection |
| [025](ADR-025-derived-board-handoff.md) | Accepted | Derived KiCad handoff and read-only exported-board checks under D16-D17 |

ADR-018 supersedes ADR-002, ADR-003, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, and ADR-017 for the executable local product. Those files remain historical records rather than descriptions of the current runtime.

ADR-019 clarifies the Git-native authority introduced by ADR-018: a working-tree approval is not yet published knowledge, and one publication commit must not combine knowledge/evidence data with the schema/policy contract it depends on.

ADR-020 extends ADR-018/019 after the software repository became open source. Production authority now lives in an explicitly selected, self-contained knowledge Git workspace with a canonical manifest and pinned schema snapshot. Its historical public data-empty restriction and Git-original requirement are superseded by ADR-021. Explicit selection and pinned schemas remain current.

Changes to an accepted decision require a new superseding ADR. Edit an ADR only to fix non-semantic errors or clarify facts that were true at decision time.

ADR-022 sets the current direction: knowledge exists to let a design brief become a manufacturable board. It replaces the intake lane, the v1 per-record approval workflow and per-record immutability with one v2 record model, verification levels and commit-pinned bundles. Evidence identity, the local original cache, license gates, workspace selection and the runtime boundary remain.
