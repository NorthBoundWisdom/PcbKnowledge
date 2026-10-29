# TODO — PcbKnowledge roadmap

> Status: `STAGE_1_CONTRACTS`
> Updated: 2026-10-29
> Goal: a design package (for example a simple hardware-competition brief) becomes a
> manufacturable board. PcbKnowledge supplies the knowledge, calculators and block
> expansion; PcbAtlas does placement, routing, DRC and fabrication output.
> Direction: [ADR-022](docs/adr/ADR-022-board-generation-knowledge.md) ·
> Model: [knowledge-model-v2](docs/knowledge-model-v2.md) ·
> Targets: [golden designs](docs/golden-designs.md) ·
> Architecture: [architecture](docs/architecture.md)

## How this file works

- This is the only list of unfinished work. One section per stage, in order.
- A stage is done when its exit criteria pass. Record a one-to-three-line receipt
  under the stage (commit, commands, test count, first failure if any). Do not
  create separate receipt documents.
- Progress is measured by golden-design acceptance level (A1 to A6), not by record
  counts.
- Work that does not serve the current stage or a golden design waits.

## Owner decisions

Each has a default so work is not blocked. The owner may override; record the
answer here.

| ID | Decision | Default until the owner decides |
|---|---|---|
| D1 | MCU family for G1 | STM32F103C8T6 (LQFP-48) |
| D2 | Fab and assembly house for the first fab profile | A generic low-cost two-layer, 1.6 mm, 1 oz, single-side assembly profile; values cited from the selected fab's public capability page |
| D3 | Handoff format to PcbAtlas | Design intent JSON as the authority, plus derived KiCad netlist and footprint library (PcbAtlas already imports KiCad) |
| D4 | Where brief-to-block-graph synthesis runs | PcbAtlas AI runtime calling the PcbKnowledge query API; PcbKnowledge ships the agent skill and golden evaluations |
| D5 | Keep a GUI after v2 | Remove v1 decision UI; keep the PDF evidence viewer only if a v2 read-only browser needs it in Stage 2 |
| D6 | Distributor part numbers in public records | Allowed as identifiers only (no copied catalog data) |

## Stage 0 — Course correction (complete)

Stop expanding the old design, remove dead weight, align instructions.

- [x] Reorganize documentation: new ADR-022, architecture, knowledge model v2,
  golden designs, this roadmap; retiring-subsystem docs moved to `docs/legacy/`,
  historical receipts to `docs/archive/`, links rewritten.
- [x] Update `AGENTS.md`, `README.md` and `CONTRIBUTING.md` to ADR-022.
- [x] Freeze the intake queue: no new batches, annotations, handoff cards,
  evaluation manifests or worked examples. Local tag `intake-final` pins `82b4eff`; the owner pushes the tag.
- [x] Remove the pilot harness and its exclusive snapshot helper, all fixed
  per-device evaluators, and the intake growth handoff tool with their tests/docs.
- [x] Run the full repository gate: Build/Test each 378 tests, no skips; all guards,
  workspace/authority validation, Config and Package pass. The local `intake-final`
  tag retains the frozen pre-removal tree. Verification details are in the stage commit.

Exit: the deletions above are complete, all gates pass, and no document or
instruction asks for new intake batches or per-batch receipts.

## Stage 1 — Contracts for the first golden design (active)

- [ ] Write the brief JSON Schema and machine-readable G1, G2, G3 briefs in
  `evals/golden-designs/`.
- [ ] Write a hand-made expected **block graph** for G1 (the reference answer the
  AI synthesis is later compared against).
- [ ] Write JSON Schemas for v2 records (envelope, typed quantity, unknown, source,
  package, part, block, rule, fab profile) and the initial registries, limited to
  what G1 needs.
- [ ] Write the block-graph input schema and the design-intent output schema.
- [ ] Agree the design-intent handoff with the PcbAtlas owner (D3, D4) and record
  it as ADR-023.

