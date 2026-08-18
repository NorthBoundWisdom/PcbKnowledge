# PcbKnowledge

[![CI](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml/badge.svg)](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml)

PcbKnowledge is a **Git-native, Agent-native, evidence-backed** PCB engineering knowledge repository and local review tool. It turns engineering statements from datasheets, application notes, reference designs, and similar sources into validated `Source`, `Entity`, `Fact`, and `EvidenceAnchor` records, with human review and Git publication as explicit boundaries.

> **Open-source boundary:** this repository publishes software, schemas, documentation, and Agent workflows under Apache-2.0. Production knowledge, internal rules, waivers, historical reviews, and third-party PDF originals are not part of the default open-source distribution. A publicly accessible datasheet is not automatically redistributable. See [`docs/open-source-boundary.md`](docs/open-source-boundary.md).

## Current status

```text
P0.0 Git-native hardening             COMPLETE
P0.1 Typed authority model            COMPLETE
P0.2 Agent-native ingestion           COMPLETE
P0.2.5 Knowledge Workspace boundary   NEXT
P0.3 Local Review Workbench
P0.4 First real dataset + evals
```

The typed authority and Agent ingestion paths are implemented. The current GUI is still the Source Corpus editor. P0.2.5 separates the public software checkout from private knowledge workspaces before P0.3 evolves the GUI into the Fact Review Workbench. See [`TODO.md`](TODO.md) for the execution roadmap and [`docs/architecture.md`](docs/architecture.md) for the durable architecture.

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
- mutate live PCB board state.

## Quick start

Requirements:

- Git
- Python 3.11+

No Docker, database, account system, Node runtime, or hosted service is required.

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py run
```

The same Config / Build / Run / Test / Package actions are available through the FreeCM VS Code / Cursor extension. The editor binds only to loopback and must not be exposed to a LAN, VPN, or the public internet.

## Agent CLI

```bash
python3 configs/pcbknowledge_agent.py source list
python3 configs/pcbknowledge_agent.py entity list
python3 configs/pcbknowledge_agent.py fact list
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py change-scope
```

The Agent CLI already accepts a separate Git repository as its knowledge root:

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
```

P0.2.5 makes that boundary a first-class workspace contract for the GUI, FreeCM workflow, packaging, and initialization as well.

## Public source and private knowledge

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

Any additional tracked file below `knowledge/**` or `evidence/**` fails that check. Public fixtures must be synthetic or have a separately reviewed redistribution basis.

`PUBLIC_REFERENCE` means that a source is publicly accessible; it is **not equivalent to** `OPEN_LICENSE`. Each `SourceRecord` controls its own license policy. Apache-2.0 covers this repository's software and documentation, not third-party engineering documents.

## Verification

Run the local gates before publishing code changes:

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

GitHub Actions runs the same core gates on pushes and pull requests. Public repositories additionally enable the cross-platform matrix and CodeQL. Workflows use minimum repository permissions and do not expose project secrets to ordinary pull requests.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/open-source-boundary.md`](docs/open-source-boundary.md) before opening a pull request. Do not place internal company material, unlicensed PDFs, real credentials, or production knowledge fixtures in issues, pull requests, Actions artifacts, or Git history.

Report security issues privately according to [`SECURITY.md`](SECURITY.md).

## License

PcbKnowledge software and repository documentation are licensed under the [Apache License 2.0](LICENSE), unless a file explicitly states otherwise. Third-party engineering documents and knowledge datasets retain their own rights and licenses.
