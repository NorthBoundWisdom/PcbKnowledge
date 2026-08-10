# Architecture decision records

ADRs record durable choices from the architecture baseline. `Accepted` decisions govern the MVP now. `Deferred` decisions describe a constrained target whose implementation is outside the first MVP; deferred capability must not be advertised as current.

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
| [010](ADR-010-p1-hybrid-retrieval.md) | Deferred | P1 may use BGE-M3, pgvector, and BGE reranking |
| [011](ADR-011-model-gateway.md) | Deferred | Model access is mediated by ModelGateway |
| [012](ADR-012-immutable-publication.md) | Accepted | Published records are immutable and superseded by versions |
| [013](ADR-013-evidence-anchor-coordinates.md) | Accepted | Evidence anchors use page plus normalized PDF coordinates |
| [014](ADR-014-knowledge-snapshot.md) | Deferred | Formal agent runs require a KnowledgeSnapshot |
| [015](ADR-015-ipc-license-default.md) | Accepted | IPC defaults to `LICENSED_BLOCKED_FOR_AI` |
| [016](ADR-016-mcp-adapter-only.md) | Deferred | MCP is an adapter, not the domain protocol |
| [017](ADR-017-two-role-review.md) | Superseded | Historical shared-service role model; human review intent remains |
| [018](ADR-018-git-native-local-editor.md) | Accepted | Git-native local editor supersedes the service-platform MVP decisions |

ADR-018 supersedes ADR-002, ADR-003, ADR-005, ADR-006, ADR-007, ADR-008,
ADR-009 and ADR-017 for the executable local MVP. Those files remain historical
records rather than descriptions of the current runtime.

Changes to an accepted decision require a new superseding ADR. Edit an ADR only to fix non-semantic errors or clarify facts that were true at decision time.
