# TODO — PcbKnowledge roadmap

> Status: `CONTINUOUS_MODE_STAGE_8_CI_PENDING` (G1 at A2)
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
- **Continuous mode** (from Stage 6): an implementing agent works the queue
  without a per-round brief. Take the first unchecked item of the lowest open
  stage, finish it, and continue. At every stage exit run the full gate and an
  independent review per [`docs/review-checklist.md`](docs/review-checklist.md),
  fix what it finds, record the receipt, push, and start the next stage. The
  standing task prompt is [`docs/implementer-brief.md`](docs/implementer-brief.md).
- Items marked **(owner-only)** never block the queue: skip them and continue with
  the next item. Items marked **(escalate)** stop work until the owner answers.

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
| D7 | G1 design inputs (these are design decisions, not missing evidence) | USB-C sink input budget 500 mA (5.1 kOhm Rd on CC1/CC2, default USB power); 3.3 V rail load budget 150 mA including 50 mA for expansion headers; MCU external crystal 8 MHz; I2C standard mode 100 kHz with a 100 pF bus-capacitance budget; four 3.2 mm non-plated M3 holes with 6.0 mm keepout, centers 3.5 mm from the board edges; no component height limit for G1. Agent allocation of the 50 mA header budget: SWD 5 mA, I2C 40 mA, UART 5 mA |
| D8 | Package courtyard allowance for Stage 3 | 0.25 mm, selected by the agent as an engineering default; check against generated geometry and the selected fab profile |
| D9 | G1 USB-C input protection topology | No series Schottky on the USB-C sink input (reverse polarity cannot occur on USB-C). Use PTC (MF-MSMF050-2) plus unidirectional TVS (SMBJ5.0A) ahead of the LDO. SS14 is reserved for G2. `ldo_headroom` still checks the worst case at VBUS 4.75 V |
| D10 | Substitution when an official source is inaccessible | Select an equivalent part whose manufacturer drawing or datasheet downloads without bypass; record the substitution and the failed URL in the commit body. Example: Wurth 61300211121 (HTTP 403) is replaced by another manufacturer's 2.54 mm header |
| D11 | G1 passive parts | One series per passive type so one cited source covers every value: KEMET C0603C ceramic capacitors (and the same family in 0805 where 10 uF needs it) and Vishay CRCW0603 thick-film resistors. Each value is its own orderable `part` record citing the series datasheet |
| D12 | Fab profile for G1 (refines D2) | JLCPCB standard two-layer, 1.6 mm FR-4, 1 oz outer copper, single-side SMT assembly. Values are cited from its public capability pages with access date; the owner may replace the fab |
| D13 | G1 evaluation temperature | Implementer-selected under brief delegation, not owner-specified: evaluate G1 at 23 degC, matching Eaton PTC resistance evidence; retain the full 0.5 A USB budget in headroom. This is not all-temperature qualification. |
| D14 | Evidence-driven G1 substitutions | Implementer-selected under D10 delegation: Yageo resistors, Eaton PTS120615V050 PTC and ST SM6T6V8A TVS replace inaccessible/restricted sources; ST LDL1117S33R replaces failed-headroom LD1117; 25 V input capacitance covers the selected TVS clamp. |
| D15 | Board and oscillator compatibility | Implementer-selected under brief delegation: use Wurth 632723300011 explicitly supporting 1.6 mm boards instead of the 0.8 mm Amphenol; use ABLS-8.000MHZ-18 and 22 pF loads after source-based startup/conditional drive screening. Physical oscillator measurement is part of G1 bring-up (Stage 7, owner-only). |
| D16 | Layout handoff files | Decided by the reviewing agent under owner delegation: besides design intent JSON (authority), derive a KiCad 9 board project: `.kicad_pcb` with outline, mounting holes at their constrained positions, every footprint with nets assigned (unplaced footprints parked outside the outline), net classes, and a `.kicad_dru` rule file from the fab profile and layout constraints. Recorded in ADR-025 (Stage 7) |
| D17 | Who checks A3 and A4 | PcbKnowledge ships a read-only conformance checker over an exported `.kicad_pcb` file (layout constraints, A3) and runs `kicad-cli pcb drc` with the generated rules when available (A4). An exported file is not a live board; PcbKnowledge still never places, routes or mutates board state |
| D18 | Through-hole parts in G1 | Keep the THT headers and switch. Each package states its mount type (`SMT`, `THT`, `MECHANICAL`); design intent and BOM list THT parts as hand-solder or THT-assembly items; the fab profile states which mount types it assembles. Not a refusal |
| D19 | Commit types | Add `data` to the allowed types. `[data]:` commits touch only `knowledge/` (change-scope `DATA_ONLY`); other types never touch `knowledge/`. CI enforces both |
| D20 | Web-page sources (fab capability pages) | Store the saved page bytes (HTML or printed PDF) in the local SHA-256 cache with access date; the record states `media_type`. Pages change: a later fetch with different bytes is a new source revision, not a mismatch error |
| D21 | Generalization corpus | Synthetic competition-style briefs beyond G1-G3: two G1 variants (G1V1, G1V2) and three negative briefs (N1-N3) that the closed world must refuse (Stage 8). Later briefs are added only when the previous ones reach A2 |
| D22 | Evaluation independence | An attempt's author, its equivalence reviewer and the orchestrating agent are three different agent identities. The orchestrator may run commands but never judges equivalence |
| D23 | Next fab profile | None until G2 needs one. G2 and G3 use the D12 profile unless a check fails against it |
| D24 | Exported-board measurement policy | Implementer-selected under D16-D17: GROUP defaults to a 10 mm maximum pairwise origin distance; exact edge distances allow 0.01 mm serialization tolerance; loop area is a pad-center convex-hull estimate, not routed-loop certification. Ambiguous Kelvin branches and unsupported/unfilled copper geometry are NOT_CHECKABLE, never silently passed. |
| D25 | Fine-pitch generated land allowance | Implementer-selected after real KiCad DRC: cap the nominal LQFP side fillet at 0.04 mm per side for the 0.50 mm pitch / 0.27 mm maximum STM32 lead width, giving a 0.35 mm pad and 0.15 mm inter-pad gap. Preserve cited dimensions and fab clearance; this is a derived engineering land-pattern decision, not a manufacturer recommendation. |
| D26 | G1 USB land-pattern compatibility | Implementer-selected under D10: replace Wurth 632723300011, whose exact recommended annular rings fail the unchanged 0.25 mm fab floor, with Hirose CX90B2-24P using its exact drawing and handling guide. Keep 5 V sink, 1.6 mm PCB and fab limits; no enlargement of the original pattern or DRC waiver. |
| D27 | Irregular connector courtyard datum | Keep CX90B2-24P manufacturer pad coordinates and cited physical body dimensions. A conservative 4.4 mm courtyard margin bounds the uncertain body-center offset about that drawing datum; it is an implementer envelope, not a manufacturer land recommendation or measured body size. |
| D28 | G1V1 temperature branch | Implementer-selected under D21/D10: NXP PCT2075D,118 replaces the current-monitor function, not the G1 reference. Ground address pins for 0x48, retain 0.1 uF decoupling and an existing 1 kOhm OS pull-up; reserve 7 mA, exceeding 5.5 V / 990 Ohm + 0.4 mA. The 150 mA rail budget is unchanged. New Microchip/TI source processing was stopped at explicit extraction restrictions. |
| D29 | G1V2 UART bridge | Implementer-selected under D21/D10: WCH CH340C in external 3.3 V mode, V3 tied to VCC, internal clock, CTS/DSR/RI/DCD inactive-high and R232 low. Reserve 20 mA within the existing 150 mA rail; this is a design allowance, not a guarantee extrapolated from the 25 degC current test. Replace the UART header; retain SWD 5 mA and I2C expansion 40 mA allowances. |
| D30 | USB data-pair transport | Implementer-selected layout defaults: USB_DP/USB_DN pair with 0.15 mm minimum width, 0.15 mm gap and 0.5 mm maximum skew; direct CH340C data connection follows its source. These are explicit routing constraints, not a certified 90 Ohm impedance result. Use a distinct USB2 sink block so existing G1 behavior is unchanged. |

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

