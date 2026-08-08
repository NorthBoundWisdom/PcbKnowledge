# ADR-014: Require KnowledgeSnapshot for formal agent runs

## Status

Deferred — KnowledgeSnapshot is outside the first MVP.

## Context

Long-running or regulated agent work must reproduce the exact knowledge versions, policies, and retrieval configuration used even after publication changes.

## Decision

Once implemented, every formal production agent run must pin a `KnowledgeSnapshot` before using evidence. A snapshot identifies immutable record versions, effective-time and access context, relevant source revisions, and retrieval configuration. Until then, PcbKnowledge must not claim reproducible formal agent-run pinning.

## Alternatives

- Resolve “latest” on each tool call.
- Save only response text in an agent log.
- Pin document revisions but not record/policy versions.

## Consequences

Formal runs become reproducible and impact analysis is possible, while snapshot creation, retention, authorization, and stale handling add cost.

## Rollback

Disable formal agent-run integration rather than falling back to unpinned latest data. Existing snapshots remain immutable and readable.
