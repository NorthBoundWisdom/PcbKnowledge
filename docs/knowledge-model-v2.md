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
is the active golden-design corpus; unneeded future types are not added speculatively.

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
  Missing bindings produce typed refusals. A function's optional `package_family`
  must be paired with `package_role`: the actual selected component must have both
  that role and family, not merely share a block with a matching passive.
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
quantities. The TIA total-capacitance calculator and preserved historical four-part
calculator have distinct exact input contracts and share one numerical core (D70).
`geometry_affine` computes signed package coordinates as offset plus
factor times dimension, using cited dimensional leaves and explicit mathematical
coefficients. Nested calculations retain source closure; intervals round outward,
and nonfinite results or lost nonzero scalar values fail. The G1 reference and independent graphs use collected records, not
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
derived. Parked layout handoff and read-only board checks remain separate from
A1/A2 expansion and do not claim physical acceptance.

Historical receipts retain their original schema/software context. Use the
recorded software checkout and pinned input commit to reproduce them; current
strict contracts and audit inputs are not retroactive compatibility promises.

## Migration

The intake queue is frozen at local tag `intake-final` (owner publishes the tag).
Only golden-design parts are rechecked and migrated. V2 schema/workspace policy
changes and knowledge data use separate commits. Stage 2 removed the v1 records, review flows and intake toolchain. Later migration
reads the frozen history rather than restoring the queue.

## Exported-board conformance

[ADR-025](adr/ADR-025-derived-board-handoff.md) permits deterministic parked
KiCad projects derived from revalidated intent.
Rules and net classes preserve fab floors and intent minimum widths. Assembly
CSV includes mount types and orderable identities; no placement file is emitted.
A read-only bounded board parser checks identity and supported layout geometry.
Unresolved Kelvin branches, unsupported shapes and absent filled copper remain
`NOT_CHECKABLE`; native DRC absence is `NOT_RUN`. Neither state is success.

## Corpus query and evaluation contracts

`v2 coverage --all` gives one JSON line per brief; `--json` emits the aggregate
report and `--human` emits readable summaries. Every preserved graph is retained.
Graph-specific coverage remains JSON. Counts describe verified block closure, not
independent synthesis; missing graphs are `NOT_RUN`, and incomplete coverage exits 2.
Eligibility and graph refusals remain distinct. Negative expectations live in each
current brief and bind a controlled refusal code to a required function.

