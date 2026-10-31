# ADR-023: Design intent handoff to PcbAtlas

- Status: Accepted
- Date: 2026-10-29
- Applies owner-decision defaults D3 and D4 from `TODO.md`.
- Accepted: 2026-10-29 by the agent under explicit owner delegation (AGENTS.md section 3).

## Context

Golden designs need a reproducible boundary between knowledge expansion and board
layout. ADR-022 assigns the catalog, calculators and pure block expansion to
PcbKnowledge; PcbAtlas owns synthesis orchestration, board state and manufacturing
outputs. This decision specifies that boundary. PcbAtlas integration is not
implemented by this repository.

## Contract

### Inputs and ownership

A consumer synthesizes a block graph from a design brief using the PcbKnowledge
query API (D4), selecting catalog blocks and parts. Committed golden-design graphs
provide reference inputs. Expansion consumes a validated, Git-commit-pinned bundle
and a graph; the bundle supplies the brief, catalog records and schema snapshot.

Expansion resolves component selections, physical pins, nets, checks and design
intent. It performs no network access, source-original fetch, board mutation,
Git write or catalog change. Identical inputs produce identical intent.
PcbKnowledge owns the pinned structural contracts under `schemas/` and validates
cross-record closure and the weakest selected verification level.

### Authoritative output (D3)

Design intent JSON is the handoff authority. Its schema defines:

- brief identity, bundle commit and input block-graph SHA-256;
- components with selected part, package and footprint identifiers;
- named nets with physical component pin numbers, and BOM quantities;
- the selected fab profile, mechanical envelope, mounting and edge-interface
  requirements, and layer/thickness/copper/assembly-side requirements;
- layout and net constraints, electrical checks and typed refusal reasons;
- the weakest verification level used and source/page evidence references.

The mechanical envelope is a design limit, not final placed-board coordinates.
Mounting components carry selected package/footprint geometry; placement belongs
to the layout consumer. Nominal copper weight is an explicit manufacturing
requirement, separate from any declared engineering thickness model.

`EXPANDED` requires resolved manufacturing and mechanical inputs, components, nets
and BOM, passing electrical checks and no refusals. `REFUSED` carries typed reasons
with paths and query guidance. Missing evidence, unresolved selections and invalid
physical bindings are not replaced by guessed facts. Design defaults remain
explicit engineering decisions. JSON Schema alone does not establish cross-record
relationships.

Expansion does not prove a future board satisfies every registered layout kind.
The saved-board checker returns `NOT_CHECKABLE` where a constraint cannot be
measured. Consumers must reject unsupported schema versions and refused intents,
and retain any unsupported constraint rather than silently claiming acceptance.
Export and report commands replay the selected bundle/graph expansion before
consuming supplied intent JSON.

### Derived interchange

`export` writes intent and graph copies, a KiCad netlist and a `.pretty` footprint
library. `layout export` also writes a board, project, design rules, local library
table and assembly CSV. The [consumer guide](../consumer-guide.md) gives exact
commands and filenames.

The board is an unplaced transport artifact: it uses the rectangular envelope,
resolves mounting edge distances and parks other footprints outside the board.
It contains no routed solution. The assembly CSV is a BOM-style assembly listing,
not pick-and-place coordinates. Derived files do not replace JSON design authority;
a KiCad consumer must retain its constraints and provenance through editing.

No source-original bytes, cache paths, private metadata or credentials are part
of the handoff. Evidence references identify catalog sources and pages; original
access remains subject to the source license and workspace boundary.

### Measured reports and acceptance responsibilities

D108's owned reports are defined in `envelope.schema.json` as
`#/$defs/layoutReport`, `#/$defs/bringupReport` and `#/$defs/drcReport`.
Their identity, snapshot selection and consistency requirements are specified once
in the [v2 model](../knowledge-model-v2.md#owned-consumer-reports).

PcbKnowledge verifies knowledge closure and electrical checks (A1/A2). Its
read-only saved-board checks and isolated KiCad DRC wrapper provide measured
reports for consumers; these tools do not implement placement or routing.
PcbAtlas owns placed/routed acceptance (A3), DRC against the selected fab profile
(A4), and fabrication outputs (A5). The owner performs hardware bring-up (A6).
Bring-up `COMPLETE` describes plan coverage; observations remain `NOT_RUN`.

## Consequences and review

- Graph and intent are separate contracts; no live board API is introduced here.
- Named fab profiles are catalog inputs. The generic two-layer profile contains
  explicit engineering defaults informed by cited capabilities; selecting it does
  not establish manufacturer qualification for a particular board.
- Structural and domain validation, bundle compilation, expansion, interchange
  exports and saved-board report producers are implemented in PcbKnowledge.
  PcbAtlas import and integration remain external work.
- The original acceptance applied D3/D4 to the Stage 1 handoff decision. Current
  conformance and report tests exercise the implemented contract without changing
  that historical acceptance date or recording owner hardware observations.
