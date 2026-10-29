# Knowledge model v2 (target)

> Status: target design accepted by [ADR-022](adr/ADR-022-board-generation-knowledge.md);
> not yet implemented. The executable contract will live in code and JSON Schemas;
> when they land, they become the authority and this page shrinks to a summary.

## 1. Consumer queries come first

A record type exists only because a consumer asks a question it answers. The
board-generation pipeline asks these questions; each maps to a record type and an
API operation (section 8).

| # | Consumer query | Answered by |
|---|---|---|
| Q1 | Which catalog parts satisfy a role and constraints (for example "3.3 V LDO, at least 300 mA, input up to 6 V, SOT-223 or smaller")? | `part` parameters + `part.roles` |
| Q2 | For an MPN: which package, which footprint, and which pin number has which name and electrical type? | `part.pins` + `package` |
| Q3 | What land pattern (pads, courtyard, silkscreen, pin 1) does a package use? | `package.footprint` |
| Q4 | Which reusable circuit blocks provide a function (power input, regulation, MCU core, crystal, debug header, I2C sensor, motor driver)? | `block` |
| Q5 | Given block parameters, what components, values and nets does the block expand to? | `block` expansion |
| Q6 | Which components must be placed near which pins, grouped, or kept in a tight current loop? | `block.layout`, `rule` |
| Q7 | Which nets need minimum width, clearance, a differential pair, a Kelvin connection or a pour? | `block.layout`, `rule`, calculators |
| Q8 | What does each IC power pin need for decoupling by default, and where does a part override that? | `rule` + `part.overrides` |
| Q9 | What are the fab limits (trace, space, drill, annular ring, stackup, assembly)? | `fab_profile` |
| Q10 | Do the chosen operating points respect part limits (dissipation, voltage, current)? | calculators + `part` parameters |
| Q11 | Which inputs are missing, so generation must stop or ask? | typed `UNKNOWN` values and expansion refusals |
| Q12 | Which evidence and verification level backs each value used in a design? | `evidence`, `verification` |

## 2. Repository layout

```text
knowledge/
├── registry/          controlled vocabularies (quantities, parameters, pin types,
│                      layout-constraint kinds, package families, roles)
├── sources/           one record per exact document revision
├── packages/          package body + land pattern (parametric or explicit)
├── parts/             orderable parts: identity, package, pins, parameters, sourcing
├── blocks/            reusable sub-circuits with ports, expansion and layout rules
├── rules/             class-level defaults (decoupling, net classes, edge connectors)
└── fab-profiles/      manufacturing capability profiles
evals/golden-designs/  design briefs and expected acceptance checks
src/pcbknowledge/calc/ calculators (pure functions, unit tested)
```

One JSON file per record, deterministic UTF-8 serialization, file name equal to
the record ID slug. The workspace manifest pins the v2 schema set exactly as v1
did.

## 3. Common record envelope

```json
{
  "schema": "pcbknowledge.part.v2",
  "id": "part:st/ld1117s33tr",
  "verification": "AGENT_VERIFIED",
  "provenance": {
    "created_by": "agent:<id>",
    "verified_by": ["agent:<other id>"],
    "notes": "optional, short"
  }
}
```

- `verification`: `DRAFT` (not usable for generation), `AGENT_VERIFIED` (an
  independent agent checked every cited value against the source),
  `HUMAN_VERIFIED` (the owner checked it). Generation reports the weakest level
  it used. Never record a human verifier who did not act.
- History, authorship and corrections are Git history. There is no per-record
  `supersedes` or immutable-approval state.

## 4. Values, units, conditions and unknowns

Every physical value is a typed quantity:

```json
{"min": 4.75, "typ": 5.0, "max": 5.25, "unit": "V",
 "conditions": {"TA": {"value": 25, "unit": "degC"}},
 "basis": "DATASHEET",
 "evidence": {"source": "source:st/ld1117-rev38", "page": 7}}
```

- `unit` must be the canonical unit for the parameter's quantity in
  `registry/quantities.json` (V, A, W, ohm, F, H, Hz, s, degC; lengths in mm).
  The validator rejects other units; conversion happens at ingest time.
- Parameter names come only from `registry/parameters.json`, which defines the
  quantity, meaning and allowed condition keys. A new name is a small registry
  change reviewed on its own. Free-form parameter names are rejected.
- `conditions` keys come from the parameter's allowed list; values are typed
  quantities. Prose belongs in an optional short `note`, never in place of a
  structured condition.
