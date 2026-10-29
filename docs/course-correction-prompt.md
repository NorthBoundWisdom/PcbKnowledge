# Course-correction brief for implementers

> Temporary. Delete this file when Stage 1 in `TODO.md` is complete.

Copy everything below the line into the implementing agent's or engineer's task.

---

You are taking over implementation of PcbKnowledge, a Python standard-library
repository. The project direction changed on 2026-10-29. Your job is to execute
the remaining **Stage 0** items and then **Stage 1** in `TODO.md`, and to keep the
work from drifting back into the old pattern.

## Read first, in this order

1. `AGENTS.md` (rules; section 0 is new and overrides habits from earlier work)
2. `docs/adr/ADR-022-board-generation-knowledge.md` (why the direction changed)
3. `TODO.md` (stages, owner decisions with defaults, exit criteria)
4. `docs/knowledge-model-v2.md` (target model, consumer queries, API)
5. `docs/golden-designs.md` (targets G1 to G3, acceptance levels A1 to A6)
6. `docs/architecture.md` (what the current code is, and what is kept, replaced or removed)

## The goal in one paragraph

A design package (for example a simple hardware-competition brief) should become
a manufacturable board. PcbKnowledge supplies a closed-world catalog of parts,
footprints, reusable circuit blocks with layout constraints, class-level rules,
fab profiles and calculators, and a pure `expand` step that turns a block graph
into a design intent (netlist, BOM, constraints). PcbAtlas, a separate repository
you must not modify, does placement, routing, DRC and fabrication output. The
first target is golden design G1, a small USB-powered sensor-logger board.

## What went wrong before (do not repeat)

- **Data nobody could query.** 329 annotations used 302 distinct parameter names,
  1018 value keys and prose conditions, with no unit on 71% of items. Every value
  you add from now on uses registry names, canonical units and structured
  conditions, or it does not get added.
- **Collecting what the consumer does not need.** Work went into device-selection
  limits while layout needs pin-to-pad maps, footprints, decoupling placement,
  current loops and fab limits. Before adding anything, name the consumer query
  (Q1 to Q12 in the model doc) or golden-design requirement it serves.
- **Process instead of product.** A pilot harness that never ran, per-device demo
  evaluators, one narrative review document per batch, dated acknowledgement
  documents, receipts copied across README, TODO and docs, and commit titles like
  "without hardware claims". Do not create receipt documents. Put verification in
  commit bodies and one-line TODO receipts.
- **Defensive prose.** Repeated "not a certification / bounded / no claim of"
  wording. A typed `UNKNOWN` or a refusal reason says this once, in data.
- **Two models in parallel.** A typed canonical store with zero records next to a
  noncanonical queue holding all the content. There will be one model (v2), and
  the old ones are deleted, not kept as a compatibility layer.
- **Tests that pin document bytes.** Replay tests hashed review Markdown files.
  Test behavior and data contracts, not prose.

## Your tasks

1. Finish Stage 0: freeze intake, delete the pilot harness, the per-device
   evaluators and the intake handoff tool with all their tests, docs, CLI wiring and
   CI steps, as listed in `TODO.md`. Run the full gate and record the new test
   count. Use a hard cut; do not leave stubs or compatibility aliases.
2. Do Stage 1: the brief schema and G1 to G3 briefs, the hand-made G1 block graph,
   the v2 record and registry JSON Schemas limited to G1 needs, and the block-graph
   and design-intent schemas. Draft ADR-023 for the PcbAtlas handoff using the D3
   and D4 defaults, marked `Proposed`, for the owner to accept.
3. Stop at the Stage 1 exit and report. Do not start Stage 2 without the owner.

Owner decisions D1 to D6 in `TODO.md` have defaults. Use the defaults. Do not
stop to ask unless a default is impossible to apply.

## How to work

- Keep the invariants: SHA-256 source identity, originals only in the ignored
  cache, license gates, explicit workspace selection, pinned schemas, loopback-only
  standard-library runtime, separate data and contract commits, unknown is a
  result, no fabricated human verifier.
- Prefer deleting over keeping. Git history is the archive.
- Keep schemas small: only what G1 needs. A registry name, layout-constraint kind
  or calculator is added when a G1 block uses it, not in anticipation.
- If you find that the plan conflicts with the code or is wrong, do not silently
  diverge. Write the disagreement and your proposed alternative in your report.
- Repository writes: commit to `main` in coherent stage commits using the
  `[type]: description` format. Do not push until the owner has reviewed, unless the
  owner tells you otherwise.

## Report when you stop

- What changed, by stage item, with commit hashes.
- Lines of code and tests removed and added; new test count.
- Exact gate commands and exit codes; any skip or failure.
- Disagreements with the plan, open questions, and what Stage 2 should start with.
