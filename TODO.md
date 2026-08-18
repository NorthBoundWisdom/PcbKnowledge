# TODO — PcbKnowledge Roadmap

> Status: `P0.4A_HARNESS_READY_PRIVATE_PILOT_NEXT`
> Updated: 2026-08-18
> Goal: run the completed ingestion/review system against a small real private PCB knowledge workspace before expanding schema breadth or retrieval complexity.

## 0. Permanent boundaries

- The public repository contains software, schemas, documentation, Agent skills, synthetic tests, evaluation harnesses, and explicitly reviewed runtime dependencies, but no production knowledge/evidence.
- Real Source / Entity / Fact authority, internal rules, reviews, waivers, and third-party PDF evidence live in a separately controlled knowledge Git workspace.
- A knowledge workspace is self-contained: its manifest, pinned schemas, authority, evidence, and Git history define publication.
- The GUI and Agent share one typed authority model, validator, and repository write path.
- Agents may prepare, edit, validate, and submit drafts; they may not approve, reject, stage, commit, or push knowledge data.
- Working-tree `APPROVED` is distinct from publication. Formal reads use a fully validated committed Git snapshot.
- Unknown values, conflicts, wrong revisions, wrong packages, missing anchors, and license blocks stay explicit.
- Deliberately wrong/ambiguous evaluation inputs are evaluation metadata, not false canonical authority.
- PcbKnowledge does not read or mutate live PCB board state and is not a PcbCore runtime dependency.
- SQLite/FTS/page-text/vector indexes are disposable derived state, never authority.
- Vector retrieval is not a P0/P1 prerequisite and enters the roadmap only after evaluation demonstrates value.

---

## 1. Completed foundation

### P0.0 — Git-native Core Hardening — COMPLETE

Implemented deterministic Git-native JSON/PDF authority, canonical serialization, content-addressed PDF evidence, append-only review history, optimistic revision tokens, committed-approved immutability, explicit `supersedes`, evidence lifecycle protection, repository write locking, `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change scope, validated published readers, and deterministic package snapshots.

### P0.1 — Typed Authority Model — COMPLETE

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

### Open-source + P0.2.5 Workspace Foundation — COMPLETE

Stage commit:

```text
cdf71606610d49504eb6d9ce0783832e6ba58100
[feat]: establish open-source workspace foundation
```

Implemented Apache-2.0 licensing, English-only source policy, public-source data/evidence guard, GitHub Actions, CodeQL, Dependabot, contribution/security/AGENTS contracts, public/private workspace separation, canonical workspace manifest, pinned workspace schemas, explicit `--workspace` / `--repo` selection, external-workspace GUI/package support, and cross-platform repository locking.

---

## 2. P0.3 — Local Review Workbench — COMPLETE

### P0.3a — Typed Workbench Foundation — COMPLETE

Stage commit:

```text
4cb0318b457be19fb9e1c1337d98f2259148fbf3
[feat]: build typed review workbench foundation P0.3a
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

The old `/records/**` Source-only route family was hard-cut. HTTP/security transport, application/view-model construction, repository/domain logic, and HTML rendering are separated. Source/Entity/Fact/supersedes/conflict navigation is derived from canonical authority, not a sidecar graph.

Verified stage tree: 83 tests, 0 failures/errors/skips on Ubuntu 3.11/3.14, macOS 3.11, and Windows 3.11, plus Config/Build/Agent validate/Package gates.

### P0.3b — Visual Evidence Review — COMPLETE

Stage commit:

```text
8b357ff0b28c9ad08fa6976df2677ee6b18e5410
[feat]: complete visual evidence review P0.3b
```

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
- explicit crop/rotation/origin/axis semantics in ADR-013.

Verified stage tree: 88 tests, 0 failures/errors/skips across the public matrix, including the pinned PDF.js vendor integrity gate.

### P0.3c — Review Closure — COMPLETE

Stage commit:

```text
44b8338c0217a1cf5f5d837cd0b2a0d0278f2050
[feat]: complete typed human review workbench P0.3c
```

Completed:

