# TODO — PcbKnowledge Roadmap

> Status: `P0.3_IMPLEMENTATION_COMPLETE_P0.4A_NEXT`
> Updated: 2026-08-18
> Goal: validate the completed Git-native ingestion and human-review system against a small real PCB knowledge workspace before expanding retrieval or schema breadth.

## 0. Permanent boundaries

- The public PcbKnowledge repository contains software, schemas, documentation, Agent skills, synthetic tests, and explicitly reviewed runtime dependencies, but no production knowledge/evidence.
- Real Source / Entity / Fact authority, internal rules, reviews, waivers, and third-party PDF evidence live in a separately controlled knowledge Git workspace.
- A knowledge workspace is self-contained: its manifest, pinned schemas, authority, evidence, and Git history define publication.
- The GUI and Agent share one typed authority model, validator, and repository write path.
- Agents may prepare, edit, validate, and submit drafts; they may not approve, reject, stage, commit, or push knowledge data.
- Working-tree `APPROVED` is distinct from publication. Formal reads use a fully validated committed Git snapshot.
- Unknown values, conflicts, wrong revisions, wrong packages, missing anchors, and license blocks stay explicit.
- PcbKnowledge does not read or mutate live PCB board state and is not a PcbCore runtime dependency.
- SQLite/FTS/page-text/vector indexes are disposable derived state, never authority.
- Vector retrieval is not a P0/P1 prerequisite and enters the roadmap only after evaluation demonstrates value.

---

## 1. Completed foundation

### P0.0 — Git-native Core Hardening — COMPLETE

