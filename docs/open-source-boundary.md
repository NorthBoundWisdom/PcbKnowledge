# Public knowledge and source-original boundary

[ADR-021](adr/ADR-021-lightweight-curation-local-evidence.md) and
[ADR-022](adr/ADR-022-board-generation-knowledge.md) allow software and small
original curated metadata in this upstream. Third-party PDFs, extracted pages,
screenshots, copied libraries/catalogs, private data and secrets stay out of Git.
Public availability is `PUBLIC_REFERENCE`, not `OPEN_LICENSE`.

Source records classify processing rights before bytes are read. `UNKNOWN`,
`RESTRICTED` and `LICENSED_BLOCKED_FOR_AI` block processing; IPC is blocked by
default. Originals live only in ignored content-addressed local caches and are
never packaged. A metadata-only clone reports `NOT_LOCALLY_VERIFIED`.

`python3 configs/check_public_repo.py` checks both index blobs and working files
for allowed metadata paths, binary payloads, source originals and size limits.
Only the exact pinned PDF.js runtime files have a software vendor exception.
`python3 configs/check_english_repo.py` enforces English repository text.

Workspaces pin the `board-generation-v2` contract and exact schema bytes. Keep
private knowledge in explicitly selected external Git workspaces. Data commits
stay separate from schemas and policy. Commit and push only with task authority;
fetch and reconcile before an authorized push. The browser never performs Git writes.
