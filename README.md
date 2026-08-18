# PcbKnowledge

[![CI](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml/badge.svg)](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml)

PcbKnowledge is a **Git-native, Agent-native, evidence-backed** PCB engineering knowledge repository and local review tool. It turns engineering statements from datasheets, application notes, reference designs, and similar sources into validated `Source`, `Entity`, `Fact`, and `EvidenceAnchor` records, with human review and Git publication as explicit boundaries.

> **Open-source boundary:** this repository publishes software, schemas, documentation, Agent workflows, and explicitly reviewed runtime dependencies under Apache-2.0-compatible terms. Production knowledge, internal rules, waivers, historical reviews, and third-party PDF originals live in separately controlled knowledge workspaces. A publicly accessible datasheet is not automatically redistributable. See [`docs/open-source-boundary.md`](docs/open-source-boundary.md).

## Current status

```text
P0.0 Git-native hardening             COMPLETE
P0.1 Typed authority model            COMPLETE
P0.2 Agent-native ingestion           COMPLETE
P0.2.5 Knowledge Workspace boundary   COMPLETE
P0.3a Typed Workbench Foundation      COMPLETE
P0.3b Evidence Review                 COMPLETE
P0.3c Review Closure                  NEXT
P0.4 First real dataset + evals
```

The software/knowledge boundary, typed workbench, and visual evidence-review surface are executable. The public checkout stays data-empty, while real authority is stored in an explicitly selected self-contained Git workspace with a canonical manifest and pinned schema snapshot. The local GUI exposes `/review`, typed Source/Entity/Fact views, and a Fact-to-PDF evidence inspector with exact Source revision/page context and normalized bbox overlays. See [`TODO.md`](TODO.md) and [`docs/architecture.md`](docs/architecture.md).

## Core model

```text
knowledge/
├── sources/       SourceRecordV1
├── entities/      ManufacturerV1 / ComponentV1 / PackageV1
└── facts/         ComponentPinFactV1 / ParameterLimitFactV1

evidence/sha256/  immutable PDF originals
```

A Fact can bind to an exact source revision, PDF page, normalized bounding box, and quote hash. Unknown values, conflicts, wrong packages, wrong revisions, missing evidence, and license blocks remain explicit instead of being filled from model priors.

Published Knowledge is read only from a fully validated immutable Git ref containing committed `APPROVED` authority. Working-tree approval is not publication.

## Software checkout and knowledge workspace

The open-source repository is the software installation. A production data repository is a **knowledge workspace**:

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
mkdir ../PcbKnowledgeData
cd ../PcbKnowledgeData
git init
cd ../PcbKnowledge
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData
```

Or let the initializer create Git only for a missing/empty target:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData --init-git
```

Initialization writes the canonical workspace manifest, pins the current three schemas, and creates empty authority/evidence directories. It **does not** stage, commit, or push. Review and commit the workspace contract with your normal Git workflow before publishing data.

Validate either working files or a committed ref:

```bash
python3 configs/pcbknowledge_workspace.py validate ../PcbKnowledgeData
python3 configs/pcbknowledge_workspace.py validate-ref ../PcbKnowledgeData --ref HEAD
```

A schema/manifest mismatch fails closed. Schema upgrades are explicit contract changes; PcbKnowledge never silently overwrites an existing workspace with a newer schema snapshot.

## Local editor and evidence review

Requirements:

- Git
- Python 3.11+

No Docker, database, account system, Node runtime, or hosted service is required at runtime.

