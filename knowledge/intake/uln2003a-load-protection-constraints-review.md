# ULN2003ADR application-constraint collection receipt

Current review status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**; see the
[dated independent acceptance](#independent-agent-review-accepted-2026-10-28-utc)
below. The preceding collector sections are historical draft-stage receipts,
not the current review state. Integration/publication gates remain separate.

## Historical collector draft and ownership

Issue #15; base `9530c0d66d497e284a5887b37a5558d22aa8a9c0`.
Collector: `agent:/root/curate_pcbknowledge_constraints/collect_uln2003a_constraints`.
Collected 2026-10-28 UTC. Historical acceptance at collection was **DRAFT**,
pending a different Agent's source review at that time. This is not human review, canonical approval, protection sign-off,
or a complete thermal design. Only this receipt and its companion JSON are owned.

Eight annotations `uln2003a-app-01` through `uln2003a-app-08` answer the scoped
questions without a record quota. Four batch-local source issues preserve unknown
load, drive, curve applicability and protection conditions. Existing
`b004-ti-uln2003a-01` through `-07` are referenced, not modified or duplicated as
new pin/COM/saturation facts.

## Evidence actually inspected

Official URL: https://www.ti.com/lit/ds/symlink/uln2003a.pdf . Fresh acquisition
succeeded on 2026-10-28; 1,850,862 bytes, SHA-256
`ba83a908675b45c41e84fb06ea390efb10f4b7a358edfee656f87a968dd1d62f`.
Actual bytes match the earlier receipt, rather than assuming URL equality.
Electrical revision is SLRS027T, March 2025. The packaging addendum is separately
dated 18 September 2026. Its first page (PDF page 23) identifies ULN2003ADR as
SOIC (D), 16 pins, -40 to 70 C; AI/ULN2004A/DYY rows are not substitutes.

Original is local-only at
`.pcbknowledge/evidence/sha256/ba/ba83a908675b45c41e84fb06ea390efb10f4b7a358edfee656f87a968dd1d62f.pdf`.
No PDF, full text, page render or third-party original belongs in Git or packages.
Redistribution license is not asserted; this is the owner-authorized noncanonical
factual-curation lane, not canonical processing clearance. No supplemental source
was added; SPRA953 is cited by TI but was not consulted here.

Collector inspected extracted text and actual rendered PDF pages 4, 5, 6, 10, 15,
16, 17, 19 and 23. Page numbers are one-based PDF pages; electrical printed labels
coincide, while page 23 is Addendum-Page 1. No precise bbox was measured. Local
renders/text under `.pcbknowledge/uln-review/` are ignored review aids. Render
commands exited 0 despite a font-cache warning; the resulting pages were actually
viewed, not presumed valid from command success.

- Pages 4-6: D-package thermal column, stress versus operation, correct ULN2003A
  electrical columns and 25 C drive/clamp conditions.
- Page 10: Figure 5-4 is D package at 70 C, N=1..7 and duty 0..100%, under Typical
  Characteristics. No numeric curve values were digitized or promoted to guarantees.
- Pages 15-17: inductive current path, example versus specification distinction,
  load/drive dependence and simultaneous-channel thermal calculation context.
- Page 19: excessive output-to-COM forward current warning.
- Page 23: exact orderable/package identity and separate appendix date.

## Replayable candidate queries

Run from the repository root. Each command below exited 0 during collection.
These are candidate-retrieval checks, not electrical answers. Every selected fact
preserves all four batch-local warnings, `canonical: false`, DRAFT and
`NOT_LOCALLY_VERIFIED`; that reader marker does not claim it rehashed local bytes.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --parameter simultaneous_channel_duty
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --parameter continuous_load_thermal_budget
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --parameter controller_input_current
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --parameter inductive_clamp_connection_limits
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id uln2003a-app-ti-slrs027t-d
```

Expected fact IDs respectively: `uln2003a-app-01`, `-02`, `-04`, `-06`.
Expected warning IDs: `uln2003a-app-load-unknown`, `-drive-unknown`, `-curve-scope`,
`-protection-unknown`. Warning lookup is filter-only so wording cannot hide it.

1. "Can all channels drive the proposed load continuously at this ambient?"
   Retrieve `-01`, `-02`, and warnings. N, duty, D package and 70 C curve condition
   remain explicit. Proposed load/ambient/board are absent; answer remains UNKNOWN.
   `-05` labels seven-channel/100% table entries as example inputs, not entitlement.
2. "Does the controller meet the selected load's ON/saturation conditions?"
   Retrieve `-04` and referenced old `-05/-06/-07` records. Input current at 3.85 V
   and 25 C is not a controller guarantee; ON-state voltage is a maximum required
   characteristic, not maximum allowed VI. Page 4's 30 V input stress limit must
   not be confused with that requirement. No actual controller evidence was supplied.
3. "Does COM connection establish inductive-load protection?"
   Retrieve `-06`, `-07`, `-08` and warnings. Current path and clamp limits are
   documented; coil energy, repetition, supply absorption and faults remain unknown.

## Negative and semantic checks

The following exact selections exited 0 with empty lists. Zero matches are not
proof of electrical permission or lack of ambiguity.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --manufacturer STMicroelectronics
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --device ULN2004A
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --device ULN2003AI
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id uln2003a-app-ti-slrs027t-d --package 'DYY, 16-pin SOT'
```

Semantic exclusions are retained in the selected records, not implemented as a new
answer engine: `-01` forbids one-channel-to-seven transfer and typical-to-guaranteed
promotion; its 70 C curve cannot become another-temperature envelope. `-04` retains
25 C and VI=3.85 V, and does not transfer AI conditions. `-05` is application-example
input, not a thermal qualification. `-02` distinguishes less-than-125 C application
target from the 150 C stress ceiling. `-07/-08` do not authorize repetitive energy.
A changed duty/temperature/controller/load requires separate evidence, not a search hit.

## Checks and integration dependency

Collector replay assertions covered four positive exact selections (including all
four attached warnings), four identity negatives and all-warning lookup: 9 passed.
`python3 configs/check_english_repo.py` and `python3 configs/check_public_repo.py`
exited 0. They do not replace independent source review; untracked additions must
also be checked after authorized staging by the integrator.

The first attempted unittest command lacked `PYTHONPATH=src` and reported one
import error (23 tests attempted); it is not a pass. Corrected focused result is
recorded below. Full repository validation/package/CI are not claimed at collection.
The current pinned 100-record manifest deliberately excludes new batches; its
aggregate failure must be resolved by maintainer-owned coherent integration, not
by weakening this batch or editing shared manifests independently.

## Independent review handoff

Review actual cached bytes and pages, all eight final records and four warnings.
In particular check N/duty interpretation, Table 8-1's non-guarantee, the page 6
ULN2003A versus AI/2004 column boundary, and clamp stress versus energy scope.
Verify all conditions and old-record links, source hash/orderable identity, replay
IDs and exclusions. Record corrections and actual reviewer provenance before
changing DRAFT; append review history rather than erase collection limitations.
No publication or maintainer acceptance is claimed by this draft.

Corrected collector command:
`PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`
exited 0: 31 tests passed, zero skips. The pinned command
`python3 configs/pcbknowledge_intake_eval.py --repo . --cases evals/intake-retrieval-100.json`
exited 2 with `dataset bytes or batch set changed; review cases before updating pins`.
This expected integration dependency is not a passing aggregate gate.

Independent-review correction requested and applied before acceptance: explicitly
separated the exact ULN2003ADR -40..70 C ambient scope (pages 4/23) from junction
limits in the thermal candidate, and renamed GPIO example values as discrete
3.3 V or 5 V options rather than an interval. Reviewer reinspection is pending.


## Independent Agent review accepted (2026-10-28 UTC)

This dated successor section supersedes the earlier pending-review handoff, not its
collection history. Reviewer: `agent:/root/curate_pcbknowledge_constraints/review_constraint_batches`, separate from collector.
Authority: OWNER_DELEGATION. Status: AGENT_REVIEWED_UNDER_OWNER_DELEGATION.
`human_reviewed: false` and `canonical: false` remain unchanged. The owner receipt
at main `2181df9` covers only the previous 100 annotations, not this new batch.

The reviewer independently recomputed each source SHA-256 and byte size from the
actual ignored cache and inspected actual cited page renders, not just extracted
text or the collector's summary. Item-specific coverage: Pages 4 (app-02 ambient/junction and app-08 stress), 5 (app-03 package thermal metric), 6 (app-04/07 electrical columns), 10 (app-01 D-package curve), 15-17 (app-01/02/05/06 example, simultaneous channels and dissipation), 19 (app-06 supply and diode cautions), 23 (exact ULN2003ADR identity/ambient).

Verified corrections: exact orderable ambient -40..70 C is distinct from junction temperature, and app-05 GPIO values are discrete 3.3 V or 5 V examples. D-package N=1..7 duty curve remains nonnumeric typical guidance, not all-channel continuous-load permission. Clamp current/voltage does not qualify energy or repetition.

Review input SHA-256: `3a06ba40d763c5219303850223951572b581ceb0fb1c0257c435cd8556230d24`.
Reviewed JSON SHA-256: `99eaf2121d91a0fd11e7f4b19d8d5893890885edace26a62dd0bcaece18cff20`.
Review time: `2026-10-28T02:22:52.549320+00:00`.

Independent CLI replay after status update: 12 cases, exit 0. For EVERY fact,
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id SOURCE --parameter PARAMETER`
selected exactly its ID and preserved the complete fact, conditions, source, all
source-local warnings, noncanonical status and NOT_LOCALLY_VERIFIED marker.
`intake issues --source-id SOURCE` returned exactly all corresponding warning IDs.
Each source was tested with wrong manufacturer/device/package filters: empty.
The 4 concrete negative commands in the collector receipt above were also rerun
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
`dc6bdb0cd00711a4da1cf2b8142ec5557a53503648e2ea5d908c2e3917a7d733`. Append-only JSON review history identifies the prior bytes.
The independent reviewer reran all 41 full-payload CLI cases across the three
batches after correction: exit 0. Complete warnings, source/fact payloads and
NOT_LOCALLY_VERIFIED/noncanonical markers were preserved.
`PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`
exited 0: 44 tests, zero skips (28.331 seconds), including the maintainer's
source-disposition extension. Aggregate 125 integration/CI is a separate receipt.
