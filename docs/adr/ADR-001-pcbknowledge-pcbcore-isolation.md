# ADR-001: Isolate PcbKnowledge from PcbCore

## Status

Accepted — 2026-08-08.

## Context

PcbCore is the authority for live board identity, geometry, connectivity, transactions, and deterministic validation. PcbKnowledge governs external documents and reviewed evidence. Coupling either runtime to the other would make board work dependent on a fallible knowledge service and blur correctness ownership.

## Decision

PcbKnowledge is a separate repository, deployment, database, and API. It does not link PcbCore libraries, access PcbCore storage, mutate boards, or make PcbCore wait for knowledge availability. Agents compose the two systems and submit any board change through PcbCore's own validated contracts.

## Alternatives

- Embed retrieval in PcbCore.
- Share a database or domain model.
- Let PcbKnowledge emit or apply internal PcbCore patches.

## Consequences

Board editing remains deterministic and offline-capable. Cross-system evolution needs explicit adapters and versioned contracts; some data is intentionally duplicated at the boundary.

## Rollback

Only a superseding cross-repository ADR with failure isolation, ownership, compatibility, and recovery evidence may relax this boundary. No direct dependency may be introduced as an incremental shortcut.
