# ADR-022: Consumer-driven knowledge for board generation

- Status: Accepted
- Date: 2026-10-29
- Supersedes: ADR-012 for v2 records; the intake lane of ADR-021; the per-record
  approval workflow of ADR-018/019; ADR-014 (replaced by pinned bundles).
- Retains: ADR-001, ADR-004, ADR-013 (optional bbox), ADR-015, ADR-020 workspace
  selection and schema pinning, ADR-021 local-only original cache.

## Context

The product goal is now explicit: from a **design package** (for example a simple
hardware-competition brief), produce a **manufacturable board**: netlist, BOM with
orderable parts, footprints, placement, routing, a DRC-clean layout for a named
fab profile, and fabrication outputs. PcbAtlas (with PcbCore and an external
router) owns board state and layout. PcbKnowledge must supply the knowledge that
pipeline needs.

The repository as of `58c6614` does not serve that goal:

- Canonical typed authority (`knowledge/sources|entities|facts`) holds zero records.
- All real content is the noncanonical intake queue: 329 annotations over 36
  devices, using 64 `kind` values, 302 distinct `parameter` names, 1018 distinct
  value keys, no unit on 71% of items, and prose conditions averaging 245
  characters. A program cannot query it; an AI can only read it as text.
- The content targets device-selection limits, while layout needs pin-to-pad maps,
  footprints, decoupling placement, current loops, net classes and fab limits.
  For example, the AO3400A numbered pin map is recorded as permanently unknown,
  which is the single fact a layout tool needs most.
- Process outweighs data: about 16.6k lines of Python, 270 KB of documents and a
  48 KB roadmap, a pilot harness that never ran, per-device demo evaluators, and a
  narrative review document per batch.

## Decision

1. **Consumer first.** Every record type and every collection task must serve a
   named consumer query (see [knowledge model v2](../knowledge-model-v2.md)) or
   a requirement of a [golden design](../golden-designs.md). Knowledge that serves
   neither is not collected.
2. **Closed world.** Generation may use only parts, packages, blocks and rules in
   the catalog. A missing or `UNKNOWN` input makes the generator refuse with a
   typed reason; it never improvises. This carries forward the existing "unknown is
   a result" principle into generation.
3. **Layered knowledge.** Generic engineering math is code (calculators). Package
   and footprint geometry, orderable parts with pin maps, reusable circuit blocks
   with layout constraints, class-level rules and fab profiles are typed records
   with a controlled vocabulary and SI-based units.
4. **One model, one write path.** The v2 records replace the v1
   Source/Entity/Fact families and the intake queue. The intake queue is frozen
   now, migrated selectively (only parts that the golden designs use), and then
   deleted with its toolchain. Nothing runs both models in parallel indefinitely.
5. **Git commit is the version.** Consumers pin a compiled bundle built from one
   validated commit. Per-record `APPROVED` immutability and `supersedes` chains are
   not carried into v2; a correction is an ordinary reviewed commit. Each record
   carries a `verification` level (`DRAFT`, `AGENT_VERIFIED`, `HUMAN_VERIFIED`)
   and every generated design reports the weakest level it relied on.
6. **Evidence stays, ceremony goes.** Source documents keep SHA-256 identity and
   the ignored local cache. Records cite a source and page; a bbox is optional.
   Each value states its basis: `DATASHEET`, `STANDARD_CONVENTION`,
   `ENGINEERING_DEFAULT` or `CALCULATED`. Automated validators and sampled human
   checks replace per-batch narrative review documents. Receipts belong in commit
   messages and one-line roadmap entries.
7. **Boundary with PcbAtlas.** PcbKnowledge owns knowledge, calculators, block
   expansion (block graph to netlist, BOM and constraint set) and the design-brief
   contract. PcbAtlas owns design synthesis orchestration, board state, placement,
   routing, DRC and fabrication output. PcbKnowledge never reads or mutates a live
   board; its expansion is a pure function over a pinned bundle.
   [ADR-025](ADR-025-derived-board-handoff.md) permits derived parked handoff
   projects and read-only checks over exported files, without transferring
   placement, routing or live-board ownership.
   [ADR-026](ADR-026-reference-layout-pipeline.md) subsequently permits a derived
   reference layout pipeline under `build/`, retaining the live-board boundary.

## Consequences

- The pilot harness, the per-device worked-example evaluators, the intake
  toolchain and the v1 approve/reject review closure are removed in stages listed
  in [`TODO.md`](../../TODO.md). Their retiring documentation was removed with the code; historical receipts
  remain in `docs/archive/` and Git.
- Reusable infrastructure stays: canonical JSON, deterministic IDs, the SHA-256
  evidence cache, workspace manifest and schema pinning, change-scope checks,
  repository locking, packaging, English and public-source guards, the loopback
  runtime and standard-library-only policy.
- Progress is measured by golden-design coverage (how much of a target BOM and
  its layout constraints resolve without `UNKNOWN`) and finally by a fabricated
  board that passes bring-up, not by annotation counts.
- An Agent may reach `AGENT_VERIFIED` without waiting for a human. Production use
  of a generated board still requires the owner to review the design report.