## Stage 2 — Contract corrections, v2 core and hard cut (complete)

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

- [x] Move the corrected schemas from `docs/contracts/v2/` into `schemas/`, bump the
  workspace format, pin the new digest, and update `workspace init|validate`.
  Existing v1 workspaces fail with a clear upgrade message; no silent rewrite.

### 2d G1 sources and parts (data-only commits)

- [x] The local evidence cache in this checkout is empty. Re-download each G1
  source PDF from its recorded official URL into `.pcbknowledge/evidence/sha256/`
  and confirm the recorded SHA-256. A mismatch is a new source revision recorded as
  such, never an override.
- [x] Write v2 `source` and `part` records for the G1 devices present in intake:
  LD1117S33TR (fixed 3.3 V), INA219AIDCNR and 24LC256-I/SN. The owner removed
  SMBJ5.0A, SS14, MF-MSMF050-2, C0603C104K5RACTU and CRCW060310K0FKEA
  from this migration on 2026-10-29 because their cited PDFs have no numbered
  terminal map; Stage 4 may add them after obtaining that evidence or select
  alternatives. The owner also removed Wurth 61300211121 after its official PDF
  remained unavailable (HTTP 403); connector selection stays in Stage 4.
- [x] An independent agent re-checks every cited value and pin, then sets
  `AGENT_VERIFIED` with its actual identity.

