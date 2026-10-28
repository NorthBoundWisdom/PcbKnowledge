# TPS22918 load-switch constraints: collection and review receipt

## Historical collection checkpoint

DRAFT collected by `agent:/root/curate_translation_loadswitch_wave/collect_loadswitch_constraints` on 2026-10-28 against main `0373a341`. Eight small original annotations and four batch-local warnings address #25. Independent review is pending at this historical checkpoint. This is noncanonical intake, not human review, approval of canonical facts, or board certification.

## Actual source evidence

Official https://www.ti.com/lit/ds/symlink/tps22918.pdf accessed 2026-10-28: SHA-256 `1b28eb58003d28b18bf919a15734056f296a499bebee2bd493a1e4358c4dfb1c`, 1,072,926 bytes, 30 PDF pages. Electrical revision SLVSD76C, July 2017. Separate package addendum July 15, 2026, PDF page 23 / Addendum-Page 1 lists exact TPS22918DBVR, DBV/SOT-23 six pins, separately from .A, DBVT and G4 orderables. This identifies accessed bytes, not a global-latest revision guarantee.

Original bytes stay in ignored `.pcbknowledge/evidence/sha256/1b/1b28eb58003d28b18bf919a15734056f296a499bebee2bd493a1e4358c4dfb1c.pdf`; text and render aids are ignored local-only files. Public reference does not imply open licensing or canonical source-processing clearance. No original PDF, source image or substantial source extract is a public deliverable.

Collector inspected rendered PDF pages 3, 4, 5, 6, 11, 13, 14, 15, 16, 17, 19, 20 and 23. Printed pages equal PDF pages through 20. All bbox coordinates are null because none were measured.

- Page 3 pins and page 23 orderable row establish identity; do not transfer another TPS229xx or package.
- Page 4 separates recommended table VIN starting at zero from page 20 functional description starting at 1 V. Stress limits, current test conditions and thermal derating do not establish board operating capability.
- Page 5 RON test-current sign, VIN and temperature rows stay attached. Typical RON is not the hot maximum. RPD at VIN=5 V has 24 ohm typical and 30 ohm maximum, not a universal discharge resistance.
- Page 6 only has typical timing, with VIN steady before ON, VON=5 V, TA=25 C, RL=10 ohm, CIN=1 uF, CL=0.1 uF, CT=1000 pF and QOD open. Page 11 circuit and timing arrows distinguish delay, turn-on and 10%-90% rise. Load resistance affects discharge.
- Page 14 CT equation is approximate, already uses 10%-90% timing, and excludes CT=0. Table 2 is typical at 25 C with 25 V X7R 10% CT capacitor; capacitor tolerance is not a worst-case device timing bound. Page 15 voltage-rating boundaries require the higher rating at 1.2/4 V.
- Pages 13-15 separate QOD tied, external-resistor and open modes. Internal-only QOD allows no more than 200 uF, must remain within TJ=125 C and requires natural discharge rather than driven charge. Falling VIN weakens RPD. QOD is not reverse protection.
- Page 17 explicitly describes possible body-diode current from VOUT to VIN after supply removal; there is no quantified reverse-blocking guarantee here. Page 20 explicitly excludes controlled slew when ON arrives before VIN.
- Page 16 Table 5 prints CL=22 uF, while page 19 equations 10/12 and page 20 captions print 22 pF. These are visibly inconsistent, not an extraction artifact. The warning preserves this conflict; the example is not silently repaired or adopted as a numerical guarantee. Application information is explicitly outside the component specification.

## Bounded unknowns and exclusions

Actual source impedance, supply ramp, load waveform, effective CIN/CL/CT and tolerances, discharge resistor/path, prebias, ON state and thermal environment were not provided. No calculated board inrush, startup deadline, safe reverse current or guaranteed current-limit threshold is invented. Semantic negative cases include wrong orderable/package; dropped CT/load/timing/temperature conditions; typical-to-guaranteed promotion; slew control treated as current limiting; QOD treated as reverse blocking; zero-supply operation inferred from a table boundary; and unit conflict silently repaired. No power-path simulator or current-limit feature was built.

