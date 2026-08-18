# TODO — PcbKnowledge Roadmap

> Status: `P0.2.5_COMPLETE_P0.3_NEXT`
> Updated: 2026-08-18
> Goal: evolve the completed Git-native typed-authority, Agent-ingestion, and workspace-boundary core into a practical evidence-review and retrieval system for PCB engineering Agents.

## 0. Permanent boundaries

- The public PcbKnowledge repository contains software, schemas, documentation, Agent skills, and synthetic tests, but no production knowledge/evidence.
- Real Source / Entity / Fact authority, internal rules, reviews, waivers, and third-party PDF evidence live in a separately controlled knowledge Git workspace.
- A knowledge workspace is self-contained: its manifest, pinned schemas, authority, evidence, and Git history define publication.
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

Implemented:

- deterministic Git-native JSON/PDF authority;
- SHA-256 content-addressed evidence;
- canonical serialization and strict layout validation;
- append-only review history and optimistic revision tokens;
- committed `APPROVED` immutability plus explicit `supersedes`;
- orphan/shared/published evidence protection;
- repository write locking;
- `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change scope;
- separation between working-tree approval and committed publication;
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

Implemented contracts include exact identity lookup, explicit Source license taxonomy, page/bbox/quote evidence anchors, typed Fact conditions/applicability, reference closure, semantic conflict detection, and synthetic publication tests.

### P0.2 — Agent-native Ingestion — COMPLETE

Repository-local skills:

```text
ingest-engineering-source
resolve-component-identity
extract-component-facts
prepare-knowledge-review
```

Implemented Agent behavior includes typed Source/Entity/Fact commands, stable idempotency keys, exact identity resolution, `source authorize-read`, explicit unknown/missing-anchor/conflict reporting, selected-closure `review-status`, and `DATA_ONLY + WAIT_FOR_HUMAN_REVIEW` handoff.

### Open-source preparation — COMPLETE

Implemented:

- Apache-2.0;
- English-only source-repository policy and CI gate;
- public-source data/evidence guard;
- GitHub Actions, CodeQL, and Dependabot configuration;
- CONTRIBUTING / SECURITY / PR contracts;
- rewritten clean public branch history.

---

## 2. P0.2.5 — Knowledge Workspace Boundary — COMPLETE

ADR: [`ADR-020`](docs/adr/ADR-020-knowledge-workspace-boundary.md)

### 2.1 Workspace contract

Implemented target layout:

```text
PcbKnowledge/                     public software

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

Completed:

- [x] canonical `pcbknowledge.workspace.json`;
- [x] `pcbknowledge-workspace-v1` format and `typed-v1` schema contract;
- [x] deterministic SHA-256 schema digest over exact schema byte identities and paths;
- [x] strict field/canonical-JSON validation;
- [x] working-tree manifest/schema validation;
- [x] immutable-ref manifest/schema validation;
- [x] explicit failure on manifest/schema drift;
- [x] no silent schema upgrade.

### 2.2 Workspace initialization

Implemented:

```bash
python3 configs/pcbknowledge_workspace.py init <workspace>
python3 configs/pcbknowledge_workspace.py init <workspace> --init-git
python3 configs/pcbknowledge_workspace.py validate <workspace>
python3 configs/pcbknowledge_workspace.py validate-ref <workspace> --ref HEAD
```

Completed:

- [x] existing clean Git repository requirement by default;
- [x] `--init-git` only for missing/empty targets;
- [x] pinned schema copy;
- [x] manifest generation;
- [x] authority/evidence placeholders;
- [x] rejection of conflicting existing authority/layout;
- [x] idempotent replay only for the exact same contract;
- [x] no automatic production data;
- [x] no stage/commit/push behavior.

### 2.3 Runtime selection

Completed:

