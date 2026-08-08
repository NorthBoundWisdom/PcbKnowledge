# ADR-003: Use PostgreSQL 18 as the transactional source of truth

## Status

Accepted — 2026-08-08.

## Context

Publication, review, authorization, audit, jobs, conflicts, and snapshots need consistent transactions and relational constraints. Multiple authoritative stores would make failure handling and recovery ambiguous.

## Decision

PostgreSQL 18 is the only transactional fact store. Business state, job leases, outbox entries, and append-only audit events commit there. Search indexes and object-store assets are either referenced permanent bytes or rebuildable derivatives; neither replaces relational authority.

## Alternatives

- SQLite for local or production fallback.
- Separate document, graph, queue, or search databases as authorities.
- Event sourcing as the primary model.

## Consequences

Strong constraints and one recovery boundary simplify correctness. PostgreSQL capacity and migration quality become critical, and integration tests require a real server.

## Rollback

A superseding ADR must identify a proven PostgreSQL bottleneck, define dual-write avoidance and reconciliation, and demonstrate restore consistency. SQLite or memory fallback is never a rollback path.
