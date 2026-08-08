# ADR-015: Block AI processing of IPC material by default

## Status

Accepted — 2026-08-08.

## Context

Paid standards and commercial databases may restrict parsing, indexing, model processing, extraction, and redistribution. Presence of a file does not establish those rights.

## Decision

IPC and equivalent licensed material defaults to `LICENSED_BLOCKED_FOR_AI`: parsing, local/external models, embeddings, indexing, and agent raw access are denied. The system may retain authorized license metadata and manual citations. Only a recorded, scoped license policy approved by an authorized administrator can enable an action.

## Alternatives

- Treat all uploaded material as processable.
- Rely on users to remember license terms per operation.
- Block storage of all licensed references.

## Consequences

The default protects contractual obligations but limits automation and requires explicit policy administration. Authorization must run before parsing or retrieval, not after ranking.

## Rollback

There is no permissive fallback. A legal determination may create a narrower approved policy with provenance, effective dates, scope, and audit; revocation stops future processing and triggers derivative impact review.