### 2e Hard cut

- [x] Delete v1 Source/Entity/Fact families, the approve/reject review closure, all
  v1 and intake GUI pages, the intake queue and its whole toolchain (`intake*.py`,
  intake CLI commands, replay tests, `evals/intake-*.json`, the CI replay step,
  `docs/legacy/`). Later migrations read intake from the `intake-final` tag.
- [x] Per D5, keep the server shell, PDF.js and the evidence endpoint, and add
  read-only v2 part and block pages that show each value beside its cited page.
- [x] Rewrite `.codex/skills/` for v2: register source, extract part, verify part,
  write block.
- [x] Update `AGENTS.md` sections 6 and 7, `architecture.md` and `README.md` to
  describe only v2; delete `docs/course-correction-prompt.md`.

Exit: one model and one validator; G1 parts from 2d validate as `AGENT_VERIFIED`;
full gate passes; record the test count and lines removed.
Stage receipt (2026-10-29): all gate commands exit 0; Build/Test each 81 tests, no skips; 19 pins across three independently verified parts and sources.
One v2 model/validator, read-only HTTP/PDF smoke and deterministic public/external metadata packages passed; +4356 / -97806 lines overall. Exact commands and first failures are in commit bodies.
Browser canvas visual acceptance remains manual because no browser surface was available; steps are in `docs/local-workflow.md`. G1 acceptance levels remain NOT_RUN.
Review (2026-10-29, `4a79bf2`): one model, one validator and one write path are in
place; 81 tests and the full gate pass on a local rerun; the three IC sources match
their recorded SHA-256. Three issues are fixed by
[ADR-024](docs/adr/ADR-024-terminals-packages-selection.md) in Stages 3 and 4:
two-terminal parts were blocked for lacking numbered tables, packages stored
placeholder pad arrays as authority (SOT-223 without its tab), and selection
matching ignored min/typ/max ranges. LD1117S33TR also needs the parameters that
`ldo_headroom` and `ldo_dissipation` read.

## Stage 3 — Packages and footprints (complete)

### 3a Package contract per ADR-024 (contract-only commit)

- [x] Change `schemas/package.schema.json` so a package holds exactly one of:
  `drawing` (cited body and lead dimensions, pitch, pin count, tab or exposed pad)
  plus `generator` and `density`, or `explicit_pads` (irregular parts, cited land
  pattern). Remove stored pads from standard families. Re-pin the contract digest.
- [x] Validator: derive pads for both forms before pin/pad coverage; reject records
  with both forms or neither; keep `pin1`, courtyard and the D8 margin.

### 3b Generators (code)

- [x] Original-code generators in `src/pcbknowledge/v2/footprints/`: two-terminal
  chip (0402, 0603, 0805, 1206 and the 1812 PTC body), molded diode (SOD-123,
  SMA, SMB), gull-wing two-side (SOT-23-3/5/6/8, SOT-223 with tab, SOIC-8,
  TSSOP/VSSOP), gull-wing four-side (LQFP-48), four-pad crystal (3225), and
  through-hole pin header (2.54 mm, 1 to 2 rows).
- [x] Pad sizes follow one documented, original rule set per family (toe, heel and
  side fillets by density level), written as code with named constants; do not
  read IPC documents (ADR-015).