- `basis` is one of `DATASHEET`, `STANDARD_CONVENTION`, `ENGINEERING_DEFAULT` or
  `CALCULATED`. `DATASHEET` requires `evidence` with a source and page.
  `STANDARD_CONVENTION` names the convention (for example a JEDEC outline), not
  copied standard text. `ENGINEERING_DEFAULT` is an explicitly labeled rule of
  thumb. `CALCULATED` names the calculator and its inputs.
- Unknown is explicit and typed:

```json
{"status": "UNKNOWN", "reason": "No numbered terminal table in Rev 3.1",
 "blocks": ["Q2"]}
```

A value is either a typed quantity or `UNKNOWN`; never a guess.

## 5. Record types

### source

An exact document revision: `title`, `publisher`, `revision`, `url`,
`accessed_on`, `sha256`, `bytes`, `pages`, `license_class`. Originals stay in the
ignored `.pcbknowledge/evidence/sha256/` cache (ADR-021). `license_class` gates
agent processing exactly as today (ADR-015).

### package

```json
{
  "schema": "pcbknowledge.package.v2",
  "id": "package:sot-223-3",
  "family": "SOT-223",
  "body": {"length_mm": 6.5, "width_mm": 3.5, "height_max_mm": 1.8},
  "pads": {"generator": "gullwing_two_side", "params": {"...": "..."}},
  "pin1": "pad 1, bottom-left in top view",
  "courtyard_margin_mm": 0.25,
  "basis": "STANDARD_CONVENTION",
  "evidence": {"source": "source:...", "page": 12}
}
```

- Prefer a parametric generator (original code) for standard families: chip
  0402/0603/0805/1206, SOD-123, SMA/SMB, SOT-23-3/5/6, SOT-223, SOIC, TSSOP/VSSOP,
  LQFP, QFN with exposed pad, 2.54 mm headers. Use explicit pads for irregular
  parts (USB-C receptacles, switches, connectors) taken from the manufacturer's
  recommended land pattern.
- Generated pads are compared in tests against hand-checked dimension tables.
- Export to KiCad `.kicad_mod` is a derived artifact.

### part

```json
{
  "schema": "pcbknowledge.part.v2",
  "id": "part:st/ld1117s33tr",
  "manufacturer": "STMicroelectronics",
  "mpn": "LD1117S33TR",
  "package": "package:sot-223-3",
  "roles": ["regulator.linear.fixed"],
  "pins": [
    {"number": "1", "name": "GND", "type": "GROUND"},
    {"number": "2", "name": "VOUT", "type": "POWER_OUT"},
    {"number": "3", "name": "VIN", "type": "POWER_IN"},
    {"number": "TAB", "name": "VOUT", "type": "POWER_OUT", "same_net_as": "2"}
  ],
  "parameters": {"output_voltage": {"...": "typed quantity"},
                 "output_current": {"...": "typed quantity"}},
  "overrides": [{"rule": "rule:decoupling-default", "replace_with": "block-provided"}],
  "sourcing": {"lifecycle": "ACTIVE", "distributor_ids": {"lcsc": "C..."}},
  "pin_evidence": {"basis": "DATASHEET", "source": "source:...", "page": 1}
}
```

The pin values above are illustrative only; real records must cite their source.
Pin `type` comes from `registry/pin-types.json` (`POWER_IN`, `POWER_OUT`,
`GROUND`, `INPUT`, `OUTPUT`, `BIDIRECTIONAL`, `OPEN_DRAIN`, `ANALOG`, `PASSIVE`,
`NO_CONNECT`). Every pin number must exist as a pad in the package. Only the
parameters a consumer query uses are required; others are optional.

### block

A reusable sub-circuit. It is the main unit the synthesis step selects.

```json
{
  "schema": "pcbknowledge.block.v2",
  "id": "block:ldo-fixed",
  "category": "power.linear",
  "parameters": {"vout": {"quantity": "voltage"}, "iout_max": {"quantity": "current"},
                 "vin_max": {"quantity": "voltage"}},
  "ports": [
    {"name": "VIN", "kind": "POWER_IN"},
    {"name": "VOUT", "kind": "POWER_OUT"},
    {"name": "GND", "kind": "GROUND"}
  ],
  "components": [
    {"ref": "U", "select": {"role": "regulator.linear.fixed",
                            "match": {"output_voltage": "=vout"}}},
    {"ref": "CIN", "select": {"role": "capacitor.ceramic", "capacitance_F": 1e-5,
                              "voltage_rating_min": "=vin_max*1.5"}},
    {"ref": "COUT", "select": {"role": "capacitor.ceramic", "capacitance_F": 1e-5}}
  ],
  "nets": [
    {"name": "VIN", "connect": ["port:VIN", "U.pin:VIN", "CIN.1"]},
    {"name": "VOUT", "connect": ["port:VOUT", "U.pin:VOUT", "COUT.1"]},
    {"name": "GND", "connect": ["port:GND", "U.pin:GND", "CIN.2", "COUT.2"]}
  ],
  "checks": [{"calc": "ldo_dissipation", "require": "tj_margin_degC >= 20"}],
  "layout": [
    {"kind": "PLACE_NEAR", "subject": "CIN", "target": "U.pin:VIN", "max_distance_mm": 3},
    {"kind": "PLACE_NEAR", "subject": "COUT", "target": "U.pin:VOUT", "max_distance_mm": 3},
    {"kind": "COPPER_AREA", "target": "U.pin:VOUT", "min_area_mm2": 100}
  ],
  "evidence": [{"basis": "DATASHEET", "source": "source:...", "page": 7}]
}
```

