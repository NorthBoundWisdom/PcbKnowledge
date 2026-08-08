# ADR-002: Use a modular monolith plus worker

## Status

Accepted — 2026-08-08 for P0/P1.

## Context

Knowledge, evidence, review, conflicts, ACL, audit, and publication require strong transactional consistency. Initial scale and team size do not justify distributed service coordination, while PDF processing must not block request handling.

## Decision

Use one Python domain codebase and PostgreSQL schema, exposed by an API process and consumed by independently scalable worker processes. Modules communicate through application services or public domain interfaces. Cross-process side effects use a transactional outbox.

## Alternatives

- Independent microservices and message brokers.
- One synchronous web process for all work.
- Serverless functions per pipeline stage.

## Consequences

Transactions and local development remain understandable. API and workers can scale separately, but deployments share a release and careless imports could erode module boundaries.

## Rollback

Split a module only after measured ownership, scaling, release-cadence, or fault-isolation pressure meets the architecture trigger. Preserve the application interface and migrate via an outbox-backed contract under a superseding ADR.
