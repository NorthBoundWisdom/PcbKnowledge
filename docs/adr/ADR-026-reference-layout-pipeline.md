# ADR-026: Reference layout pipeline

- Status: Superseded on 2026-10-31 by the owner (decision D78 in `TODO.md`). PcbKnowledge is a knowledge base; the pipeline is deleted and remains in Git history up to `e1a5cbe`.
- Date: 2026-10-31
- Accepted: 2026-10-31 by the owner (decision D63 in `TODO.md`).
- Amends: ADR-022 decision 7 and ADR-025 ("PcbAtlas or the owner owns actual
  placement, routing and board edits").

## Context

G1 to G5 reach A2. A3 to A5 need a placed and routed board, DRC and fabrication
outputs. PcbAtlas has no placement or routing plan, so no golden design can pass
A3 and the product goal (a brief becomes a manufacturable board) cannot be shown
end to end.

## Decision

PcbKnowledge adds a **reference layout pipeline** that turns a validated design
intent into a placed, routed and checked board under `build/`:

1. **Placement** is original, deterministic Python code driven by the intent's
   layout constraints: edge and mechanical items first, then anchor ICs, then
   `PLACE_NEAR` and `GROUP` members, with courtyard legalization. It writes a
   derived `.kicad_pcb` (Stage 7 export plus placement and a ground zone).
2. **Routing** is delegated to an external autorouter, Freerouting, run as a
   separate process on a Specctra DSN file; its session (SES) result is merged
   back into the derived board. PcbKnowledge writes DSN and reads SES with
   original code, or uses an installed KiCad's own conversion if available.
3. **Checks** reuse ADR-025: `layout check` for A3 and `kicad-cli pcb drc` with
   the generated rules for A4 (zero violations, zero unconnected items).
4. **Fabrication outputs** use `kicad-cli pcb export gerbers|drill|pos` plus the
   Stage 7 BOM. A5 also requires an independent re-read of the outputs (layer
   set, drill count, every BOM reference present in the position file).

Boundaries:

- Output is derived state under `build/`, rebuildable from intent and bundle.
  It is a reference result and a test oracle for PcbAtlas, not knowledge
  authority. Manual edits are never imported back.
- PcbKnowledge never connects to a running editor and never writes PcbAtlas or
  any board outside `build/`.
- KiCad, Java and Freerouting are optional external tools located by explicit
  path or `PATH`, like `kicad-cli` today. They are not vendored, not runtime
  dependencies of the catalog, and not needed by unit tests. Missing tools give
  `NOT_RUN`, never a pass. Tests use synthetic fixtures and recorded DSN/SES
  samples written for the test.
- The placer must not relax a layout constraint to succeed. If it cannot satisfy
  one, it reports the failing constraint and the board is not A3.

## Consequences

- A3 to A5 become measurable inside PcbKnowledge for every golden design. A6
  (fabricated board bring-up) stays owner-only.
- PcbAtlas can later replace either step and be compared against the reference.
- The escalation rule in `AGENTS.md` changes from "PcbKnowledge never places or
  routes" to "only through this pipeline, only into `build/`".

### Placement support propagation

Connected placement clusters use exact pairwise support propagation before
ranking candidates. A candidate is removed only when no remaining candidate of
an adjacent constrained component supports it. Cached witnesses are checked
against the current domain; all support scans and queue work consume the shared
search budget. Loop and full-board checks still run on completed assignments.
Resource exhaustion and finite heuristic exhaustion are not geometric
infeasibility proofs. Synthetic exhaustive-oracle tests preserve every solution.

### Existing copper in the router projection

KiCad 9 exports unlocked copper with DSN `type route`. Freerouting 2.5.0's
`Wiring.calcFixed` treats that token as `USER_FIXED`, whereas `normal` is
`UNFIXED`. The pipeline translates only `route` to `normal` for a paired native
export from a board without locked copper or unsupported groups. Explicit
fixed states remain unchanged; malformed and unknown states refuse. The
projection preserves every other DSN node and records input/output hashes.

The installed release JAR's scanner and whole-board reader independently
confirmed the state change. This corrects router access to movable existing
copper; it does not change widths, clearances, nets, placement or DRC rules.
The final session, native board, layout and DRC checks remain authoritative.
Source: [Freerouting 2.5.0 Wiring parser](https://github.com/freerouting/freerouting/blob/v2.5.0/src/main/java/app/freerouting/io/specctra/parser/Wiring.java).

### Authenticated local routing repair

`reservation_repair.reserve_route` accepts an original handoff, current partial
board, its exact prior DRC board/report, pinned intent/bundle, and an explicit
failed-pad UUID. It selects native-clearance-checked escape candidates and removes
only authenticated unlocked generated copper blocking the chosen candidate.
Every other board node is retained. Intermediate dangling findings remain FAIL;
continuation requires exact seed or released-track adjacency provenance and no
other geometric/manufacturing findings.

The DSN projection protects the exact new escape and all unaffected already
connected nets. Only nets derived from seed and removed copper remain movable.
The installed router reader verifies these states. Postflight compares exact
seed and unaffected-copper multisets; all displaced connections remain required.
Final native DRC still requires zero violations and zero unconnected items.
The repair result stays FAIL when layout has NOT_CHECKABLE checks, even when its
native A4 result passes. Owner inspection eligibility is evaluated separately.
