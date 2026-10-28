# TPS3808G33 reset constraints: collection and review receipt

## Historical collection checkpoint

DRAFT collected by `agent:/root/curate_reset_rs485_wave/collect_reset_constraints` on 2026-10-28, base `e4ce9305a4c48011eff9fa81cb751a0a5a5a87a8`. Eight annotations and three batch-local warnings answer bounded #22 questions. Separate source/full-payload review is pending at this checkpoint; this is not human review, canonical approval or board certification.

## Actual evidence

Official source https://www.ti.com/lit/ds/symlink/tps3808.pdf downloaded on 2026-10-28: SHA-256 `74d889c0f68af88032f1633c26381817cc03e10d9fd3b4c177a044ad3ed86eed`, 2,046,179 bytes, 39 pages. Electrical revision SBVS050N, August 2026. Orderable addendum dated July 16, 2026 independently lists TPS3808G33DBVR, DBV/SOT-23, six pins at PDF page 22 / Addendum-Page 4. These are accessed bytes, not a global-latest claim. No neighboring G01/G30/WSON/E variant transfer.

Original bytes are solely in ignored `.pcbknowledge/evidence/sha256/74/74d889c0f68af88032f1633c26381817cc03e10d9fd3b4c177a044ad3ed86eed.pdf`; ignored local render/text aids are not public deliverables. Public reference is not open licensing or canonical processing clearance. Only brief original paraphrases and metadata are delivered.

Collector viewed actual rendered pages 3, 4, 5, 6, 7, 10, 11, 12, 13 and 22. Printed pages equal PDF pages through 13. Null bbox values remain unmeasured.

- Page 3 separates the G33 nominal 3.3 V rail from 3.07 V threshold.
- Page 6 min/typ/max columns and conditions distinguish threshold tolerance, hysteresis, MR thresholds and output sink tests. Footnote markers are inconsistent with note texts: this is explicitly unresolved, not silently repaired.
- Page 7 pulse/propagation numbers for MR/SENSE are typical only. No minimum pulse or maximum propagation guarantee is invented. Timing diagram requires both MR and SENSE qualification.
- Page 11 Figure 7-2 separates open CT, resistor-to-VDD and capacitor-to-ground modes; the equation and capacitance recognition floor are distinct from tolerance-qualified table examples.
- Pages 12/13 separate low-supply asserted reset from below-POR undefined behavior. Open-drain high impedance is not a driven high or proof of unpowered-recipient safety.

## Bounded unknowns and semantic exclusions

No load/rail/ramp/noise/receiver/timing/CT-tolerance inputs were supplied. These remain batch-local warnings. Source marker ambiguity must not disappear from threshold/startup retrieval. Mutations must reject nominal-rail-as-trip, typical pulse-as-minimum, guaranteed zero-VDD reset, swapped CT modes, lost MR/SENSE qualification, missing pull-up/load conditions, or invented debounce/receiver-domain safety. No reset circuit or timer simulator was built.

## Executed draft replay

Fifteen exact CLI selections passed with exit 0. Full source/fact/warning payloads, ordered IDs, canonical=false, DRAFT and NOT_LOCALLY_VERIFIED were checked, not only counts. An initial load attempt failed because the collector used `status` rather than `issue_status` for unresolved warnings; corrected before these successful checks. No factual change was needed for that schema correction. Independent review must replay final accepted payloads. Repository-wide/integration/CI gates belong to the integrator and are not claimed here.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter fixed_threshold_hysteresis
```
Expected and observed IDs: `["reset-app-01"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter supply_sense_operating_boundary
```
Expected and observed IDs: `["reset-app-02"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter delay_modes_bounds
```
Expected and observed IDs: `["reset-app-03"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter external_CT_relationship
```
Expected and observed IDs: `["reset-app-04"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter manual_reset_qualification
```
Expected and observed IDs: `["reset-app-05"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter reset_output_pullup_sink
```
Expected and observed IDs: `["reset-app-06"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter power_up_down_validity
```
Expected and observed IDs: `["reset-app-07"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --parameter sense_transient_supply_guidance
```
Expected and observed IDs: `["reset-app-08"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n
```
Expected and observed IDs: `["reset-app-01", "reset-app-02", "reset-app-03", "reset-app-04", "reset-app-05", "reset-app-06", "reset-app-07", "reset-app-08"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id reset-app-ti-g33-dbv-n
```
Expected and observed IDs: `["reset-app-delay_drive_unknown", "reset-app-footnote_mapping", "reset-app-rail_receiver_unknown"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --device TPS3808G01DBVR
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --device TPS3808G33DRVR
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --device TPS3808EG33DBVR
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --package 'DRV (WSON, 6 pins)'
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id reset-app-ti-g33-dbv-n --manufacturer 'Other Manufacturer'
```
Expected and observed IDs: `[]`; exit 0.

Draft JSON SHA-256: `3bf98e31b9701e49b1a3574d1ef545bfe54682c5fa45e3d71fdda9a1e0433612`. Final acceptance and exact hashes must be appended by the different reviewer.

## Independent final acceptance

At 2026-10-28T04:58:44.916771+00:00, distinct reviewer `agent:/root/curate_reset_rs485_wave/review_reset_rs485_sources` independently verified the SHA-256/byte size above and inspected actual rendered pages 3, 4, 5, 6, 7, 10, 11, 12, 13 and 22. The reviewer read the complete JSON (including every additional-evidence field, current provenance/status, warnings and historical checkpoint) and this review prose. No factual correction was required. The page 6 marker mismatch remains unresolved; nominal versus trip, MR/SENSE qualification, CT modes, typical-only pulse and propagation values, output-load/domain and low-supply boundaries remain intact.

Acceptance is `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`, with explicit `AGENT` / `OWNER_DELEGATION` provenance, `canonical=false` and `human_reviewed=false`. Current evidence methods reflect completed distinct review; historical DRAFT records remain historical. An initial acceptance replay correctly rejected missing explicit top-level delegated-review provenance; this metadata was supplied before the successful final replay. No schema or policy was changed.

The independent reviewer reran all fifteen exact commands above against the final accepted JSON: exit 0 for every command, exact ordered IDs and equality of the complete source/fact/warning payloads. All returned items retain `NOT_LOCALLY_VERIFIED`, which is the CLI local-cache label, not a denial of the separately recorded source inspection. No originals, renders or extracted source text are committed. Final JSON SHA-256: `091cd036013fa38cca0f468f159f4dd9d8cf1f7be889662c75f5c0dcf3574e2e`. Aggregate/CI results belong to the integrator's separate receipt.