- Source and Fact approve/reject from typed review views;
- immediate revalidation of status, typed closure, and next-commit scope before every decision write;
- append-only rejection/edit/resubmission/approval history;
- fail-closed missing/incomplete anchor gate;
- fail-closed semantic conflict gate;
- fail-closed Source license gate for Fact approval;
- `CLEAN` / `DATA_ONLY` decision requirement and `CODE_ONLY` / `MIXED` blocking;
- exact selected closure paths, Git status, and diff before decision;
- visual evidence before Fact decision controls;
- immutable approved-Fact UX;
- preserved loopback Host/Origin, CSRF, optimistic revision, workspace isolation, and GUI no-stage/no-commit/no-push boundaries.

Verified stage tree: 96 tests, 0 failures/errors/skips across Ubuntu 3.11/3.14, macOS 3.11, and Windows 3.11, plus English/public/PDF.js/workspace/Agent/package gates.

P0.3 does not claim human pixel-level acceptance against a real vendor PDF. That belongs to P0.4a.

---

## 3. P0.4 — First Real Dataset + Evals

### P0.4a — Private Pilot — HARNESS READY / REAL PILOT NEXT

The public software repository now contains the pilot evaluation contract and synthetic vertical coverage. Real Sources, Facts, PDFs, observations, and potentially sensitive evaluation notes remain private.

Public harness:

```bash
python3 configs/pcbknowledge_pilot.py scaffold --output <private-eval.json>
python3 configs/pcbknowledge_pilot.py metrics --workspace <private-workspace>
python3 configs/pcbknowledge_pilot.py report \
  --workspace <private-workspace> \
  --manifest <private-eval.json>
python3 configs/pcbknowledge_pilot.py report \
  --workspace <private-workspace> \
  --manifest <private-eval.json> \
  --require-pass
```

Harness capabilities:

- [x] measure working authority separately from committed Published Knowledge;
- [x] count Source/Entity/Fact/fact-family/review/conflict/anchor coverage;
- [x] enforce 3–5 Component and 20–40 Fact pilot bounds;
- [x] require both initial Fact families;
- [x] detect at least one multi-package Component from canonical pin Facts;
- [x] require an explicit Source revision/supersedes chain;
- [x] keep deliberately wrong/ambiguous scenarios outside canonical authority;
- [x] require 5–10 negative/ambiguous scenario receipts;
- [x] require explicit `UNKNOWN`, table-pin, and footnote-limit receipts;
- [x] record expected vs observed symbolic outcomes with `PASS / FAIL / NOT_RUN` semantics;
- [x] bind visual acceptance receipts to an exact Source, Fact, page, and complete anchor;
- [x] require at least one visual PASS and browser resize/zoom receipt;
- [x] report rotated/cropped or complex-font coverage when available;
- [x] require fully reviewed working Source/Fact authority;
- [x] require committed published counts to match reviewed working authority;
- [x] provide a deterministic synthetic 3-Component / 20-Fact vertical test.

Real private pilot still required:

- [ ] initialize and commit one private `pcbknowledge-workspace-v1` workspace;
- [ ] perform the first desktop-browser visual acceptance on a real vendor PDF;
- [ ] include at least one rotated/cropped or otherwise non-trivial PDF page where available;
- [ ] ingest 3–5 common ICs;
- [ ] create 20–40 total Facts;
- [ ] include at least one multi-package component;
- [ ] include at least one datasheet revision + explicit `supersedes` case;
- [ ] run 5–10 deliberately wrong or ambiguous negative cases without creating false authority;
- [ ] include table-based pin Facts;
- [ ] include parameter limits with footnotes/conditions;
- [ ] preserve at least one unresolved unknown outcome rather than guessing a Fact;
- [ ] review every pilot Source/Fact through the workbench;
- [ ] commit only reviewed data and confirm Published Knowledge matches the working closure;
- [ ] make `pcbknowledge_pilot.py report --require-pass` succeed;
- [ ] record real failures before changing schemas or adding new Fact families.

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

See [`docs/pilot-evaluation.md`](docs/pilot-evaluation.md).

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

Use the narrowest relevant tests during editing, then the applicable repository checkpoint. GUI work requires focused HTTP/view-model coverage and a real loopback smoke. Workspace work requires a temporary external Git repository and tamper tests. Pilot/evaluation work additionally requires deterministic synthetic structural/negative/visual/publication closure. Production/pilot data is never added to this public software repository. Interrupted, truncated, skipped, or unexecuted checks are not passes.
