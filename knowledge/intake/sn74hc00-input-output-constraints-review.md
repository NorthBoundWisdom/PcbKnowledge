# SN74HC00 input/output constraints review

Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**. The dated independent
acceptance below supersedes the historical pending handoff. Human and canonical
approval are not asserted; aggregate integration remains a separate gate.

## Collection scope

Seven noncanonical observations extend the existing TI SN74HC00/D lane. Existing
TI pilot pin/supply and 4.5-V input-threshold records remain byte-for-byte unchanged.
No whole orderable code is invented, and no Nexperia/HCT/SN54HC00 data is inherited.

Collector: `agent:/root/collect_logic_input_constraints`.
The official SCLS181H (August 2021) cached original has SHA-256
`3d3bdace13c7ebeb542e516ae670fc9d7b0b551f9d5222579294e330af38c111`,
2,135,969 bytes and 39 PDF pages. Recomputed from actual local bytes, not the old
receipt alone. The PDF was acquired on 2026-10-27; this is a pinned-source reuse,
not proof of a new download or the latest revision. No original, text extract or
render is included in the deliverable.

Actual 1450-pixel pdftoppm renders were inspected on pages 1, 3, 4, 5, 8, 9, 11,
12 and 14. Page numbers equal one-based PDF pages here; exact bbox remains null.

## Useful distinctions and exclusions

- 2-V and 6-V input threshold pairs complement, rather than duplicate, existing
  4.5-V annotations. No supply interpolation or TTL/HCT compatibility is inferred.
- Input rise/fall limits are not propagation delay or output transition time.
  Unused/intermittently driven inputs need valid levels; 10 kohm is guidance, not
  a guaranteed choice for unspecified driver/capacitance/edge conditions.
- Commercial 4.5-V/4-mA VOH/VOL columns retain separate 25-C typical/limits and
  full-temperature limits. They are distinct from +/-25-mA per-output and
  +/-50-mA supply/ground stress ratings and do not qualify simultaneous outputs.
- 50 pF is application load guidance, not a damage threshold or timing guarantee.
  Unused outputs remain open, not tied to rails as unused inputs may be.
- Page 14 Figure 11-1 depicts an RKS/20-pin/OE arrangement, not the D/SOIC-14
  device on pages 1/3. Exclude that figure from D pin/footprint/wiring use and use
  Table 5-1 instead. Retain only independently supported section 10 bypass prose.
  The warning remains explicit; this is a practical exclusion, not a guessed
  manufacturer correction.
- Numerical input leakage and propagation-delay claims are deliberately omitted;
  source units and absent application load assumptions are not silently repaired.

## Independent review pending

A distinct Agent must recompute source bytes/hash, inspect actual cited rendered
pages including the conflicting layout example, check every condition and review
the complete returned source/fact/warning payloads. Wrong manufacturer, SN54, HCT,
Nexperia and package/orderable filters must remain empty. Agent acceptance is not
human review, canonical approval or circuit qualification.

No aggregate manifest, shared checkout or main ref is changed by this pair.
The existing pinned aggregate is expected to refuse a changed batch set until
the single integrator explicitly updates the aggregate; refusal is not green.

## Bounded current-link check

