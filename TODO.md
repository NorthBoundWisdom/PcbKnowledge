# TODO — PcbKnowledge roadmap

> Status: `STAGE_2_ACTIVE`
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
| D5 | Keep a GUI after v2 | Stage 2 deletes all v1 pages, decision flows and intake pages. Keep the loopback server shell, pinned PDF.js and the evidence endpoint, and add minimal read-only v2 part and block pages that show each value beside its cited PDF page, for owner spot checks |
| D6 | Distributor part numbers in public records | Allowed as identifiers only (no copied catalog data) |
| D7 | G1 design inputs (these are design decisions, not missing evidence) | USB-C sink input budget 500 mA (5.1 kOhm Rd on CC1/CC2, default USB power); 3.3 V rail load budget 150 mA including 50 mA for expansion headers; MCU external crystal 8 MHz; I2C standard mode 100 kHz with a 100 pF bus-capacitance budget; four 3.2 mm non-plated M3 holes with 6.0 mm keepout, centers 3.5 mm from the board edges; no component height limit for G1 |

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

## Stage 1 — Contracts for the first golden design (complete)

- [x] Write the brief JSON Schema and machine-readable G1, G2, G3 briefs in
  `evals/golden-designs/`.
- [x] Write a hand-made expected **block graph** for G1 (the reference answer the
  AI synthesis is later compared against).
- [x] Write JSON Schemas for v2 records (envelope, typed quantity, unknown, source,
  package, part, block, rule, fab profile) and the initial registries, limited to
  what G1 needs.
- [x] Write the block-graph input schema and the design-intent output schema.
- [x] Agree the design-intent handoff (D3, D4) and record it as
  [ADR-023](docs/adr/ADR-023-design-intent-handoff.md): accepted 2026-10-29 by the
  agent under explicit owner delegation.

Exit: schemas validate the G1 brief and G1 block graph; ADR-023 accepted.
Target schemas remain outside the active v1 schema pin until Stage 2c.
Stage receipt: Build/Test each 406 tests, no skips; full gate and 801 retained intake cases pass.
Independent review passed 44 focused checks after fixing manufacturing handoff and mechanical blocks.
Contract and registry data use separate commits; exact remote CI is checked after publication.
Review (2026-10-29, `6a69feb`): Stage 0 removal is clean (−9.7k lines, no stale
references, identity coverage kept, CI green). Stage 1 shapes are usable. Four
corrections moved into Stage 2a: design decisions recorded as `UNKNOWN`,
vocabulary duplicated between schemas and registries, a test-only validator that
would become a second validator, and contract size (about 4.2k lines of schema for
one design). The local `intake-final` tag is not yet on the remote.

## Stage 2 — Contract corrections, v2 core and hard cut (active)

Work in the order 2a to 2e; each step is a
coherent commit or a small group of commits. Data and contract commits stay separate.

### 2a Contract corrections from the Stage 1 review

- [x] **Design inputs are decisions, not unknowns.** `UNKNOWN` means evidence a
  source must supply. A brief author or synthesizer decides current budgets,
  crystal frequency, bus speed and hole sizes. Replace the design-choice `UNKNOWN`
  values in `g1.brief.json` (9) and `g1.block-graph.json` (4) with the D7 values
  (`basis: ENGINEERING_DEFAULT`). Replace
  `test_g2_and_g3_keep_unspecified_requirements_unknown` with a test that every
  required G1 design input is concrete. G2 and G3 get concrete inputs when their
  stage starts. Otherwise A1 ("no refusal") can never pass, by construction.
- [x] **Registries are the only vocabulary authority.** Remove parameter names,
  units, condition keys, roles, pin types, package families and layout-constraint
  kinds from schema `enum`/`const`/`properties`. Schemas check structure (ID
  strings, quantity shape); the semantic validator checks registry membership, the
  canonical unit per quantity and the allowed condition keys per parameter. Delete
  `test_schema_vocabulary_and_registry_data_have_one_matching_contract`. Adding a
  parameter must be a one-file registry change.
- [x] **One validator.** Move `tests/contract_schema.py` to the runtime package
  (for example `src/pcbknowledge/v2/schema.py`) as the single structural
  validator; tests import it from there. No second schema evaluator.
- [x] **Shrink to G1.** Remove schema properties that no G1 fixture, consumer query
  or ADR-023 field uses (the brief schema alone is 754 lines). Record the before
  and after line counts in the commit body.