Exit: schemas validate the G1 brief and G1 block graph; ADR-023 accepted.

## Stage 2 — v2 core, migration and hard cut

- [ ] Implement the v2 model and validator (knowledge-model-v2 section 7), reusing
  canonical JSON, deterministic IDs, the SHA-256 evidence cache, workspace pinning
  and change-scope.
- [ ] Bump the workspace format to v2 in a contract-only commit; data commits follow.
- [ ] Read-only CLI: `validate`, `part show|search`, `package show`,
  `block show|search`, `fab show`.
- [ ] Migrate the G1 parts that exist in intake (see golden designs) into v2 `source`
  and `part` records, re-checking pins against the cited source.
- [ ] Rewrite the repository Agent skills (`.codex/skills/`) for v2 ingestion:
  register source, extract part, verify part, write block.
- [ ] Hard cut: delete v1 Source/Entity/Fact families, the approve/reject review
  closure and its UI, the intake queue and its whole toolchain (`intake*.py`,
  intake CLI commands, replay tests, `evals/intake-*.json`, the CI replay step,
  `docs/legacy/intake/`, `docs/legacy/agent-workflow-v1.md`). Later migrations read
  intake content from the `intake-final` tag.
- [ ] Decide D5 and either adapt the evidence viewer to v2 or delete it.

Exit: one model; all gates pass; G1 migrated parts validate as `AGENT_VERIFIED`.

## Stage 3 — Packages and footprints

- [ ] Parametric land-pattern generators (original code) for the G1 package
  families: chip 0402/0603/0805, SOD-123, SMA/SMB, SOT-23-3/5, SOT-223, SOIC-8,
  TSSOP/VSSOP, LQFP-48, crystal 3225, 2.54 mm headers.
- [ ] Explicit-pad packages for irregular G1 parts: USB-C receptacle, tactile
  switch, connectors.
- [ ] Tests against hand-checked dimension tables; pad-to-pin closure for every part.
- [ ] Derived KiCad `.kicad_mod` export.
- [ ] Manual acceptance: open the exported footprints in KiCad or PcbAtlas and
  compare against the manufacturer drawings.

Exit: every G1 part has a validated package and exported footprint.

## Stage 4 — G1 knowledge content

- [ ] Remaining G1 parts (MCU per D1, crystal, USB-C receptacle, LEDs, switch,
  passives) with pins, key parameters and sourcing.
- [ ] G1 blocks: USB-C 5 V sink input, input protection, fixed LDO, MCU core
  (decoupling, crystal, reset, boot), SWD header, LED indicator, button input,
  I2C bus with pull-ups, INA219 monitor, I2C EEPROM, UART header, mounting holes.
- [ ] Rules: default IC decoupling, edge-connector placement, power net class.
- [ ] Fab profile per D2.
- [ ] Calculators needed by these blocks: `ldo_dissipation`, `led_resistor`,
  `i2c_pullup`, `ipc2152_width`.

Exit: G1 knowledge coverage is 100% for the hand-made block graph (A1 reachable).

## Stage 5 — Bundle, expansion and AI synthesis

- [ ] `bundle build` from one validated commit; query CLI over the bundle.
- [ ] `expand`: block graph to design intent (components, parts, footprints, nets,
  BOM, layout and net constraints, check results, weakest verification level,
  typed refusals). Deterministic and pure.
- [ ] A2 electrical checks inside `expand`.
- [ ] Derived KiCad netlist and footprint-library export from a design intent.
- [ ] Agent skill: brief to block graph using only the query API. Evaluate on G1
  against the hand-made block graph; must pass A1 and A2.

Exit: G1 reaches A2 from an AI-produced block graph.

## Stage 6 — G1 end to end with PcbAtlas (cross-repository)

Work in PcbAtlas is tracked there; this list records what PcbKnowledge needs back.

