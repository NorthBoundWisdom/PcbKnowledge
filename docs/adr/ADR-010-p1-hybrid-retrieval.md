# ADR-010: Add hybrid retrieval in P1

## Status

Deferred — outside the first MVP.

## Context

Open-ended evidence discovery may eventually benefit from dense recall and reranking, but vectors cannot enforce MPN, package, revision, ACL, license, or publication correctness.

## Decision

When P1 evaluation justifies it, use a SHA-pinned BAAI/bge-m3 embedding model, pgvector as a rebuildable index, and BAAI/bge-reranker-v2-m3 over a small filtered candidate set. Exact scope and structured/FTS retrieval always run first.

## Alternatives

- Enable vectors in P0.
- Hosted embeddings without a data policy.
- Pure dense top-k.
- A separate vector database.

## Consequences

Potential recall gains come with model licensing, artifact pinning, compute, index rebuild, and regression obligations. No MVP endpoint or acceptance claim may depend on this decision.

## Rollback

Disable dense and rerank stages, delete their derivative indexes, and serve exact plus FTS results. Permanent assets, typed facts, and retrieval traces remain valid.
