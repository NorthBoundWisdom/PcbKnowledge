# TODO — PcbKnowledge roadmap

> Status: `CONTINUOUS_MODE_STAGE_13_ACTIVE` (G1-G5 at A2; reference layout next, ADR-026)
> Updated: 2026-10-31
> Goal: a design package (for example a simple hardware-competition brief) becomes a
> manufacturable board. PcbKnowledge supplies the knowledge, calculators and block
> expansion and the ADR-026 reference layout pipeline; PcbAtlas is the product layout tool.
> Direction: [ADR-022](docs/adr/ADR-022-board-generation-knowledge.md) ·
> Model: [knowledge-model-v2](docs/knowledge-model-v2.md) ·
> Acceptance: [current table](docs/golden-designs.md#current-acceptance) · Targets: [golden designs](docs/golden-designs.md) ·
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
- **A blocked stage parks; the queue moves on.** When a stage cannot finish
  (missing evidence no listed default resolves), record the blocker under the
  stage in two or three lines, mark the status `..._PARKED`, and start the next
  stage. Stop the session only when every remaining stage is parked or an
  escalation applies. Revisit parked stages at the start of each session.
- **One implementing session at a time.** Do not run two implementing agents on
  `main` in parallel; it produced duplicate rebased commits and an ancestry merge
  in Stage 8. Reviewer and synthesis sub-agents inside one session are fine.

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
| D13 | G1 evaluation temperature | Implementer-selected under delegation: evaluate G1 at 23 degC to match Eaton PTC resistance evidence; retain the 0.5 A USB headroom budget. |
| D14 | Evidence-driven G1 substitutions | Under D10: Yageo resistors, Eaton PTS120615V050 PTC and ST SM6T6V8A TVS replace inaccessible sources; LDL1117S33R replaces failed-headroom LD1117; 25 V input capacitors cover the TVS clamp. |
| D15 | Board and oscillator compatibility | Under D10: select Wurth 632723300011 for 1.6 mm boards and ABLS-8.000MHZ-18 with 22 pF loads after oscillator screening. Stage 7 hardware bring-up checks startup and drive. USB selection subsequently changes under D26. |
| D16 | Layout handoff files | Under owner delegation, the reviewing agent selected a derived export: a derived KiCad 9 project with outline, constrained mounting holes, net-assigned footprints parked outside the outline, net classes and fab/layout rules; design intent JSON remains authority (ADR-025). |
| D17 | Who checks A3 and A4 | Provide a read-only exported-board conformance checker for A3 and an optional KiCad CLI DRC runner for A4. |
| D18 | Through-hole parts in G1 | Keep THT headers and switch. Packages state mount type; BOM/intent distinguish SMT assembly from hand-solder or THT assembly using the fab's supported mount types. |
| D19 | Commit types | Allow [data] commits touching only knowledge/; other types cannot touch knowledge/. CI enforces the separation. |
| D20 | Web-page sources (fab capability pages) | Cache actual saved HTML or printed PDF bytes with access date and media type; changed page bytes create a new source revision. |
| D21 | Generalization corpus | Use two positive G1 variants and three negative briefs for Stage 8; add later briefs after the preceding positive briefs reach A2. |
| D22 | Evaluation independence | Synthesis author, equivalence reviewer and orchestrator must be three distinct agent identities. |
| D23 | Next fab profile | Reuse D12 for G2/G3 unless a manufacturing check requires another profile. |
| D24 | Exported-board measurement policy | Under D16-D17: GROUP maximum origin distance 10 mm; edge serialization tolerance 0.01 mm; loop area uses pad-center convex hull. Ambiguous Kelvin branches and unsupported copper geometry return NOT_CHECKABLE. |
| D25 | Fine-pitch generated land allowance | Cap nominal LQFP side fillets at 0.04 mm for 0.50 mm pitch and 0.27 mm maximum lead width, producing 0.35 mm pads and the unchanged 0.15 mm fab gap. |
| D26 | G1 USB land-pattern compatibility | Under D10: replace Wurth 632723300011, whose recommended annular rings fail the 0.25 mm fab floor, with Hirose CX90B2-24P. Preserve 5 V sink, 1.6 mm board and fab limits. |
| D27 | Irregular connector courtyard datum | Preserve CX90B2-24P source pad coordinates and body dimensions; use a 4.4 mm courtyard margin to cover the drawing's uncertain body-center offset. |
| D28 | G1V1 sensor preference | Initial TMP102AIDRLT preference is superseded by D31. Replace current monitoring with temperature sensing within the existing 3.3 V / 150 mA budget. |
| D29 | G1V2 bridge preference | Initial CP2102N-A02-GQFN28 preference is superseded by D32-D33. Replace the UART header with a USB-to-UART bridge within the 150 mA rail budget. |
| D30 | Negative corpus inputs | N1 requests 12 V input, N2 Wi-Fi and N3 a BGA MCU; bind expected refusals to typed required functions and actual selected capabilities. |
| D31 | G1V1 temperature branch | Under D21/D10: use NXP PCT2075D,118 at address 0x48 with 0.1 uF decoupling and 1 kOhm OS pull-up; reserve 7 mA (above 5.5 V / 990 Ohm + 0.4 mA) within 150 mA. D38 reopens previously excluded TI/Microchip sources. |
| D32 | G1V2 UART bridge | Under D21/D10: use WCH CH340C with V3 tied to 3.3 V VCC, internal clock, CTS/DSR/RI/DCD high and R232 low. Reserve 20 mA, retain SWD 5 mA and I2C expansion 40 mA, and replace the UART header. |
| D33 | USB data-pair transport | Use a distinct USB2 sink block with USB_DP/USB_DN minimum width 0.15 mm, gap 0.15 mm and maximum skew 0.5 mm; connect CH340C directly per its source. |
| D34 | G2 electrical and manufacturing defaults | Use 7-12 V connector input, 500 mA total input and 3.3 V / 150 mA logic budgets; reuse D12 fab and 8 MHz G1 core on a 100 by 80 mm board with 20 mm height limit and four M3 holes. Include conversion losses in the input budget. |
| D35 | G2 actuation and monitoring scope | Drive two external relay coils and one separate low-side load, each at most 100 mA, 100 mH and 10 Hz. Loads tolerate the protected supply range; measure all protected-input branches. |
| D36 | G2 discrete relay substitution (superseded by D40) | Historical D10 substitution: two RQ5E025TNTL + SS14 relay sinks and a third separate channel. D40 restores ULN2003A; D41 supplies the hot-resistance engineering factor. |
| D37 | G2 input monitor substitution (superseded by D40) | Historical D10 substitution: BD14210G-LATR plus BD79124MUF-CE2, 0.1 Ohm shunt, 10 Ohm/100 nF filter and 2 us RC budget. D40 restores INA219 to resolve the 3.3 V transfer-data gap. |
| D38 | Source eligibility (owner decision, 2026-10-30, not delegated) | The owner accepts the risk of extracting factual parameters, pin maps and drawing dimensions from publicly downloadable manufacturer datasheets, including TI and Microchip, whose site terms limit commercial use and automated mining. Conditions: download each document individually by hand or with `evidence fetch` for one source at a time (no crawling or bulk scraping; publishers that block scripts are downloaded manually and imported with `evidence add`); originals stay in the ignored local cache; Git holds only small original structured facts with citations. Such sources are `PUBLIC_REFERENCE`. `RESTRICTED` is only for documents behind login or NDA, a document that itself prohibits AI processing, and paid standards (IPC). Site terms alone are not a reason to stop |
| D39 | Evidence needed to select a switching regulator | Decided by the reviewing agent under owner delegation: a buck part is eligible when its datasheet gives guaranteed values over the operating range for input voltage, output voltage or feedback reference, output current, switching frequency, UVLO, enable threshold and current limit, and describes its light-load mode. The block's calculators then check the design inputs against those values. Do not require plots or proof for every input/load combination |
| D40 | G2 topology after D38 | Decided by the reviewing agent under owner delegation: return to the brief's original topology. ULN2003A drives the relay coils; the existing INA219 (26 V bus range) monitors the protected input; the separate low-side channel uses a logic-level MOSFET whose datasheet specifies RDS(on) at VGS of 2.5 V or lower. D36 and D37 records that become unreachable are deleted by the audit |
| D41 | MOSFET hot resistance when only typical curves exist | Engineering default: conduction-loss checks use the datasheet maximum RDS(on) at 25 degC times 1.5 for TJ up to 125 degC, unless the datasheet gives a guaranteed hot maximum, which then wins |

| D42 | G2 buck selection | TPS5430DDA replaces the original preference: its published operating-range limits and light-load description satisfy D39. |
| D43 | Relay variant and startup | Select industrial ULN2003AIPWR and 10 kOhm pull-downs on both active inputs for inactive reset behavior. |
| D44 | TPS5430 DAP variants | Use 2.71 by 3.4 mm copper covering both published DDA variants and a -0.15 mm paste margin, giving a 2.41 by 3.1 mm aperture with a 0.125 mm stencil; no order-code variant mapping is assumed. |
| D45 | G2 thermal evaluation | Evaluate the indoor controller at 40 degC ambient, with explicit board thermal models and a 125 degC power-device ceiling; retain the MCU's lower published junction limit. |
| D46 | G2 control pins | Use PA0, PA1 and PA9 for relay1, relay2 and the separate sink; firmware preloads LOW before selecting 2 MHz push-pull GPIO, with normal user-flash boot and no simultaneous UART function; unused BUTTON and UART_RX inputs connect to ground. |
| D47 | G2 external connectors | Use the reviewed Wurth four-pin header for input and each load: supply, return, ground, ground; 12 V DC selection is an engineering decision, not a conversion of its 250 V AC rating. |
| D48 | G2 full-input monitor | Reuse INA219 at address 0x40 with PG=01 (80 mV), a 0.1 Ohm shunt and 500 mA total budget; place all protected loads downstream. |
| D49 | G2 passive selections | Use TDK CLF7045NIT-101M-D 100 uH, Panasonic 25SVPF180M output and 25SVPF47M input capacitors, Littelfuse 0451001.MRL fuse and KEMET C0603C103K5RACTU bootstrap capacitor. |
| D50 | G2 application models | Use 56 uH minimum operating inductance and the manufacturer's 0.81 A overall rating; capacitor ESR maximum times two and ripple rating times one-half; two local 10 uF ceramics with 0.5 bias-retention model; TPS switch resistance times two and 90 degC/W board model; fuse 0.75 continuous and 0.9 temperature factors with twice nominal resistance; SS14 0.6 V and 176 degC/W model; FET gate allocation 100 uA. Source test conditions remain recorded separately. |
| D51 | G2 feedback and damping | Use 10 kOhm upper feedback and 10 kOhm parallel with (10 kOhm + 4.7 kOhm) lower feedback; two parallel 0.1 Ohm resistors provide the output capacitor's series damping floor. |
| D52 | Buck enable connection | Leave TPS5430 ENA unconnected as explicitly permitted by its internal pull-up; the part records the source-backed ENABLED default and the input checker retains it. |
| D53 | G2 input edge | Place the power input header at the RIGHT edge within 5 mm, matching the existing header rule; the brief requires edge access but no particular side. This removes opposed defaults on the exported 80 by 100 mm outline. |
| D54 | G2 entry placement | Place the fuse on the RIGHT edge within 8 mm and its directly connected input-header pad within 5 mm of the fuse pad. Matching edge names alone does not constrain along-edge separation. |
| D55 | G3 operating inputs | Agent-selected bench front end: external 3.2-3.4 V/150 mA, analog branch 10 mA, 15-35 degC, 80 by 100 mm envelope and 20 mm height. Two-layer 1.6 mm board, common ground, separate analog/digital routing groups. |
| D56 | G3 analog models | 940 nm, DC-1 Hz, imposed 0-50 uA photocurrent; 10 kohm transimpedance and buffered half-reference. Reference 2.35-2.65 V and 50 mV aggregate TIA DC error are engineering envelopes. Typical bandwidth/input capacitance inform a stability estimate. NTC checks use the Beta approximation and component tolerances. |
| D57 | G3 interfaces | ADS1115 +/-4.096 V, 8 SPS single-shot with OS polling, 100 kHz host I2C and 50 pF total bus limit. Separate external-host UART/control drives 115200 bit/s RS-485; two 120 ohm terminations, one 2 kohm-per-leg bias pair and 0.6 mA adverse receiver-loading model. The second node also uses SN65HVD75; generic +200 mV receivers are outside this idle-bias design. |
| D58 | G3 reference bias | Three parallel 1 kohm resistors bias TL431; 0.5 mA maximum reference load and no cathode capacitor. |
| D59 | G3 land density | Use the original COMPACT pad-fillets for ADS1115 VSSOP and MH2029 chip packages after source-contact review. This preserves the selected fab clearance and all manufacturer dimensions; NOMINAL fillets left insufficient pad clearance. |
| D60 | G3 functional wiring | Bind functional supply, reference, sensor-channel and common-return endpoints to the actual expanded nets. Each named group shares one physical net and different groups remain distinct. Fixed parameter values alone do not establish physical wiring. |
| D61 | First corpus growth cycle | G4 is a slow optical alignment-score acquisition peripheral; G5 is a dual-temperature agreement telemetry peripheral. Reuse the G3 bench envelopes and verified blocks, with an external host responsible for sequential ADC acquisition, scoring/comparison and communication. Distinct functional channel bindings define each composition. |
| D62 | Reused ADC channels and receiver counterexample | G4 grounds unused ADC AIN0. G5 maps temperature A/B to physical AIN0/AIN1, although the existing second port is named AIN_TIA; AIN2 measures the shared reference. N4 requests a generic +0.2 V idle receiver threshold, which the existing SN65-specific weak-bias block does not support. |
| D63 | Who places and routes (owner decision, 2026-10-31) | The owner chose a reference layout pipeline inside PcbKnowledge ([ADR-026](docs/adr/ADR-026-reference-layout-pipeline.md)): original constraint-driven placement, Freerouting as an external autorouter, KiCad DRC and fabrication exports, all derived into `build/`. PcbAtlas remains the product layout tool and can be compared against this reference |
| D64 | Layout tools | KiCad 9 or 10 `kicad-cli` (the owner has 10.0.6 at `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`), Java 21 or newer, and the latest stable Freerouting release jar. Record the exact Freerouting version and jar SHA-256 in `docs/local-workflow.md` at first use; run it single-threaded with fixed passes. Outputs must work on KiCad 9 and 10 |
| D65 | Corpus themes (fixed order, chosen by the reviewing agent under delegation) | T1 adjustable DC-DC supply with digital setpoint and readback; T2 single-cell Li-ion charger with boost to 5 V; T3 brushed DC motor H-bridge with encoder input; T4 bipolar stepper driver; T5 DAC signal generator with op-amp output stage; T6 OLED and keypad user-interface board; T7 CAN bus node; T8 Wi-Fi module carrier with USB programming; T9 thermocouple measurement with cold-junction sensing; T10 class-D audio amplifier. Take themes in this order; do not reshape a theme to reuse existing blocks |

| D66 | Reference layout knowledge corrections | Replace impossible center-origin proximity proxies with the electrically relevant source-mapped pins, retaining every numerical limit and loop/GROUP check. Use GCT USB4110-GF-A with a typed mating-face datum and Abracon ABMM2-8.000MHZ-18-T to make physical placement possible; cited source values and native geometry checks remain authoritative. |
| D67 | G1 bring-up acceptance windows | Use independently measured conditional steady-state rail windows at exact graph-bound terminals, with load, thermal, resistance, distribution-drop, headroom, capacitance stability and uncertainty prerequisites. Keep all hardware observations and unmet conditions NOT_RUN. |
| D68 | Power-only USB connector | Use GCT USB4125-GF-A-0190 for the power-only sink: the USB4110 recommended locators conflict with the unchanged 0.25 mm hole-clearance rule. The replacement has no NPTH locators and passes the same native coupon rules; retain USB4110 for the separate USB2 block and manually solder the four new shell stakes. |

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

Receipt: integrated remote `999c85d`; full gate 277 tests, no skips, 95 records and 74/74 reachable. Current G1/G1V1/G1V2 graphs expand; N1-N3 screen with their required typed refusals.
Review: preserved remote audit/multi-graph guards; registry-only vocabulary finding and synthetic-fixture omissions fixed. Independent note-only D31-D33 review preserves numeric/source/pin provenance.
Historical G1V1/G1V2 A2 3/3 and N1-N3 refusals 3/3 retain original input `2da9522` (tree-equivalent `7c1cf3f`), not new-brief attempts; Published `12c4ce0`; exact CI and CodeQL passed.

## Stage 9 — G2 to A2

Review (2026-10-30, `6816f39`): Stages 6-8 are complete and pushed with green CI;
the code (about 5.2k lines in `src/pcbknowledge/v2/`) passes the new style,
commit and reachability guards. Stage 7 exports a KiCad 9 board project that DRCs
with zero rule violations; Stage 8 adds G1V1, G1V2 and N1-N3 with 3/3 results.
Course corrections: the queue stopped at Stage 9 because TI and Microchip
sources were treated as off-limits (resolved by owner decision D38), the buck
evidence bar required proof for every input/load combination (D39), and the
substitutions this forced (D36, D37) left `UNKNOWN` inputs that A2 can never pass
(D40, D41). Two implementing sessions ran in parallel, causing duplicate commits
and an ancestry merge. Commit subjects and decision notes drifted back into
disclaimers ("bounded", "honestly refused", "not a ... guarantee").

### 9a Course corrections

- [x] Apply D38 to the skills and docs that classify sources (already updated in
  AGENTS section 7, `register-source`, `open-source-boundary.md`); re-screen the
  sources stopped under site terms and record which are now eligible.
- [x] `check_commits.py` rejects subjects containing `honest`, `bounded` or
  `not a` and subjects over 72 characters. Trim D13-D37 to the decision and its
  reason (drop "not a certification/guarantee/recommendation" clauses); move any
  real limitation into a typed `UNKNOWN` or a check instead.
- [x] Synthesis and evaluation receipts pin the bundle's content digest (Git tree
  of the catalog), not only a commit hash, so a rebase does not invalidate them.
  Remove the need for ancestry merges like `12c4ce0`; do not rewrite history.

