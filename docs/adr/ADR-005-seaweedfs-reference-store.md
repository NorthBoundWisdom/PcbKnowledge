# ADR-005: Use SeaweedFS as the reference S3-compatible store

## Status

Accepted — 2026-08-08.

## Context

Original PDFs and derived assets need an independently scalable object API. The reference implementation should be self-hostable, Compose-friendly, and avoid making database blobs the evidence vault.

## Decision

SeaweedFS with its authenticated S3 API is the reference object store. Application code depends on a narrow S3-compatible adapter and content-addressing rules, not SeaweedFS internals. Anonymous buckets and known fallback credentials are forbidden.

## Alternatives

- PostgreSQL large objects.
- Filesystem paths shared by processes.
- MinIO as the default reference implementation.
- A cloud-vendor SDK embedded in domain code.

## Consequences

Local and single-host deployments have an Apache-licensed reference service and can later use a compatible managed store. Operators must back up volumes and qualify S3 behavior used by the adapter.

## Rollback

Switch the adapter to a qualified S3-compatible implementation, copy and hash-verify every permanent object, then atomically redirect reads. Historical database identities and digests stay unchanged.
