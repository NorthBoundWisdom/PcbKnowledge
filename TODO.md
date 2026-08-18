# TODO — PcbKnowledge Roadmap

> Status: `P0.2_COMPLETE_P0.2.5_NEXT`
> Updated: 2026-08-18
> Current public-source baseline: repository history rewritten for open-source release
> Goal: evolve the completed typed-authority + Agent-ingestion core into a practical PCB engineering knowledge system that can ingest real data, support human evidence review, provide deterministic local retrieval, and feed PCB Agents without making PcbCore depend on the knowledge runtime.

## 0. Document responsibility

This file is the repository's single execution roadmap. It records current stage, unfinished tasks, completion gates, and execution order. Durable architecture belongs in [`docs/architecture.md`](docs/architecture.md); the software/data distribution boundary belongs in [`docs/open-source-boundary.md`](docs/open-source-boundary.md). Historical implementation detail belongs in ADRs and Git history rather than being duplicated here.

### Permanent boundaries

- The public PcbKnowledge repository contains code, schemas, documentation, Agent skills, and synthetic tests, but no production knowledge/evidence.
- Real Source / Entity / Fact authority, internal rules, reviews, waivers, and third-party PDF evidence live in a separately controlled private knowledge workspace.
- A knowledge workspace is a Git repository and remains the only authority for its published knowledge.
- PDF originals are content-addressed from actual SHA-256 bytes.
- The GUI and Agent use the same typed authority model and validator.
- Agents may prepare, edit, validate, and submit drafts; they may not approve, reject, stage, commit, or push.
- Working-tree approval is distinct from Git publication. Formal reads use a fully validated committed snapshot.
- Unknown values, conflicts, wrong revisions, wrong packages, missing anchors, and license blocks stay explicit.
- PcbKnowledge does not read or mutate live PCB board state and is not a PcbCore runtime dependency.
- SQLite/FTS/page-text/vector indexes are disposable derived state, never authority.
- Vector retrieval is not a P0/P1 prerequisite and enters the roadmap only after evaluation demonstrates value.

---

## 1. Completed foundation

### P0.0 — Git-native Core Hardening — COMPLETE

Implemented capabilities include:

- deterministic Git-native JSON/PDF authority;
- SHA-256 content-addressed evidence;
- canonical serialization and strict layout validation;
- append-only review history and optimistic revision tokens;
- committed `APPROVED` immutability plus explicit `supersedes`;
- orphan/shared/published evidence protection;
- repository write locking;
- `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change scope;
- strict separation between working-tree approval and committed publication;
- fully validated published readers;
- deterministic package snapshots.

### P0.1 — Typed Authority Model — COMPLETE

Implemented authority types:

```text
SourceRecordV1
EntityRecordV1
  - ManufacturerV1
  - ComponentV1
  - PackageV1
FactRecordV1
  - ComponentPinFactV1
  - ParameterLimitFactV1
