# ADR-023: Design intent handoff to PcbAtlas

- Status: Accepted
- Date: 2026-10-29
- Applies owner-decision defaults D3 and D4 from `TODO.md`.
- Accepted: 2026-10-29 by the agent under explicit owner delegation (AGENTS.md section 3).

## Context

G1 needs a reproducible boundary between knowledge expansion and board layout.
ADR-022 assigns the catalog, calculators and pure block expansion to PcbKnowledge;
PcbAtlas owns synthesis orchestration, board state and manufacturing outputs.
This proposal specifies the handoff without modifying PcbAtlas.

## Contract

### Inputs and ownership

PcbAtlas synthesizes a block graph from the design brief using the PcbKnowledge
query API (D4). It may choose only catalog blocks and parts. PcbKnowledge also
ships a hand-written G1 graph as the reference answer for later synthesis tests.
Stage 1 graphs describe intended interfaces; the catalog and expansion engine
are implemented in later stages.

Expansion consumes one validated, Git-commit-pinned knowledge bundle and one
block graph. It performs no network access, source-original fetch, board mutation,
Git write or catalog change. Identical inputs produce identical design intent.
PcbKnowledge owns the active pinned structural contracts under `schemas/`.

### Authoritative output (D3)

The design intent JSON is the handoff authority. Its schema defines:

- the brief identity, bundle commit and input block-graph SHA-256;
- components with selected part, package and footprint identifiers;
- named nets with physical component pin numbers, and BOM quantities;
- the selected fab profile, mechanical envelope, mounting and edge-interface
  requirements, and layer/thickness/copper/assembly-side requirements;
- the full layout and net constraints to be checked by PcbAtlas;
- electrical check results and typed refusal reasons;
- the weakest verification level used and source/page evidence references.

The mechanical envelope is a design limit, not final placed-board coordinates.
Mounting components carry their selected package/footprint geometry; PcbAtlas
owns placement. Nominal copper weight is an explicit manufacturing requirement,
not an invented conversion to physical copper thickness.

`EXPANDED` requires resolved manufacturing and mechanical inputs, components, nets and BOM, passing checks and no
refusals. `REFUSED` carries actionable typed reasons. Unknown operating inputs,
missing pin or pad mappings, unsupported constraints and unresolved catalog
selection are not replaced by guessed values. The semantic validator must also
check cross-record closure and compute the weakest level; JSON Schema alone
does not establish those relationships.

PcbAtlas must reject unsupported schema versions, unresolved/refused intents or
constraint kinds it cannot check. It must not silently drop a constraint while
reporting acceptance. The consumer's acceptance report records the exact bundle
commit and input graph identity from the handoff.

### Derived interchange

PcbKnowledge later exports a KiCad netlist and `.pretty` footprint library from
the same design intent. Those files are interchange artifacts, not a second
source of design decisions. Reimport or manual edits cannot silently replace the
JSON authority. A consumer which uses KiCad transport must still retain and
check the JSON constraints and provenance.

No source-original bytes, cache paths, private metadata or credentials are part
of the handoff. Evidence references identify catalog sources and pages; original
access remains subject to the source license and local workspace boundary.

### Acceptance responsibilities

PcbKnowledge verifies knowledge closure and electrical checks (A1/A2).
PcbAtlas verifies placed/routed constraints (A3), DRC against the named fab
profile (A4), and fabrication outputs (A5). The owner performs hardware bring-up
(A6). The Stage 1 fixtures do not assert any of those levels have passed.

## Consequences and review

- Design intent and block graph are separate contracts; no live board API is
  introduced in PcbKnowledge.
- The generic fab profile remains an unresolved catalog target until its real
  capabilities are collected in Stage 4. Stage 1 assigns no manufacturer limits.
- Schema shape checks ship now. Domain validation, bundle compilation, expansion,
  exporters and PcbAtlas import/checking remain in their roadmap stages.
- Acceptance applies the D3/D4 defaults and closes the Stage 1 exit; Stage 2
  implements against this contract.
