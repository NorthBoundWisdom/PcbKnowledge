# TL431 feedback/regulation constraints: collection and review receipt

## Historical collection checkpoint

DRAFT collected by `agent:/root/curate_measurement_timing_wave/collect_tl431_constraints` at 2026-10-28T04:26:41.599229+00:00.
Base: `e4c65741e80526aadbe2f3caf1ab0d56d8caa2e0`. Independent source/full-payload review is not yet recorded.

Six new annotations and four batch-local warnings cover the bounded questions in #20. No existing pin, reference, recommended-current or minimum-regulation record was recopied. Existing records are referenced by ID.

## Evidence receipt

Fresh official download: https://www.ti.com/lit/ds/symlink/tl431.pdf .
Actual SHA-256: `ed2e90697de4e2c553195514adf1ee59cda42863716b6ef702b8304a5b921d22`; 3,087,819 bytes, matching the prior byte identity by measurement, not URL inference.
Electrical revision SLVS543S, May 2024; package addendum September 18, 2026. Page 41 (Addendum-Page 8) shows TL431CDBZR, DBZ/SOT-23, three pins, C operating range 0 to 70 C. No global latestness or transfer to A/B, I/Q, TL432 or DBV.
Original stays only at ignored `.pcbknowledge/evidence/sha256/ed/ed2e90697de4e2c553195514adf1ee59cda42863716b6ef702b8304a5b921d22.pdf`. No original, full extract or image is part of this deliverable.

Collector inspected actual rendered PDF pages 6, 17, 18, 19, 22, 26, 27, 31 and 41. Printed pages equal one-based PDF pages through 31; PDF 41 is Addendum-Page 8. Bounding boxes remain null.

- Page 6: standard-C Iref typ/max columns and test conditions, not A/B accuracy.
- Pages 17/18: Figure 6-16 excludes SOT23-3; Figure 6-18 covers SOT-23 and applies here. Inspected current/capacitance axes, A/B/C/D voltages, 25 C label and Figure 6-19 circuit (150 ohm feed, R1=10 kohm for B/C/D). No numeric boundaries were digitized.
- Pages 19/26: real sign discrepancy. Figure 7-2 gives a positive reference-current term and an arrow into REF; section 9.2.2.2.1 prints a negative term. Both source expressions and locators are retained with `reference-app-equation-conflict`. No erratum, correction or universal reconciled expression is claimed.
- Pages 22/27/31: no-output-capacitor compensation, conditional added capacitance, accuracy contributors and current limiting. Figure 9-16 is TL432 DBZ and is excluded from TL431 pin routing.
- Page 26: current-budget equations are explicitly derived KCL/Ohm-law from the drawn topology with a defined external load, not manufacturer limits. DC excludes capacitor transients.

## Application limitations and semantic negatives

Source claims remain conditional candidates. Actual supply/load/resistor ranges and tolerances, bias, temperature, board thermal conditions and external-loop details are unknown. A low-input/high-load point may lack cathode current; high-input/light-load dissipation is a separate check. Neither passes solely from ratio or separate current/voltage bounds. The maximum required minimum is not a maximum allowed current. Typical bias/curves are not worst-case guarantees.

The Figure 6-18 typical plot is not a universal capacitor/ESR selection chart, numeric stable envelope, phase-margin proof or full-loop certification. No arbitrary capacitor, temperature transfer, interpolation, startup behavior or example-value promotion is asserted. The full batch-local sign, operating-point, stability and layout warnings travel with every fact result. Explicit wrong device/grade/package/manufacturer filters below return no candidates, which is not electrical permission or proof that ambiguity is absent.

## Executed draft retrieval receipts

Executed 2026-10-28T04:27:41.935464+00:00; all 13 commands exit 0, no skipped cases. Exact fact payload equality (not counts alone), attached four warnings, canonical=false and NOT_LOCALLY_VERIFIED were checked. Review status is DRAFT at this collection checkpoint; final accepted-state replay belongs to the independent reviewer/integrator.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --parameter divider_reference_current
```
Expected and observed IDs: `["reference-app-01"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --parameter reference_input_current
```
Expected and observed IDs: `["reference-app-02"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --parameter cathode_current_budget
```
Expected and observed IDs: `["reference-app-03"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --parameter divider_accuracy_budget
```
Expected and observed IDs: `["reference-app-04"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --parameter capacitive_load_stability
```
Expected and observed IDs: `["reference-app-05"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --parameter capacitor_and_current_limiting
```
Expected and observed IDs: `["reference-app-06"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id reference-app-ti-tl431-slvs543s-dbz
```
Expected and observed IDs: `["reference-app-equation-conflict", "reference-app-layout-scope", "reference-app-operating-point-unknown", "reference-app-stability-unknown"]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --device TL432CDBZR
```
Expected and observed IDs: `[]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --device TL431ACDBZR
```
Expected and observed IDs: `[]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --device TL431BCDBZR
```
Expected and observed IDs: `[]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --device TL431IDBZR
```
Expected and observed IDs: `[]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --package 'DBV, 5-pin SOT-23'
```
Expected and observed IDs: `[]`.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reference-app-ti-tl431-slvs543s-dbz --manufacturer 'Other Manufacturer'
```
Expected and observed IDs: `[]`.

## Independent review handoff

Review the actual hash-identified pages and entire final JSON including status, conditions, four source issues and this prose. Pay particular attention to the source equation-sign conflict, SOT-23 plot selection and unknown full-loop/cathode budgets. Keep draft history and append actual reviewer decisions/corrections; do not fabricate human verification. Shared successor manifest, semantic mutation checks, complete repository gates and exact-commit CI are owned by the single integrator. No full-suite or CI pass is claimed here.

## Independent accepted-state review

At 2026-10-28T04:29:35.846475+00:00, `agent:/root/curate_measurement_timing_wave/review_measurement_timing` independently recomputed the cached source SHA-256/size/page count and visually inspected every page in the JSON review receipt. The fresh official download is the collector's observation, not a second reviewer download. Reviewed the complete JSON and this prose, including all conditions, warnings, status and evidence claims. No factual correction required; review metadata updated, DRAFT history preserved.

Current status: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; canonical=false, human_reviewed=false, no precise bbox and no circuit qualification. Source wording conflicts and unspecified application inputs remain unresolved.

Independently reran all 13 documented commands after acceptance: exit 0, no skips; exact fact/issue selections, complete source/fact/warning payload equality, attached batch warnings and NOT_LOCALLY_VERIFIED markers passed. Empty negative retrieval is not electrical permission.

Final JSON SHA-256: `10d0a12c2717e55471d6b48178e574759dd084863483efab454406e9800d8155`. Reviewed source/fact/warning payload SHA-256 (JSON sorted keys, compact separators, UTF-8): `b8a7eb269cb82b920831e71e7a1bbc109959aacea89cac0dc383a9f0966ce1b5`. Original draft SHA-256: `ab199bcfefeac1c300b17192ee7205af06eb6e7ae6b561e0fb0caa345a162dcd`. Full suite and exact-commit CI remain integrator-owned.

Reviewer harness initially compared warning arrays without sorting by ID and failed on ordering only. Corrected the harness to compare sorted complete warning objects, then all 13 commands passed; no fact changes resulted.
