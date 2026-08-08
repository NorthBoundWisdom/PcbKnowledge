# Architecture decision records

ADRs record durable choices from the architecture baseline. `Accepted` decisions govern the MVP now. `Deferred` decisions describe a constrained target whose implementation is outside the first MVP; deferred capability must not be advertised as current.

| ADR | Status | Decision |
|---|---|---|
| [001](ADR-001-pcbknowledge-pcbcore-isolation.md) | Accepted | PcbKnowledge and PcbCore remain physically and dependency isolated |
| [002](ADR-002-modular-monolith-worker.md) | Accepted | P0/P1 use a modular monolith plus worker |
| [003](ADR-003-postgresql-transaction-source.md) | Accepted | PostgreSQL 18 is the sole transactional source of truth |
| [004](ADR-004-content-addressed-assets.md) | Accepted | Original assets use SHA-256 content addressing |
| [005](ADR-005-seaweedfs-reference-store.md) | Accepted | SeaweedFS is the reference S3-compatible store |
| [006](ADR-006-frontend-stack.md) | Accepted | React/Vite/MUI/PDF.js is the frontend stack |
| [007](ADR-007-backend-stack.md) | Accepted | FastAPI/Pydantic/SQLAlchemy is the backend stack |
| [008](ADR-008-postgresql-job-queue.md) | Accepted | PostgreSQL job queue replaces Celery/Redis |
| [009](ADR-009-postgresql-fts.md) | Accepted | P0 uses PostgreSQL FTS and makes no BM25 claim |
| [010](ADR-010-p1-hybrid-retrieval.md) | Deferred | P1 may use BGE-M3, pgvector, and BGE reranking |
| [011](ADR-011-model-gateway.md) | Deferred | Model access is mediated by ModelGateway |
| [012](ADR-012-immutable-publication.md) | Accepted | Published records are immutable and superseded by versions |
| [013](ADR-013-evidence-anchor-coordinates.md) | Accepted | Evidence anchors use page plus normalized PDF coordinates |
| [014](ADR-014-knowledge-snapshot.md) | Deferred | Formal agent runs require a KnowledgeSnapshot |
| [015](ADR-015-ipc-license-default.md) | Accepted | IPC defaults to `LICENSED_BLOCKED_FOR_AI` |
| [016](ADR-016-mcp-adapter-only.md) | Deferred | MCP is an adapter, not the domain protocol |
| [017](ADR-017-two-role-review.md) | Accepted | Data curators cannot approve high-risk engineering facts |

Changes to an accepted decision require a new superseding ADR. Edit an ADR only to fix non-semantic errors or clarify facts that were true at decision time.
