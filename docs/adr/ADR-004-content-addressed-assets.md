# ADR-004: Content-address original assets with SHA-256

## Status

Accepted — 2026-08-08.

## Context

Evidence must remain tied to exact immutable bytes across aliases, document revisions, parsing changes, and long-lived audit records. User filenames and object keys are not stable identities.

## Decision

The service streams and verifies SHA-256 server-side before promoting an upload from staging. Original objects use an organization-scoped content-addressed key and are never overwritten. Logical documents and revisions may refer to the same bytes without duplicating the object.

## Alternatives

- Random object keys only.
- Filename/version-based keys.
- Mutable objects with database version metadata.

## Consequences

Byte-level deduplication, integrity checks, and reproducible evidence become straightforward. Promotion and orphan reconciliation require explicit workflows, and metadata deduplication remains a separate concern.

## Rollback

If the digest algorithm becomes unsuitable, add a versioned digest identity and dual-verify existing objects. Preserve SHA-256 references for historical evidence; never rewrite an object in place.
