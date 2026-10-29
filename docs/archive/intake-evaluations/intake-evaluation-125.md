# Application-constraint retrieval evaluation (125 annotations)

This is a separately pinned successor evaluation for the eight-batch application
collection, not a rewrite of the historical 100-annotation acceptance. The original
five JSON batches, `evals/intake-retrieval-100.json`, and the snapshot-specific
[owner acceptance](../receipts/owner-acceptance-2026-10-28.md) remain unchanged. New records
carry independent Agent review under owner delegation, not that earlier human
batch acceptance, canonical approval, or engineering sign-off.

This is now a historical snapshot; CI selects the
[current signal/logic aggregate](intake-evaluation-signal-logic.md).

## Replay

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-125.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

Both CI jobs selected this command at the 125-annotation stage. The evaluator still rejects changed
batch sets or bytes before running queries. It also requires the separately
pinned source-disposition manifest and rejects changed disposition bytes/sets.
No subset fallback, automatic pin refresh, or relaxed equality was introduced.
The old 100-record manifest intentionally fails against the enlarged collection;
use its original snapshot when replaying that historical acceptance.

The aggregate manifest has 64 cases, combined with six existing disposition cases:

- All 18 original query definitions and expected selections are retained unchanged.
  In this reviewed dataset, the new source prose does not add lexical hits to those
  cases. This is an observed bounded result, not a promise about future additions.
- Twenty-five source/parameter selections cover every new application annotation.
- Four filter-only warning selections retain all 11 new batch-local unknowns.
- Sixteen negative selections exclude wrong manufacturers, devices/orderables,
  packages, and unsupported semantic kinds.
- One explicit old ADS1115 pin-rail selection preserves the separate recommended
  pin constraint instead of copying it into the new PGA annotations.

Expected IDs come from the independently reviewed collection receipts and explicit
source/parameter mappings, not captured CLI output. The evaluator compares each
selected result to the full pinned input projection: original conditions, evidence,
source identity, warnings, review status and noncanonical/nonverification markers.
Where present, complete `source_issue_dispositions` metadata is part of that oracle.
A matching count or list of IDs alone cannot pass.

## Bounded engineering questions

| Question | Manifest selections and limitation |
| --- | --- |
| Which capacitor/ESR requirements apply to each LDO scope? | `ldo-app-ti-capacitor_requirements` and `ldo-app-st-capacitor_requirements`, with their separate source warnings. No cross-vendor transfer, nominal-capacitance equivalence or unknown ST ESR inference. |
| Is a requested LDO load supported at this dropout and temperature? | Both `dropout` selections, load/current selections and `thermal_budget` selections. Preserve typical/maximum and test conditions; unspecified operating point and thermal design remain unknown. |
| Does ADS1115 PGA range permit an input above supply? | `ads1115-app-PGA_full_scale`, `ads1115-app-single_ended_range`, and `ads-prior-pin-rail-not-pga`. Differential scaling does not relax per-pin limits or turn stress limits into operation. |
| Can a high-impedance sensor settle after configuration changes? | `ads1115-app-input_loading`, `conversion_settling`, `configuration_change`, plus source warnings. Typical impedance and conversion behavior do not establish an external RC or system error budget. |
| Is the controller interface compatible? | ADS voltage, timing, pull-up and startup selections plus warnings. Retain table conditions; no answer without actual controller, pull-up and bus evidence. |
| Can all ULN channels drive continuously? | `uln2003a-app-simultaneous_channel_duty`, `continuous_load_thermal_budget`, `junction_to_ambient`, and `seven_channel_example_not_entitlement`. Preserve N, duty, package and temperature; typical curves/examples are not all-channel entitlement. |
| Does controller drive or COM connection qualify the load? | ULN input-current, clamp connection/forward-voltage/stress selections plus warnings. Existing ON/saturation records remain separate references; clamp connections do not qualify energy, repetition or fault survival. |

These are candidate retrieval recipes, not a question-answer engine. Exact identity
and semantic-kind negatives are automated exclusions. Duty/temperature mismatch,
current-limit-to-continuous-current transfer, typical-to-guaranteed promotion and
unknown-to-safe inference are prohibited by preserved conditions and warnings;
the CLI does not evaluate a proposed circuit or prove it safe. Zero matches do not
prove no ambiguity or establish electrical permission.

## Source-disposition preservation

The existing MCP23017 disposition remains bound to its original batch/source/issue
and SHA-256 `ae402bd8a19a3fcb2af3d696a74405b0ee5d8d21a42b866fed343e62c13431d0`.
The separate six-case disposition manifest is unchanged. Historical MCP23017 facts
are not relabeled as Rev E; historical warnings are not rewritten as resolved.
Read-only candidates and metadata-only packages retain the full handling receipt,
including its conservative-scope limitations. See the
[source-disposition receipt](../receipts/mcp23017-source-disposition-2026-10-28.md).

## Regression boundaries and verification

`tests/git_native/test_application_replay.py` checks original-case/pin retention,
new-record coverage, separate warning/negative selections and CI's two manifests.
Its synthetic application records have invented values and no manufacturer PDF
content. Mutations with identical IDs/counts must fail if they promote a typical
value, invent a guaranteed bound, change mode/channel conditions, turn current
limit into continuous entitlement, or replace an unknown answer with safety.
Existing evaluator/disposition suites additionally cover lost warnings/provenance,
wrong sources, tampered byte pins and omitted disposition metadata.

The source-content reviews remain the authority for the new annotations:
LDO (`git show intake-final:knowledge/intake/ldo-application-constraints-review.md`),
ADS1115 (`git show intake-final:knowledge/intake/ads1115-input-interface-constraints-review.md`), and
ULN2003A (`git show intake-final:knowledge/intake/uln2003a-load-protection-constraints-review.md`).
Replay does not newly verify original bytes, page images, human acceptance or
canonical authority. All original PDFs, extracted text and renders stay outside
Git and packages. Full integrated gates, package member inspection and exact-commit
remote CI are separate publication checks; a local replay alone is not CI success.