Stage 9a receipt: full gate PASS, 311 tests/no skips; content identities survive rebases and explicit replay reports engine changes.
Independent review found one decision-attribution wording issue, corrected; source re-screen follows D38 and historical attempts are unchanged.

### 9b G2 content

- [x] Concrete G2 design inputs as `ENGINEERING_DEFAULT` decisions (D34-D37).
- [x] Calculators: `buck_inductor_ripple`, `buck_output_ripple`,
  `mosfet_conduction_loss`, `rc_time`. The two buck calculators are limited to
  fixed-frequency positive-current CCM.
- [x] Buck regulator per D39: pick one part (any eligible vendor under D38) with
  VIN covering the protected 7-12 V input after reverse-protection drop and a
  3.3 V or 5 V output at the D34 budget; its inductor, input and output
  capacitors and Schottky (SS14 per D9) if non-synchronous.
- [x] Input protection block: fuse, reverse-polarity protection and bulk
  electrolytic capacitor with cited ratings.
- [x] Relay drive per D40: ULN2003A with numbered pin map and flyback through its
  COM pin; low-side MOSFET channel with VGS-specified RDS(on) and D41 loss check;
  INA219 reused as the input monitor. Delete records left unreachable.
- [x] External load connectors for every relay and low-side channel.
- [x] Blocks with hot-loop, thermal, Kelvin and edge constraints; new constraint
  kinds are registry additions with `layout check` support from Stage 7.
