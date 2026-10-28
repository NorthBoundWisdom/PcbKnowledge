# NE555 timing/application constraints: collection and review receipt

## Historical collection checkpoint

DRAFT collected by `agent:/root/curate_measurement_timing_wave/collect_ne555_constraints` at 2026-10-28T04:26:45.193469+00:00. Base: `e4c65741e80526aadbe2f3caf1ab0d56d8caa2e0`. Independent review is not yet recorded.

Eight new annotations and three batch-local warnings cover bounded issue #21 timing/application questions. Existing timer pilot pin, supply and temperature records are referenced, not recopied. No canonical records or prior dispositions change.

## Source and visual evidence

Fresh official download: https://www.ti.com/lit/ds/symlink/ne555.pdf . Actual SHA-256 `a3756e59fd06d0ba736edf9ffe71d99d2aae33fb7e49fedc86165a241179f4a6`, 2,258,813 bytes, 39 PDF pages. Matching the earlier pilot identity was measured from bytes, not inferred from the URL. Electrical revision SLFS022K, March 2026; package addendum September 18, 2026. PDF page 21 (Addendum-Page 1) identifies NE555DR, SOIC (D), eight pins, 0 to 70 C. No transfer to NA555/SA555/SE555, TLC555/LMC555 or other packages; no global latestness guarantee.

Original is only in ignored `.pcbknowledge/evidence/sha256/a3/a3756e59fd06d0ba736edf9ffe71d99d2aae33fb7e49fedc86165a241179f4a6.pdf`. Full local text/renders are ignored aids, not public deliverables. Public availability is not an open license or canonical license clearance. Owner-authorized noncanonical factual curation retains only small original paraphrases and locators.

Collector actually viewed rendered PDF pages 5, 6, 7, 11, 12, 13, 18, 19 and 21. Printed page numbers match PDF pages through 19. Bounding boxes remain null; no graph coordinates were digitized.

- Pages 11/12: Figure 6-2 monostable wiring and trigger-release conditions; Figure 6-5 astable RA/RB charge/discharge paths and equations. The driver duty is low-output fraction; waveform duty is high-output fraction. They are not interchangeable. Approximate RC equations are topology-specific, not absolute timing guarantees.
- Page 7: NE555/SA555 switching table, not the NA555/SE555 table above it. Temperature coefficients have typical values but no maximum. Monostable supply sensitivity has a maximum; astable supply sensitivity does not. Footnotes supply RA and C ranges; astable RB range is not stated. Characterized/design values are not production tested.
- Pages 5/6: threshold/off-discharge leakage rows and resistance guidance. These are not a demonstrated total long-delay error budget.
- Pages 11/13: trigger must be high at least 10 microseconds before mono interval end; reset dominates and interrupts; reset-based reinitiation is distinct from ordinary trigger retriggering. Basic mono cannot retrigger during its active timing interval.
- Pages 12/18: optional CONT capacitance and supply bypass guidance, not an asserted noise/startup qualification.
- Page 19: revision history deletes initial-error specification in revision J. Current K does not supply a numerical initial-error guarantee.

## Application boundaries and semantic negatives

The records retain min/typ/max qualifiers, VCC/temperature/load conditions and the distinction between approximate relationships, source guidance, and unknown application outcomes. They do not promise arbitrary duty cycle, capacitor tolerance, oscillator accuracy, loaded output swing, first-cycle duration, retriggering, noise immunity, or deterministic startup. Missing R/C values/tolerances/leakage, circuit topology, duty convention, supply ramp, initial capacitor state and RESET/TRIG/CONT waveforms remain explicit batch-local warnings. Existing recommended supply/temperature facts do not prove a specific timing design.

Wrong-family/package/manufacturer retrieval negatives below establish filter behavior only: empty results are not electrical permission or proof that an application is safe. A semantic regression must reject swapping driver/waveform duty, promoting typical coefficient to maximum, inventing an initial-error guarantee, dropping the trigger-release condition, or treating startup unknowns as guarantees.