- [x] Tests: for every family, a hand-checked table of expected pad centers and
  sizes for at least one real G1 package; symmetry, pitch, pin-1 position, no
  overlapping copper, courtyard encloses pads and body.

### 3c Re-record the existing packages (data-only commit)

- [x] Replace the three placeholder records (SOIC-8 for 24LC256, SOT-23-8 for
  INA219, SOT-223 for LD1117) with cited drawing dimensions. The SOT-223 tab is a
  separate physical pad sharing the evidenced VOUT number; no extra electrical
  pin is invented. Independent agent verification to `AGENT_VERIFIED`.

### 3d KiCad footprint export and manual check

- [x] Derived `.kicad_mod` export for every package, deterministic bytes, written
  under `build/`. Tests check structure, pad count, numbers and coordinates.
- [x] If `kicad-cli` is available locally, load each exported footprint with it and
  record the result; otherwise say so in the receipt (not a failure).
- [x] Add owner manual-acceptance steps to `docs/local-workflow.md`: open the
  exported library in KiCad and compare against the cited drawing pages.

Exit: every current package validates from drawing dimensions or explicit pads,
exports to KiCad, and passes generator tests.

Stage receipt: `42409c3`, `8befe85`, `ba923d8`; full gate passed, Build/Test each 92 tests, no skips.
Native KiCad 9 parsed all three footprints; exact pushed CI passed. G1 coverage: 0/15 (0%), before Stage 4 data.

## Stage 4 — G1 knowledge content (complete)

### 4a Selection semantics and coverage tool (code)

- [x] Implement ADR-024 selection matching in `catalog.py` with tests for nominal,
  `typ`-only, min/max range and `UNKNOWN` cases.
- [x] `v2 coverage <block-graph>`: for each block instance, report whether the
  block exists, its selections resolve, every referenced part and package is
  `AGENT_VERIFIED` or better, and which items remain. Use it to drive the rest of
  the round; record its output summary at each checkpoint.

### 4b Parts (data-only commits, independently verified)

Use D9 to D15; D14-D15 supersede the originally named alternatives below. Every part has a cited source, a package from Stage 3 and the
parameters its blocks and calculators read.

- [x] Power path: USB-C 16-pin USB 2.0 receptacle (explicit pads), MF-MSMF050-2
  PTC, SMBJ5.0A TVS (convention numbering, cited cathode band), LD1117S33TR with
  the parameters `ldo_headroom` and `ldo_dissipation` need (dropout versus output
  current, maximum input voltage, output current, output-voltage range, thermal
  resistance for SOT-223).
- [x] MCU per D1: STM32F103C8T6 (LQFP-48) with its full numbered pin map, power
  pin groups, BOOT0, NRST, HSE pins and SWD pins; an 8 MHz 3225 crystal with load
  capacitance and ESR.
- [x] Monitor and memory: INA219AIDCNR and 24LC256-I/SN parameters for supply range
  and I2C; a shunt resistor sized by a calculator for the G1 current budget.
- [x] Passives per D11: the capacitor and resistor values the blocks need
  (decoupling, bulk, LDO input and output, crystal load, CC 5.1 kOhm, I2C
  pull-ups, LED series, reset and BOOT0 networks).
- [x] Indicators and input: one 0603 LED color with cited polarity, one tactile
  switch with a numbered terminal drawing.
- [x] Headers: 2.54 mm single-row headers for SWD, I2C and UART per D10; M3
  mounting hole as a mechanical package.

### 4c Blocks, rules, fab profile and calculators

- [x] Calculators (pure, unit tested, refusing on missing inputs):
  `ldo_headroom`, `ldo_dissipation`, `led_resistor`, `i2c_pullup`,
  `shunt_resistor`, `trace_width`. `trace_width` uses the widely published
  IPC-2221 external-layer equation implemented from first principles; do not read
  IPC documents (ADR-015).
- [x] Register calculators so block `checks` and `CALCULATED` values validate;
  remove the fail-closed placeholders in `catalog.py`.
- [x] Blocks: USB-C 5 V sink input (CC resistors), input protection (D9), fixed LDO,
  MCU core (per-pin decoupling, bulk, crystal with load caps, NRST, BOOT0
  pull-down, VDDA filtering), SWD header, LED indicator, button input, I2C bus with
  pull-ups, INA219 monitor with shunt, I2C EEPROM (address and WP strapping),
  I2C header, UART header, mounting holes. Each block has layout constraints
  (`PLACE_NEAR`, `GROUP`, `EDGE_PLACEMENT`, `NET_WIDTH_MIN` and others the block needs).