- [x] Agent wrapper validates `--repo <workspace>` before dispatch;
- [x] published Agent reads validate the workspace contract from `HEAD` before typed published access;
- [x] `run --workspace <path>`;
- [x] `open --workspace <path>`;
- [x] `test --workspace <path>`;
- [x] `package --workspace <path>`;
- [x] Config/Build remain software-checkout operations;
- [x] invalid explicit workspace never falls back silently;
- [x] terminal output reports the selected workspace.

### 2.4 GUI boundary

Completed with a workspace-aware wrapper around the stable Source Corpus server:

- [x] selected workspace is validated before server startup;
- [x] all Source/evidence/review/Git-diff operations use only the selected repository;
- [x] every rendered page shows the exact selected workspace root;
- [x] static UI assets continue to come from the software installation;
- [x] existing loopback Host/Origin, CSRF, optimistic revision, and no-Git-write boundaries are preserved.

### 2.5 Packaging boundary

Completed:

- [x] package contents come from the selected workspace;
- [x] archive includes `pcbknowledge.workspace.json` and pinned schemas;
- [x] authority/evidence are validated before packaging;
- [x] ZIP/SHA-256 output remains under the software checkout's ignored `build/package/` directory;
- [x] package creation does not write derived files into the knowledge workspace.

### 2.6 Agent skill boundary

Completed:

- [x] all four skills validate `<workspace>` before ingestion/review;
- [x] all Agent command examples use `--repo '<workspace>'`;
- [x] `INVALID_WORKSPACE` is a stop condition;
- [x] skills explicitly forbid silent public/private workspace switching.

### 2.7 Automated coverage

Added synthetic coverage for:

- [x] deterministic initialization and replay;
- [x] non-Git and conflicting-layout rejection;
- [x] explicit `--init-git` behavior;
- [x] working and committed schema/manifest tamper detection;
- [x] Agent writes constrained to an external workspace;
- [x] public-source checkout remains data-empty;
- [x] GUI workspace identity;
- [x] external-workspace packaging;
- [x] workflow argument contract;
- [x] Agent skill explicit-workspace contract.

### 2.8 Completion receipt — 2026-08-18

Validated candidate head: `89b1356f9b4951f88174785f9701b96e2fc1da5e`.

GitHub Actions CI run `32129686030` completed successfully:

- Ubuntu / Python 3.11 core: English guard, public-source guard, workspace contract validation, Config, Build, Test, Agent validate, and Package all passed;
- Ubuntu / Python 3.14: full public cross-platform test job passed;
- macOS / Python 3.11: full public cross-platform test job passed;
- Windows / Python 3.11: full public cross-platform test job passed;
- the integrated test suite ran 78 tests with 0 failures/errors/skips on the validated head;
- CodeQL run `32129686024` completed successfully;
- source-checkout authority remained 0 Source / 0 Entity / 0 Fact;
- deterministic package output was `PcbKnowledge_f58e138fd4337765.zip` with SHA-256 `d5ee3feb43616470703cbc98dd98b67f8f66fee9b278f0403cc6df3dd61987c6`.

Cross-platform validation also exposed and closed two pre-existing portability issues before the milestone was published:

- the repository write lock no longer depends on an unavailable Windows `fcntl` module; POSIX preserves native `flock(2)` semantics while Windows uses the standard-library `msvcrt.locking` primitive;
- the published-symlink hardening test now constructs a Git mode-`120000` entry directly instead of requiring host OS symlink privileges.

The validated commit chain was fast-forwarded directly to `main`; the temporary validation PR was closed after its head became the mainline, with no separate merge commit required.

---

## 3. P0.3 — Local Review Workbench — NEXT

P0.3 now builds on an explicit external workspace rather than the public software checkout.

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
- [ ] selected workspace identity in every review page;
- [ ] preserve all existing loopback security and Git-write boundaries.

### P0.3b — Evidence Review

The primary product loop becomes Fact-to-source review rather than generic CRUD pages.