EvidenceAnchorV1
```

Implemented contracts include:

- `knowledge/sources/`, `knowledge/entities/`, and `knowledge/facts/`;
- three canonical JSON schemas;
- explicit Source license taxonomy;
- exact manufacturer / MPN / package identity;
- PDF page + normalized bbox + quote evidence anchors;
- Fact conditions, applicability, and supersedes relationships;
- full Source/Entity/Fact reference-closure validation;
- semantic conflict detection;
- synthetic end-to-end publication tests.

### P0.2 — Agent-native Ingestion — COMPLETE

Repository-local skills:

```text
ingest-engineering-source
resolve-component-identity
extract-component-facts
prepare-knowledge-review
```

Agent CLI supports:

- typed `source / entity / fact` commands;
- stable idempotency keys;
- exact identity resolution;
- `source authorize-read` license/bytes gate;
- explicit unknown, missing-anchor, and conflict output;
- selected-closure `review-status`;
- `DATA_ONLY + WAIT_FOR_HUMAN_REVIEW` handoff;
- explicit `--repo <path>` repository selection.

Open-source source-repository controls include:

- Apache-2.0;
- public-source data guard;
- English-only repository text guard;
- GitHub Actions, CodeQL, and Dependabot configuration;
- CONTRIBUTING / SECURITY / pull-request contracts;
- machine enforcement that the public `knowledge/**` and `evidence/**` roots contain placeholders only.

---

## 2. P0.2.5 — Knowledge Workspace Boundary — NEXT

### 2.1 Objective

Separate the PcbKnowledge software checkout from the Knowledge authority Git repository at runtime before real data or the P0.3 workbench is built around the wrong storage root.

The target structure is:

```text
PcbKnowledge/                     public software
├── src/
├── configs/
├── schemas/
├── docs/
└── tests/

PcbKnowledgeData/                 private knowledge workspace
├── .git/
├── pcbknowledge.workspace.json
├── schemas/
│   ├── source-record.schema.json
│   ├── entity-record.schema.json
│   └── fact-record.schema.json
├── knowledge/
│   ├── sources/
│   ├── entities/
│   └── facts/
└── evidence/sha256/
```

The workspace stays self-contained: a published snapshot must validate against schemas stored in that same Git repository, not mutable schemas from the public software checkout.

### 2.2 Workspace manifest

Add canonical `pcbknowledge.workspace.json` with at least:

```json
{
  "format": "pcbknowledge-workspace-v1",
  "schema_contract": "typed-v1",
  "schema_digest": "<sha256>",
  "created_with": "PcbKnowledge"
}
```

Requirements:

- [ ] canonical UTF-8 JSON with stable field order and trailing newline;
- [ ] strict unsupported-field rejection;
- [ ] schema digest covers the exact three workspace schema files;
- [ ] workspace validation fails if the manifest/schema snapshot disagrees;
- [ ] schema upgrade is explicit and never silently copied over an existing contract;
- [ ] workspace manifest is part of the published-snapshot validation surface.

### 2.3 Workspace initialization

Add an explicit command, preferably:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData
```

Requirements:

- [ ] target must be an existing clean Git repository unless an explicit `--init-git` mode is provided;
- [ ] create `pcbknowledge.workspace.json`;
- [ ] copy/pin the current three schemas;
- [ ] create `knowledge/sources`, `knowledge/entities`, `knowledge/facts`, and `evidence/sha256` placeholders;
- [ ] refuse non-empty/ambiguous authority layouts rather than overwriting them;
- [ ] validate immediately after initialization;
- [ ] initialization is idempotent when the exact contract already exists;
- [ ] no production data is created automatically.

### 2.4 Runtime repository resolution

Introduce one explicit workspace-resolution layer used by CLI, GUI, workflow, and packager.

Requirements:

- [ ] no hidden fallback from an explicitly requested external workspace to the software checkout;
- [ ] `KnowledgeRepository` continues to receive a concrete workspace root and does not learn about sibling repositories;
- [ ] runtime validation checks `.git`, workspace manifest, schemas, authority layout, and evidence layout;
- [ ] public-source checkout may still be used as an empty development workspace for synthetic/local tests, but production commands must support an explicit external root;
- [ ] error messages identify the selected workspace path without leaking evidence contents.

### 2.5 FreeCM / workflow support

Add explicit workspace selection to relevant lifecycle commands:

```bash
python3 configs/pcbknowledge_workflow.py run --workspace ../PcbKnowledgeData
python3 configs/pcbknowledge_workflow.py open --workspace ../PcbKnowledgeData
python3 configs/pcbknowledge_workflow.py package --workspace ../PcbKnowledgeData
```

Also support `test`/`validate` against a selected workspace where useful without changing the software-build receipt semantics.

Requirements:

- [ ] Config/Build remain software-checkout operations;
- [ ] Run/Open validate the selected workspace before binding the server;
- [ ] Package exports the selected workspace, not the public software checkout;
- [ ] workspace selection is visible in terminal receipts;
- [ ] no lifecycle action automatically stages, commits, or pushes either repository;
- [ ] FreeCM manifest and workflow tests remain consistent.

### 2.6 GUI support

The server already accepts a repository root internally; wire it to explicit workspace selection instead of fixed `REPO_ROOT` behavior in the workflow.

Requirements:

- [ ] GUI title/header identifies the selected workspace clearly enough to prevent accidental editing of the wrong repository;
- [ ] all Source edits, evidence reads, review actions, and Git diff views operate only on that workspace;
- [ ] source code/static assets continue to come from the software installation;
- [ ] Host/Origin/CSRF/revision protections remain unchanged;
- [ ] the GUI still performs no Git write operations.

### 2.7 P0.2.5 tests

Add a synthetic external-workspace vertical suite covering at least:

- [ ] initialize an empty temporary Git repository;
- [ ] reject a non-Git target;
- [ ] reject a conflicting/non-empty legacy layout;
- [ ] verify deterministic workspace manifest + schema digest;
- [ ] verify initialization replay is idempotent;
- [ ] Agent `--repo` creates typed data only in the private temporary workspace;
- [ ] GUI reads/writes the external workspace while static assets come from software source;
- [ ] Package exports external workspace authority/evidence/schema;
- [ ] published reader validates workspace-local schema contract;
- [ ] tampered workspace schema or manifest fails closed;
- [ ] public source checkout retains only its four authority/evidence placeholders after the full vertical flow.

### 2.8 Completion gate

P0.2.5 is complete only when:

- [ ] workspace initialization and validation are executable;
- [ ] Agent / GUI / Run/Open / Package can target the external workspace;
- [ ] workspace schema pinning is hermetic and publication-safe;
- [ ] the public-source guard still passes after external data operations;
- [ ] all repository tests pass with no skips;
- [ ] a real loopback GUI smoke test succeeds against a temporary external workspace;
- [ ] `TODO.md`, README, architecture, local workflow, Agent workflow, and open-source-boundary documentation describe the implemented contract rather than a future design.

---

## 3. P0.3 — Local Review Workbench

P0.3 starts only after P0.2.5 closes the workspace boundary.

### P0.3a — Typed Workbench Foundation

Refactor the current Source-only GUI into a small application/view layer while retaining the standard-library server and no Node build chain.

Target routes:

```text
/review                 primary task queue
/sources
/entities
/facts
```

Tasks:

- [ ] keep HTTP/security routing separate from typed view-model construction;
- [ ] Source list/detail;
- [ ] Entity list/detail with manufacturer/component/package identity;
- [ ] Fact list/detail with typed payload inspector;
- [ ] Source/Entity/Fact/supersedes navigation;
- [ ] explicit workspace identity in every review page;
- [ ] preserve all existing loopback security and Git-write boundaries.

### P0.3b — Evidence Review

The primary product loop becomes Fact-to-source review rather than CRUD pages.

- [ ] vendor and pin an approved PDF.js build or equivalent reviewed local PDF viewer asset;
- [ ] render exact source revision and page;
- [ ] normalized bbox overlay;
- [ ] quote/hash display;
- [ ] navigate multiple anchors;
- [ ] show package/revision/applicability next to the typed Fact;
- [ ] never expose evidence that fails the Source processing policy.

Target review composition:

```text
Agent-prepared Fact
        |
        v
/review
        |
        +-- source revision + PDF page + bbox
        +-- typed Fact payload + conditions/applicability
        +-- Entity/package identity
        +-- unknown/conflict/license/missing gates
        +-- review history
```

### P0.3c — Review Closure

- [ ] approve/reject Source and Fact from the typed review view;
- [ ] rejection comment and resubmission history;
- [ ] missing-anchor gate;
- [ ] semantic-conflict gate;
- [ ] license-block gate;
- [ ] DATA_ONLY/MIXED state in the UI;
- [ ] selected change diff;
- [ ] immutable approved-state UX;
- [ ] no Git stage/commit/push operations.

### P0.3 completion gate

- [ ] a human can review an Agent-created Source + Entity + Fact closure entirely from the workbench;
- [ ] the PDF evidence anchor can be inspected visually;
- [ ] approve/reject history is preserved;
- [ ] conflicts/missing/license blockers are visible and fail closed;
- [ ] the resulting change is reviewable as a `DATA_ONLY` Git diff;
- [ ] loopback/security tests and real GUI smoke pass.

---

## 4. P0.4 — First Real Dataset + Evals

Do not bulk-ingest data immediately. Use real material to challenge the authority model and review UX first.

### P0.4a — Pilot dataset

Start with 3–5 common ICs and deliberately choose cases that stress the model:

- [ ] 20–40 total facts;
- [ ] at least one component with multiple packages;
- [ ] at least one datasheet revision/supersedes case;
- [ ] at least 5–10 deliberately wrong or ambiguous negative cases;
- [ ] table-based pin facts;
- [ ] parameter limits with footnotes/conditions;
- [ ] at least one incomplete/unknown case that remains intentionally unresolved.

Evaluate whether the current model handles:

- table cells spanning visual regions;
- multi-line and multi-page conditions;
- package-specific applicability;
- footnote-linked constraints;
- multiple anchors supporting one Fact;
- revision drift and anchor invalidation.

Schema or UX changes discovered here must be fixed before scaling the dataset.

### P0.4b — First production-scale dataset

After the pilot stabilizes:

- [ ] 20–30 common ICs;
- [ ] at least 100 pin facts;
- [ ] at least 100 parameter-limit facts;
- [ ] at least two datasheet revision-update cases;
- [ ] at least 20 deliberately wrong/ambiguous negative cases.

Restore/expand `evals/` to cover wrong MPN, wrong package, wrong revision, absolute-max vs recommended, unknown, supersede, conflict, license block, anchor drift, review history, uncommitted approval, mixed commit, and wrong-workspace targeting.

---

## 5. P1 — Local Retrieval

Build local retrieval only after a real published dataset exists.

Derived state:

```text
.pcbknowledge/index.sqlite
```

Tasks:

- [ ] exact manufacturer / MPN / package / fact-type index;
- [ ] SQLite FTS5;
- [ ] derived PDF page-text cache;
- [ ] published snapshot is the default index source;
- [ ] working-tree preview requires explicit opt-in;
- [ ] index can be deleted and rebuilt from the workspace authority;
- [ ] query results retain Fact/evidence/conflict/unknown structure.

Query order:

```text
exact entity
-> exact package / revision / fact type
-> published filters
-> FTS
-> fact / evidence / conflict / unknown
```

---

## 6. P1.5 — PCB Knowledge Expansion

Add new typed Fact families only after P0.4 shows the initial review/retrieval loop is stable.

Candidate types:

- [ ] PackageDimension;
- [ ] PowerSequence;
- [ ] Decoupling;
- [ ] ClockReset;
- [ ] LayoutGuideline.

Every new type requires schema, executable model, validator, Agent projection, review UI, synthetic tests, and at least one real-data evaluation case.

---

## 7. P2 — Product Integration

Expand beyond datasheet facts without making PcbKnowledge a live board authority.

Candidate knowledge types:

- FabCapability;
- InternalRule;
- DesignReview;
- Waiver;
- Lifecycle;
- Replacement;
- HistoricalCase.

Product-facing work:

- [ ] immutable `KnowledgeSnapshot` contract;
- [ ] task-level query/read API;
- [ ] read-only PCBAtlas/PcbCore adapter;
- [ ] iOS/read-only snapshot format where useful;
- [ ] Agent harness combines PcbCore live board facts with one pinned KnowledgeSnapshot;
- [ ] PcbCore remains fully usable when PcbKnowledge is unavailable.

---

## 8. P3 — Advanced Retrieval

Vector/embedding/reranking work begins only after golden evaluation shows a stable benefit over Exact + FTS for open-ended guideline or historical-case retrieval.

Before implementation:

- [ ] define retrieval metrics and a fixed golden set;
- [ ] measure Exact + FTS baseline;
- [ ] demonstrate repeatable quality gain worth added complexity;
- [ ] write a new ADR selecting local vector technology and lifecycle;
- [ ] keep vectors disposable and rebuildable from published authority.

Historical pgvector plans do not automatically reactivate.

---

## 9. Verification contract

Every development round runs the narrowest relevant tests first, then the applicable repository gates:

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py change-scope
python3 configs/pcbknowledge_workflow.py package
```

For external-workspace work, run the equivalent commands against a temporary Git workspace. GUI changes also require a real loopback smoke test. Commands that were not run, were interrupted, were truncated, or skipped required checks must not be recorded as passes.