- [x] Rules: default IC decoupling, edge-connector placement, power net class.
- [x] Fab profile per D12 with cited values.
- [x] Design risk: with D9 (no series Schottky), `ldo_headroom` must still pass at
  VBUS 4.75 V minus the PTC drop at the G1 current budget. If it fails, record the
  failure and switch the LDO block to a lower-dropout part rather than relaxing
  the check.

Exit: `v2 coverage` reports 100% for the hand-made G1 block graph (A1 reachable).

Stage receipt: full gate passed; Build/Test each 135 tests, no skips; 94 records, 28 local source hashes verified.
G1 coverage 15/15 (100%); all 21 package exports parsed by KiCad 9. D13-D15 record source/compatibility substitutions.

## Stage 5 — Bundle, expansion and AI synthesis (complete)

### 5a Bundle and queries

- [x] `bundle build` from one validated commit (refuse a dirty or unvalidated
  tree), deterministic bytes, written under `build/bundle/`; query commands accept
  `--bundle` as well as `--repo`.

### 5b Expansion

- [x] `expand --bundle <bundle> <block-graph>`: design intent per ADR-023 and
  `schemas/design-intent.schema.json` (components with parts, packages and
  footprints; nets with physical pin numbers; BOM; complete layout and net
  constraints; fab profile and mechanical inputs; check results; weakest
  verification level; typed refusals). Deterministic and pure; identical inputs
  give identical bytes.
- [x] A2 checks inside `expand`: every IC power and ground pin connected; decoupling
  per rule; no required input floating (BOOT0, NRST, WP, address pins); every block
  calculator check passes; I2C pull-ups present once per bus; LED currents and
  LDO headroom and dissipation within limits.
- [x] Tests: the G1 reference graph expands to `EXPANDED` with all A2 checks
  passing; mutated graphs (missing decoupling, floating BOOT0, LDO over budget,
  unknown part) produce the expected typed refusals.

### 5c KiCad interchange

- [x] Derived KiCad netlist and footprint library from a design intent, written
  under `build/`. If `kicad-cli` is available, import-check them and record the
  result.

### 5d AI synthesis

- [x] Skill `.codex/skills/synthesize-block-graph/`: brief to block graph using only
  the read-only query CLI over a bundle; never invent blocks or parts.
- [x] Evaluation command: run synthesis on G1, expand the result, and compare it
  with the reference graph (same blocks and connections, or a documented
  equivalent). Run at least three independent attempts and record pass counts.

Exit: G1 reaches A2 from an AI-produced block graph in at least two of three
attempts, and the reference graph reaches A2 deterministically.

Stage receipt: full gate passed; Build/Test each 139 tests, no skips. G1 coverage 15/15 (100%); cross-platform temporary-path failures repaired.
Reference plus 3/3 fresh-context AI graphs reach A2 on `ad7b843`: 46 components, 25 nets, 89 passing checks; preserved independent receipts in `evals/synthesis/g1/`.
KiCad 9 XML reader links all 46 components/23 library parts without warnings; CLI has no PCB netlist-import command.
Review (2026-10-29, `2902b13`): rerun confirms the gate, CI and G1 reference
expansion (`EXPANDED`, 46 components, 25 nets, 89/89 checks, `AGENT_VERIFIED`).
Spot checks of ABLS, RL1206 and B3F values against downloaded sources match.
Findings, all scheduled in Stage 6: four unused parts with their packages and
sources; LDL1117S33R uses a package drawn from the LD1117 datasheet; the brief's
copper and assembly fields are prose matched by `startswith`; commit subjects
dropped the `[type]` brackets and used an unlisted `data` type; `expand` is one
311-line function and 19 lines exceed 140 characters; the synthesis evaluation
cannot fail meaningfully because the catalog holds exactly the G1 blocks, and the
orchestrator judged equivalence; THT parts are not distinguished under a
single-side SMT profile; most sources are not in the owner's local cache.

## Stage 6 — Review fixes and mechanical audit

Goal: turn the review above into code so later stages need no manual audit.
Work in order; each item is one coherent commit or a small group.

