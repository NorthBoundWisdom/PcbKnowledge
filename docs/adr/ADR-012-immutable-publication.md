# ADR-012: Make published knowledge immutable

## Status

Accepted — 2026-08-08.

## Context

Audits and future snapshots must reproduce the exact fact, conditions, evidence, and review decision used at a point in time. In-place edits destroy that evidence chain.

## Decision

A stable `KnowledgeRecord` owns immutable `KnowledgeRecordVersion` entries. Publication atomically records the version, evidence, reviews, audit, and outbox event. Corrections create a new version and explicit supersession or withdrawal; application and database policy reject payload mutation.

## Alternatives

- Mutable rows plus change logs.
- Soft timestamps without immutable payloads.
- Replace old facts and retain only the newest copy.

## Consequences

History and citation remain reproducible and concurrent changes are visible. Storage grows and every consumer must select effective versions explicitly.

## Rollback

There is no destructive rollback. A superseding ADR may introduce another append-only representation after proving history-preserving migration; existing published versions remain readable.
