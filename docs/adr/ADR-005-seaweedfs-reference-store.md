# ADR-005: Use SeaweedFS as the reference S3-compatible store

## Status

Accepted — 2026-08-08.

## Context

Original PDFs and derived assets need an independently scalable object API. The reference implementation should be self-hostable, Compose-friendly, and avoid making database blobs the evidence vault.

## Decision

SeaweedFS with its authenticated S3 API is the reference object store. Application code depends on a narrow S3-compatible adapter and content-addressing rules, not SeaweedFS internals. Anonymous buckets and known fallback credentials are forbidden.

Long-lived API credentials can read permanent objects and read/write only the
isolated staging bucket. Cleanup-worker credentials can delete only staging
objects. M1 deliberately does not give either process permanent-bucket write
access; M2 must introduce and qualify an isolated verifier/promotion boundary
before wiring upload finalization into a runtime endpoint.

M2 uses a separate `pcbknowledge_verifier` database login and SeaweedFS identity
for that promotion boundary. It may read/write staging and permanent content but
has neither SeaweedFS Admin nor List. The API and cleanup worker still cannot
write permanent content.

## Alternatives

- PostgreSQL large objects.
- Filesystem paths shared by processes.
- MinIO as the default reference implementation.
- A cloud-vendor SDK embedded in domain code.

## Consequences

Local and single-host deployments have an Apache-licensed reference service and can later use a compatible managed store. Operators must back up volumes and qualify S3 behavior used by the adapter.

SeaweedFS 3.85 does not enforce the conditional-copy semantics required as an
object immutability boundary. The adapter therefore uses a verified private
snapshot and a PostgreSQL advisory lock, never copies onto an existing
content-addressed key, and keeps permanent write credentials out of the
long-lived API and cleanup worker. The verifier/promotion process remains a
trusted, isolated component and must retain these negative tests.

The reference verifier is that trusted component, not a storage-level WORM
boundary. SeaweedFS 3.85 cannot grant create-only permanent writes, so compromise
of the verifier credential could overwrite or delete a known key. The local
qualification proves normal code never copies onto an existing canonical key;
production requires a bounded promotion broker or a backend qualified for
conditional create/object lock before claiming credential-compromise resistance.

SeaweedFS 3.85 also lacks `PutBucketCors`. Its process-level `allowedOrigins`
option gates the exact local browser origins, but successful preflights use
wildcard allow-method/header response fields. The local browser therefore uses
credential-free presigned PUT with only `Content-Type`, and tests both an allowed
upload and denial of an untrusted origin. This behavior is not an exact
production CORS policy.

## Rollback

Switch the adapter to a qualified S3-compatible implementation, copy and hash-verify every permanent object, then atomically redirect reads. Historical database identities and digests stay unchanged.