- [x] Expansion checks for switching converters: inductor saturation and RMS
  current within rating, input and output capacitor ripple-current rating,
  regulator dissipation.
- [x] Reference block graph for G2 reaching A2.
- [x] Synthesis evaluation as in Stage 8.

Exit: G2 reference and two of three AI attempts reach A2; Stage 7 exports and
`layout check` cover every G2 constraint kind.

Stage 9b receipt: reference A2; fresh `9b4aa7d` attempts 3/3 and separate D54 unchanged-graph regression 3/3; 404 tests/no skips.
Independent reviews fixed edge/fuse placement findings; original packets, submissions, transcripts and identities remain preserved.
KiCad 9.0.2 parked export: identity PASS, 0 DRC violations, 128 unconnected; A3/A4 remain open.

## Stage 10 — G3 to A2

- [x] Concrete G3 inputs, reference graph.
- [x] Parts and blocks: op-amp front end, voltage reference, ADC, RS-485
  transceiver with termination and bias, analog/digital return-path constraints.
- [x] Calculators: `opamp_gain`, `rc_filter`, `reference_load`,
  `rs485_termination`, `trace_impedance_microstrip` (published closed-form
  approximation, implemented from first principles).
- [x] Synthesis evaluation as in Stage 8.

Receipt: published input `5b16185`; reference and three fresh query-mediated attempts reach A2, 62 checks each.
Full gate: 455 tests/no skips; 162 records/125 reachable/23 graphs. Review: complete-graph equivalence and preserved input/submission hashes; A3-A6 remain open.

