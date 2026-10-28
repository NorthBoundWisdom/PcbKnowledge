# Vishay SS14 rectifier constraint intake

This pair contains seven small original noncanonical annotations and three
unresolved application warnings for **Vishay General Semiconductor SS14 in
SMA (DO-214AC)**. It is not a generic SS14 replacement rule, a complete diode
model, or approval of a flyback/SMPS/freewheel circuit or MOSFET pairing.

## Source and identity receipt

- [Official product page](https://www.vishay.com/en/product/88746/).
- [Official datasheet](https://www.vishay.com/docs/88746/ss12.pdf), document 88746,
  technical revision **23-Apr-2020**, accessed 2026-10-28.
- Official `https://www.vishay.com/doc?88746=` download returned HTTP 200 and
  redirected to the official datasheet URL above; no alternate mirror was used.
- Actual SHA-256:
  `b32a2d93d2d2cf9f48d6cf678ab03713956b7501029c0424c6a554425df562da`.
- Actual size: **1,174,123 bytes; five PDF pages**. Technical pages 1-4 carry the
  2020 revision. PDF page 5 is document 91000's separate 01-Jan-2026 legal notice,
  not a newer SS14 electrical revision. No latest-revision guarantee is made.
- Collector: `agent:/root/collect_rectifier_application_constraints`.
- Collector independently rendered and inspected all five pages. Claims use
  pages 1-4; the legal appendix is recognized separately. No precise bounding
  boxes or human review are claimed.
- Page 1 identifies SS14 and SMA; page 4 confirms the outline and cathode band.
  Page 2 uses **SS16 examples** in its ordering table. The full SS14 orderable,
  grade and numbered footprint pad convention therefore remain unresolved.
- Existing 162-candidate corpus at `e4c65741e80526aadbe2f3caf1ab0d56d8caa2e0`
  was checked for SS14, document 88746 and rectifier overlap; no duplicate found.

Original PDF bytes, extracted text, renders and test logs stay outside Git.
Public reference access is not redistribution permission or canonical license
clearance. Only this note and the adjacent original-annotation JSON are delivery
files under ADR-021.

## Review-critical distinctions

| Annotation | Source pages | Required distinction |
| --- | --- | --- |
| app-01 | 1 | 40-V repetitive/DC and 28-V RMS limits; no inferred reverse-surge/avalanche allowance |
| app-02 | 1, 3 | 1 A depends on lead temperature and Figure 1 mounting, not ambient alone; no digitized knee |
| app-03 | 1, 3 | 40 A / 8.3 ms single half-sine; nonrepetitive, not a repetitive load budget |
| app-04 | 2, 3 | 0.50-V maximum at 1 A, 25 C, 300 us, 1%; typical curves not guarantees |
| app-05 | 1, 2, 3 | 40-V reverse test; 0.2/6.0-mA limits at 25/100 C, <=40 ms; not SS15/16 hot leakage |
| app-06 | 1, 2, 3 | 88/28 C/W are typical with stated pads; junction/storage ranges are not ambient ratings |
| app-07 | 1, 4 | Banded end is cathode; no assumed pin numbering or cross-vendor footprint interchange |

The JSON keeps explicit identity/orderable, waveform/application and thermal
unknowns. No equation, exact derating knee, repetitive energy rating or circuit
qualification is invented from a family headline or characteristic plot.

## Independent review pending

A distinct Agent must independently recompute source bytes/hash/page count,
inspect the rendered pages and evaluate every fact plus its complete source and
three warnings. The reviewer must test exact complete payloads and deliberate
wrong-manufacturer, sibling-device, wrong-package and wrong-kind cases, not just
keyword counts. Acceptance remains Agent review under owner delegation, never
human review or canonical approval.

The user authorizes processed original summaries/annotations and focused
publication to NorthBoundWisdom/PcbKnowledge. Original documents and private
personal information are excluded. An unreferenced two-file delivery commit may
be created after review; this task must not update main or any remote ref. The
single integrator owns the successor aggregate, combined publication and CI.
If an authorized GitHub publication action is denied, stop at the first denial
and report the exact action/target/reason; do not retry another transport.

## Validation boundary

An isolated checkout is based on main
`e4c65741e80526aadbe2f3caf1ab0d56d8caa2e0`. Baseline and final gate results will
be appended after they run. The old aggregate is expected to refuse a changed
batch set with exit 2; this is an integration requirement, **not a green pass**.
No existing aggregate, code, schema, prior data or shared checkout is edited.


## Independent Agent review accepted (2026-10-28 UTC)

This successor section supersedes the pending-review request above, preserving
collection history. Reviewer:
`agent:/root/collect_rectifier_application_constraints/review_vishay_ss14_constraints`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; authority: `OWNER_DELEGATION`.
`canonical: false` and `human_reviewed: false` remain unchanged. The collector's
live-download observation remains attributed to the collector: this reviewer
rechecked local evidence bytes, not the original HTTP response.

The reviewer used `sha256sum`, `stat` and `pdfinfo` to independently verify the
stated source SHA-256, **1,174,123 bytes and five pages**, independently rerendered
those bytes with `pdftoppm`, and inspected all five resulting images with
`view_image`. Technical pages 1-4 and the separate 2026 legal appendix were
confirmed. The item-specific pages are recorded in the table above and JSON
`review.fact_visual_pages`. No factual correction was required; changes add
review provenance and acceptance only. All three warnings and explicit unknowns
remain intact. No generic SS14, orderable, terminal-number or circuit fit was
inferred. The page-3 current curve's knee was deliberately not digitized.

Review input SHA-256:
`6d9c04939db8a241f1c91631a3c19d81bcbb6590560d4bafff59a9eeb52b5858`.
Accepted JSON SHA-256:
`6537e3323bd556482167c9a268c799f1d8527e8f4d23d610ccfc88b0f2654407`.
Review timestamp: `2026-10-28T04:39:03.223149+00:00`.

### Exact payload and exclusion replay

The reviewer used a separate isolated checkout, initially at
`e4c65741e80526aadbe2f3caf1ab0d56d8caa2e0`, then refreshed it to observed main
`c36256e0ed652529dd328f2fc781e3f4f096ee18`. The complete replay was rerun after
that refresh. The new batch is the only SS14/88746 source in the resulting
**17-batch, 191-annotation** set (184 prior annotations plus these seven).

All **27 CLI commands exited 0** on the final base, with no skipped case:

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search \
  --source-id vishay-ss14-88746-20200423-sma --parameter PARAMETER
python3 -B configs/pcbknowledge_agent.py --repo . intake issues \
  --source-id vishay-ss14-88746-20200423-sma
```

`PARAMETER` iterated all seven stored parameter strings. Each returned array
matched the complete expected object exactly: full fact, entire source, all
three complete sorted source warnings, path, acceptance status,
`FACT_CANDIDATE`, `canonical: false`, and
`evidence_verification: NOT_LOCALLY_VERIFIED`. The issues command matched all
three complete `SOURCE_ISSUE` objects. There was no substring-only comparison.

Nineteen searches with the same source ID returned exactly `[]`:

- `--manufacturer "Diodes Incorporated"` or `"Vishay"` (not the stored exact
  manufacturer name; this is an exact-filter test, not an alias judgment).
- `--device SS12`, `SS13`, `SS15`, `SS16`, `SS14-E3/61T`, or `SS14HE3_B/H`.
- `--package "SMB (DO-214AA)"`, `SMAF`, or `SOD-123`.
- `--parameter nonrepetitive_forward_surge --kind recommended_operating`.
- `--parameter average_forward_current_derating --kind electrical_characteristic`.
- `--parameter thermal_and_temperature_limits --kind maximum_rating`.
- `--parameter cathode_band_polarity --kind pin`.
- `--parameter reverse_surge_voltage`, `repetitive_forward_surge`,
  `guaranteed_thermal_resistance`, or `numbered_pin_assignment`.

These tests establish exact-filter retrieval and unaltered warning delivery,
not semantic electrical-answer capability or absence of uncurated specs.
Independent page review, rather than empty searches, establishes the recorded
rating/typical/test-condition distinctions.

### Independent focused gates and deliberate aggregate refusal

On the refreshed base:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover \
  -s tests/git_native -p 'test_intake*.py' -q
```

Exit **0**: **117 tests in 7.269 seconds**, no failures, errors or skips. The
initial-base focused run also passed 117 tests in 7.190 seconds; it is not being
substituted for the refreshed run.

```bash
python3 -B configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-measurement-timing.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

Exit **2**: `dataset bytes or batch set changed; review cases before updating
pins`. This is the expected refusal of the existing 184-annotation pin after
adding this seven-record batch, **not a pass**. The earlier signal-logic aggregate
also refused the changed batch set with exit 2. No aggregate was edited, bypassed
or declared green. The single integrator must review the combined successor.

The reviewer changed no existing repository file, code, schema, aggregate or
remote ref, and performed no publication or CI action. Full policy guards,
Config/Build/Test/Agent validate/Package, actual delivery bytes and final remote
CI remain separate collector/integrator responsibilities.

## Collector delivery gates on refreshed main

Collector refreshed only its isolated checkout to observed main
`c36256e0ed652529dd328f2fc781e3f4f096ee18`; existing code/data/aggregate bytes
remain unchanged. The baseline aggregate with dispositions passed **236 cases,
16 batches, 184 annotations** before adding this batch. The earlier 162-record
baseline also passed its 165 cases. These are separate, pinned-baseline results.

The accepted JSON above was used for all final gates. On 2026-10-28 UTC these
commands exited **0**, with exactly the two delivery files staged:

- `python3 configs/check_english_repo.py`.
- `python3 configs/check_public_repo.py` (index and worktree).
- `python3 configs/check_pdfjs_vendor.py`.
- `python3 configs/pcbknowledge_workspace.py validate .`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover -s tests/git_native -p 'test_intake*.py' -q`:
  **117 tests in 5.422 seconds**, no failures/errors/skips.
- `python3 configs/pcbknowledge_workflow.py config`.
- `python3 configs/pcbknowledge_workflow.py build`:
  **280 tests in 40.596 seconds**, no failures/errors/skips.
- `python3 configs/pcbknowledge_workflow.py test`:
  **280 tests in 40.262 seconds**, no failures/errors/skips.
- `python3 configs/pcbknowledge_agent.py --repo . validate`.
- `python3 configs/pcbknowledge_workflow.py package`.
- `python3 configs/pcbknowledge_agent.py --repo . change-scope`:
  `DATA_ONLY`, valid for one data commit.
- `git diff --cached --check`.

The collector's separate exact-payload script passed **61 assertions across 25
CLI commands**, including all seven full candidates, the complete issues set
and 17 negative filters. It also asserted the source bytes, explicit unknowns
and the exact pulsed voltage/leakage conditions. This is additional to, not a
replacement for, independent reviewer replay and page inspection.

The package has **23 JSON metadata members**, 17 intake batches and 191
annotations. Its SS14 member is byte-identical to the accepted JSON. No original
PDF, image, extract, local cache or review Markdown is included. Package SHA-256:
`1b54a74ff35bb7d1b6b446c086702cda3233844b4ce932550e7e800cf8f60234`.

An explicit local audit ran:

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake evidence-audit \
  --cache-root <absolute-local-official-source-directory> \
  --cache-file vishay-88746.pdf --source-id vishay-ss14-88746-20200423-sma
```

Exit **0**, one `FOUND_MATCH` at 1,174,123 bytes and the pinned hash. An earlier
attempt used a relative cache-root containing `..`; it was correctly rejected
with exit 2. The successful rerun supplied the explicit absolute directory.
This observation verifies bytes only, changes no metadata, and does not replace
visual review. Ordinary intake reads still say `NOT_LOCALLY_VERIFIED`.

The final pinned measurement-timing aggregate command with dispositions exited
**2**: `dataset bytes or batch set changed; review cases before updating pins`.
That expected refusal is **not a pass**. The collector did not modify its pins,
claims or code to hide it; the single integrator must review a combined successor.
After completing this review note, the collector reruns both policy guards,
whitespace checking, exact payload replay and package generation on delivery
bytes. No main publication or remote CI success is claimed by this pair.

The next handoff is an unreferenced two-file GitHub commit only, preserving the
same reviewed JSON. Integration with other pending work, aggregate renewal,
main publication and final-commit CI remain the single integrator's scope.
