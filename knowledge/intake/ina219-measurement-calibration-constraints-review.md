# INA219 measurement and calibration constraints

## Historical collection scope and source

DRAFT pending distinct Agent review. Collector:
`agent:/root/curate_measurement_timing_wave/collect_ina219_constraints`.
Collected 2026-10-28 UTC against base `e4c6574`; issue #19 claim names the
collector and separate `review_measurement_timing` reviewer. Eight small original
annotations extend, rather than duplicate, the six `ti-ina219` baseline facts.
No canonical or human acceptance is asserted. The integrator owns shared
manifest/replay/CI work; this collector owns only this pair.

Actual official [INA219 PDF](https://www.ti.com/lit/ds/symlink/ina219.pdf):
SBOS448G, December 2015, 38 pages, 892731 bytes, SHA-256
`58004eda854d07478e6fc6f4398c114f60a3bcf18d4877471c7c1a306d1fa1cb`.
The fresh official download matched the previously recorded `ti-ina219` hash.
Exact INA219AIDCNR, A accuracy grade, DCN/SOT-23 eight-pin identity is on PDF
page 29 (Addendum-Page 1). The addendum date is March 5, 2026, not a new electrical
revision. No latest-revision guarantee or redistribution license is asserted.
Actual originals remain in the ignored content-addressed local cache; no PDF,
extracted text or rendered pages belong in Git, issues or packages.

Collector inspected actual renders of PDF/printed pages 5, 9, 10, 12, 19, 20,
23, 24 and 27, plus PDF page 29. No bounding box was measured. The separate
reviewer must inspect bytes and actual renders, not merely this prose.

| ID suffix | Parameter | Evidence and scope |
| --- | --- | --- |
| 01 | raw_voltage_decoding | p12 scaling, p20 signed shunt, p23 bus flags, p9 reference nodes |
| 02 | calibration_and_scale | p12 equations; p24 read-only-zero FS0 |
| 03 | calibration_reset_zero | p12 prerequisite; p19 reset semantics |
| 04 | computed_current_power | p12 scaling; p23 signed current versus power data format |
| 05 | shunt_range_and_accuracy | p5 A-grade error/header; p19 bipolar PGA ranges |
| 06 | conversion_ready_overflow | p23 CNVR/OVF; p10 conflicting clearing prose |
| 07 | conversion_sequence_and_timing | p20 mode/timing; p5 actual typ/max; p9 sequential conversion; p10 sample separation |
| 08 | kelvin_shunt_layout | p27 layout guidance, not a universal shunt selection |

All IDs have prefix `monitor-app-`. All records use source `monitor-app-ti-g-dcn`.
The source's page-10 CNVR clearing prose names a Status register and convert pin,
whereas page 23 names the Power register and mode writes. This remains an explicit
source-wording warning. The page-23 observation is not a silently resolved driver
contract. Exact validated side effects need manufacturer clarification or hardware
evidence. No nonexistent register or pin is invented.

## Runnable bounded retrieval

From the software checkout use an explicit selected workspace (`.` here):

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter raw_voltage_decoding
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter calibration_and_scale
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter calibration_reset_zero
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter computed_current_power
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter shunt_range_and_accuracy
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter conversion_ready_overflow
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter conversion_sequence_and_timing
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter kelvin_shunt_layout
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id monitor-app-ti-g-dcn
```

Searches select exactly `monitor-app-01` through `monitor-app-08` in order. Each
result retains the complete fact value/unit/conditions/evidence, source identity,
path, noncanonical status, acceptance state and all three batch-local warnings:
`monitor-app-calibration-freshness-unknown`, `monitor-app-readiness-wording`,
`monitor-app-shunt-unknown` (sorted). The issues command selects those three
warnings, not Facts. Read-side `NOT_LOCALLY_VERIFIED` remains honest even when
collector/reviewer independently inspected the ignored cache: this CLI does not
perform a fresh local-byte verification. Acceptance does not change that label.

### Engineering and negative semantic cases

- **Zero computed current after reset:** retrieve 02/03/04 and warnings. Calibration
  may be zero; neither zero load nor fresh conversion follows. Actual reset/write
  history and shunt are missing.
- **Replace the shunt but retain firmware scaling:** retrieve 02/05/08 and warnings.
  Re-evaluate actual resistance, calibration truncation/FS0, PGA peak differential
  range, current-code range, heating and total error. No default shunt or safe
  current rating is inferred.
- **Negative shunt voltage:** retrieve 01/04. Decode signed shunt and current;
  bus low bits are flags, not voltage. Do not reinterpret all registers identically
  or infer signed negative-power support from signed current.
- **OVF is clear so input is safe:** retrieve 05/06 and warnings. Math overflow is
  distinct from analog clipping and pin stress. Existing baseline retrieval below
  retains the separate stress/supply constraints, without duplicating them.
- **One successful read proves instantaneous power:** retrieve 06/07 and warnings.
  Sequential channel conversion, averaging, retained data, host latency and
  unresolved clearing prose block that conclusion.
- **A-grade has B-grade precision, or typical timing is worst case:** retrieve 05/07.
  A-grade header and explicit typical/maximum fields prevent both substitutions;
  no total board-accuracy claim is present.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ti-ina219 --parameter VS
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id ti-ina219 --parameter differential_shunt_voltage
```

These select `b005-ti-ina219-05` and `b005-ti-ina219-06`, respectively; retain their
original full payloads and baseline-local warnings. These are supply-operating and differential full-scale records, not stress ratings;
full-scale endpoints are not pin-stress permission. The following exact-filter misses return empty lists,
not guessed equivalents or unsupported guarantees:

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --device INA219BIDCNR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --package 'D (SOIC, 8 pins)'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --manufacturer 'Microchip Technology'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter guaranteed_total_circuit_accuracy
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id monitor-app-ti-g-dcn --parameter signed_power_guarantee
```

## Collector verification

2026-10-28 UTC: 14 real CLI cases exited 0: eight one-record searches, five exact
negative misses, and one three-warning query. For all eight searches, complete
fact/source/warning objects matched the adjacent draft JSON, including values,
units, conditions and evidence (not merely IDs); canonical=false, DRAFT and
NOT_LOCALLY_VERIFIED were checked. This is collection verification, not independent
acceptance or aggregate integration. Independent reviewer and integrator receipts
must record their own executed results; no CI/push success is claimed here.

## Independent accepted-state review

At 2026-10-28T04:30:26.529554+00:00, `agent:/root/curate_measurement_timing_wave/review_measurement_timing` independently recomputed the cached source SHA-256/size/page count and visually inspected every page in the JSON review receipt. The fresh official download is the collector's observation, not a second reviewer download. Reviewed the complete JSON and this prose, including all conditions, warnings, status and evidence claims. Classified readiness wording warning as UNRESOLVED_SOURCE_WORDING rather than application inputs; discrepancy remains unresolved. No numeric correction.

Current status: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; canonical=false, human_reviewed=false, no precise bbox and no circuit qualification. Source wording conflicts and unspecified application inputs remain unresolved.

Independently reran all 14 new-lane documented commands after acceptance: exit 0, no skips; exact fact/issue selections, complete source/fact/warning payload equality, attached batch warnings and NOT_LOCALLY_VERIFIED markers passed. Empty negative retrieval is not electrical permission.

Final JSON SHA-256: `e9e38e94ec1b2c2883ad992eea7e0b6302b0b61174d1339ef4e33a4ddbc37ed1`. Reviewed source/fact/warning payload SHA-256 (JSON sorted keys, compact separators, UTF-8): `c73880f6b31e434c381a2cb4ae7b39fb1403ee736918e01052f7bc230da536f2`. Original draft SHA-256: `96809dcea22d7878de8a82daf2fea6bdfc9960b7f2a1dc22150c2d60d872df35`. Full suite and exact-commit CI remain integrator-owned.

Reviewer also executed the two unchanged-baseline commands: exact IDs b005-ti-ina219-05 and b005-ti-ina219-06 observed. Corrected this receipt to identify them as supply-operating/full-scale, not stress records.