Exit: G3 reference and two of three AI attempts reach A2.

## Stage 11 — Corpus growth loop

Repeat until the owner changes direction: add two new synthetic competition-style
briefs per cycle (power, sensing, motor, communication, display themes), each
needing at most a few new blocks; reach A2 for both, with refusals tested for one
new negative brief per cycle. Record one receipt line per cycle with the corpus
pass rate. Stop adding briefs when a cycle's new briefs pass with no new blocks.

Cycle 1 receipt: published input a5e2bad; G4/G5 references and fresh attempts reach A2 (3/3 each), N4 typed refusals 3/3. No new blocks; independent review passed after strengthening exact block-content stop proof. Full gate: 471 tests/no skips, 162 records/125 reachable/31 graphs.
Stop: this successful cycle needs no new blocks, so no further briefs are added under the Stage 11 stopping condition. A3-A6 remain owner/cross-repository work.
Review (2026-10-31, `7b786b4`): all gates pass locally (471 tests, no skips) and
in CI; TPS5430 source hash and cited UVLO, enable, frequency, current-limit and
RDS(on) values match the datasheet. G2 and G3 are real progress. Two issues: the
Stage 11 stop rule let the implementer choose briefs (G4, G5) built from existing
blocks, so the stop proved nothing (replaced by the fixed theme list D65); and
synthesis evidence is committed in full (about 6.5 MB of `evals/`, 200 KB
transcripts per attempt), which grows with every cycle. D55-D62 lost spaces
("external3.2-3.4 V") and carry "not manufacturer guarantees" clauses again.

