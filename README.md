# PcbKnowledge

[![CI](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml/badge.svg)](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml)

PcbKnowledge is a **Git-native, Agent-native, evidence-backed** PCB engineering knowledge repository and local review tool. It turns engineering statements from datasheets, application notes, reference designs, and similar sources into validated `Source`, `Entity`, `Fact`, and `EvidenceAnchor` records, with human review and Git publication as explicit boundaries.

> **Open-source boundary:** this repository publishes software, schemas, documentation, Agent workflows, synthetic tests, and explicitly reviewed runtime dependencies. Production knowledge, internal rules, waivers, historical reviews, and third-party PDF originals live in separately controlled knowledge workspaces. A publicly accessible datasheet is not automatically redistributable. See [`docs/open-source-boundary.md`](docs/open-source-boundary.md).

## Current status

```text
P0.0 Git-native hardening             COMPLETE
P0.1 Typed authority model            COMPLETE
P0.2 Agent-native ingestion           COMPLETE
P0.2.5 Knowledge Workspace boundary   COMPLETE
P0.3a Typed Workbench Foundation      COMPLETE
P0.3b Visual Evidence Review          COMPLETE
P0.3c Review Closure                  COMPLETE
P0.4a Pilot dataset                   NEXT
```

The P0 software path is implemented end-to-end: Agents can prepare typed Source/Entity/Fact authority in an explicitly selected knowledge workspace; humans can inspect exact Source evidence, review typed closure, approve or reject Source/Fact records, and then publish with ordinary Git. The GUI never stages, commits, or pushes.

## Core authority

```text
knowledge/
├── sources/       SourceRecordV1
├── entities/      ManufacturerV1 / ComponentV1 / PackageV1
└── facts/         ComponentPinFactV1 / ParameterLimitFactV1

evidence/sha256/  immutable PDF originals
```

A Fact can bind to an exact Source revision, PDF page, normalized bounding box, and quote hash. Unknown values, conflicts, wrong packages, wrong revisions, missing evidence, and license blocks remain explicit instead of being filled from model priors.

Published Knowledge is read only from a fully validated immutable Git ref containing committed `APPROVED` authority. Working-tree approval is not publication.

## Public software versus private knowledge workspace

The open-source repository is the software installation. Production knowledge belongs in a separate self-contained Git workspace:

```text
PcbKnowledge/                     public software

PcbKnowledgeData/                 private workspace
├── .git/
├── pcbknowledge.workspace.json
├── schemas/
├── knowledge/
│   ├── sources/
│   ├── entities/
│   └── facts/
└── evidence/sha256/
```

Create a clean workspace:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData --init-git
```

Or initialize an existing empty Git repository:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData
```

Initialization pins the current schemas and creates the empty authority/evidence layout. It does **not** stage, commit, push, or create production data.

Validate working files or an immutable ref:

```bash
python3 configs/pcbknowledge_workspace.py validate ../PcbKnowledgeData
python3 configs/pcbknowledge_workspace.py validate-ref ../PcbKnowledgeData --ref HEAD
```

A manifest/schema mismatch fails closed. Schema upgrades are explicit contract changes; existing workspaces are never silently rewritten to the software checkout's latest schema.

## Local workbench

Requirements:

- Git
- Python 3.11+

No Docker, database, account system, hosted service, or Node runtime is required at runtime.

