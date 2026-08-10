# ADR-019: Git commit is the publication boundary and data/code commits stay separate

## Status

Accepted — 2026-08-10.

## Context

ADR-018 moved the MVP authority from database transactions to repository files and Git history. The
first implementation still left two ambiguities:

1. an `APPROVED` record in the working tree could be mistaken for formally published knowledge;
2. one commit could theoretically change validators/schema/policy and add newly approved knowledge at
   the same time.

Both weaken the review model. A local approval is a human decision, but it is not yet a durable team
publication receipt. Likewise, a commit that changes the acceptance rules and the accepted data cannot
be reviewed as a clean knowledge ingestion event.

## Decision

1. Working-tree records are preparation/review state, including working-tree `APPROVED`.
2. Published Knowledge is an `APPROVED` record read from the committed Git ref used for publication;
   for the current workflow this is `main`/local `HEAD` after the accepted commit.
3. Agent-facing formal reads must use a published view. Workspace reads remain explicit preparation
   operations.
4. Repository changes are classified as:
   - `DATA_ONLY`: only `knowledge/**` and/or `evidence/**`;
   - `CODE_ONLY`: every other repository path;
   - `MIXED`: both.
5. `MIXED` is not a valid single commit. Knowledge/evidence ingestion and software/schema/policy
   changes must be committed separately.
6. The application still does not stage, commit or push. Humans keep the final Git publication
   decision.

## Consequences

- Approval and publication become distinct and inspectable.
- Future SQLite/FTS/vector indexes can rebuild only from published data by default.
- Agent runs can avoid accidentally consuming another user's uncommitted drafts.
- Validation rules cannot be changed in the same commit that introduces data relying on those changes.
- Operators must sometimes split one workspace into two commits; this is intentional.

## Implementation

- `KnowledgeRepository.read_published_snapshot()` validates all three typed schemas, canonical
  Source/Entity/Fact records, filename identity, reference/supersedes closure, EvidenceAnchors and
  content-addressed evidence from one immutable Git commit before exposing approved authority. It
  never borrows JSON, schemas or evidence from the working tree.
- Agent CLI supports `list --published`.
- `KnowledgeRepository.git_change_scope()` and Agent CLI `change-scope` expose the commit classifier.
  A non-empty index is the commit candidate; otherwise unstaged/untracked paths are the preview.
  Rename/copy classification includes both source and destination.
- SourceRecordV1 and FactRecordV1 preserve review decisions in append-only `review_history` so
  publication does not erase prior rejection/resubmission context.

## Alternatives rejected

- Treat any working-tree `APPROVED` record as published: not durable and can leak local drafts.
- Auto-commit approval in the GUI: removes the deliberate Git review boundary.
- Allow mixed commits with reviewer discretion: too easy for an Agent to modify its own acceptance
  rules and data in one change.

## Rollback

A future shared-service architecture may introduce a database publication transaction, but it must
explicitly supersede this ADR. Existing Git-published records remain immutable historical evidence.
