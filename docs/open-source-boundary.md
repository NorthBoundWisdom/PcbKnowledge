# Open-source distribution boundary

> Status: ACTIVE
> Established: 2026-08-18
> Applies to: the PcbKnowledge public source repository, contributors, CI, Agents, and private knowledge workspaces

## 1. Purpose

PcbKnowledge software infrastructure is suitable for public collaboration, while PCB engineering knowledge and source evidence have different copyright, redistribution, and commercial-sensitivity boundaries. This document separates them:

```text
Public PcbKnowledge source
  = code + schemas + docs + Agent skills + synthetic tests

Private knowledge workspace
  = Source / Entity / Fact authority + licensed/internal evidence + review history
```

Open source does not mean publishing every file that happens to be in a development checkout. Apache-2.0 licenses only the software and repository material that the project has the right to license. It does not relicense manufacturer datasheets, IPC or similar standards, internal company guidelines, customer information, or user data.

## 2. Public upstream contract

The public upstream tracks only directory placeholders below `knowledge/**` and `evidence/**`:

```text
knowledge/sources/.gitkeep
knowledge/entities/.gitkeep
knowledge/facts/.gitkeep
evidence/sha256/.gitkeep
```

`configs/check_public_repo.py` validates this contract against tracked Git paths. Any real JSON, PDF, or other file added below these roots fails the check. CI runs this gate before the core repository tests.

Synthetic fixtures belong under `tests/**`. Do not rename or redact a restricted real document and treat it as a synthetic fixture.

If the project later publishes a public PCB knowledge dataset, create a separate data repository with its own licensing and redistribution review. Do not disable the public-source guard in this software repository.

## 3. Private knowledge workspace

Production data belongs in a separate private Git repository, for example:

```text
PcbKnowledge/              # public software
PcbKnowledgeData/          # private authority/evidence
```

The Agent CLI already accepts an explicit repository root:

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData source list
```

P0.2.5 makes the workspace contract explicit for initialization, GUI, FreeCM lifecycle, and packaging. The target workspace remains a self-contained Git publication unit: its schemas, authority JSON, evidence, and publication history must be verifiable from the same repository snapshot.

An Agent must never move data between public and private repositories on its own. The caller selects the target workspace explicitly. License gates, review state, immutability, publication, and `DATA_ONLY/MIXED` rules remain unchanged in the private workspace.

## 4. License taxonomy and redistribution

The `SourceRecord` taxonomy is unchanged by the open-source status of the software:

- `PUBLIC_REFERENCE`: the source is publicly accessible; **this does not grant permission to re-host or redistribute the original**;
- `OPEN_LICENSE`: an explicit open license exists and its terms still apply;
- `INTERNAL`: internal processing is permitted, but the material does not enter the public upstream;
- `RESTRICTED`: distribution or processing is restricted and policy fails closed;
- `LICENSED_BLOCKED_FOR_AI`: Agent/model reading, parsing, indexing, embedding, and derived-content exposure are blocked;
- `UNKNOWN`: rights are uncertain, so processing fails closed.

Public examples and test material must be synthetic or have an explicit, documented redistribution basis.

## 5. Pull requests and CI

Public pull requests are untrusted input:

- workflows default to `contents: read`;
- ordinary pull requests must not receive repository secrets;
- credentials, internal endpoints, customer identifiers, production logs, and unauthorized evidence are rejected;
- `check_english_repo.py` and `check_public_repo.py` run before the core tests;
- code/schema/policy changes and knowledge-data changes do not share a commit;
- CodeQL is enabled when the repository is public;
- Dependabot maintains GitHub Actions versions.

## 6. Repository language

The public repository uses English as its contributor and UI language. Documentation, user-facing UI strings, repository policy text, comments intended for contributors, and public fixtures must not introduce CJK, Kana, or Hangul text. `configs/check_english_repo.py` enforces this on tracked UTF-8 source files.

This is a repository-maintenance rule, not a restriction on knowledge content in a private workspace. A private workspace may contain source-backed multilingual engineering material when licensing and processing policy allow it.

## 7. Visibility-change and rewritten-history gate

Before changing repository visibility, audit more than the current working tree:

1. scan reachable Git history for secrets;
2. verify copyright and provenance for historical source, templates, images, and fixtures;
3. inspect relevant Actions logs and artifacts;
4. inspect non-`main` branches, tags, and pull-request refs;
5. verify third-party licenses and attribution for vendored material;
6. revoke or rotate any discovered secret before deciding whether history must be rewritten.

The repository history was intentionally rewritten before public release. Force-pushing removes old commits from the normal branch history but may not immediately remove server-side unreachable Git objects addressable by a known SHA. If such an object contains an actual credential or similarly sensitive material, use the hosting provider's sensitive-data-removal process rather than treating the rewrite as erasure.

The public-source guard is a continuous integration control, not a historical scanner.

## 8. Publication boundary remains unchanged

Inside a private knowledge workspace, the original three-layer publication boundary still applies:

```text
working tree DRAFT / READY_FOR_REVIEW
    = preparation in progress

working tree APPROVED
    = human-approved, not yet published

committed APPROVED in publication ref
    = Published Knowledge
```

"Published Knowledge" means published to the controlled audience of that knowledge workspace. It does not imply publication to the public internet.