## Stage 12 — Cleanup from the Stage 11 review

- [x] Synthesis evidence storage: per attempt, commit the graph, the receipt with
  SHA-256 of the initial packet, submissions and transcript, and the independent
  review verdict. Full packets and transcripts go to the ignored local cache
  (`.pcbknowledge/evals/`). Replay tests keep passing. Keep `evals/` under 1.5 MB.
- [x] D42-D62: restore missing spaces; keep each entry to the decision and its
  reason, and move real limitations into typed `UNKNOWN` values or checks.
- [x] Update `README.md`, `architecture.md` and `golden-designs.md` for ADR-026
  and the current acceptance table (one authority, linked from the others).

Exit: `evals/` within budget, replay unchanged, docs match ADR-026.

Receipt (2026-10-31): full gate PASS, Test 476/no skips; committed evals 1.13 MB, all original receipt and submission hashes retained.
Independent review verified cache-free replay of all 36 archived attempts; malformed-input and cross-platform byte handling findings fixed.

## Stage 13 — Reference layout for G1 (A3 to A5)

Implements [ADR-026](docs/adr/ADR-026-reference-layout-pipeline.md) on G1 first.

- [ ] `layout tools`: report the located `kicad-cli`, Java and Freerouting jar
  with versions, or `NOT_FOUND`. Document setup per D64.