## Executed draft replay

Fifteen exact source-filtered CLI selections below passed with exit 0. Replay checked full source, fact and warning dictionaries, ordered IDs, canonical=false, DRAFT and NOT_LOCALLY_VERIFIED, not only counts. NOT_LOCALLY_VERIFIED is the intake CLI metadata contract and is not changed into canonical verification by collector-local byte inspection. Independent reviewer must replay accepted payloads after review. Integration tests, broad repository gates, packaging and CI belong to the integrator and are not claimed by this collection receipt.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter operating_stress_thermal_boundary
```
Expected and observed IDs: `["loadswitch-app-01"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter on_control_sequence
```
Expected and observed IDs: `["loadswitch-app-02"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter ron_load_temperature
```
Expected and observed IDs: `["loadswitch-app-03"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter ct_rise_time_relationship
```
Expected and observed IDs: `["loadswitch-app-04"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter switching_test_timing
```
Expected and observed IDs: `["loadswitch-app-05"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter qod_modes_discharge
```
Expected and observed IDs: `["loadswitch-app-06"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter inrush_capacitance_boundary
```
Expected and observed IDs: `["loadswitch-app-07"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --parameter reverse_current_power_loss_boundary
```
Expected and observed IDs: `["loadswitch-app-08"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c
```
Expected and observed IDs: `["loadswitch-app-01", "loadswitch-app-02", "loadswitch-app-03", "loadswitch-app-04", "loadswitch-app-05", "loadswitch-app-06", "loadswitch-app-07", "loadswitch-app-08"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id loadswitch-app-ti-tps22918-dbv-c
```
Expected and observed IDs: `["loadswitch-app-example_unit_conflict", "loadswitch-app-rail_load_thermal_unknown", "loadswitch-app-reverse_current_guarantee_unknown", "loadswitch-app-timing_discharge_unknown"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --device TPS22918DBVR.A
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --device TPS22918DBVT
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --device TPS22918DBVTG4
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --device TPS22919DBVR
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id loadswitch-app-ti-tps22918-dbv-c --package 'WSON (6 pins)'
```
Expected and observed IDs: `[]`; exit 0.

## Independent Agent acceptance

Reviewer `agent:/root/curate_translation_loadswitch_wave/review_translation_loadswitch` accepted at 2026-10-28T05:53:05.110758+00:00 under `OWNER_DELEGATION`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`. Canonical and human-review flags remain false.
This supersedes the historical pending checkpoints above and in collector evidence methods; it does not erase them.

Reviewed draft JSON SHA-256: `41b93603bb795c1d49ab9e3370804c3be25b92b6c264ac2eda6bbcba02602b2f`.
Accepted JSON SHA-256: `ffb85158f9e7ace4587611f1f23075d86fb6f3cf1b61516625f7e435be81b4f8`.

The reviewer independently recomputed actual PDF SHA-256 and byte size, checked page count, and inspected rendered PDF pages 3, 4, 5, 6, 11, 13, 14, 15, 16, 17, 19, 20, 22, 23.
All 8 complete annotations, 4 warnings, evidence locators, identity/revision/addendum distinctions and review prose were checked. No factual corrections were required.

Independent replay used 25 actual CLI calls for this pair: source-scoped full facts/issues, each exact parameter, wrong source/device/manufacturer/package and unsupported-property negatives. Complete source/fact/warning equality was checked, with noncanonical and `NOT_LOCALLY_VERIFIED` preserved. No skipped assertions. Final accepted replay is recorded below after execution. Retrieval integrity is not electrical reasoning or local-byte verification.

Final accepted-payload replay: PASS, exit 0, 49 CLI calls across the two reviewed pairs (25 load-switch, 24 translation), no skips. Complete accepted source/fact/warning payloads and metadata markers matched the independently constructed input-based oracle.