Fresh corpus authors receive only the target brief, synthesis skill and mediated
catalog query results, not a raw bundle containing reference answers. Preserve the
actual query transcript and exact bundle-file, skill, brief and graph/refusal hashes.
Current receipts also pin the authenticated catalog tree, semantic audit-input
digest and executing Python source digest; commit metadata changes alone do not
change this identity. See [input recovery](architecture.md#replaying-preserved-synthesis-inputs).
A separate reviewer supplies a controlled `EQUIVALENT`/`NOT_EQUIVALENT` verdict
for positive graphs and an explicit explanation. Negative cases carry a typed
code/path and are reproduced by the evaluator. Actor independence and hashes are
checked; honest access provenance still requires human/agent review.

`DIFFERENTIAL_PAIR` constraints specify two nets, minimum width, gap and maximum
skew. Derived KiCad rules retain these values and the fab floors. They neither
establish 90-ohm impedance nor replace routing, signal-integrity or physical tests.

### Functional electrical bindings

A brief may declare `electrical_bindings`: uniquely named groups with an `id`
and at least two `endpoints`, each naming a brief `function` and selected block
`port`. Each bound function must have exactly one occurrence. An endpoint may
appear only once across the groups. These are functional net requirements, not
graph net labels or reference-instance names.

Expansion resolves each function to its selected instance, then checks the
actual merged physical nets. All endpoints within a group must share one net;
different groups must remain on different nets. Missing or ambiguous functions,
ports without physical connections, rewired endpoints and shorted groups refuse
expansion. Eligibility also checks that candidate blocks expose the required
ports. Existing briefs without the optional field retain their prior behavior.

Derived intent carries the resulting checks. External intent consumption replays
the graph against the pinned bundle's original brief through
`validate_expansion`; supplied PASS labels cannot replace that reconstruction.
These relations do not model voltage propagation through arbitrary components.

### Guard and reference copper requirements

`GUARD_RING` names a sensitive `net`, a distinct `guard_net`, positive scalar
`min_clearance` and `min_width` in millimeters. It requires same-surface guard
copper around the exposed sensitive-net geometry. It does not infer the guard
net's drive impedance. `RETURN_PATH` names a signal `net` and distinct
`return_net`, requiring a continuous adjacent reference copper path. Analog and
digital signals may reference the same ground; this is not a split-ground,
star-return or separated-corridor requirement.

Expansion resolves both net identities and refuses a merged signal/guard or
signal/reference short. Guard geometry must meet the selected fab floors.
Intent exports retain each complete requirement; KiCad rules additionally carry
supported guard width and pairwise clearance minima. Those DRC minima do not
prove enclosure or reference continuity. `RETURN_PATH` uses the D100 read-only
track-corridor measurement described in [local workflow](local-workflow.md#return-copper-measurement);
unsupported topology remains `NOT_CHECKABLE`. `GUARD_RING` uses the D101
[enclosure measurement](local-workflow.md#guard-enclosure-measurement), deriving
every exposed F/B surface from all named-net pads and tracks, including through-hole
pad faces and explicitly proved guard through-via connections. This repository generates no copper (D78).

### Firmware pin configuration

A part pin may list source-cited `functions` from `registry:pin-functions`.
Graph `pin_configurations` resolve an instance port to exactly one physical pin
and carry its supported mode, initial state and evidence into design intent.
`GPIO_PUSH_PULL` with initial `LOW` is the first supported configuration.
These are requirements for the firmware consumer; expansion does not execute them.

A block port's `required_function` checks the selected physical net, while graph
`port_requirements` can declare an additional explicit function. A UART transmit
requirement conflicts with configuring that same pin as GPIO. Names and prose do
not determine pin functions. Missing capabilities, unsupported states, duplicate
configuration and conflicting output drivers refuse expansion. Synthesis
structural comparison includes both graph fields.

### External load power returns

`POWER_SINK` denotes a physical switched power return, exported as KiCad
`open_collector` and routed with the `POWER` net class. It does not waive ordinary
`OPEN_DRAIN` pull-up checks. A block's typed `external_loads` declaration pairs
an actual connector supply pin (mapped to a `POWER_IN` port) with a distinct
return pin (mapped to a `PASSIVE` port). Derived intent preserves that declaration
and the catalog-backed physical `POWER_OUT` provider on the supply net. Validation
rechecks selected parts, pin mappings, provider provenance and actual net membership;
a mere header or a label is not proof of an external load. Every declared return
requires a connected power sink, and every connected sink requires an approved
return without ground, supply or competing active-output shorts. Unconnected spare
collectors are allowed. This is a concrete topology contract, not general power-flow
inference or proof of load ratings.

### Package datum and non-electrical holes

A package may state `body.center.x/y` as typed millimeter coordinates relative to
its footprint datum. Missing center means `(0, 0)`. Derived courtyard encloses
that translated body and every pad, with the recorded margin. This supports a
connector mating-face origin without changing an edge-placement distance.
Manufacturer land generators may declare the cited `pad_numbers` permutation;
numbering changes never move or resize the cited lands.

`MECHANICAL` locator holes are not electrical part terminals. Derived KiCad NPTH
pads have blank numbers, matching native KiCad serialization; geometry, drill,
count and netlessness remain checked. SMT/THT footprint attributes follow the
package mount type so native placement export retains assembly identity.

A part may declare an evidence-backed `bootstrap_supplies` topology for an internal
regulator-and-diode charger. The exact bootstrap input remains `POWER_IN`; its
sourced nominal ceramic capacitor must connect to the declared switch terminal.
Expansion qualifies that pin only after ordinary input supply and ground paths
are established. The same capacitor binding drives decoupling and the unchanged
local placement rule. Neither the bootstrap nor switch net becomes a board power
source, and unrelated supply inputs still require ordinary source paths.

### Independent mask and paste openings

Packages may bind `layer_apertures` to an existing, uniquely numbered physical copper pad.
Each supplied `mask` or `paste` array replaces that pad's implicit opening on the front
layer; geometry is expressed as exact quantities with explicit basis in the bound pad's
local coordinates. Supported shapes are RECT, ROUND and OVAL with orthogonal rotations.
Independent mask currently requires an SMD pad; paste-only through-hole bindings preserve
both existing mask sides. Empty patterns, ambiguous physical bindings, overlapping
same-layer bounding boxes and scalar paste-margin conflicts are refused. Existing scalar
exposed-pad paste margins remain supported unchanged.

Derived apertures have no electrical identity, net, drill or copper. KiCad export uses
empty-number, netless, layer-only pads. Board identity matches these openings as a separate
exact multiset, including their rigid front/back placement; added, missing or changed
openings fail identity. Inherited nonzero mask or paste settings that would change these
explicit openings are unsupported. Electrical pad counts and router copper are unchanged.

Geometry support does not establish assembly capability. In particular, pin-in-paste
process and stencil qualification remain prerequisites before a process-constrained
package or design can reach manufacturing acceptance. The current aperture contract does
not supply that qualification or authorize a manual-solder substitution.