- [ ] Placer (original code, deterministic): rectangular outline from the brief;
  edge, mechanical and connector items first; anchor ICs; `PLACE_NEAR` and `GROUP`
  members around their targets; courtyard legalization on a grid; top-side SMT per
  the fab profile. Unsatisfiable constraints are reported, never relaxed.
- [ ] Copper: bottom-layer GND zone and stitching vias where the intent asks;
  zones are filled before DRC and export.
- [ ] Routing: write Specctra DSN with net classes (widths, clearances, via size)
  from the fab profile and intent; run Freerouting single-threaded; read SES and
  merge tracks and vias into the derived board. Tests use small hand-written
  DSN/SES fixtures; no tool needed.
- [ ] `layout run <intent>`: place, route, merge, fill, `layout check`, `drc`,
  export, re-read; one report with A3, A4 and A5 each `PASS`, `FAIL` or `NOT_RUN`.
- [ ] Fabrication outputs: `kicad-cli pcb export gerbers|drill|pos` plus the BOM;
  independent re-read checks the layer set, board extents, drill count against
  holes, and that every SMT BOM reference has a position line. Document the CPL
  rotation convention for the D12 fab.
- [ ] Bring-up checklist export from the intent: each rail with expected voltage
  range and test location, programming connector pinout, and the brief's
  functional tests. Used by the owner in Stage 15.