On 2026-10-28 the [official current TI PDF link](https://www.ti.com/lit/ds/symlink/sn74hc00.pdf)
still identified SCLS181H/August 2021, 39 pages, and page-14 text retained the RKS
caption, 20 numbered pins and OE labels. No corrected newer electrical revision
was found through this single-link check. That web check did not establish a new
byte hash; all factual claims remain pinned to the cached original above.

## Independent Agent review accepted (2026-10-28 UTC)

This dated successor section supersedes the pending-review handoff above while
preserving the collection history. Reviewer:
`agent:/root/collect_logic_input_constraints/review_sn74hc00_constraints`.
Authority: `OWNER_DELEGATION`. Decision:
`AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; `canonical: false` and
`human_reviewed: false` remain unchanged. This does not extend prior owner
acceptance or assert canonical approval.

Reviewer recomputed SHA-256/byte size with `sha256sum`/`stat`, checked `pdfinfo`
(39 pages), and independently inspected actual page images with `view_image`
for pages 1, 3, 4, 5, 8, 9, 11, 12 and 14. The source hash and size above match
actual bytes. The page-14 RKS/20-pin/OE arrangement is visibly incompatible with
the selected D/SOIC-14 identity; page 3 Table 5-1 instead has D VCC/GND at 14/7.
The operational exclusion is retained, not converted to a manufacturer erratum.
The live-link check remains attributed to the collector; the reviewer did not
redownload it or infer web-response byte identity.

Item-specific visual coverage:

| Fact | Printed/PDF pages | Checked distinctions |
| --- | --- | --- |
| app-01 | 4, 12 | 2/6-V thresholds, SN74 temperature, input versus output |
| app-02 | 4, 8, 9 | Input tt maxima; 10/90-percent measurement; slow-edge warning |
| app-03 | 9, 12, 14 | Floating/unused input rules; conditional 10-kohm guidance |
| app-04 | 5, 12 | 4.5-V/4-mA commercial columns; typical versus bounds |
| app-05 | 4, 9, 11 | Output versus rail current stress; no load permission |
| app-06 | 11, 8, 9, 12 | Application-only 50-pF guidance, CL, unused outputs/contention |
| app-07 | 14, 3, 4 | Section 10 bypass text; wrong-layout exclusion; D identity |

No factual correction was needed. Review changes add separate Agent provenance,
source-byte/page coverage and completed acceptance language only. All three source
warnings, unknown user inputs, orderable uncertainty and noncanonical limits are
preserved. The original TI pilot and pinned aggregate bytes matched `git show HEAD`.

Review input SHA-256:
`a17c08402a0212b359af888821c8e5ef82106fbf121077bc3c31492cf7cf66f8`.
Reviewed JSON SHA-256:
`977866bb2ffb99439b79b4bf5d9ff4bcd91fc6cf043862ed5eb2cb97be9eabe5`.
Review time: `2026-10-28T04:06:47.918754+00:00`.
Checkout base: `9ae3b9a28280529d6d9e095c33870a9e56d8c109`.

### Exact payload and negative replay

All 24 CLI cases exited 0 after the status update. Seven commands used:

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search \
  --source-id sn74hc00-app-ti-scls181h-d --parameter PARAMETER
```

`PARAMETER` iterated every fact's exact stored parameter. Each result equaled the
complete expected candidate object: exact fact, entire source, all three complete
warnings sorted by ID, path, acceptance, `FACT_CANDIDATE`, `canonical: false` and
`evidence_verification: NOT_LOCALLY_VERIFIED`. No partial/string-only comparison
was used. `intake issues --source-id sn74hc00-app-ti-scls181h-d` equaled all three
complete source-issue candidate objects.

Sixteen negative searches added these exact filters to the same source ID:

- `--manufacturer Nexperia`
- `--device SN74HCT00`, `SN54HC00`, `74HC00D`, `SN74HC00DR`, or `SN74HC00D`
- `--package "FK, 20-pin LCCC"`, `"RKS, 20-pin VQFN"`, or `"D, 8-pin SOIC"`
- `--parameter VOH`, `output_transition_time_limits`, or `logic_thresholds_at_3_3_V`
- `--parameter output_and_supply_current_stress_limits --kind recommended_operating`
- `--parameter logic_thresholds_at_2_and_6_V --kind electrical_characteristic`
- `--parameter input_transition_time_limits --kind switching_characteristic`
- `--parameter local_supply_bypass_with_figure_exclusion --kind pin`

All returned exactly `[]`. These prove exact-filter retrieval exclusion only,
not semantic electrical-answer capability. Input/output, recommended/stress and
typical/guaranteed distinctions were independently checked against source pages
and remain in returned full conditions. Missing candidates do not prove that an
uncurated specification does not exist.

The preexisting aggregate command:

```bash
python3 -B configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-network-memory-power.json
```

exited **2**, reporting `dataset bytes or batch set changed; review cases before
updating pins`. This is an expected integration refusal, **not a pass**. The
reviewer did not edit the aggregate, stage files, change refs, publish or run CI.
The single integrator owns the new aggregate and final remote/CI verification.

Independent focused suite:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover \
  -s tests/git_native -p 'test_intake*.py' -q
```

Exit 0: 82 tests, 5.016 seconds, no failures, errors or skips. Public/English
guards on staged files and full Config/Build/Test/Package remain the collector's
separate delivery gates; these focused results do not claim those passed.

## Collector delivery gates on refreshed main

Collector `agent:/root/collect_logic_input_constraints` first ran full gates at
`9ae3b9a28280529d6d9e095c33870a9e56d8c109` (237 tests each in Build and Test),
then observed the disjoint evidence-audit release and refreshed only the isolated
checkout to `07e8ce3f7ff94c99158c341cfab9c696b5a021d0`. The shared checkout and
all preexisting intake/aggregate files remained unchanged by this task.

On the refreshed base, all of these exited 0 on 2026-10-28 UTC:

- `python3 configs/check_english_repo.py` and `python3 configs/check_public_repo.py`
  with exactly the reviewed pair staged; `python3 configs/check_pdfjs_vendor.py`.
- `PYTHONPATH=src python3 -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`:
  117 tests, no failures, errors or skips.
- `python3 configs/pcbknowledge_workspace.py validate .`.
- `python3 configs/pcbknowledge_workflow.py config`.
- `python3 configs/pcbknowledge_workflow.py build`: 272 tests, 28.727 seconds,
  no failures, errors or skips.
- `python3 configs/pcbknowledge_workflow.py test`: 272 tests, 28.220 seconds,
  no failures, errors or skips.
- `python3 configs/pcbknowledge_agent.py --repo . validate`.
- `python3 configs/pcbknowledge_workflow.py package` and `git diff --cached --check`.

The package has 18 JSON metadata members, including this exact reviewed JSON;
no source originals, extracted text, renders or local evidence cache is included.
The earlier baseline aggregate replay without the new batch passed 114 cases,
11 batches and 148 annotations. With this batch added, the same pinned aggregate
plus `--dispositions evals/intake-dispositions-2026-10-28.json` exited **2** because
the batch set changed. That refusal is expected and is **not a green aggregate**.
The single integrator must review a successor manifest and final combined gates.

A separate explicit local byte audit used:

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake evidence-audit \
  --cache-root <local-official-source-cache> --cache-file sn74hc00.pdf \
  --source-id sn74hc00-app-ti-scls181h-d
```

It exited 0 with one `FOUND_MATCH` at 2,135,969 bytes and the recorded SHA-256.
This ephemeral byte observation does not replace source-page review or alter
metadata; ordinary intake reads still report `NOT_LOCALLY_VERIFIED`.

Only the adjacent JSON and this review note are delivery files. The next handoff
is an unreferenced two-file GitHub commit, not a main-branch update. Aggregate
publication and exact-final-commit CI remain the single integrator's responsibility.
