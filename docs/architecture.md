# PcbKnowledge architecture

> Updated: 2026-10-29
> Direction: [ADR-022](adr/ADR-022-board-generation-knowledge.md) (board-generation knowledge)
> Target model: [knowledge-model-v2.md](knowledge-model-v2.md)
> Targets and metric: [golden-designs.md](golden-designs.md)
> Execution order: [`TODO.md`](../TODO.md)

## 1. Product role

The end goal is to turn a design package (for example a simple hardware-competition
brief) into a manufacturable board. PcbKnowledge is the knowledge side of that
pipeline: a closed-world, evidence-backed catalog of parts, footprints, reusable
circuit blocks, layout rules, fab profiles and calculators, plus a pure expansion
step that turns a block graph into a design intent.

```text
design brief --synthesis--> block graph --expand--> design intent --> placement/routing/DRC --> fab outputs
 (golden          (PcbAtlas AI,             (PcbKnowledge,   (netlist, BOM,   (PcbAtlas, PcbCore,      (Gerber, drill,
  designs)         uses query API)           pure function)   constraints)     external router)          BOM, CPL)
```

Ownership:

| Concern | Owner |
|---|---|
| Parts, packages, footprints, blocks, rules, fab profiles, calculators | PcbKnowledge |
| Design-brief contract and golden designs | PcbKnowledge |
| Block expansion to design intent; electrical checks (A1, A2) | PcbKnowledge |
| Synthesis orchestration (brief to block graph) | PcbAtlas AI runtime, using the PcbKnowledge query API |
| Board state, placement, routing, DRC, fabrication outputs (A3 to A5) | PcbAtlas / PcbCore |

PcbKnowledge is not a PcbCore runtime dependency and never reads or mutates a live
board (ADR-001). Consumers pin a bundle built from one validated commit.

## 2. Current implementation

Stage 0 removed the unused pilot harness, its snapshot fingerprint helper,
fixed per-device evaluators and intake handoff tool. The remaining code still
implements the earlier review-centric design. It is tested, but it
is not the target. Status of each part:

| Subsystem | Code | Status |
|---|---|---|
| Canonical JSON, deterministic IDs, SHA-256 evidence cache, repository lock | `store.py`, `model.py` | **Keep**; reuse for v2 |
| Workspace manifest, pinned schemas, explicit `--workspace` / `--repo` | `workspace.py`, `configs/pcbknowledge_workspace.py` | **Keep** |
| Change-scope (`CLEAN` / `DATA_ONLY` / `CODE_ONLY` / `MIXED`) | `store.py` | **Keep** |
| Metadata-only package, FreeCM Config/Build/Run/Test/Package | `configs/pcbknowledge_workflow.py` | **Keep**; package becomes the bundle |
| English and public-source guards, PDF.js vendor pin | `configs/check_*.py`, `public_repo.py`, `pdfjs_vendor.py` | **Keep** |
| v1 typed records: Source, Manufacturer/Component/Package, ComponentPin/ParameterLimit Facts | `model.py`, `store.py`, `cli.py` | **Replace** by v2 records (zero canonical records exist) |
| v1 human approve/reject review closure and decision UI | `review_closure*.py`, `workbench*.py`, `server.py` | **Remove** decision flows; keep a read-only browser and the PDF evidence viewer only if v2 needs them |
| Noncanonical intake queue (`knowledge/intake/`, 37 batches / 329 annotations) | `intake*.py`, `configs/pcbknowledge_intake_*.py`, replay tests, `evals/intake-*.json` | **Frozen**; migrate golden-design parts, then delete |

Documentation for retiring subsystems is under [`legacy/`](legacy/README.md) until
their code is removed. Historical receipts are under [`archive/`](archive/README.md).

### Facts the current code enforces and v2 keeps

- **Exact identity.** Component identity uses the manufacturer and the raw MPN with
  surrounding whitespace removed; case, punctuation and suffixes are significant. A
  normalized key is a search aid, never proof of identity. Package or variant is
  never inferred from an MPN suffix.