Prepare the software checkout:

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
```

Open a selected workspace:

```bash
python3 configs/pcbknowledge_workflow.py open --workspace ../PcbKnowledgeData
```

Active routes:

```text
/review
/sources
/sources/<id>
/entities
/entities/<id>
/facts
/facts/<id>
/diff
```

Every page shows the exact selected workspace root. Source/Entity/Fact authority, evidence, review state, and Git diffs come only from that workspace; code and static assets come from the PcbKnowledge software checkout.

### Visual evidence review

Fact detail keeps typed payload, component/package identity, conditions/applicability, Source revision, and EvidenceAnchor metadata beside a local PDF rendering. The workbench renders the exact referenced Source page and overlays the `PDF_NORMALIZED_V1` bbox. Multiple anchors remain independently navigable, and quote plus `quote_sha256` stay visible.

PDF rendering uses the pinned local `pdfjs-dist` 6.2.108 display layer and worker. Viewer code is not fetched from a CDN at runtime. Source evidence is served only when the Source license policy permits Agent/model processing; blocked evidence is rejected by the backend endpoint, not merely hidden in the browser. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`ADR-013`](docs/adr/ADR-013-evidence-anchor-coordinates.md).

### Human review closure

For a `READY_FOR_REVIEW` Source or Fact, the workbench recomputes the decision closure before showing or accepting a human review write.

Fact approval fails closed on:

- missing or incomplete evidence anchors;
- unresolved semantic conflicts;
- referenced Source not `APPROVED`;
- missing Source PDF evidence;
- Source license classes that block evidence processing.

Both approval and rejection require the current next-commit candidate to be `CLEAN` or `DATA_ONLY`. `CODE_ONLY` and `MIXED` block the decision so review history cannot be mixed with software/schema/policy changes.

Before a decision the UI shows the exact selected closure paths, selected Git status, and selected diff. The POST path recomputes the same gates immediately before mutation; the browser is not the authority for review policy.

Approved Facts are immutable in place and expose no mutation form. Corrections use a new Fact plus explicit `supersedes`.

## Agent / human boundary

Agents may:

- create and edit Source/Entity/Fact drafts;
- attach evidence that passed the Source license gate;
- validate authority and inspect unknown/conflict/missing-anchor state;
- submit Source/Fact records for human review;
- prepare a `DATA_ONLY` handoff.

Agents may not:

- approve or reject records;
- stage, commit, or push Git changes;
- bypass Source license policy;
- infer facts from similar MPNs/devices or model priors;
- silently switch workspaces;
- mutate live PCB board state.

Use an explicit workspace:

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData source list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData entity list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData fact list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData change-scope
```

Repository-local Agent skills enforce the same explicit-workspace boundary.

## Public source guard

The public upstream intentionally keeps only placeholders under production authority roots:

```text
knowledge/sources/.gitkeep
knowledge/entities/.gitkeep
knowledge/facts/.gitkeep
evidence/sha256/.gitkeep
```

The machine gate is:

```bash
python3 configs/check_public_repo.py
```

`PUBLIC_REFERENCE` means publicly accessible, not automatically redistributable. Apache-2.0 applies to this repository's software/documentation unless stated otherwise; third-party engineering documents retain their own rights and licenses.

## Verification

Main repository gate sequence:

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/check_pdfjs_vendor.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

P0.3c's validated checkpoint runs 96 tests with 0 failures, errors, or skips across Ubuntu/Python 3.11, Ubuntu/Python 3.14, macOS/Python 3.11, and Windows/Python 3.11.

Automated HTTP tests verify loopback Host/Origin, CSRF, optimistic revisions, selected workspace identity, Source/Fact decision gating, immutable approved UX, PDF license blocking, and GUI no-stage behavior. Pixel-level PDF/bbox placement on a real vendor document is deliberately the first P0.4a private-workspace acceptance rather than a synthetic browser claim.

## Next: P0.4a pilot dataset

The next stage is not another infrastructure expansion. It is a small real-data pilot: 3–5 common ICs, 20–40 Facts, at least one multi-package case, one revision/supersedes case, several deliberately wrong/ambiguous negatives, and real visual evidence acceptance. The pilot should expose schema/viewer shortcomings before P1 retrieval or broader Fact families are built.

See [`TODO.md`](TODO.md) for the executable roadmap.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`AGENTS.md`](AGENTS.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and [`docs/open-source-boundary.md`](docs/open-source-boundary.md) before contributing. Do not place internal material, unlicensed PDFs, real credentials, or production knowledge fixtures in issues, pull requests, Actions artifacts, or Git history.

Report security issues privately according to [`SECURITY.md`](SECURITY.md).

## License

PcbKnowledge software and repository documentation are licensed under the [Apache License 2.0](LICENSE), unless a file explicitly states otherwise. Vendored third-party assets retain their upstream notices and licenses. Third-party engineering documents and knowledge datasets retain their own rights and licenses.
