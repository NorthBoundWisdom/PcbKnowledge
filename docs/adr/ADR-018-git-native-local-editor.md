# ADR-018: Git-native local editor supersedes the service-platform MVP

- Status: Accepted
- Date: 2026-08-10
- Supersedes for the current MVP: ADR-002, ADR-003, ADR-005, ADR-006, ADR-007, ADR-008, ADR-009, ADR-017
- Preserves: ADR-001, ADR-004, ADR-012, ADR-013, ADR-015, ADR-016

## Context

The first implementation assumed a multi-user online knowledge service. That led to a local
Compose topology containing an identity provider, PostgreSQL, S3-compatible storage, an API,
workers, a web application, a gateway, migrations and observability. Its security properties
were appropriate for a shared service, but its installation and operating model did not match
the actual first users: two trusted internal contributors who clone the same Git repository,
want a local GUI, inspect diffs and commit accepted data.

Improving container startup or hiding login screens would not fix this mismatch. The canonical
data source and review receipt must move from database transactions to repository files and Git
history.

## Decision

The current MVP is a local, Git-native editor:

1. Canonical knowledge records are deterministic UTF-8 JSON files under `knowledge/records/`.
2. Original PDFs are content-addressed by actual SHA-256 bytes under `evidence/sha256/`.
3. The editor is one loopback-only Python process with repository-owned static assets. It has no
   login page, network identity provider, database or object store.
4. Local operating-system file permissions are the runtime trust boundary. Git author identity,
   diffs and commit history are the collaboration and attribution boundary.
5. Saving edits changes only the working tree. The application never stages, commits or pushes.
6. AI Agents use the same validation library and file model. They may prepare drafts but have no
   approve, commit or push operation.
7. `DRAFT` and `READY_FOR_REVIEW` may contain explicit unknowns. `APPROVED` fails closed unless
   required identity, source, license and evidence fields are complete and internally coherent.
8. Derived search indexes and previews are disposable and must be rebuildable from Git data.

The prior service implementation is removed rather than maintained as a second runtime. The old
ADRs remain as historical records and may inform a future shared-service product, but they no
longer govern the executable MVP.

## Security and evidence consequences

- This is not an anonymous administrator mode: there is no shared administrative service. A user
  can only edit a local clone already writable by that user's operating-system account.
- The application binds only to loopback and rejects cross-origin mutation requests.
- Git author names are suitable for the explicitly trusted two-person phase, but are not strong
  authentication. Remote/shared deployment requires a new ADR and authentication design.
- Git history improves recovery from erroneous edits, but it is not a substitute for an off-device
  repository backup.
- Binary PDF contents do not have a useful textual diff. Their digest, size, source, license and
  record linkage remain reviewable as text. Git LFS may be introduced later by a separate decision
  when repository size justifies its installation cost.

## Rejected alternatives

- Keep Compose and hide it behind a launcher: still slow, opaque and database-centric.
- Use a mutable local SQLite database as the source of truth: diffs and merge review would remain
  opaque. A SQLite index is permitted only as a derived cache.
- Trust a device hostname as identity: hostnames are mutable and add no value in a local Git trust
  model.
- Automatically commit from the GUI or Agent: removes the deliberate human review boundary.
