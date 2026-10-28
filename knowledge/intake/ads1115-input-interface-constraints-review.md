# ADS1115 application constraints: collection and review receipt

Current review status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**; see the
[dated independent acceptance](#independent-agent-review-accepted-2026-10-28-utc)
below. The preceding collector sections are historical draft-stage receipts,
not the current review state. Integration/publication gates remain separate.

## Historical collector draft and ownership

Issue: https://github.com/NorthBoundWisdom/PcbKnowledge/issues/14

Base: `9530c0d66d497e284a5887b37a5558d22aa8a9c0`.
Collector: `agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints`.
Collected on 2026-10-28 UTC. At collection, the adjacent JSON was DRAFT;
independent review, coordinated evaluation integration, publication and CI were
not yet claimed. The nine annotations answer distinct scoped questions rather
than a target record count. The existing seven ADS1115 annotations are unchanged.

## Actual evidence

Fresh official download: https://www.ti.com/lit/ds/symlink/ads1115.pdf .
SHA-256: `eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834`.
Byte count: 2654255. PDF pages: 57. Electrical revision: SBAS444E, December 2024.
Packaging addendum: 14-Oct-2025, distinct from electrical revision. Fresh bytes
match the previous `ti-ads1115-e` receipt; URL equality was not used as proof.
Actual original is local-only under
`.pcbknowledge/evidence/sha256/ee/eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834.pdf`.
No original, extracted page text or rendered image belongs in Git or a package.

Collector inspected text and actual rendered PDF pages 4, 5, 6, 14, 15, 18, 20,
28, 29, 31, 37 and 42. One-based PDF and printed page numbers agree until the
addendum; PDF page 42 is Addendum-Page 1. Its orderable row establishes
ADS1115IDGSR, VSSOP DGS, 10 pins; other family members and package/orderable
suffixes are not selected. No precise bbox was measured. These are collector
checks, not independent review or canonical source-processing authorization.

## What the candidates preserve

- `ads1115-app-01/02`: differential scaling versus single-ended operation;
  referenced existing pin operating limits remain distinct from stress limits.
- `ads1115-app-03`: the 6 Mohm common-mode and 4.9 Mohm differential values are
  typical at the specified PGA/supply/rate/temperature, not guaranteed bounds.
- `ads1115-app-04/05`: one-cycle converter settling is not external-network
  settling; an in-flight continuous result retains the previous configuration.
  Actual data-rate variation and approximate single-shot wake-up remain visible.
- `ads1115-app-06/07/08`: controller voltage, sink/load and timing checks cannot
  be replaced by a nominal bus frequency or the typical pull-up example.
  The fast-mode table is not transferred to high-speed mode.
- `ads1115-app-09`: supply bypass placement and approximate startup guidance.

The three same-source batch-local issues retain missing sensor/error-budget,
controller/bus and input-trajectory information. No RC values, allowed universal
sensor impedance, level-shifter choice or board accuracy guarantee is invented.

## Replay commands and expected selections

Run from the repository root. All commands below use the real read-only CLI;
results are candidates, not synthesized answers. They retain `canonical: false`,
DRAFT acceptance and reader `NOT_LOCALLY_VERIFIED` even though the collector
checked local bytes. Every selected candidate includes all three batch warnings.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter PGA_full_scale
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter single_ended_range
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter input_loading
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter conversion_settling
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter configuration_change
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter digital_interface_voltage
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter I2C_fast_mode_timing
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter I2C_pullup_selection
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --parameter decoupling_and_startup
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id ads1115-app-ti-e-dgs
```

The nine searches select `ads1115-app-01` through `ads1115-app-09`, respectively,
with original conditions/evidence unchanged. The warning lookup returns, in order,
`ads1115-app-controller-uncertainty`, `ads1115-app-range-uncertainty`,
`ads1115-app-sensor-uncertainty`. They remain `SOURCE_ISSUE`, not Facts.

For the above-supply question, replay the PGA and single-ended selections plus
`--source-id ti-ads1115-e --parameter analog_input_pin_voltage` to reference
`b003-ti-ads1115-e-07` without duplicating it. The stress discussion on page 4
is not permission to operate above the recommended pin range. For high-impedance
sensor/channel-change questions, replay loading, settling and configuration-change
plus all warnings; requested mode/rate and external dynamics still must be known.
For controller compatibility, replay voltage, timing, pull-up and startup plus
warnings; compatibility remains unestablished without controller and bus evidence.

Each following search must return an empty candidate list, not a fallback:

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --device ADS1015
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --device ADS1114
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --device ADS1115IDGST
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --manufacturer STMicroelectronics
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --package 'RUG, 10-pin X2QFN'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --kind absolute_maximum
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --kind guaranteed_source_impedance
```

The last two are semantic negatives for this new batch, not proof that the source
has no stress specification. Typical loading cannot become a guaranteed bound;
a different PGA/rate/temperature does not inherit its stated typical values.
The CLI does not solve such applicability questions: callers must inspect retained
conditions. Empty results do not establish electrical permission or no ambiguity.

## Actual collector checks

- All nine parameter searches, warning retrieval and seven negative filters:
  exit 0; exact IDs and full source/fact/warning payload equality checked.
- `PYTHONPATH=src:. python3 -m unittest discover -s tests/git_native -p 'test_intake*.py'`:
  exit 0, 31 tests, no skips. An earlier invocation without PYTHONPATH failed
  module import; this was a test invocation error, not a passing run.
- `python3 configs/check_english_repo.py`: exit 0.
- `python3 configs/check_public_repo.py`: exit 0 for its tracked/index scope;
  new files must be checked again when staged for coordinated publication.
- `python3 configs/pcbknowledge_agent.py --repo . validate`: exit 0,
  metadata closure VALID; no canonical records. Concurrent draft batches may
  change the displayed intake count, not this batch's scope.
- `python3 configs/pcbknowledge_intake_eval.py --repo . --cases evals/intake-retrieval-100.json`:
  exit 2, expected changed-batch-set failure. This is NOT full-gate success.
  Do not change or weaken the fixed manifest here; maintainer integration is
  required before publication as stated in issue comment 6458747252.

Collector correction before handoff: independent reviewer requested explicit
VDD=3.3 V and FSR=+/-2.048 V conditions for the data-rate tolerance;
`ads1115-app-04` now carries them. A first payload-comparison probe incorrectly
expected original warning-array order; CLI sorts warnings by ID. The corrected
order-insensitive full-warning comparison passed for all nine candidates.

## Independent-review handoff

Inspect the actual cached PDF, not only these annotations. Check table columns,
units and header conditions on pages 4-6; PGA and switched-capacitor semantics on
14-15; mode transition on 18; high-speed distinction on 20; typical application
scope on 28-31; power guidance on 37; exact orderable row on 42. Report corrections
and item-specific limitations, actual actor/time, reviewed artifact digest/SHA,
commands/exit codes and publication/CI status. Until then leave DRAFT unchanged.


## Independent Agent review accepted (2026-10-28 UTC)

This dated successor section supersedes the earlier pending-review handoff, not its
collection history. Reviewer: `agent:/root/curate_pcbknowledge_constraints/review_constraint_batches`, separate from collector.
Authority: OWNER_DELEGATION. Status: AGENT_REVIEWED_UNDER_OWNER_DELEGATION.
`human_reviewed: false` and `canonical: false` remain unchanged. The owner receipt
at main `2181df9` covers only the previous 100 annotations, not this new batch.

The reviewer independently recomputed each source SHA-256 and byte size from the
actual ignored cache and inspected actual cited page renders, not just extracted
text or the collector's summary. Item-specific coverage: Pages 4 (app-01/02 rail distinction), 5 (app-03/04/06 header, typical impedance and electrical columns), 6 (app-07 timing), 14-15 (app-01/03 input structure/PGA), 18 (app-04/05 conversion modes), 20 (app-07 fast versus high speed), 28-29/31 (app-02/08 examples and pullups), 37 (app-09 startup/decoupling), 42 (exact orderable).

Verified correction to app-04: explicit VDD=3.3 V and FSR=+/-2.048 V table header conditions. The 6/4.9 Mohm quantities remain typical, not source-impedance guarantees; external settling and unspecified controller compatibility remain unresolved.

Review input SHA-256: `e77fff47a30927cc93002b70a280cdde8c06cdcfe3eca156835afff92b100099`.
Reviewed JSON SHA-256: `3061dc9993bbe80b018605a09e9d2a61bf2cf2968ec7319b7539994a5cb27b10`.
Review time: `2026-10-28T02:22:52.549320+00:00`.

Independent CLI replay after status update: 13 cases, exit 0. For EVERY fact,
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id SOURCE --parameter PARAMETER`
selected exactly its ID and preserved the complete fact, conditions, source, all
source-local warnings, noncanonical status and NOT_LOCALLY_VERIFIED marker.
`intake issues --source-id SOURCE` returned exactly all corresponding warning IDs.
Each source was tested with wrong manufacturer/device/package filters: empty.
The 7 concrete negative commands in the collector receipt above were also rerun
independently, each exit 0 and empty result. These are retrieval exclusions, not
a new electrical-answer engine; semantic safety exclusions were checked against
the source and retained in the selected annotations.

`PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`:
exit 0, 31 tests, zero skips (7.108 seconds), independently rerun with all three
reviewed batches. `python3 configs/pcbknowledge_intake_eval.py --repo . --cases evals/intake-retrieval-100.json`:
exit 2, changed-batch-set refusal. This remains an unresolved integration gate,
NOT a pass. The initial reviewer helper assumed one cache-path field across all
batches and stopped with KeyError before any file edit; corrected to use the
SHA-addressed cache layout, then all four source byte checks succeeded.

No source originals, text extracts or renders are part of this deliverable. No
precise bounding boxes, latest-revision guarantee, human verification or complete
circuit-safety qualification is claimed. The separate coordinator owns staged
public guards, package validation, coherent maintainer integration, final commit,
remote verification and CI; none is claimed completed by this review.


## Maintainer metadata correction (2026-10-28 UTC)

Addressed [review comment 6459117069](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/13#issuecomment-6459117069).
Current limitations no longer incorrectly say independent acceptance is pending.
For ADS, all three warning evidence methods now identify the completed separate
Agent inspection. Historical DRAFT entries remain unchanged. Numerical facts,
source evidence limitations and unresolved engineering inputs were not changed.
Correction actor: `agent:/root/curate_pcbknowledge_constraints/review_constraint_batches`.

This supersedes the earlier reviewed JSON digest only; current JSON SHA-256 is
`746353eeab5df619970c2cc2767a440b7fe92e5914fa42577208fdb9e233b5e7`. Append-only JSON review history identifies the prior bytes.
The independent reviewer reran all 41 full-payload CLI cases across the three
batches after correction: exit 0. Complete warnings, source/fact payloads and
NOT_LOCALLY_VERIFIED/noncanonical markers were preserved.
`PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`
exited 0: 44 tests, zero skips (28.331 seconds), including the maintainer's
source-disposition extension. Aggregate 125 integration/CI is a separate receipt.
