# ADR-009: Use PostgreSQL FTS for P0

## Status

Accepted — 2026-08-08.

## Context

The MVP needs evidence discovery after exact ACL, entity, package, revision, and review filters. It does not need a separate search cluster or semantic retrieval.

## Decision

Use PostgreSQL `tsvector`/GIN with English/simple configurations plus a Unicode bigram derivative where needed. Identifier lookup uses normalization and exact matching rather than stemming. Product and metrics language must call this PostgreSQL FTS ranking, not BM25.

## Alternatives

- OpenSearch/Elasticsearch from P0.
- Vector-only top-k search.
- SQL `LIKE` scans.

## Consequences

Search remains transactionally close and operationally simple. Advanced ranking and language features are limited, so golden retrieval evaluation and bounded queries are essential.

## Rollback

Add a rebuildable external index only after recall/latency/feature triggers are measured. Keep PostgreSQL authority and exact security filters; index loss must never lose permanent knowledge.
