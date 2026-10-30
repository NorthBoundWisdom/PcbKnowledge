# Stage-exit review checklist

An independent reviewer agent runs this list at every stage exit, after the full
gate passes and before the push. The reviewer is not the agent that wrote the
stage's code or records. Findings are fixed in the same stage; anything that
cannot be fixed becomes a `TODO.md` item. Record one summary line in the stage
receipt, for example `Review: 13 checks, 2 findings fixed (<commits>)`.

When a guard automates a check, delete the check here and name the guard in the
"Automated" list.

## Automated (do not repeat by hand)

- Full gate: commit range, code style, English, public source, PDF.js vendor, workspace, Config, Build, Test,
  `v2 validate`, Package (`AGENTS.md` section 10).
- `test_v2_g1_acceptance` and synthesis evaluation tests: G1 reference and preserved attempts reach A2.
- `check_commits.py`: subject type/format and knowledge-only data commits for the introduced range.
- `check_code_style.py`: 120-character lines, one statement per line, functions at most 80 physical lines; no Stage 6c allowances.
- `v2 audit` through `v2 validate` and bundle compilation: parts, packages and sources are reachable from design graphs. This does not establish electrical acceptance.

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

6. New blocks, rules and fab profiles serve an actual golden or corpus design;
   automated part/package/source reachability is not a license for unused abstractions.
7. Checks were not weakened to pass: compare check counts, thresholds and test
   assertions with the previous stage. A removed or relaxed check needs an
   escalation answer from the owner.
8. Engineering defaults are plausible for the design (currents, distances,
   tolerances). Flag values chosen only because they make a check pass.
9. Evaluations can fail: a negative case exists for each new check, and synthesis
   attempts had no access to references, tests or other attempts.

## Code and documents

10. New code has cohesive responsibilities and explicit dependencies; mechanical
    formatting is automated. No unapproved third-party runtime dependency.
11. No string matching on prose fields; decisions use controlled values.
    Decision entries and notes state the decision and its reason once, without
    "not a guarantee/certification/recommendation" clauses.
12. No design carries an essential `UNKNOWN` that a different eligible part
    would resolve (D38); no source was stopped for website terms alone.
13. `TODO.md`, `README.md`, `architecture.md` and `knowledge-model-v2.md` match the
    code; completed temporary documents are deleted.
14. Any new public file is original work or small cited metadata; no copied
    third-party data.
