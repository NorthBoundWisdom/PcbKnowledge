# ADR-007: Fix the backend stack

## Status

Accepted — 2026-08-08.

## Context

The service needs typed REST contracts, strong validation, relational transactions, migrations, and a local PDF/data ecosystem without hiding evidence policy behind an orchestration framework.

## Decision

Use Python 3.14 with `uv`, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, and psycopg 3. Pydantic models define API and extraction DTOs; ORM instances remain inside persistence adapters. Business code does not depend on LangChain or LlamaIndex.

## Alternatives

- Node.js, Go, or JVM services.
- Django as an integrated framework.
- Raw SQL in business services.
- A generic RAG framework as the application core.

## Consequences

Contracts and validation remain explicit and OpenAPI generation is direct. Python/version compatibility, dependency pinning, static typing, and migration review are required.

## Rollback

A superseding ADR must preserve REST/OpenAPI semantics, migration ownership, audit atomicity, and fixture compatibility. Migrate behind versioned contracts; do not run two authorities indefinitely.
