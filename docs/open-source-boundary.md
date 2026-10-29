# Public knowledge and source-original boundary

The owner has replaced the former data-empty public-software restriction. The
current contract is [lightweight knowledge](legacy/intake/lightweight-knowledge.md), accepted in
[ADR-021](adr/ADR-021-lightweight-curation-local-evidence.md). Earlier ADRs preserve
historical design rationale, not a prohibition on the newly authorized curation.

## Allowed public material

- Software, schemas, documentation, synthetic tests, and reviewed vendor assets.
- Small original paraphrased summaries, factual annotations, and source metadata.
- Explicitly noncanonical intake with truthful Agent review under owner delegation.
- Canonical typed metadata only when it actually satisfies the canonical contract.

Never add third-party PDFs, screenshots, archives, raw extracted pages, private
records, internal rules, waivers, customer data, secrets, or credentials. Public
access is not permission to redistribute. Apache-2.0 covers this project's own
software/documentation, not the manufacturer documents cited by annotations.

`PUBLIC_REFERENCE` is distinct from `OPEN_LICENSE`. Unknown redistribution rights
remain explicit in intake. Canonical `UNKNOWN`, `RESTRICTED`, and
`LICENSED_BLOCKED_FOR_AI` source-processing gates are not overridden by a curated
intake review. IPC and equivalent restricted standards remain blocked by default.

## Storage and checks

Original bytes live only in ignored `.pcbknowledge/evidence/sha256/` local caches.
Packages omit those bytes. A metadata-only clone reports absent evidence as
`NOT_LOCALLY_VERIFIED`, not verified. Existing pinned PDF.js runtime assets are
retained as software, not used as an exception for document uploads.

Run `python3 configs/check_public_repo.py` against both tracked working files and
index blobs before committing. Staged-only files, alternate paths, binary payloads,
and oversize text cannot bypass the gate. It has per-file limits rather than a
fixed lifetime corpus ceiling. Passing a machine size/type check does not establish
factual quality, rights, or acceptance.

## Workspace and collaboration

Select workspaces explicitly; never fall back to a different checkout. Pin exact
schemas with `typed-v2-local-cache`. Do not silently migrate an older workspace or
replace its digest. Keep private knowledge in controlled repositories.

The owner authorizes Agent review of intake and focused main-branch commits/pushes.
Fetch/reconcile remote work, preserve others' modifications, and never force-push.
The GUI remains free of Git write operations. Do not falsely describe Agent
acceptance as human review or incomplete intake as published canonical Facts.

Public repository-facing text stays English. Review issues, logs, artifacts, and
Git diffs for sensitive material before publication; do not assume ignored files
are safe to attach to an issue or package.