### 2b v2 runtime alongside v1 (code only, no catalog data yet)

- [x] `src/pcbknowledge/v2/`: loader, canonical serialization (reuse existing
  helpers), structural validator from 2a, semantic validator covering the list in
  knowledge-model-v2 "Validation boundary".
- [x] Read-only CLI: `v2 validate`, `part show|search`, `package show`,
  `block show|search`, `fab show`, `registry show`. JSON output.
- [x] Tests on synthetic records in a temporary external Git workspace, including
  tamper cases (unknown registry name, wrong unit, pin without pad, dangling block
  reference, fabricated human verifier).

### 2c Workspace contract v2 (contract-only commit)

- [ ] Move the corrected schemas from `docs/contracts/v2/` into `schemas/`, bump the
  workspace format, pin the new digest, and update `workspace init|validate`.
  Existing v1 workspaces fail with a clear upgrade message; no silent rewrite.

### 2d G1 sources and parts (data-only commits)

- [ ] The local evidence cache in this checkout is empty. Re-download each G1
  source PDF from its recorded official URL into `.pcbknowledge/evidence/sha256/`
  and confirm the recorded SHA-256. A mismatch is a new source revision recorded as
  such, never an override.
- [ ] Write v2 `source` and `part` records for the G1 devices present in intake:
  LD1117 (G1 needs a fixed 3.3 V orderable such as LD1117S33TR; intake covers the
  adjustable LD1117STR, so confirm the fixed variant in the same document),
  SMBJ5.0A, SS14, MF-MSMF050-2 or SF-1206S050-2, C0603C104K5RACTU,
  CRCW060310K0FKEA, INA219AIDCNR, 24LC256-I/SN, Wurth 61300211121. Intake holds
  pin facts only for LD1117, INA219 and 24LC256; every other numbered pin map is
  new extraction from the cited page.
- [ ] An independent agent re-checks every cited value and pin, then sets
  `AGENT_VERIFIED` with its actual identity.

### 2e Hard cut

- [ ] Delete v1 Source/Entity/Fact families, the approve/reject review closure, all
  v1 and intake GUI pages, the intake queue and its whole toolchain (`intake*.py`,
  intake CLI commands, replay tests, `evals/intake-*.json`, the CI replay step,
  `docs/legacy/`). Later migrations read intake from the `intake-final` tag.
- [ ] Per D5, keep the server shell, PDF.js and the evidence endpoint, and add
  read-only v2 part and block pages that show each value beside its cited page.
- [ ] Rewrite `.codex/skills/` for v2: register source, extract part, verify part,
  write block.
- [ ] Update `AGENTS.md` sections 6 and 7, `architecture.md` and `README.md` to
  describe only v2; delete `docs/course-correction-prompt.md`.

Exit: one model and one validator; G1 parts from 2d validate as `AGENT_VERIFIED`;
full gate passes; record the test count and lines removed.

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
- [ ] Calculators needed by these blocks: `ldo_dissipation`, `ldo_headroom`,
  `led_resistor`, `i2c_pullup`, `ipc2152_width`.
- [ ] Known design risk the A2 checks must catch: USB VBUS can be 4.75 V. A series
  Schottky (about 0.4 V to 0.5 V) leaves about 1 V for a 3.3 V regulator, and an
  LD1117-class LDO needs about 1 V of dropout. The input-protection and LDO blocks
  must either omit the series diode on a USB-C sink or use a lower-dropout
  regulator, and `ldo_headroom` must refuse a combination that does not fit.

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
- [ ] (owner-only) Owner orders G1 boards; bring-up: rails, programmer connects, LED and I2C
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
- Owner decisions may be delegated to the agent and are recorded as delegated
  (AGENTS.md section 3). `HUMAN_VERIFIED` requires a person who actually checked.

## Verification contract

Run the narrowest affected tests while editing, then the full gate at the stage
exit: `python3 configs/check_english_repo.py`, `python3 configs/check_public_repo.py`,
`python3 configs/check_pdfjs_vendor.py`, `python3 configs/pcbknowledge_workspace.py
validate .`, and `python3 configs/pcbknowledge_workflow.py config|build|test|package`
plus `python3 configs/pcbknowledge_agent.py validate`. Record commands, exit codes,
test counts and skips. Skipped, interrupted or truncated runs are not passes.
