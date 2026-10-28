# LDO application constraints: collection and independent-review receipt

Current review status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**; see the
[dated independent acceptance](#independent-agent-review-accepted-2026-10-28-utc)
below. The preceding collector sections are historical draft-stage receipts,
not the current review state. Integration/publication gates remain separate.

Issue: https://github.com/NorthBoundWisdom/PcbKnowledge/issues/13

Base: `9530c0d66d497e284a5887b37a5558d22aa8a9c0`. Collector: `agent:/root/curate_pcbknowledge_constraints/collect_ldo_constraints`, 2026-10-28 UTC. Historical collection state: **DRAFT**, with independent review not yet recorded at that time. No human approval, canonical publication or engineering sign-off is claimed.

## Evidence and scope

The two official PDFs were downloaded on 2026-10-28. Recomputed actual byte identities match the older receipts; no detected byte or electrical-revision drift. New source IDs identify this application scope without overwriting old receipts.

- `ldo-app-ti-lm1117-q`: Texas Instruments LM1117, adjustable; standard temperature; not LM1117I or fixed output, DCY, SOT-223; SNOS412Q (2023-01). [Official document](https://www.ti.com/lit/ds/symlink/lm1117.pdf). SHA-256 `c117f5dd97fd15e62c0dee3adbf1af60480a128a10a0f9a9c28aafb8220ec3aa`, 2920491 bytes, 47 pages. Original retained only at ignored `.pcbknowledge/evidence/sha256/c1/c117f5dd97fd15e62c0dee3adbf1af60480a128a10a0f9a9c28aafb8220ec3aa.pdf`. Collector visually inspected PDF pages 3, 6, 14, 15, 18, 19; zero-based locators are in JSON. No bbox measured.
- `ldo-app-st-ld1117-r38`: STMicroelectronics LD1117STR, adjustable; standard temperature; not C grade or fixed output, SOT-223; DocID2572 Rev 38 (2025-01-27). [Official document](https://www.st.com/resource/en/datasheet/ld1117.pdf). SHA-256 `4fd8415a20d932fdc1de5be99e1aa5d2af1546f05c0a785a047ff93420364348`, 1634512 bytes, 46 pages. Original retained only at ignored `.pcbknowledge/evidence/sha256/4f/4fd8415a20d932fdc1de5be99e1aa5d2af1546f05c0a785a047ff93420364348.pdf`. Collector visually inspected PDF pages 1, 7, 14, 24, 44; zero-based locators are in JSON. No bbox measured.

TI full orderable is intentionally unknown; the family/adjustable/DCY lane is not procurement identification. TI electrical revision is January 2023; the package-option addendum text is June 8, 2026 and package-material appendix text August 10, 2026. Those appendix dates are not an electrical revision. ST electrical revision date is confirmed in the revision-history text (page 45); the actual LD1117STR/SOT-223 row was visually inspected on page 44. Review-grade visual claims are item-specific. Text and page renders remain ignored local derivatives, never publication artifacts.

Public-reference access is not an open license. This pair contains original factual paraphrases and metadata only, not raw source copies or canonical Source processing authorization.

## Draft contents and review questions

Eight candidate annotations: `ldo-app-ti-01` through `ldo-app-ti-04`, and `ldo-app-st-01` through `ldo-app-st-04`. Four batch-local warnings: `ldo-app-ti-orderable-capacitor-gap`, `ldo-app-ti-operating-point-gap`, `ldo-app-st-capacitor-gap`, `ldo-app-st-operating-point-gap`.

- Capacitor query: separately inspect TI guidance/ESR and ST example/minimum semantics. ST numeric ESR/ceramic qualification remains unknown. Nominal capacitance equality does not establish interchangeability.
- Dropout/load query: inspect current and temperature columns, typical versus maximum, and TI footnote's dropout criterion. Do not transfer a fixed variant, C/I grade, or another manufacturer's limits.
- Current/thermal query: confirm TI current limit is not a continuous thermal entitlement. ST labels its characteristic Output current, not Current limit; preserve the source label. Actual load, headroom, board, airflow and ambient evidence is absent.
- Thermal review: TI copper-area figures are design aids; ST Table 2 does not supply board/airflow conditions. Do not make the Table 1 stress power rating or a table thermal metric into a board-safe current answer.

Existing pin/stress/junction records are referenced by prior batch/source IDs, not copied or modified. Warnings are local to this new batch, so both positive candidates and filter-only warning retrieval preserve them.

## Replayed CLI selections

Commands below ran from the repository root on 2026-10-28 with exit 0. Every candidate preserved its complete conditions, both same-source warnings, DRAFT, canonical false and NOT_LOCALLY_VERIFIED. These are retrieval receipts, not synthesized electrical answers.

`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter capacitor_requirements` -> ldo-app-ti-01; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter capacitor_requirements` -> ldo-app-st-01; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter dropout` -> ldo-app-ti-02; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter dropout` -> ldo-app-st-02; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter thermal_budget` -> ldo-app-ti-04; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter thermal_budget` -> ldo-app-st-04; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --manufacturer STMicroelectronics` -> []; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --device LM1117-3.3` -> []; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --device LM1117IMP-ADJ/NOPB` -> []; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --device LD1117SC-R` -> []; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --package DPAK` -> []; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id ldo-app-ti-lm1117-q` -> ldo-app-ti-operating-point-gap, ldo-app-ti-orderable-capacitor-gap; exit 0.
`python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id ldo-app-st-ld1117-r38` -> ldo-app-st-capacitor-gap, ldo-app-st-operating-point-gap; exit 0.
PASS: 13 CLI cases plus six semantic preservation assertions; no skips.

A source-filtered positive query cannot answer whether an unspecified circuit is safe. The semantic checks retained distinct typical/maximum arrays and explicit null ESR/continuous-load qualification. The recorded negative cases reject cross-vendor, fixed-output, unverified TI orderable, C grade and wrong-package transfer. No command promotes typical or stress values to recommended operation.

## Validation and honest limitations

- `python3 configs/pcbknowledge_agent.py --repo . intake list`: exit 0; draft loads alongside the existing queue.
- `python3 configs/check_english_repo.py`: exit 0.
- `python3 configs/check_public_repo.py`: exit 0; untracked owned files still need the final staged guard before publication.
- Initial ad hoc replay incorrectly used `issue` instead of `source_issue`; corrected the replay harness, then all 13 CLI cases and six semantic assertions passed. Production code was not changed.
- Initial `python3 -m unittest discover -s tests/git_native -p 'test_intake*.py'` lacked PYTHONPATH, producing one import error. This was an invocation error, not a passed test; corrected invocation is recorded below.
- `python3 configs/pcbknowledge_intake_eval.py --repo . --cases evals/intake-retrieval-100.json`: exit 2, expected changed-batch-set refusal. The original pinned 100-record manifest is unchanged. This is **not** an aggregate-gate pass.

Independent source acceptance, coherent maintainer-owned aggregate integration, final staged/public/package checks, full gates, published SHA and CI are pending. Do not push this pair alone or weaken the pinned gate. Reviewer should independently inspect both PDFs and final JSON, record item-specific corrections/limitations, then append a truthful review entry before changing DRAFT status. Maintainer owns final evaluation integration and closure.

Corrected focused invocation: `PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py'` exited 0: 31 tests, no failures/errors/skips (7.576 seconds). This synthetic suite is distinct from the intentionally blocked real-corpus pinned evaluator.


## Independent Agent review accepted (2026-10-28 UTC)

This dated successor section supersedes the earlier pending-review handoff, not its
collection history. Reviewer: `agent:/root/curate_pcbknowledge_constraints/review_constraint_batches`, separate from collector.
Authority: OWNER_DELEGATION. Status: AGENT_REVIEWED_UNDER_OWNER_DELEGATION.
`human_reviewed: false` and `canonical: false` remain unchanged. The owner receipt
at main `2181df9` covers only the previous 100 annotations, not this new batch.

The reviewer independently recomputed each source SHA-256 and byte size from the
actual ignored cache and inspected actual cited page renders, not just extracted
text or the collector's summary. Item-specific coverage: TI pages 3 (family/package), 6 (ti-02/03 columns and footnotes), 14-15 (ti-01 capacitor guidance), 18-19 (ti-04 equations, copper table and still-air plot); ST pages 1/24 (st-01 minimum and example), 7 (st-04 thermal table), 14 (st-02/03 adjustable characteristics), 44 (exact LD1117STR identity). ST revision date was also checked in actual PDF text history.

No numeric correction needed. TI exact orderable remains null; ST ESR envelope remains null. TI versus ST typical/maximum and capacitor scopes are not interchangeable.

Review input SHA-256: `701b849115a244e1a2622aa6a942e6d4a00544237a36a2a7649d08763ae517e5`.
Reviewed JSON SHA-256: `93be166f57e8e40b79f274f5d4461d498e4ec5d0b0bf45c10ed4be2a78974c01`.
Review time: `2026-10-28T02:22:52.549320+00:00`.

Independent CLI replay after status update: 16 cases, exit 0. For EVERY fact,
`python3 configs/pcbknowledge_agent.py --repo . intake search --source-id SOURCE --parameter PARAMETER`
selected exactly its ID and preserved the complete fact, conditions, source, all
source-local warnings, noncanonical status and NOT_LOCALLY_VERIFIED marker.
`intake issues --source-id SOURCE` returned exactly all corresponding warning IDs.
Each source was tested with wrong manufacturer/device/package filters: empty.
The 5 concrete negative commands in the collector receipt above were also rerun
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
`defbd7220856312f4d7100c9122bb5ca33892412c37941bf7d24869b90757e53`. Append-only JSON review history identifies the prior bytes.
The independent reviewer reran all 41 full-payload CLI cases across the three
batches after correction: exit 0. Complete warnings, source/fact payloads and
NOT_LOCALLY_VERIFIED/noncanonical markers were preserved.
`PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`
exited 0: 44 tests, zero skips (28.331 seconds), including the maintainer's
source-disposition extension. Aggregate 125 integration/CI is a separate receipt.