### 6a Mechanical guards (code, CI)

- [x] `configs/check_commits.py <range>`: subject format `[type]: description`
  with the AGENTS types plus `data` (D19); `[data]` commits are `DATA_ONLY`,
  others touch no `knowledge/` path; no `MIXED` commit. Run it in CI over the
  pushed range (AGENTS section 1 already lists `data`). Existing history is not
  rewritten.
- [x] `configs/check_code_style.py` (standard library only): maximum line length
  120, one statement per line, no function longer than 80 lines in
  `src/pcbknowledge/`. Add to the full gate and CI. Fix existing violations in
  6c; until then the checker may carry an explicit allowlist that 6c empties.
- [x] `v2 audit` (part of `v2 validate`): every part, package and source must be
  reachable from the expansion of at least one golden or corpus block graph, or
  from a block selection that some graph uses. Unreachable records fail
  validation with their IDs. Delete the four unused parts
  (`abracon-abm8-8-18`, `amphenol-10155435-00011lf`, `kemet-c0603c270j5gactu`,
  `st-ld1117s33tr`) and whatever packages and sources become unreachable, in a
  `[data]` commit.
- [x] Package scope: a package record lists the MPNs or series its cited drawing
  covers, with page evidence; the validator rejects a part whose MPN is not
  covered by its package. Re-record LDL1117S33R's SOT-223 from the LDL1117
  datasheet's own package page (do not reuse the LD1117 drawing).
- [x] Golden regression: the G1 reference expansion's canonical bytes are pinned by
  a SHA-256 in a test. An intended change updates the hash in the same commit and
  states why in the body.

### 6b Contract corrections

- [x] Brief `manufacturing.copper` and `manufacturing.assembly` become controlled
  values (registry or enum, for example `ONE_OZ`, `SINGLE_SIDE_TOP`), prose moves
  to `note`. Remove the string matching in `expansion.py`. Contract-only commit,
  re-pinned digest.
- [x] Mount type per D18: packages state `SMT`, `THT` or `MECHANICAL`; the fab
  profile states assembled mount types; design intent and BOM mark THT items.
  Expansion reports the THT count as a check, not a refusal.
- [x] Web-page sources per D20: `media_type` on sources, cache accepts the saved
  bytes, the viewer shows non-PDF sources as a link plus hash.

### 6c Code readability (behavior unchanged)

- [x] Split `expand` into named phases (resolve instances, unite nets, apply
  rules, run checks, assemble intent) and split `_drawing_pads` per family.
  Golden hash from 6a must not change. Empty the style allowlist.
- [x] Move the workspace and policy helpers the v2 code imports from
  `pcbknowledge.git_native` into a neutral module; delete the old name.

### 6d Evidence for the owner

- [x] `evidence fetch [--source <id>]`: download missing sources from their recorded
  URL into the cache, verify SHA-256, report `MATCH`, `DIFFERENT_BYTES` (kept
  aside, never replaces the cache) or `FAILED` with the HTTP status. Never retry
  around bot checks or access controls.
- [x] `evidence add <file>`: import a manually downloaded file and accept it only
  when its SHA-256 equals a recorded source. Document both in
  `docs/local-workflow.md`, including which publishers block scripted downloads
  (ST and Wurth did on 2026-10-29) and that some spec-sheet generators stamp the
  date into each download.

### 6e Review procedure

- [x] Use `docs/review-checklist.md` at this stage exit and keep it current: each
  check that 6a or a later stage automates moves to its "Automated" list.

Exit: CI runs the commit, style, audit and golden-hash guards; zero unreachable
records; LDL1117 package re-recorded; G1 still `EXPANDED` with all checks passing.

Receipt (2026-10-29): guards `287ae6a`, contracts `19f68bc`, data `79d4bb2`; full gate PASS, 179 tests, zero skips, 66/66 audited records reachable; G1 reference and three preserved graphs EXPANDED.
Review: 13 checks, three commit-guard findings fixed; independent source/package review sampled seven dimensions and two pin maps. Canonical G1 hash changed intentionally for own-source LDL packaging and explicit assembly metadata; readability refactor preserves bytes.
Next: Stage 7 derived layout handoff and exported-board checks; owner-only hardware/layout work remains unclaimed.