## Executed draft full-payload retrieval

Executed 2026-10-28T04:28 UTC: 15 selections, all exit 0. Checked exact ordered IDs, complete source and fact payload equality, exact attached batch-local warning list, canonical=false and NOT_LOCALLY_VERIFIED. Source-issue retrieval checks exact warning identities; independent reviewer/integrator must replay final accepted payloads. No canonical evidence verification is asserted by this draft retrieval.

Two initial local harness mistakes were corrected before the successful run: expected warnings needed ID sorting, and the issue projection key is `source_issue`, not `issue`. Neither required factual payload changes. These failed preliminary harness runs are not represented as passes.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter monostable_trigger_duration
```
Expected and observed IDs: `["timer-app-01"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter reset_interruption_retrigger
```
Expected and observed IDs: `["timer-app-02"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter astable_frequency_duty
```
Expected and observed IDs: `["timer-app-03"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter monostable_timing_characteristics
```
Expected and observed IDs: `["timer-app-04"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter astable_timing_characteristics
```
Expected and observed IDs: `["timer-app-05"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter timing_node_leakage_constraints
```
Expected and observed IDs: `["timer-app-06"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter output_edge_test_conditions
```
Expected and observed IDs: `["timer-app-07"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --parameter control_reset_supply_practices
```
Expected and observed IDs: `["timer-app-08"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k
```
Expected and observed IDs: `["timer-app-01", "timer-app-02", "timer-app-03", "timer-app-04", "timer-app-05", "timer-app-06", "timer-app-07", "timer-app-08"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id timer-app-ti-ne555dr-slfs022k
```
Expected and observed IDs: `["timer-app-mode-duty-unknown", "timer-app-startup-control-unknown", "timer-app-timing-budget-unknown"]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --device SE555DR
```
Expected and observed IDs: `[]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --device TLC555DR
```
Expected and observed IDs: `[]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --device LMC555CM
```
Expected and observed IDs: `[]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --package 'P, 8-pin PDIP'
```
Expected and observed IDs: `[]`. Exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id timer-app-ti-ne555dr-slfs022k --manufacturer STMicroelectronics
```
Expected and observed IDs: `[]`. Exit 0.

## Independent-review handoff

Designated distinct reviewer: `agent:/root/curate_measurement_timing_wave/review_measurement_timing`. Status remains DRAFT until that reviewer verifies actual bytes, rendered source, complete payload, conditions and warning propagation. No human review is claimed. Integration, successor manifest, accepted-state replay and CI belong to the single wave integrator; this collector edits only the NE555 pair.

## Independent accepted-state review

At 2026-10-28T04:29:53.850200+00:00, `agent:/root/curate_measurement_timing_wave/review_measurement_timing` independently recomputed the cached source SHA-256/size/page count and visually inspected every page in the JSON review receipt. The fresh official download is the collector's observation, not a second reviewer download. Reviewed the complete JSON and this prose, including all conditions, warnings, status and evidence claims. No factual correction required; review metadata updated, DRAFT history preserved.

Current status: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; canonical=false, human_reviewed=false, no precise bbox and no circuit qualification. Source wording conflicts and unspecified application inputs remain unresolved.

Independently reran all 15 documented commands after acceptance: exit 0, no skips; exact fact/issue selections, complete source/fact/warning payload equality, attached batch warnings and NOT_LOCALLY_VERIFIED markers passed. Empty negative retrieval is not electrical permission.

Final JSON SHA-256: `bac46b80f8a5bbd63c0974457f793e1d5929aa46350944b1f06acea1af6ce3b5`. Reviewed source/fact/warning payload SHA-256 (JSON sorted keys, compact separators, UTF-8): `fc2b5c9a34fae30933ad3ffd967bfc5b02e2d03ceb55a77f48c50f8d928183b6`. Original draft SHA-256: `c754a61726233c508e84bfed007c6e5798b1ab4b77f9e42883d91ee083cbf221`. Full suite and exact-commit CI remain integrator-owned.
