# TODO — PcbKnowledge Roadmap

> Status: `P0.3A_COMPLETE_P0.3B_NEXT`
> Updated: 2026-08-18
> Goal: evolve the completed Git-native typed-authority, Agent-ingestion, workspace-boundary, and typed-workbench foundations into a practical evidence-review and retrieval system for PCB engineering Agents.

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
- CONTRIBUTING / SECURITY / AGENTS contracts;
- clean public software/production-data boundary.

---

## 2. P0.2.5 — Knowledge Workspace Boundary — COMPLETE

ADR: [`ADR-020`](docs/adr/ADR-020-knowledge-workspace-boundary.md)

Implemented workspace layout:

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
- [x] deterministic schema digest over exact schema byte identities and paths;
- [x] working-tree and immutable-ref manifest/schema validation;
- [x] explicit failure on manifest/schema drift and no silent schema upgrade;
- [x] deterministic workspace initialization with no automatic data/stage/commit/push;
- [x] explicit Agent `--repo <workspace>` boundary;
- [x] `run/open/test/package --workspace <path>`;
- [x] workspace-aware GUI and external-workspace packaging;
- [x] all four Agent skills require one explicit workspace.

P0.2.5 completion receipt is recorded by the validated main history preceding P0.3a: cross-platform CI and CodeQL passed, with 78 tests at that milestone.

---

## 3. P0.3 — Local Review Workbench — IN PROGRESS

P0.3 builds on an explicit external workspace rather than treating the public software checkout as production data authority.

### P0.3a — Typed Workbench Foundation — COMPLETE

The Source-only GUI foundation has been hard-cut into a typed application/view architecture while retaining the standard-library server and no Node build chain.

Implemented runtime layers:

```text
HTTP handler
    |
    v
WorkbenchApplication / typed view models
    |
    v
KnowledgeRepository / domain model
    |
    v
selected Git workspace

HTML renderer <- typed view models only
```

Implemented routes:

```text
/review                 primary Source/Fact human queue
/sources                Source list
/sources/<id>           exact Source revision and human Source workflow
/entities               Manufacturer / Component / Package list
/entities/<id>          exact identity and related records
/facts                  typed engineering Fact list
/facts/<id>             typed payload, applicability, anchors, conflicts
/diff                   read-only workspace Git diff
```

Completed:

- [x] HTTP/security routing separated from typed view-model construction and HTML rendering;
- [x] Source list/detail;
- [x] existing Source create/edit/submit/approve/reject migrated to `/sources/**`;
- [x] Entity list/detail with manufacturer/component/package identity;
- [x] Fact list/detail with typed payload inspector;
- [x] Source/Entity/Fact/supersedes navigation derived from canonical authority;
- [x] semantic Fact conflict navigation without winner selection;
- [x] EvidenceAnchor page/bbox/quote/hash metadata exposed in Fact detail;
- [x] READY_FOR_REVIEW Source/Fact queue with explicit current closure blockers;
- [x] selected workspace identity rendered on every workbench page;
- [x] Git change count and change scope shown in the review foundation;
- [x] retired `/records` HTTP route family removed with no compatibility alias;
- [x] loopback Host/Origin, CSRF, optimistic revision, evidence validation, and no-Git-write boundaries preserved;
- [x] Entity and Fact UI remains read-only until the later review/mutation stages require additional human actions.

#### P0.3a verification receipt

Implementation commit:

```text
f4ff4e28de9077ed44959d15aa5700be26225053
[feat]: build typed workbench foundation P0.3a
```

Validation-only PR #4 used the pre-P0.3a main snapshot as its base; development itself remained directly on `main`.

CI run `32133271445` passed on:

- Ubuntu / Python 3.11 — full Core Config -> Build -> Test -> Validate -> Package;
- Ubuntu / Python 3.14;
- macOS / Python 3.11;
- Windows / Python 3.11.

Core receipt:

```text
83 tests
0 failures
0 errors
0 skips
English-only guard: PASS
public-source guard: PASS
workspace contract validation: PASS
Agent validate: PASS
Package: PASS
```

Focused coverage includes typed review queue projection, Source/Entity/Fact relationship navigation, Source human review flow, Fact typed inspector, retired `/records` rejection, workspace identity, loopback Host/Origin, CSRF, stale revision tokens, evidence serving, and GUI no-stage behavior.

Manual visual acceptance for a local checkout:

1. run `python3 configs/pcbknowledge_workflow.py open --workspace <workspace>`;
2. confirm `/review`, `/sources`, `/entities`, `/facts`, and `/diff` share one workspace banner;
3. confirm Source creation/review remains usable through `/sources/**`;
4. confirm Fact detail shows typed payload, identities, Source revision links, anchors, conflicts, and review history;
5. confirm `/records/new` returns 404 rather than silently falling back to the retired UI.

### P0.3b — Evidence Review — NEXT

The primary next product loop is Fact-to-source visual evidence review.

- [ ] vendor and pin an approved PDF.js build or equivalent reviewed local PDF viewer asset;
- [ ] render the exact Source revision and PDF page;
- [ ] normalized bbox overlay;
- [ ] quote/hash display next to the visual anchor;
- [ ] navigate multiple anchors;
- [ ] show package/revision/applicability beside the typed Fact;
- [ ] never expose evidence that fails Source processing policy;
- [ ] keep viewer assets local and covered by CSP/supply-chain review.

Target composition:

```text
Agent-prepared Fact
        |
        v
/review or /facts/<id>
        |
        +-- source revision + PDF page + bbox
        +-- typed Fact payload + conditions/applicability
        +-- Entity/package identity
        +-- unknown/conflict/license/missing gates
        +-- review history
```

### P0.3c — Review Closure

- [ ] approve/reject Source and Fact from the typed review view;
- [ ] preserve rejection comment and resubmission history;
- [ ] missing-anchor gate;
- [ ] semantic-conflict gate;
- [ ] license-block gate;
- [ ] DATA_ONLY/MIXED state as a decision gate, not only informational UI;
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

Every development round runs the narrowest relevant tests first, then applicable repository gates. Workspace changes require a temporary external Git repository and tamper tests. GUI changes additionally require focused HTTP/view-model coverage and a real loopback smoke against a selected workspace. Commands that were not run, were interrupted, were truncated, or skipped required checks must not be recorded as passes.