Prepare the software checkout once:

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
```

Open a selected workspace:

```bash
python3 configs/pcbknowledge_workflow.py run --workspace ../PcbKnowledgeData
# or first-use convenience:
python3 configs/pcbknowledge_workflow.py open --workspace ../PcbKnowledgeData
```

The editor binds only to loopback and every page shows the selected workspace root. Source/Entity/Fact/evidence changes and Git diffs come only from that workspace; code and static assets come from the PcbKnowledge software checkout.

Fact detail includes a local visual evidence-review section. For every anchor it keeps the typed Fact context visible, identifies the exact Source revision and page, displays quote/hash metadata, and renders the PDF page with a `PDF_NORMALIZED_V1` bbox overlay. Multiple anchors remain independently navigable.

PDF rendering uses the pinned local `pdfjs-dist` 6.2.108 legacy display-layer module and worker. The runtime does not fetch viewer code from a CDN. Source evidence is served only when the Source license policy permits Agent/model processing; a blocked Source is rejected by the backend evidence endpoint, not merely hidden in the browser. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`ADR-013`](docs/adr/ADR-013-evidence-anchor-coordinates.md).

Test or package a selected workspace:

```bash
python3 configs/pcbknowledge_workflow.py test --workspace ../PcbKnowledgeData
python3 configs/pcbknowledge_workflow.py package --workspace ../PcbKnowledgeData
```

Package contents come from the selected workspace, including its manifest and pinned schemas. The generated ZIP remains derived output under the software checkout's `build/package/` directory and never becomes workspace authority.

The same default Config / Build / Run / Test / Package actions remain available through the FreeCM VS Code / Cursor extension. Use the terminal form when selecting a non-default external workspace.

## Agent / human boundary

Agents may:

- create, edit, and submit Source / Entity / Fact drafts;
- attach evidence that passed the source license gate;
- validate authority, inspect conflicts and missing anchors, and produce diffs;
- hand a complete `DATA_ONLY` change to a human reviewer.

Agents may not:

- approve or reject records;
- stage, commit, or push Git changes;
- bypass the Source license gate to read blocked content;
- infer engineering facts from similar MPNs, similar devices, or model priors;
- silently switch workspaces;
- mutate live PCB board state.

Use an explicit workspace with the Agent CLI:

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData source list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData entity list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData fact list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData change-scope
```

The four repository-local Agent skills follow the same rule: they validate `<workspace>` first and keep `--repo '<workspace>'` on every operation.

## Public source guard

The public upstream intentionally stays data-empty:

```text
knowledge/sources/.gitkeep
knowledge/entities/.gitkeep
knowledge/facts/.gitkeep
evidence/sha256/.gitkeep
```

Real Source/Fact JSON and PDF evidence must not be committed to the public source repository. The machine gate is:

```bash
python3 configs/check_public_repo.py
```

`PUBLIC_REFERENCE` means that a source is publicly accessible; it is **not equivalent to** `OPEN_LICENSE`. Each `SourceRecord` controls its own license policy. Apache-2.0 covers this repository's software and documentation, not third-party engineering documents.

## Verification

Run the local gates before publishing code changes:

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

Workspace-boundary changes additionally use synthetic external Git repositories and schema/manifest tamper tests. GUI changes require focused HTTP/view-model tests plus a real loopback smoke. The PDF.js checker pins the exact vendor file set, byte sizes, SHA-256 values, package integrity, and version before the evidence-review server starts.

Browser-canvas placement is a visual acceptance surface: before reviewing production data, open at least one representative Fact in a desktop browser and verify that its highlighted bbox covers the quoted Source region. P0.4 expands this to rotated/cropped and complex-font PDFs.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`AGENTS.md`](AGENTS.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and [`docs/open-source-boundary.md`](docs/open-source-boundary.md) before opening a pull request. Do not place internal company material, unlicensed PDFs, real credentials, or production knowledge fixtures in issues, pull requests, Actions artifacts, or Git history.

Report security issues privately according to [`SECURITY.md`](SECURITY.md).

## License

PcbKnowledge software and repository documentation are licensed under the [Apache License 2.0](LICENSE), unless a file explicitly states otherwise. Vendored third-party assets retain their upstream notices and licenses. Third-party engineering documents and knowledge datasets retain their own rights and licenses.