- Components reference parts by role plus constraints, or by explicit part IDs.
- Pins are referenced by name (`U.pin:VIN`), resolved through the selected part.
- `layout` kinds come from `registry/layout-constraints.json`; start with
  `PLACE_NEAR`, `GROUP`, `MINIMIZE_LOOP`, `KELVIN`, `DIFF_PAIR`, `NET_WIDTH_MIN`,
  `CLEARANCE_MIN`, `KEEPOUT`, `THERMAL_VIAS`, `COPPER_AREA`, `EDGE_PLACEMENT`,
  `ORIENTATION`, `TEST_POINT`. Add a kind only when a block needs it and a
  consumer can check it.
- Values in `checks` and selection expressions use a small, safe expression
  language (parameter references and arithmetic only), not general code.

### rule

A class-level default applied unless a part or block overrides it, for example
"each `POWER_IN` pin of an IC gets one 100 nF X7R capacitor within 2 mm"
(`ENGINEERING_DEFAULT`), "connectors with `EDGE_PLACEMENT` sit within 1 mm of the
board edge", or "net width follows `ipc2152_width` for the net's current".

### fab_profile

Layer count, stackup, minimum trace and space, drill, annular ring, via types,
solder-mask web, board thickness, copper weight and assembly limits. Values cite
the fab's published capability page with access date (`basis: DATASHEET`), and
each profile records which owner decision selected it.

## 6. Calculators

Pure, unit-tested functions in `src/pcbknowledge/calc/`, registered by name and
referenced from blocks and rules: `ipc2152_width`, `ldo_dissipation`,
`divider`, `led_resistor`, `i2c_pullup`, `rc_time`, `buck_inductor_ripple`,
`trace_impedance_microstrip`. Add one only when a block or rule needs it. A
calculator returns typed quantities and refuses (typed error) on missing inputs.

## 7. Validation

The validator runs on every record and on the whole catalog:

- schema, registry names, canonical units, `min <= typ <= max`;
- `DATASHEET` values cite an existing source and a page within its page count;
- every part pin maps to a package pad and every pad is covered or marked
  `NO_CONNECT`/mechanical;
- block nets reference existing ports, component refs and pin names; every block
  port is connected; selection constraints are satisfiable by at least one
  `AGENT_VERIFIED` part;
- layout constraints reference existing refs, pins and nets;
- calculators referenced by blocks and rules exist;
- golden designs expand without `UNKNOWN` once their stage claims coverage.

## 8. Bundle and API

- `bundle build --workspace <path>` validates one commit and writes
  `build/bundle/pcbknowledge-<commit>.json` (all records, resolved registries and
  indexes). The bundle is derived state; consumers pin it by commit.
- Read-only CLI (JSON output) over a bundle: `part show`, `part search` (Q1, Q2),
  `package show` (Q3), `block search`, `block show` (Q4), `fab show` (Q9),
  `calc <name>` (Q10).
- `expand <block-graph.json>` (Q5 to Q8, Q11, Q12): input is a list of block
  instances, their parameters and port connections. Output is a **design intent**
  document: components with selected parts and footprints, nets, BOM, the
  complete layout and net constraint set, check results, the weakest verification
  level used, and typed refusals. Expansion is deterministic and pure.
- Derived exports for PcbAtlas: KiCad footprint library (`.pretty`) and KiCad
  netlist, generated from the design intent. PcbAtlas already imports KiCad.
- An MCP or PcbAtlas CommandGateway adapter may wrap these operations later; it
  never becomes a second authority (ADR-016).

## 9. Migration from the intake queue

Only parts that a golden design uses are migrated. For each one, rebuild a v2
`part` record from the cited source, map prose conditions to registry names and
typed quantities, and drop narrative that no consumer query uses. Facts about
devices outside the golden designs are not migrated. After the golden designs no
longer depend on intake, delete `knowledge/intake/`, its evaluators, replay tests,
manifests and CI step in one change.
