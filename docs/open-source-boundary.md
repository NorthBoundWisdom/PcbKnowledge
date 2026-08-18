# Open-source distribution boundary

> Status: ACTIVE
> Established: 2026-08-18
> Applies to: the PcbKnowledge public source repository, contributors, CI, Agents, and private knowledge workspaces

## 1. Purpose

PcbKnowledge software infrastructure is suitable for public collaboration, while PCB engineering knowledge and source evidence have different copyright, redistribution, and commercial-sensitivity boundaries.

```text
Public PcbKnowledge source
  = code + schemas + docs + Agent skills + synthetic tests

Private knowledge workspace
  = Source / Entity / Fact authority + licensed/internal evidence + review history
```

Apache-2.0 licenses only software and repository material that the project has the right to license. It does not relicense manufacturer datasheets, IPC or similar standards, internal company guidelines, customer information, or user data.

## 2. Public upstream contract

The public upstream tracks only directory placeholders below `knowledge/**` and `evidence/**`:

```text
knowledge/sources/.gitkeep
knowledge/entities/.gitkeep
knowledge/facts/.gitkeep
evidence/sha256/.gitkeep
```

`configs/check_public_repo.py` validates this contract against tracked Git paths. Any real JSON, PDF, or other file added below these roots fails the check. Synthetic fixtures belong under `tests/**`; do not rename or redact a restricted real document and treat it as synthetic.

The public checkout also contains `pcbknowledge.workspace.json` plus the three current schemas so it can serve as an empty development workspace for build/test/smoke validation. That does not make it a valid destination for production knowledge.

If the project later publishes a public PCB knowledge dataset, create a separate data repository with its own licensing and redistribution review. Do not disable the public-source guard in the software repository.

## 3. Private knowledge workspace

Production data lives in a separate private Git repository:

```text
PcbKnowledge/              public software
PcbKnowledgeData/          private authority/evidence
```

Initialize it explicitly:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData
```

A workspace is self-contained and carries:

```text
pcbknowledge.workspace.json
schemas/
knowledge/
evidence/
```

The manifest pins the workspace format and exact schema digest. A manifest/schema mismatch fails closed. `init` is idempotent only when the existing workspace already has the exact requested contract; it never silently upgrades schemas and never stages, commits, or pushes.

Agent CLI selection is explicit:

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
```

GUI/workflow selection is explicit:

```bash
python3 configs/pcbknowledge_workflow.py run --workspace ../PcbKnowledgeData
python3 configs/pcbknowledge_workflow.py package --workspace ../PcbKnowledgeData
```

An Agent must never move data between public and private repositories on its own. An invalid selected workspace is a stop condition rather than permission to fall back to another repository.

## 4. License taxonomy and redistribution

The `SourceRecord` taxonomy is unchanged by the open-source status of the software:

- `PUBLIC_REFERENCE`: publicly accessible; **not permission to re-host or redistribute the original**;
- `OPEN_LICENSE`: explicitly open-licensed and still subject to that license;
- `INTERNAL`: internal processing is permitted in the controlled workspace;
- `RESTRICTED`: distribution or processing is restricted and policy fails closed;
- `LICENSED_BLOCKED_FOR_AI`: Agent/model reading, parsing, indexing, embedding, and derived-content exposure are blocked;
- `UNKNOWN`: rights are uncertain, so processing fails closed.

Public examples and test material must be synthetic or have an explicit, documented redistribution basis.

## 5. Workspace publication boundary

A private workspace retains the three-layer publication model:

```text
working tree DRAFT / READY_FOR_REVIEW
    = preparation in progress

working tree APPROVED
    = human-approved, not yet published

committed APPROVED in publication ref
    = Published Knowledge
```

The workspace schema snapshot travels with the data. Supported published Agent reads validate the manifest and schema digest from the same committed ref before using the typed published reader. Mutable schemas in the software checkout do not redefine old workspace history.

Schema/manifest upgrades are contract changes and remain separate from knowledge/evidence data commits that rely on the new contract.

## 6. Pull requests and CI

Public pull requests are untrusted input:

- workflows default to `contents: read`;
- ordinary pull requests must not receive repository secrets;
- credentials, internal endpoints, customer identifiers, production logs, and unauthorized evidence are rejected;
- `check_english_repo.py` and `check_public_repo.py` run before the core tests;
- production knowledge/evidence never enters software commits;
- CodeQL is enabled when the repository is public;
- Dependabot maintains GitHub Actions versions.

## 7. Repository language

The public repository uses English as its contributor and UI language. Documentation, user-facing UI strings, repository policy text, contributor comments, and public fixtures must not introduce CJK, Kana, or Hangul text. `configs/check_english_repo.py` enforces this on tracked UTF-8 source files.

This rule does not prohibit multilingual engineering material inside a private knowledge workspace when source licensing and processing policy allow it.

## 8. Visibility and rewritten-history gate

Before changing repository visibility, audit more than the current working tree: reachable Git history, historical copyright/provenance, Actions logs/artifacts, branches/tags/pull refs, and third-party attribution.

The repository history was intentionally rewritten before public release. Force-pushing removes old commits from normal branch history but may not immediately remove server-side unreachable Git objects addressable by a known SHA. If such an object contains an actual credential or similarly sensitive material, use the hosting provider's sensitive-data-removal process rather than treating the rewrite as erasure.

The public-source guard is a continuous integration control, not a historical scanner.
