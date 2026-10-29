# Implementer brief, round 2

> Temporary. Delete this file at the Stage 2 exit (task 2e).

Copy everything below the line into the implementing agent's or engineer's task.

---

You are continuing PcbKnowledge after Stage 0 and Stage 1 (commits `bb55fe9`,
`ea622e0`, `6a69feb`). This round is **Stage 2** in `TODO.md`, tasks 2a to 2e.
ADR-023 (`docs/adr/ADR-023-design-intent-handoff.md`) is accepted; implement
against it.

## Read first

1. `AGENTS.md` (section 0 overrides older habits)
2. `TODO.md`: owner decisions D1 to D7, and the full Stage 2 section
3. `docs/knowledge-model-v2.md`, especially "Validation boundary"
4. `docs/adr/ADR-022-board-generation-knowledge.md` and ADR-023
5. `docs/golden-designs.md`, `evals/golden-designs/`, `knowledge/registry/`

## Review of the last round

The Stage 0 removal was clean and correct. Stage 1 shapes are usable and the
data/contract commit split was right. Four things must be corrected before
anything is built on top of them:

1. **`UNKNOWN` was used for design decisions.** The G1 brief has 9 `UNKNOWN`
   values and the reference graph has 4, for things like the USB current budget,
   the 3.3 V load budget, the crystal frequency and the I2C speed. Those are
   choices the brief author or the synthesizer makes, not evidence a datasheet must
   supply. With them, A1 ("no refusal") can never pass. Use the D7 values. Keep
   `UNKNOWN` for facts that must come from a cited source.
2. **Vocabulary exists twice.** Parameter names, units, condition keys, roles, pin
   types, package families and constraint kinds live in both the registries and the
   schema enums, kept equal by a test. Make the registries the only authority.
   Schemas check structure; the semantic validator checks registry membership.
3. **A test-only validator.** `tests/contract_schema.py` would become a second
   validator next to the Stage 2 runtime one. Promote it into the runtime package
   and use it from both places.
4. **Contracts are larger than one design needs.** About 4.2k lines of schema
   (754 for the brief alone) before any runtime exists. Cut every property that no
   G1 fixture, consumer query or ADR-023 field uses.

Also watch the prose. ADR-023, the model doc and the commit bodies drifted back
toward repeated disclaimers ("not a claim", "does not assert", "remains for").
State what something does and what is missing, once. Keep commit bodies to what
changed, why, and the verification receipt.

## Tasks, in order

- **2a** The four corrections above, plus their tests.
- **2b** `src/pcbknowledge/v2/`: loader, structural and semantic validators, and a
  read-only JSON CLI. Test against a temporary external Git workspace, including
  tamper cases. v1 keeps running during this step.
- **2c** One contract-only commit: corrected schemas move into `schemas/`, the
  workspace format is bumped, and the digest is pinned. Old v1 workspaces fail with
  a clear message.
- **2d** Data-only commits. The evidence cache in this checkout is empty, so
  re-download each G1 source from its recorded official URL and confirm the
  recorded SHA-256 (a mismatch is a new revision, never an override). Write v2
  `source` and `part` records with complete numbered pin maps for the G1 devices
  listed in `TODO.md`. Most pin maps are new extraction; intake has pins only for
  LD1117, INA219 and 24LC256. G1 needs a fixed 3.3 V LD1117 orderable; confirm it in
  the same document rather than reusing the adjustable record. A second agent
  re-checks every value and pin and records itself as the verifier.
- **2e** Hard cut. Delete v1, the intake toolchain, the review/decision UI and
  `docs/legacy/`. Keep the server shell, PDF.js and the evidence endpoint, and add
  minimal read-only v2 part and block pages per D5. Rewrite `.codex/skills/` for
  v2. Update `AGENTS.md` sections 6 and 7, `architecture.md` and `README.md`. Delete
  this file.

## Rules that matter most this round

- Exactly one model, one validator and one write path at the end of 2e. No
  compatibility aliases or "v1 still readable" paths.
- Never fill a value or pin from a similar part, package convention or memory.
  If the cited page does not show it, it is `UNKNOWN` with a reason.
- `HUMAN_VERIFIED` only when a person actually checked the values; no part has
  one yet. Delegated decisions follow AGENTS.md section 3: decide, record the
  delegation, continue.
- Data commits and contract commits stay separate (`change-scope` must not be
  `MIXED`).
- Push the `intake-final` tag only if the owner asks; otherwise mention it.
- If the plan conflicts with the code, write the disagreement and your alternative
  in the report instead of silently diverging.
- Repository writes: commit to `main` in coherent commits using
  `[type]: description`. Push only after the owner reviews, unless told otherwise.

## Report when you stop (at the Stage 2 exit or when blocked)

- Commits per task with hashes; lines removed and added; test count before and after.
- Gate commands with exit codes; any skip or failure.
- For each G1 part: source URL, SHA-256 match yes/no, pins extracted, verifier.
- Remaining `UNKNOWN` values in G1 and why each one needs evidence rather than a decision.
- Disagreements with the plan and what Stage 3 should start with.
