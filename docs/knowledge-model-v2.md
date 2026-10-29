# Knowledge model v2

> Stage 1 contracts are staged under [`contracts/v2/`](contracts/v2/).
> They define target document shapes, not an active v2 workspace or catalog.
> The running application remains v1 until the Stage 2 hard cut.

## Consumer queries

Every record, field and collection task serves a query below or an explicit golden
design requirement. [ADR-022](adr/ADR-022-board-generation-knowledge.md) owns the
product direction; [`TODO.md`](../TODO.md) owns implementation order.

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

## Contracts and registries

The staged JSON Schemas are the structural authority for `source`, `package`,
`part`, `block`, `rule`, `fab_profile`, the common envelope, quantities, explicit
unknowns, design briefs, block graphs and design intent. Initial controlled
vocabularies live in [`knowledge/registry/`](../knowledge/registry/). Their scope
is G1; later designs do not justify adding unused types now.

- Physical values use canonical units and structured conditions. Parameters use
  registry names. Missing values are typed `UNKNOWN` with a reason and affected
  consumer queries.
- Values identify `DATASHEET`, `STANDARD_CONVENTION`, `ENGINEERING_DEFAULT` or
  `CALCULATED` basis. Datasheet values require source/page evidence.
- Orderable parts have exact manufacturer/MPN identity, a package and a complete
  numbered pin map. Package geometry and generated land patterns become usable
  only after the later footprint stage.
- Blocks declare components, nets, ports, checks and layout constraints. Contract
  parameter references are data, not executable Python or shell expressions.
- Sources retain SHA-256 document identity and license class. Original bytes stay
  only in the ignored local cache; public availability does not grant processing
  or redistribution permission.
- Verification levels are `DRAFT`, `AGENT_VERIFIED`, `HUMAN_VERIFIED`. The actual
  creator and verifier are recorded. Generation computes the weakest level used.
  Git history, rather than per-record supersedes chains, versions v2 records.

The initial schemas are outside the active `schemas/` set deliberately: Stage 2
must explicitly replace the model, bump the workspace contract and pin the new
schema set. No current workspace is silently upgraded and no second runtime
record authority is introduced by these contract files.

## Validation boundary

The standard-library test helper in `tests/contract_schema.py` evaluates only the
JSON Schema keywords used by these staged contracts, offline, rejecting unknown
keywords and external references. Contract tests validate synthetic records,
registry structure, the three briefs and the G1 expected graph. They also check
G1 graph endpoint closure and requirement coverage.

This is not the Stage 2 catalog validator. That validator must enforce:

- canonical serialization, registry closure, parameter-specific condition rules
  and numeric ordering (`min <= typ <= max`);
- source existence, page count and license eligibility;
- independent verifier identity and truthful verification provenance;
- complete part-pin/package-pad coverage and pin aliases;
- block references, port/pin connectivity, satisfiable part selection, supported
  calculator and constraint names;
- design-intent component/net/BOM closure, electrical check completeness and
  the computed weakest verification level.

A structural pass does not resolve a planned block against a catalog. The G1
expected graph is a hand-made planning answer; its referenced catalog records
and electrical operating points still need implementation and verification.

## Consumer pipeline

```text
brief -> block graph -> expand(pinned bundle, graph) -> design intent -> PcbAtlas
```

PcbKnowledge owns the catalog, generic calculators and deterministic pure
expansion. PcbAtlas owns brief synthesis, board state, placement, routing, DRC
and fabrication output. [ADR-023](adr/ADR-023-design-intent-handoff.md) proposes
the D3/D4 handoff defaults; owner acceptance is still required.

Later stages implement read-only bundle queries for parts, packages, blocks and
fab profiles; generic calculators only when a G1 block needs them; bundle
compilation from one validated Git commit; and expansion with typed refusals.
Design intent JSON is the proposed authority, with derived KiCad netlist and
footprint-library exports. None of those runtime v2 operations ships in Stage 1.

## Migration

The intake queue is frozen at local tag `intake-final` (owner publishes the tag).
Only golden-design parts are rechecked and migrated. V2 schema/workspace policy
changes and knowledge data use separate commits. Stage 2 removes v1 records,
review flows and the intake toolchain in a hard cut; later migration reads the
frozen history rather than reviving the queue.
