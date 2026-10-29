# Stage-exit review checklist

An independent reviewer agent runs this list at every stage exit, after the full
gate passes and before the push. The reviewer is not the agent that wrote the
stage's code or records. Findings are fixed in the same stage; anything that
cannot be fixed becomes a `TODO.md` item. Record one summary line in the stage
receipt, for example `Review: 14 checks, 2 findings fixed (<commits>)`.

When a guard automates a check, delete the check here and name the guard in the
"Automated" list.

## Automated (do not repeat by hand)

- Full gate: English, public source, PDF.js vendor, workspace, Config, Build, Test,
  `v2 validate`, Package (`AGENTS.md` section 10).
- `test_v2_g1_acceptance`: G1 reference and preserved attempts reach A2.

## Evidence

1. Pick at least five cited values and two pin maps from records created or
   changed in this stage, weighted to ICs and connectors. Open the cached source at
   the cited page (`pdftotext -f N -l N -layout`) and compare the numbers, units,
   conditions and pin numbers. Record which values were checked.
2. Every part's package drawing comes from that part's own source or from a
   drawing that names its MPN or series. No drawing is borrowed from a similar part.
3. Two-terminal polarity cites a marking or drawing page; multi-terminal parts cite
   a numbered map (ADR-024).
4. `created_by` and `verified_by` are different agents, and neither is the
   orchestrator that assigned the work.
5. Every substitution or new design default has a D-number with a reason.

## Design

6. Every new record is used by some golden or corpus expansion. Nothing is kept
   "for later".
7. Checks were not weakened to pass: compare check counts, thresholds and test
   assertions with the previous stage. A removed or relaxed check needs an
   escalation answer from the owner.
8. Engineering defaults are plausible for the design (currents, distances,
   tolerances). Flag values chosen only because they make a check pass.
9. Evaluations can fail: a negative case exists for each new check, and synthesis
   attempts had no access to references, tests or other attempts.

## Code and documents

10. New code is ordinary readable Python: no compressed one-line blocks, functions
    under about 80 lines, no new third-party runtime dependency.
11. No string matching on prose fields; decisions use controlled values.
12. Commits: `[type]: description`, data separate from code and contracts, bodies
    hold the receipt without repeated disclaimers.
13. `TODO.md`, `README.md`, `architecture.md` and `knowledge-model-v2.md` match the
    code; completed temporary documents are deleted.
14. Any new public file is original work or small cited metadata; no copied
    third-party data.