- **Evidence identity.** A source is one exact document revision addressed by the
  SHA-256 of its bytes at `.pcbknowledge/evidence/sha256/<first-two>/<sha256>.pdf`.
  The cache is ignored by Git and never packaged. A missing cache file means
  `NOT_LOCALLY_VERIFIED`, never success. Path, size, media type and symlink safety
  are checked before use.
- **Anchors.** Page numbers are 1-based. Optional bboxes use `PDF_NORMALIZED_V1`
  (ADR-013): displayed page after crop and rotation, top-left origin.
- **License gate.** `UNKNOWN`, `RESTRICTED` and `LICENSED_BLOCKED_FOR_AI` block agent
  processing of a source; IPC material is blocked by default (ADR-015).
- **Unknown is a result.** Missing facts are never filled from a similar device,
  package, free text or model prior.

Stage 1 adds target JSON Schemas in `docs/contracts/v2/`, six G1 vocabulary
registries, three synthetic briefs and the expected G1 graph. Offline contract
tests check these shapes. They do not replace the active v1 model or its pinned
workspace schemas; Stage 2 owns that change. Build receipts track the contract
test inputs so schema, registry or golden-fixture edits require a fresh Build.

## 3. Target architecture (v2)

See [knowledge-model-v2.md](knowledge-model-v2.md) for the full model. In short:

```text
knowledge/registry/      controlled vocabularies and canonical units
knowledge/sources/       exact document revisions (SHA-256, license class)
knowledge/packages/      package bodies and land patterns
knowledge/parts/         orderable parts with pin maps and typed parameters
knowledge/blocks/        reusable sub-circuits with expansion and layout constraints
knowledge/rules/         class-level defaults
knowledge/fab-profiles/  manufacturing capability profiles
src/pcbknowledge/calc/   calculators
evals/golden-designs/    design briefs and acceptance checks
```

- One record model and one write path: agents and humans edit JSON through the
  same validator; Git commits publish.
- `bundle build` compiles one validated commit into a derived JSON bundle. The
  read-only query CLI and `expand` operate on a bundle.
- Each record carries a `verification` level; a design intent reports the weakest
  level it used.

## 4. Runtime and security boundary

The runtime is one loopback-only Python process using only the standard library.
There is no login, hosted service, database authority, queue, object store or
background worker; adding one requires a new ADR and explicit owner approval.
Mutation routes, while they exist, require loopback Host/Origin checks, CSRF and
optimistic revision tokens. The GUI never runs Git write commands.

Request flow stays `HTTP handler -> application/view-model -> repository/domain`;
HTML renders view models and does not rediscover domain relationships.

## 5. Workspaces and publication

A knowledge workspace is a Git repository with `pcbknowledge.workspace.json` and an
exact `schemas/` snapshot (ADR-020). This software checkout is also a workspace for
public curated data. Private knowledge lives in a separate controlled workspace.
Selection is explicit (`--workspace`, `--repo`) and never falls back to this checkout.

Knowledge data commits stay separate from schema, workspace-contract or policy
commits (`change-scope` must not be `MIXED`). A schema upgrade is an explicit
contract change, not a silent rewrite of an existing workspace.

## 6. Derived state

`.pcbknowledge/`, indexes, bundles, footprint and netlist exports, previews and
packages are derived and rebuildable. They are written under ignored directories
and never become authority.

## 7. FreeCM lifecycle

- **Config** validates the software checkout.
- **Build** compiles and runs repository tests and validates the source workspace.
- **Run/Open** start the loopback viewer for an explicit workspace.
- **Test** runs software tests and may validate an external workspace.
- **Package** exports one validated workspace (becomes `bundle build` in v2).

## 8. Deferred

Hosted multi-user service, accounts, database authority, vector retrieval without
evaluation evidence, MCP as a domain protocol (ADR-016: adapter only), automatic
Git publication and any board mutation remain out of scope.