- [ ] PcbAtlas imports the G1 design intent (or KiCad export per D3).
- [ ] PcbAtlas checks layout constraints from the design intent (A3).
- [ ] DRC against the fab profile (A4) and fabrication outputs (A5).
- [ ] Owner orders G1 boards; bring-up: rails, programmer connects, LED and I2C
  test (A6).
- [ ] Every knowledge gap found here becomes a fix in PcbKnowledge with a test.

Exit: G1 at A6.

## Stage 7 — G2 and G3

- [ ] G2: buck converter block with hot-loop and thermal constraints, low-side
  switch and ULN2003A blocks, Kelvin current sense; parts migrated from the
  `intake-final` tag where available.
- [ ] G3: analog front-end blocks, reference, ADC, RS-485 with termination and bias,
  analog/digital return-path constraints.
- [ ] Calculators as needed (`buck_inductor_ripple`, `rc_time`,
  `trace_impedance_microstrip`).

Exit: G2 and G3 at A5, then A6.

## Later (not started)

- More fab profiles, four-layer stackups, controlled impedance.
- Private workspace for non-public parts and internal rules.
- Exact and full-text index over the bundle if catalog size makes linear search slow.
- Catalog growth driven by new golden designs, not by device lists.

## Retired roadmap items

| Old item | Disposition |
|---|---|
| P0.4a real private pilot (3–5 ICs, 20–40 Facts, visual bbox acceptance) | Cancelled; v2 golden designs replace it |
| P0.4b first production dataset (20–30 ICs, 100 pin and 100 limit Facts) | Replaced by golden-design coverage |
| P1 local retrieval (SQLite/FTS) | Moved to Later; bundle search first |
| P1.5 new Fact families (PackageDimension, Decoupling, LayoutGuideline and others) | Absorbed into v2 `package`, `rule` and `block.layout` |
| P2 product integration and KnowledgeSnapshot | Replaced by Stages 5–6 and commit-pinned bundles |
| P3 vector retrieval | Deferred indefinitely (ADR-010) |
| Next application-question milestones, external collection issues | Stopped; intake frozen |
| Nexperia text-only observations, MCP23017 wording ambiguity | Closed; neither device is in a golden design |

## Completed foundation (summary)

- P0.0–P0.3c (2026-08): Git-native authority, typed v1 model, agent ingestion,
  open-source workspace boundary (`cdf7160`), typed workbench (`4cb0318`), visual
  evidence review (`8b357ff`), review closure (`44b8338`).
- Intake curation (2026-10-27 to 2026-10-29): 37 batches, 49 source scopes, 329
  agent-reviewed annotations; read-only CLI, workbench page, bundle, report and
  evidence audit; 486 tests at `58c6614`. Receipts are in `docs/archive/` and Git
  history.

## Permanent boundaries

- Never commit source originals, private data or secrets; originals live only in
  the ignored SHA-256 cache. Public availability is not a redistribution license.
- Unknown, conflict and missing evidence stay explicit; generation refuses rather
  than guesses.
- One record model, one validator, one write path. Indexes and bundles are derived.
- Knowledge data commits stay separate from schema, contract and policy commits.
- PcbKnowledge never reads or mutates a live board and is not a PcbCore runtime
  dependency.
- Loopback-only, standard-library-only runtime unless a new ADR is accepted.
- Never record a human verifier who did not act.

## Verification contract

Run the narrowest affected tests while editing, then the full gate at the stage
exit: `python3 configs/check_english_repo.py`, `python3 configs/check_public_repo.py`,
`python3 configs/check_pdfjs_vendor.py`, `python3 configs/pcbknowledge_workspace.py
validate .`, and `python3 configs/pcbknowledge_workflow.py config|build|test|package`
plus `python3 configs/pcbknowledge_agent.py validate`. Record commands, exit codes,
test counts and skips. Skipped, interrupted or truncated runs are not passes.