- [ ] vendor and pin an approved PDF.js build or equivalent reviewed local PDF viewer asset;
- [ ] render exact Source revision and page;
- [ ] normalized bbox overlay;
- [ ] quote/hash display;
- [ ] navigate multiple anchors;
- [ ] show package/revision/applicability next to the typed Fact;
- [ ] never expose evidence that fails Source processing policy.

Target composition:

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
- [ ] loopback/security tests and a real external-workspace GUI smoke pass.

---

## 4. P0.4 — First Real Dataset + Evals

### P0.4a — Pilot dataset

Start with 3–5 common ICs and deliberately stress the model:

- [ ] 20–40 total facts;
- [ ] at least one multi-package component;
- [ ] at least one datasheet revision/supersedes case;
- [ ] at least 5–10 deliberately wrong or ambiguous negative cases;
- [ ] table-based pin facts;
- [ ] parameter limits with footnotes/conditions;
- [ ] at least one intentionally unresolved unknown case.

Evaluate table-cell anchors, multi-line/multi-page conditions, package-specific applicability, footnote-linked constraints, multiple anchors per Fact, and revision drift before changing or expanding the schema.

### P0.4b — First production-scale dataset

After the pilot stabilizes:

- [ ] 20–30 common ICs;
- [ ] at least 100 pin facts;
- [ ] at least 100 parameter-limit facts;
- [ ] at least two datasheet revision-update cases;
- [ ] at least 20 deliberately wrong/ambiguous negative cases.

Expand `evals/` to cover wrong MPN, wrong package, wrong revision, absolute-max vs recommended, unknown, supersede, conflict, license block, anchor drift, review history, uncommitted approval, mixed commit, and wrong-workspace targeting.

---

## 5. P1 — Local Retrieval

Build retrieval only after a real published dataset exists.

- [ ] `.pcbknowledge/index.sqlite` rebuildable derived index;
- [ ] exact manufacturer / MPN / package / fact-type index;
- [ ] SQLite FTS5;
- [ ] derived PDF page-text cache;
- [ ] published snapshot as default index source;
- [ ] explicit opt-in for working-tree preview;
- [ ] results retain Fact/evidence/conflict/unknown structure.

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

Candidate typed knowledge after P0.4 stabilizes:

- [ ] PackageDimension;
- [ ] PowerSequence;
- [ ] Decoupling;
- [ ] ClockReset;
- [ ] LayoutGuideline.

Every new Fact family requires executable model, schema, validator, Agent projection, review UI, synthetic coverage, and at least one real-data evaluation case.

---

## 7. P2 — Product Integration

Candidate knowledge: FabCapability, InternalRule, DesignReview, Waiver, Lifecycle, Replacement, HistoricalCase.

Product-facing work:

- [ ] immutable `KnowledgeSnapshot` contract;
- [ ] task-level query/read API;
- [ ] read-only PCBAtlas/PcbCore adapter;
- [ ] iOS/read-only snapshot format where useful;
- [ ] Agent harness combines PcbCore live board facts with one pinned KnowledgeSnapshot;
- [ ] PcbCore remains fully usable when PcbKnowledge is unavailable.

---

## 8. P3 — Advanced Retrieval

Vector/embedding/reranking starts only after golden evaluation shows stable benefit over Exact + FTS for open-ended guideline or historical-case retrieval.

Before implementation:

- [ ] define retrieval metrics and a fixed golden set;
- [ ] measure Exact + FTS baseline;
- [ ] demonstrate repeatable quality gain worth added complexity;
- [ ] write a new ADR selecting local vector technology and lifecycle;
- [ ] keep vectors disposable and rebuildable from published authority.

Historical pgvector plans do not automatically reactivate.

---

## 9. Verification contract

Every development round runs the narrowest relevant tests first, then applicable repository gates. Workspace changes require a temporary external Git repository and tamper tests. GUI changes additionally require a real loopback smoke test. Commands that were not run, were interrupted, were truncated, or skipped required checks must not be recorded as passes.