Implemented deterministic Git-native JSON/PDF authority, canonical serialization, content-addressed PDF evidence, append-only review history, optimistic revision tokens, committed-approved immutability, explicit `supersedes`, evidence lifecycle protection, repository write locking, `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change scope, validated published readers, and deterministic package snapshots.

### P0.1 — Typed Authority Model — COMPLETE

Implemented:

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

The model keeps exact identity, Source licensing, typed conditions/applicability, page/bbox/quote anchors, reference closure, semantic conflicts, review history, and explicit unknowns.

### P0.2 — Agent-native Ingestion — COMPLETE

Repository-local skills:

```text
ingest-engineering-source
resolve-component-identity
extract-component-facts
prepare-knowledge-review
```

Agents have typed Source/Entity/Fact commands, stable idempotency, exact identity resolution, `source authorize-read`, explicit unknown/conflict/missing-anchor reporting, selected-closure review status, and `WAIT_FOR_HUMAN_REVIEW` handoff. Agents have no approval or Git-publication operation.

### Open-source preparation — COMPLETE

Implemented Apache-2.0 licensing, English-only source policy, public-source data/evidence guard, GitHub Actions, CodeQL, Dependabot, contribution/security/AGENTS contracts, third-party notices, and a clean public-software/private-data boundary.

### P0.2.5 — Knowledge Workspace Boundary — COMPLETE

The public software checkout and a production knowledge workspace are physically separate Git repositories. A workspace contains:

```text
pcbknowledge.workspace.json
schemas/
knowledge/sources/
knowledge/entities/
knowledge/facts/
evidence/sha256/
```

The workspace contract pins exact schemas and fails closed on drift. `run/open/test/package --workspace <path>` and Agent `--repo <path>` are explicit; invalid explicit workspaces never fall back silently. Initialization never stages, commits, pushes, or creates production data.

---

## 2. P0.3 — Local Review Workbench — IMPLEMENTATION COMPLETE

### P0.3a — Typed Workbench Foundation — COMPLETE

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

The old `/records/**` Source-only route family was hard-cut. HTTP/security transport, application/view-model construction, repository/domain logic, and HTML rendering are separated. Source/Entity/Fact/supersedes/conflict navigation is derived from canonical authority, not a sidecar graph.

Verification checkpoint: commit `f4ff4e28de9077ed44959d15aa5700be26225053`; CI run `32133271445`; 83 tests, 0 failures/errors/skips across Ubuntu 3.11/3.14, macOS 3.11, and Windows 3.11.

### P0.3b — Visual Evidence Review — COMPLETE

Completed:

- pinned local `pdfjs-dist` 6.2.108 display-layer/worker assets and upstream license;
- package integrity plus per-file SHA-256/byte-size gate;
- exact Source revision/page rendering;
- `PDF_NORMALIZED_V1` bbox overlay;
- quote and `quote_sha256` display;
- multiple-anchor navigation;
- component/package/conditions/applicability context beside evidence;
- backend Source-license enforcement before PDF bytes are served;
- same-origin viewer, worker, CSS, and PDF fetches under explicit CSP;
- explicit `PDF_NORMALIZED_V1` crop/rotation/origin/axis semantics in ADR-013.

Verification checkpoint: commits `8a4382eb71c7ea2115245697878f50a7b1738041` and `dfbca5e65a53919a741f1dced16bc763df7bb459`; CI run `32141380432`; 88 tests, 0 failures/errors/skips across the public matrix.

### P0.3c — Review Closure — COMPLETE

The workbench now owns the complete human Source/Fact decision boundary while Git remains the publication boundary.

Completed:

- [x] approve/reject Source and Fact from typed review views;
- [x] revalidate status, typed closure, and next-commit scope immediately before every decision write;
- [x] preserve append-only rejection, edit, resubmission, and approval history;
- [x] fail closed on missing/incomplete Fact anchors;
- [x] fail closed on unresolved semantic Fact conflicts;
- [x] fail closed on blocked Source license classes for Fact approval;
- [x] require `CLEAN` or `DATA_ONLY` next-commit scope for both approval and rejection;
- [x] block `CODE_ONLY` and `MIXED` review decisions rather than mixing review history with software/contract changes;
- [x] show exact selected closure paths, selected Git status, and selected diff before a decision;
- [x] exclude unrelated workspace data from the selected closure projection;
- [x] render visual evidence before Fact decision controls in the workspace runtime;
- [x] expose immutable approved-Fact UX with no mutation form;
- [x] preserve loopback Host/Origin, CSRF, optimistic revision, workspace isolation, and GUI no-stage/no-commit/no-push boundaries.

Implementation/test commits:

```text
04fdcaf7b41f2ba00996ad85cc7e195260e18c13
[feat]: complete typed human review closure P0.3c

6136f7643d659315849fe7fa5b9b3d0b89eb0b54
[test]: update typed Fact evidence expectation
```

Validation-only PR #6 used the pre-P0.3c main snapshot as its base; development remained directly on `main`. CI run `32144110435` passed on Ubuntu/Python 3.11, Ubuntu/Python 3.14, macOS/Python 3.11, and Windows/Python 3.11.

Core receipt:

```text
96 tests
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

P0.3 automated completion gates are satisfied. This milestone does **not** claim a human pixel-level browser acceptance against a real vendor PDF. That acceptance deliberately becomes the first P0.4a task, where a real private workspace can exercise rotated/cropped/complex-font material instead of another synthetic PDF.

---

## 3. P0.4 — First Real Dataset + Evals

### P0.4a — Pilot dataset — NEXT

Create a private knowledge workspace and use the completed Agent + workbench loop on 3–5 common ICs before expanding schema breadth.

Required pilot:

- [ ] initialize and commit one private `pcbknowledge-workspace-v1` workspace;
- [ ] perform the first desktop-browser visual acceptance on a real vendor PDF;
- [ ] include at least one rotated/cropped or otherwise non-trivial PDF page where available;
- [ ] ingest 3–5 common ICs;
- [ ] create 20–40 total Facts;
- [ ] include at least one multi-package component;
- [ ] include at least one datasheet revision + explicit `supersedes` case;
- [ ] include 5–10 deliberately wrong or ambiguous negative cases;
- [ ] include table-based pin Facts;
- [ ] include parameter limits with footnotes/conditions;
- [ ] preserve at least one unresolved unknown case rather than filling it;
- [ ] review every pilot Source/Fact through the workbench and publish only committed `APPROVED` authority;
- [ ] record failures before changing schemas or adding new Fact families.

Evaluate specifically:

- table-cell and multi-line anchors;
- multiple anchors per Fact;
- package-specific applicability;
- footnote-linked constraints;
- absolute maximum vs recommended operating conditions;
- revision drift and supersedes behavior;
- visual bbox accuracy under browser resize/zoom;
- intrinsic page crop/rotation;
- complex-font PDF rendering;
- wrong MPN/package/revision negatives;
- license-block and conflict decision gates.

### P0.4b — First production-scale dataset

After the pilot stabilizes:

- [ ] 20–30 common ICs;
- [ ] at least 100 pin Facts;
- [ ] at least 100 parameter-limit Facts;
- [ ] at least two datasheet revision-update cases;
- [ ] at least 20 deliberately wrong/ambiguous negative cases;
- [ ] golden evals for wrong MPN, wrong package, wrong revision, absolute-max vs recommended, unknown, supersede, conflict, license block, anchor drift, review history, uncommitted approval, mixed commit, and wrong-workspace targeting.

---

## 4. P1 — Local Retrieval

Build retrieval only after a real published dataset exists.

- [ ] `.pcbknowledge/index.sqlite` rebuildable derived index;
- [ ] exact manufacturer / MPN / package / Fact-type index;
- [ ] SQLite FTS5;
- [ ] derived PDF page-text cache;
- [ ] published snapshot as the default index source;
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

## 5. P1.5 — PCB Knowledge Expansion

Candidate typed families after P0.4 stabilizes:

- [ ] PackageDimension;
- [ ] PowerSequence;
- [ ] Decoupling;
- [ ] ClockReset;
- [ ] LayoutGuideline.

Every new Fact family requires executable model, schema, validator, Agent projection, review UI, synthetic coverage, and at least one real-data evaluation case.

---

## 6. P2 — Product Integration

Candidate knowledge: FabCapability, InternalRule, DesignReview, Waiver, Lifecycle, Replacement, HistoricalCase.

- [ ] immutable `KnowledgeSnapshot` contract;
- [ ] task-level query/read API;
- [ ] read-only PCBAtlas/PcbCore adapter;
- [ ] optional iOS/read-only snapshot format;
- [ ] Agent harness combines PcbCore live board facts with one pinned KnowledgeSnapshot;
- [ ] PcbCore remains fully usable when PcbKnowledge is unavailable.

---

## 7. P3 — Advanced Retrieval

Vector/embedding/reranking starts only after golden evaluation shows stable benefit over Exact + FTS for open-ended guideline or historical-case retrieval.

Before implementation:

- [ ] define retrieval metrics and a fixed golden set;
- [ ] measure Exact + FTS baseline;
- [ ] demonstrate repeatable quality gain worth added complexity;
- [ ] write a new ADR selecting local vector technology and lifecycle;
- [ ] keep vectors disposable and rebuildable from published authority.

---

## 8. Verification contract

Use the narrowest relevant tests during editing, then the applicable repository checkpoint. GUI work requires focused HTTP/view-model coverage and a real loopback smoke. Workspace work requires a temporary external Git repository and tamper tests. Production/pilot data is never added to this public software repository. Interrupted, truncated, skipped, or unexecuted checks are not passes.