## Stage 7 — Layout handoff and board-level checks for G1

Goal: everything a layout tool (PcbAtlas, or the owner in KiCad) needs to start
G1, plus an automatic judge for the finished layout. PcbKnowledge still never
places or routes.

- [x] ADR-025 (accepted under delegation, D16-D17): derived KiCad board project and
  a read-only checker over exported board files. Update ADR-022's boundary text by
  link, not by copy.
- [x] Rules export: `.kicad_dru` and net classes from the fab profile and the
  intent's net constraints (`NET_WIDTH_MIN`, clearance, drill, annular ring,
  hole-to-edge). Deterministic; unit tests per rule kind.
- [x] Board skeleton export: `.kicad_pcb` with the brief's outline, mounting holes
  at their `EDGE_DISTANCE` positions, all footprints from the Stage 3 library with
  nets assigned and parked outside the outline, and the rules above. If
  `kicad-cli` exists, run `pcb drc` on it and confirm only unrouted and placement
  findings appear; record the result.
- [x] `layout check <intent> <board.kicad_pcb>`: parse the exported board (an
  original minimal S-expression reader) and judge every constraint kind the G1
  intent uses: `PLACE_NEAR`, `GROUP`, `EDGE_PLACEMENT`, `EDGE_DISTANCE`,
  `KEEPOUT`, `NET_WIDTH_MIN`, `KELVIN`, `MINIMIZE_LOOP` (bounding polygon
  estimate). Each result is `PASS`, `FAIL` with measured values, or
  `NOT_CHECKABLE` with a reason. Also confirm every intent net and pad matches the
  board.
- [x] Synthetic fixture boards for the checker: one hand-built small board that
  passes and mutations that fail each kind. Fixtures are original files under
  `tests/`.
- [x] `drc` wrapper: run `kicad-cli pcb drc` with the generated rules when
  available and fold the result into one A4 report; `NOT_RUN` when KiCad is absent
  (not a pass).
- [x] Assembly BOM export (CSV) from the intent: references, MPN, manufacturer,
  footprint, mount type, quantity. Distributor numbers only as identifiers (D6).
  Placement files (CPL) need a placed board and belong to the layout tool.
- [x] `docs/local-workflow.md`: how the owner or PcbAtlas takes the G1 handoff
  project, lays it out, and runs `layout check` and `drc`.
- [ ] (owner-only) Lay out G1 in PcbAtlas or KiCad from the handoff project and
  run `layout check` and `drc` (A3, A4).
- [ ] (owner-only) Generate fabrication outputs, order boards, bring up: rails,
  SWD connects, LED and I2C test (A5, A6).

Exit: the G1 handoff project opens in KiCad 9; DRC with generated rules reports
only unrouted/placement findings; `layout check` passes the fixture board and
fails every mutation with the expected kind.

Receipt (2026-10-29): data `b4b606e`, implementation `e82bfe3`; full gate PASS, 226 tests/no skips, 85 records and 67/67 audited authority reachable; G1 remains A2 with 88 checks.
Native KiCad 9.0.2 on authenticated bundle: zero rule violations and 119 unconnected items; parked layout correctly reports FAIL (24 placement findings, eight NOT_CHECKABLE), not A3/A4 acceptance. D24-D27 record measurement, fillet and compatible USB/courtyard decisions.
Review: 13 checks; pad-geometry forgery and two source-claim findings fixed, board/courtyard checks strengthened, independent actual-source and generated-footprint visual review passed. Next: Stage 8 corpus and honest query-isolated synthesis.

## Stage 8 — Generalization and honest synthesis evaluation

Goal: prove the catalog and the synthesis skill work beyond the one design they
were built for, and that the closed world refuses instead of inventing.

- [x] Write corpus briefs (D21) under `evals/golden-designs/`:
  - G1V1: G1 with a different I2C sensor in place of the current monitor (needs
    one new part and block).
  - G1V2: G1 plus a USB-to-UART bridge replacing the UART header (needs one new
    part and block, USB D+/D- routing constraints).
  - N1: requires a 12 V input; N2: requires a Wi-Fi module; N3: requires a BGA
    MCU. Each states the typed refusal it must produce.
- [x] Extend `eval-synthesis`: per brief, three attempts by fresh agents with no
  access to references, tests or other attempts; automatic structural comparison
  where a reference exists; refusal matching for negative briefs; equivalence
  review per D22. Results in `evals/synthesis/<brief>/` with the receipt format
  used for G1.
