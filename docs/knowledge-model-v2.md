# Knowledge model v2

> The v2 workspace contract is pinned under [`schemas/`](../schemas/).

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

The pinned JSON Schemas are the structural authority for `source`, `package`,
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
  numbered pin map. Two-terminal parts use convention numbering with cited
  polarity; parts with more terminals need a cited numbered map
  ([ADR-024](adr/ADR-024-terminals-packages-selection.md)).
- Standard-family packages record cited drawing dimensions, a generator and a
  density level; pads are derived. Irregular parts record explicit pads from the
  manufacturer's land pattern (ADR-024). Package `scope.mpns` includes the exact
  selected MPN and its evidence source agrees with part identity evidence; only
  mechanical packages may use engineering-default scope. `mount_type` is `SMT`,
  `THT` or `MECHANICAL`. Selected fab `assembled_mount_types` determine assembly
  versus `HAND_SOLDER` in both components and BOM, with a through-hole count check.
- Part selection matches a requested nominal against the part's `value` or `typ`,
  and requested `min`/`max` against the part's guaranteed bounds; `UNKNOWN` never
  matches (ADR-024).
- Blocks declare components, nets, ports, checks and layout constraints. Contract
  parameter references are data, not executable Python or shell expressions.
- Brief function `category` and power-source/rail `function` bindings are explicit
  inputs to matching. Descriptions are display prose, never inferred requirements.
  Missing bindings produce typed refusals.
- Sources retain SHA-256 document identity and license class. Original bytes stay
  only in the ignored local cache, as PDF or HTML with a checked media signature; public availability does not grant processing
  or redistribution permission.
- Verification levels are `DRAFT`, `AGENT_VERIFIED`, `HUMAN_VERIFIED`. The actual
  creator and verifier are recorded. Generation computes the weakest level used.
  Git history, rather than per-record supersedes chains, versions v2 records.

Workspaces use `pcbknowledge-workspace-v2` and the `board-generation-v2`
contract. Initialization copies the schema snapshot and initial registries.
A v1 manifest fails with a re-extraction instruction; schemas are never silently
rewritten. `pin-contract` explicitly updates the software checkout manifest.

## Validation boundary

The standard-library structural evaluator in `src/pcbknowledge/v2/schema.py` is
shared by runtime code and tests. It evaluates the supported JSON Schema subset
offline and rejects unknown keywords and external references. Schemas define
structure; `v2/vocabulary.py` resolves registry membership, canonical units,
parameter condition keys and numeric ordering. Parameter condition maps name the
quantity of each allowed condition in the parameter registry.

G1 design inputs use D7 engineering defaults. An unconstrained component height
is explicit. G2 and G3 decisions are completed when their stages start.

`v2/catalog.py` loads canonical records from the selected workspace and validates
source/page/license closure, independent verifier identities, exact part/package
pin coverage and aliases, block connectivity and satisfiable selections.
`v2/intent.py` checks component/net/BOM closure, mechanical references, required
electrical checks, power decoupling connectivity and the weakest verification
level across parts, packages, rules, the fab profile and cited sources. Footprint
identifiers are derived as `pcbknowledge:<package ID suffix>`.

The read-only JSON CLI provides `v2 validate`, `part show|search`, `package show`,
`block show|search`, `fab show` and `registry show`, with an explicit `--repo`.
It validates the whole catalog before querying it. Local source-cache absence is
reported as `NOT_LOCALLY_VERIFIED`; bytes with a wrong identity fail validation.
A source with blocked rights cannot back a value. Verifier actor types and
independence are machine checked; the Git reviewer checks that the named actor
actually performed the observation.

Executable calculators validate registered inputs and recompute `CALCULATED`
quantities. The G1 reference and independent graphs use collected records, not
planned identifiers. `v2 audit` follows reference/corpus and preserved synthesis
graph selections plus dependency closure; unreachable parts, packages and sources
fail `v2 validate` and bundle compilation. A refusal fixture may demonstrate a
used selection; reachability alone does not establish electrical acceptance.

Explicit `evidence fetch [--source <id>]` and `evidence add <file>` are cache-writing
commands, unlike queries. Fetch honors source eligibility, bounds downloads and
reports failures without workarounds. Exact bytes return `MATCH`; changed bytes
return `DIFFERENT_BYTES` and stay separate; manual add requires a recorded digest.
Neither command changes knowledge or Git, or marks a record verified.

## Consumer pipeline

```text
brief -> block graph -> expand(pinned bundle, graph) -> design intent -> PcbAtlas
```

PcbKnowledge owns the catalog, generic calculators and deterministic pure
expansion. PcbAtlas owns brief synthesis, board state, placement, routing, DRC
and fabrication output. [ADR-023](adr/ADR-023-design-intent-handoff.md) defines
the handoff (D3/D4).

Commit-pinned bundles support read-only part, package, block and fab queries,
generic calculators and deterministic expansion with typed refusals. Design intent
JSON is the handoff authority; KiCad netlist and footprint-library exports are
derived. Stage 7 layout handoff and board checks remain separate work.

Historical receipts retain their original schema/software context. Use the
recorded software checkout and pinned input commit to reproduce them; current
strict contracts and audit inputs are not retroactive compatibility promises.

## Migration

The intake queue is frozen at local tag `intake-final` (owner publishes the tag).
Only golden-design parts are rechecked and migrated. V2 schema/workspace policy
changes and knowledge data use separate commits. Stage 2 removed the v1 records, review flows and intake toolchain. Later migration
reads the frozen history rather than restoring the queue.
