# TODO — PcbKnowledge Roadmap

> Status: `P0.3B_COMPLETE_P0.3C_NEXT`
> Updated: 2026-08-18
> Goal: evolve the completed Git-native typed-authority, Agent-ingestion, workspace-boundary, typed-workbench, and visual-evidence foundations into a practical review and retrieval system for PCB engineering Agents.

## 0. Permanent boundaries

- The public PcbKnowledge repository contains software, schemas, documentation, Agent skills, synthetic tests, and explicitly reviewed runtime dependencies, but no production knowledge/evidence.
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

### P0.3b — Evidence Review — COMPLETE

Fact detail now contains a local visual evidence-review surface without adding a second authority or write path.

Completed:

- [x] vendor and pin `pdfjs-dist` 6.2.108 legacy display-layer and worker assets plus the upstream Apache-2.0 license;
- [x] exact PDF.js package integrity/SHA-1 and per-file SHA-256/byte-size manifest;
- [x] independent `check_pdfjs_vendor.py` gate and runtime startup validation;
- [x] render the exact referenced Source PDF page in a local canvas;
- [x] `PDF_NORMALIZED_V1` bbox overlay over the displayed page viewport;
- [x] quote and `quote_sha256` displayed next to the visual anchor;
- [x] multiple-anchor navigation with Source revision/page context;
- [x] component/package, conditions, and applicability remain visible beside evidence review;
- [x] Source license policy enforced in the application projection and again at the PDF HTTP endpoint;
- [x] `UNKNOWN`, `RESTRICTED`, and `LICENSED_BLOCKED_FOR_AI` sources are not exposed to the viewer;
- [x] viewer code, worker, CSS, and PDF fetches are same-origin only under explicit CSP;
- [x] vendor manifest/license are not served as generic static files;
- [x] ADR-013 now defines crop/rotation/origin/axis semantics for `PDF_NORMALIZED_V1` before production authority is introduced.

#### P0.3b verification receipt

Implementation/fix commits:

```text
8a4382eb71c7ea2115245697878f50a7b1738041
[feat]: add visual PDF evidence review P0.3b

dfbca5e65a53919a741f1dced16bc763df7bb459
[fix]: preserve typed application in workspace server
```

The first integration run exposed one shared server-wrapper regression: the P0.3b workspace server subclass failed to initialize the P0.3a `WorkbenchApplication`. The second commit repaired that root cause; no platform-specific fallback was added.

Validation-only PR #5 uses the pre-P0.3b main snapshot as its base; development itself remains directly on `main`.

CI run `32141380432` passed on:

- Ubuntu / Python 3.11 — full Core Config -> Build -> Test -> Agent validate -> Package;
- Ubuntu / Python 3.14;
- macOS / Python 3.11;
- Windows / Python 3.11.

Core receipt:

```text
88 tests
0 failures
0 errors
0 skips
English-only guard: PASS
public-source guard: PASS
PDF.js vendor SHA-256 gate: PASS
workspace contract validation: PASS
Agent validate: PASS
Package: PASS
```

Focused P0.3b coverage verifies exact Source revision/page/bbox/quote projection, multiple-anchor navigation, normalized SVG overlay geometry, backend license blocking, same-origin CSP, local-only viewer asset references, vendor file-set/hash drift rejection, and preservation of the P0.3a workspace application layer.

Browser-canvas rendering is intentionally a manual visual acceptance surface rather than a second JS/browser test stack in P0.3b. Before using a real knowledge workspace for review, verify one representative PDF in a desktop browser:

1. run `python3 configs/pcbknowledge_workflow.py open --workspace <workspace>`;
2. open a Fact with a complete evidence anchor;
3. confirm the exact Source revision/page renders and the highlighted box covers the quoted source region;
4. resize/zoom the browser and confirm the normalized overlay remains attached to the same region;
5. confirm a license-blocked Source shows policy state and cannot return PDF bytes through its evidence URL.

P0.4 real-data evaluation must add rotated/cropped and complex-font PDFs before expanding the coordinate or viewer contract.

### P0.3c — Review Closure — NEXT

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
- [x] the PDF evidence anchor has an implemented local visual inspection surface;
- [ ] approve/reject history is preserved for the full Source + Fact review closure;
- [ ] conflicts/missing/license blockers are visible and fail closed at decision time;
- [ ] the resulting change is reviewable as a `DATA_ONLY` Git diff;
- [ ] loopback/security tests and a real external-workspace GUI acceptance pass.

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

Evaluate table-cell anchors, multi-line/multi-page conditions, package-specific applicability, footnote-linked constraints, multiple anchors per Fact, revision drift, intrinsic page rotation/crop boxes, and complex-font rendering before changing or expanding the schema/viewer contract.

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
