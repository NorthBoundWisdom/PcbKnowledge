# Lightweight knowledge and local evidence contract

## Two evidence levels, not two authorities

`knowledge/intake/` contains small, original paraphrased summaries and annotations.
It is a curation queue, not canonical `Source`/`Entity`/`Fact` authority. Its format
is `pcbknowledge-independent-intake-v1`, with `canonical: false`. Acceptance here
means useful reviewed material may accumulate; it does not assert engineering
sign-off, complete component coverage, validated procurement identity, or a passed
formal pilot.

The owner delegates review of these drafts to the Agent. Record the actual actor
as an Agent and the authority as owner delegation. Use
`AGENT_REVIEWED_UNDER_OWNER_DELEGATION` only after an actual review; unreviewed
material stays `DRAFT`. Never invent a human reviewer or imply that an
owner read each fact. The owner may audit, correct, or withdraw accepted intake.
No per-fact human wait is required for this delegated curation lane.

An intake item must retain source URL, document revision when known, exact device
and package scope, parameter conditions, and known limitations. `TEXT_LOCATOR_ONLY`
means source text and page/section locators were checked, but original bytes and
visual geometry were not attested. The first TI batch has stronger, separately
recorded byte-identity and rendered-page review receipts; it still lacks precise
region/bbox annotation. Review-level statements are item-specific, not a blanket
claim about every future batch. Null SHA-256, cache path, or bbox is unknown,
not permission to fabricate one. Live source URLs can change. Curation acceptance
and evidence completeness are independent dimensions.

Canonical records remain under `knowledge/sources/`, `knowledge/entities/`, and
`knowledge/facts/`, with the established typed validators and immutable publication
rules. Promotion requires actual schema-valid identities, source/revision closure,
license authorization, and evidence anchors; copying an intake status into a
canonical record is not promotion. Existing canonical workbench decisions remain
human-review operations; this release does not impersonate a human through that API.
Intake search must retain the noncanonical marker and limitations and must not be
mixed silently into published canonical Fact results.

## Metadata in Git, original bytes outside Git

The workspace schema contract is `typed-v2-local-cache`. Source originals live only
under ignored `.pcbknowledge/evidence/sha256/<prefix>/<sha256>.pdf`. Compute identity
and size from actual bytes. Never add originals, extracted full pages, screenshots,
archives, or binary datasets to Git, including through an alternate folder or the
index. Packages contain metadata, schemas, and annotations, not original PDFs.
The pinned PDF.js runtime assets are software dependencies, not source evidence.

Git publication validates pinned metadata and reference closure; it does not prove
that source bytes are present on the reader's machine. Local cache verification is
reported separately as `VERIFIED`, `NOT_LOCALLY_VERIFIED`, or `TAMPERED`. A clean
clone can have valid metadata and `NOT_LOCALLY_VERIFIED` evidence. Missing originals
are never reported as verified; mismatched bytes are not used. Visual review and
source-byte access require the actual authorized local cache. No network download
or schema migration happens silently.

Existing workspaces with the old schema contract must fail clearly. Preserve their
Git history and originals while planning an explicit migration; do not rewrite
pinned schema digests or silently relabel old evidence paths.

## Public-content and copyright boundary

Commit only small original summaries, annotations, source metadata, and executable
software/documentation. Publicly accessible does not mean openly licensed. Do not
copy substantial source text or redistribute manufacturer PDFs. Keep unknown
redistribution rights explicit. Intake metadata about public factual observations
does not grant canonical Source processing clearance; canonical license gates still
apply. Restricted/private material and credentials never belong in public intake.

Run `python3 configs/check_public_repo.py` before publishing. It checks both working
tracked files and Git index content, including staged-only additions. The guard
uses per-file bounds rather than a lifetime total corpus cap; see its executable
constants for exact limits. Passing the size guard is not a copyright or factual
quality approval. Split knowledge by meaningful source/topic, never to disguise a
raw document or evade the guard.

## Collaboration and publication

The owner authorizes focused main-branch commits and pushes for this work. Fetch
and reconcile the latest remote before pushing; never force-push or overwrite
others' changes. The GUI still performs no Git writes. Separate canonical data
publication from schema/policy changes; a bootstrap noncanonical intake batch may
accompany its tooling and must not be described as canonical publication.

Use issues for independently actionable work: give scope, source/evidence level,
acceptance criteria, file ownership, and forbidden raw artifacts. Review delivered
work against those criteria, leave specific corrections, and close only completed
issues with a verifiable receipt. Do not duplicate an existing active assignment.
Continue bounded batches with counts, provenance, corrections, and unresolved
questions; do not present unchecked quantity as knowledge quality.
