# ADR-025: Derived board handoff and read-only conformance checks

- Status: Accepted under owner delegation (D16-D17).
- Date: 2026-10-29
- Extends ADR-022 and ADR-023 without a live-board API.

## Decision

Design intent, its exact input graph and a validated commit-pinned bundle remain
engineering authority. PcbKnowledge may derive a KiCad 9 project from them:
board outline, constrained mounting-hole coordinates, generated footprints with
net assignments, fabrication rules, net classes and assembly BOM. Every other
footprint is parked outside the outline, not placed for electrical operation.
No routes, manufacturing outputs or placement/CPL files are generated.

The exporter checks the intent against its original graph and bundle before
writing only derived output. Re-exporting does not import manual edits into
knowledge. PcbAtlas or the owner owns actual placement, routing and board edits.

A separate reader inspects an explicitly supplied exported board file. It never
connects to a live editor or writes the inspected board. An original bounded
S-expression reader projects only supported geometry. Malformed inputs fail;
unsupported geometry produces explicit `NOT_CHECKABLE`, not an invented pass.
Reports retain input identities and measured values. Reference/pad/net agreement
is checked before interpreting layout results.

## Measurement scope (D24)

- Placement distances use footprint origins or the cited physical pad centers.
- A group without an explicit distance uses a 10 mm maximum pairwise origin
  distance, an implementer screening default rather than a manufacturer limit.
- Exact edge-distance comparisons allow 0.01 mm serialization tolerance. Edge
  measurements require a supported rectangular outline.
- Keepout screening uses conservative component envelopes; it is not a complete
  three-dimensional mechanical interference analysis.
- Loop screening uses the convex hull of named pad centers as the requested
  bounding-polygon estimate. This cannot establish the actual routed return path.
- Kelvin routing cannot be certified merely because two named nets exist. When
  the intent lacks an unambiguous sense-branch mapping, report `NOT_CHECKABLE`.
- Copper-area screening requires supported, filled copper geometry connected to
  the specified pad; unfilled, ambiguous or unsupported geometry is not a pass.

Each result is `PASS`, `FAIL` or `NOT_CHECKABLE`, with a method and measurement
or reason. A complete acceptance claim must not suppress unresolved constraints.
The parked G1 skeleton is deliberately not an A3 placed-board acceptance result.

## DRC and acceptance

An optional wrapper runs the installed `kicad-cli pcb drc` on a temporary copy of
the exported project and its generated rules, with isolated writable settings.
It writes reports only below the selected workspace's `build/`. Missing KiCad
means `NOT_RUN`; malformed reports or process failures do not count as success.
DRC and layout outcomes remain separate in the combined report. Neither implies
fabrication or bring-up (A5/A6).

The skeleton smoke test establishes KiCad 9 readability and classifies expected
unrouted/outside-outline findings. It does not waive DRC findings on a completed
board. Synthetic original boards exercise supported checks and negative cases.

## References

- [KiCad board S-expression format](https://dev-docs.kicad.org/en/file-formats/sexpr-pcb/)
- [KiCad 9 command-line reference](https://docs.kicad.org/9.0/en/cli/cli.html)
- [ADR-023](ADR-023-design-intent-handoff.md), [TODO decisions](../../TODO.md)
