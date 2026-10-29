# Implementer brief, round 3

> Temporary. Replace this file at the start of each round; delete it when no round is active.

Copy everything below the line into the implementing agent's or engineer's task.

---

You are continuing PcbKnowledge. Stages 0 to 2 are complete: one v2 model, one
validator, one write path, a read-only catalog server, and three verified G1 ICs.
This is a **long round**: Stages 3, 4 and 5 in `TODO.md`, ending with golden
design G1 at acceptance level A2 from an AI-produced block graph. The architecture
is stable; spend this round on breadth of working capability, not on new
infrastructure.

## Read first

1. `AGENTS.md`, especially section 3 ("Long rounds", "Owner delegation") and
   section 7 (terminal numbering, package geometry)
2. `TODO.md`: owner decisions D1 to D12, "Round 3 scope", and Stages 3 to 5
3. `docs/adr/ADR-024-terminals-packages-selection.md` (new; decided this round)
4. `docs/adr/ADR-023-design-intent-handoff.md` and `docs/knowledge-model-v2.md`
5. `docs/golden-designs.md`, `evals/golden-designs/g1.*.json`

## Review of the last round

Stage 2 was well executed: about 97.8k lines removed, one model and validator,
strong tamper tests, a safe read-only server, and source hashes that match. Three
things are corrected by ADR-024 and are now TODO items:

1. **Two-terminal parts were blocked** for lacking a numbered terminal table, which
   their datasheets never print. They now use convention numbering with cited
   polarity. Parts with more than two terminals still need a cited numbered map.
2. **Packages stored placeholder pads as authority** (35 `UNKNOWN` fields per
   record, SOT-223 without its tab). Standard packages now store cited drawing
   dimensions; pads are derived by generators. Only irregular parts store pads.
3. **Selection matching ignored ranges.** A nominal request must match `value` or
   `typ`; min/max requests compare guaranteed bounds.

Two smaller notes: `catalog.py` and `server.py` compress many statements onto one
line (`if ...:return ...`); write new code in ordinary readable Python. The v2 code
still imports workspace and policy helpers from `pcbknowledge.git_native`; leave the
name alone this round unless a move is trivial.

## Order of work

Follow `TODO.md` 3a to 5d. At each **stage exit**: run the full gate, record a
one-to-three-line receipt in `TODO.md`, commit, push, and continue to the next
stage without waiting.

- **Stage 3**: contract-only commit for the package schema; generators with
  hand-checked dimension tests; re-record the three packages from their drawings;
  KiCad footprint export.
- **Stage 4**: selection semantics and the `v2 coverage` tool first, then parts,
  calculators, blocks, rules and the fab profile. Run `v2 coverage` on the G1
  reference graph often; it is the progress meter for this stage.
- **Stage 5**: bundle, `expand` with A2 checks, KiCad netlist export, the
  synthesis skill and its three-attempt evaluation.

## Decisions are made, not asked

- Use the owner-decision defaults D1 to D12. If you need a new decision, choose a
  sensible default, add it to the table as the next D-number with a one-line
  reason, and continue.
- If an official source is inaccessible, substitute an equivalent part per D10 and
  record the failed URL in the commit body.
- If `ldo_headroom` fails for LD1117S33TR under D9, keep the check and switch the
  LDO block to a lower-dropout part; record it as a decision.
- Stop only for an owner-only item, a blocker that no default or substitution
  resolves, or a gate failure you cannot fix. Report what you finished before
  stopping.

## Rules that matter most this round

- Never fill a value or a multi-terminal pin map from a similar part, a package
  convention or memory. Cite the page, or record `UNKNOWN` with a reason.
- Design inputs are decisions with `ENGINEERING_DEFAULT`, never `UNKNOWN`.
- Every part, package, block, rule and fab profile reaches `AGENT_VERIFIED` only
  after a second, independent agent rechecks every cited value and pin.
- Do not read IPC documents (ADR-015). Footprint rules and the trace-width equation
  are written as original code with named constants.
- Data commits and contract or code commits stay separate (`change-scope` must not
  be `MIXED`).
- Keep commit bodies short: what changed, why, and the verification receipt.
  No repeated disclaimers anywhere.

## Repository writes

Commit to `main` in coherent commits using `[type]: description`. At each stage
exit, after the full gate passes: `git fetch`, rebase onto `origin/main` if it
moved, rerun the affected tests, and push. Never force-push. Wait for CI on the
pushed commit and fix any failure in the same stage.

## Report when the round ends or stops

- Commits per TODO item with hashes; lines added and removed; test count per stage.
- Gate commands with exit codes per stage exit, and CI results for pushed commits.
- `v2 coverage` summary for G1 at each stage exit.
- Parts added: MPN, source URL, SHA-256 match, numbering basis, verifier.
- New D-numbers you created and every substitution.
- `expand` result for the reference graph and the three synthesis attempts.
- Disagreements with the plan and what Stage 6 (PcbAtlas integration) needs first.