- [ ] Owner review aids: top and bottom SVG renders under `build/` and manual
  steps in `docs/local-workflow.md`.

Exit: G1 reference layout with `layout check` all `PASS` (any `NOT_CHECKABLE`
kind listed with its reason), DRC zero violations and zero unconnected items,
fabrication outputs generated and re-read. Record tool versions in the receipt.

## Stage 14 — Reference layout for G1V1, G1V2 and G2 to G5

- [ ] Run Stage 13 on every positive design. Add placer and router features each
  design needs (wide power nets and thermal copper for G2, USB pair for G1V2,
  analog/digital separation for G3-G5) as constraint support, not per-design code.
- [ ] Every layout or DRC failure that comes from knowledge (footprint, rule,
  constraint) is fixed in the catalog with a test, before tuning the placer.

Exit: every positive golden design at A5 (reference).

## Stage 15 — First fabricated board (owner-only)

- [ ] (owner-only) Order G1 from the Stage 13 outputs; hand-solder THT parts.
- [ ] (owner-only) Bring-up with the Stage 13 checklist: rails, SWD connects, LED,
  button and I2C tests (A6). Record results in `TODO.md`.
- [ ] Every bring-up failure becomes a catalog or pipeline fix with a test, ahead
  of the queue.

## Stage 16 — Corpus growth by fixed themes

Each cycle takes the next two themes from D65, in order, and one new negative
brief. A theme brief states requirements a competition would state; it is not
shaped to reuse existing blocks. Each positive brief must reach A5 (reference
layout), not only A2, with three fresh synthesis attempts as in Stage 8. A theme
may be parked only for part or evidence availability, with the blocker recorded.
Record one receipt line per cycle: themes, A-levels, new blocks and parts, and the
corpus pass rate. Continue until all ten themes are done or parked, then propose
the next ten as a TODO change.

## Owner-only and cross-repository items

These never block the queue.

- [ ] (owner-only) PcbAtlas import of the G1 handoff (tracked in PcbAtlas).
- [ ] (owner-only, optional) Open the Stage 13 G1 reference layout in KiCad and
  review placement and routing by eye before ordering boards (Stage 15).
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
- Anything that would make PcbKnowledge place, route or write a board outside the
  ADR-026 pipeline and `build/`, or relax a layout constraint to pass.

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