- [x] Add the parts and blocks G1V1 and G1V2 need (independently verified), then
  run the evaluation. The orphan audit from 6a applies.
- [x] `v2 coverage --all` prints one line per brief (blocks ready, refusals) for
  stage receipts.

Exit: G1V1 and G1V2 reach A2 in at least two of three attempts each; N1-N3 refuse
with the expected typed reason in three of three attempts and no invented part or
block.

Receipt: contract `5bec75a`, data `9d9ef7e`, original synthesis input `2da9522` (tree-equivalent remote `7c1cf3f`); full gate 262 tests, no skips; G1V1/G1V2 A2 3/3 each and N1-N3 typed refusals 3/3 each.
Review: 13-check parent review passed on `97b9e5b`, plus independent source and all fifteen attempt reviews; evaluator verdict/duplicate-instance findings and stale current edge-interface labels fixed.
Publication mapping preserves original input hashes; Stage 9 execution waits for the exact published CI result.

## Stage 9 — G2 to A2

- [ ] Concrete G2 design inputs as `ENGINEERING_DEFAULT` decisions (next D-numbers).
- [ ] Reference block graph for G2.
- [ ] Parts: buck regulator, inductor, Schottky (SS14 per D9), low-side MOSFET with
  numbered pin map, ULN2003A, Kelvin shunt, input bulk capacitors; migrate from
  the `intake-final` tag where the source is accessible.
- [ ] Calculators: `buck_inductor_ripple`, `buck_output_ripple`,
  `mosfet_conduction_loss`, `rc_time`.
- [ ] Blocks with hot-loop, thermal, Kelvin and edge constraints; new constraint
  kinds are registry additions with `layout check` support from Stage 7.
- [ ] Expansion checks for switching converters (inductor current within rating,
  input/output capacitor ripple rating).
- [ ] Synthesis evaluation as in Stage 8.

Exit: G2 reference and two of three AI attempts reach A2; Stage 7 exports and
`layout check` cover every G2 constraint kind.

## Stage 10 — G3 to A2

- [ ] Concrete G3 inputs, reference graph.
- [ ] Parts and blocks: op-amp front end, voltage reference, ADC, RS-485
  transceiver with termination and bias, analog/digital return-path constraints.
- [ ] Calculators: `opamp_gain`, `rc_filter`, `reference_load`,
  `rs485_termination`, `trace_impedance_microstrip` (published closed-form
  approximation, implemented from first principles).
- [ ] Synthesis evaluation as in Stage 8.

Exit: G3 reference and two of three AI attempts reach A2.

## Stage 11 — Corpus growth loop

Repeat until the owner changes direction: add two new synthetic competition-style
briefs per cycle (power, sensing, motor, communication, display themes), each
needing at most a few new blocks; reach A2 for both, with refusals tested for one
new negative brief per cycle. Record one receipt line per cycle with the corpus
pass rate. Stop adding briefs when a cycle's new briefs pass with no new blocks.

## Owner-only and cross-repository items

These never block the queue.

- [ ] (owner-only) PcbAtlas import of the G1 handoff (tracked in PcbAtlas).
- [ ] (owner-only) Optional spot checks: open the viewer, pick five cited values per
  stage and confirm them; a confirmed record may then be set to `HUMAN_VERIFIED`
  by the owner.
- [ ] Every gap found in layout, fabrication or bring-up becomes a PcbKnowledge
  fix with a test, ahead of the current queue.

## Escalate to the owner (stop and ask)

- Changing a permanent boundary below, the public-source boundary, or license
  classes.
- A new runtime dependency, network listener, hosted service or database.
- Weakening, skipping or deleting a check, test or golden design to make a stage
  pass, or changing the A1-A6 definitions.
- Anything that would make PcbKnowledge place, route or mutate a board.

## Later (not started)

- More fab profiles, four-layer stackups, controlled impedance.
- Private workspace for non-public parts and internal rules.
- Exact and full-text index over the bundle if catalog size makes linear search slow.

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
plus `python3 configs/pcbknowledge_agent.py --repo . v2 validate`. Record commands, exit codes,
test counts and skips. Skipped, interrupted or truncated runs are not passes.
