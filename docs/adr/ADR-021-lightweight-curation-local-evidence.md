# ADR-021: Lightweight curation and local-only original evidence

- Status: Accepted
- Date: 2026-10-27
- Supersedes: the data-empty/public-private restriction in ADR-020 and Git-original storage portions of ADR-018/019; refines ADR-004 without changing SHA-256 identity.

## Context

The owner wants an expanding knowledge repository containing processed summaries
and annotations rather than large originals, authorizes main-branch publication,
and delegates review of curated drafts to the Agent. Requiring a complete PDF
visual-review pilot before retaining any useful summary prevents incremental learning.

## Decision

Adopt the [lightweight knowledge contract](../legacy/intake/lightweight-knowledge.md). Keep typed
canonical authority and a clearly noncanonical intake queue distinct. Agent review
under owner delegation is truthful curation acceptance, not a fabricated human
canonical approval. Commit metadata and small original annotations. Store original
PDFs only in the ignored SHA-256 local cache. Pin `typed-v2-local-cache`; do not
silently upgrade old workspaces. Validate immutable Git metadata independently of
local byte availability. Export no originals in packages.

## Consequences

A clone can inspect and search curated knowledge without redistributing source
bytes. Visual verification requires authorized local evidence. Incomplete byte or
bbox verification stays visible. Public-source guards apply to index and tracked
content, not just a conventional data directory. Existing workspace isolation,
license gates, append-only review history, immutable canonical records, and the
loopback-only runtime remain. The formal real-PDF pilot is still open and cannot
be claimed complete from an intake count alone.
