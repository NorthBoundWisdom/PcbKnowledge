# SN74LVC1T45DBVR translation constraints: collection and review receipt

## Historical collection checkpoint

DRAFT collected by `agent:/root/curate_translation_loadswitch_wave/collect_translation_constraints` on 2026-10-28. Seven annotations and three batch-local unknown warnings answer bounded issue #24. Distinct full-payload review pending at this checkpoint. Not canonical, human-reviewed or board certification.

## Actual evidence

Official source https://www.ti.com/lit/ds/symlink/sn74lvc1t45.pdf: SHA-256 `e6fbd8400161399554fe905326e73236e74bb3af0b546ea1942deed14310536e`, 1,678,649 bytes, 42 pages, accessed 2026-10-28. Electrical revision SCES515N, June 2024. PDF page 21 / Addendum-Page 1, dated November 1, 2025, independently identifies exact SN74LVC1T45DBVR, DBV/SOT-23, 6 pins. Neighboring .A/E4/G4 and DCK/DRL/DPK/YZP packages are not substitutes. Accessed bytes are not a global-latest guarantee.

Original PDF exists only in ignored `.pcbknowledge/evidence/sha256/e6/e6fbd8400161399554fe905326e73236e74bb3af0b546ea1942deed14310536e.pdf`. Text/render aids remain local, outside public deliverables. Public reference is not open licensing or canonical source clearance; annotations are original bounded paraphrases. No original PDF, image or extracted text is committed.

Collector inspected rendered PDF pages 4, 5, 6, 8, 12, 13, 14, 16, 17 and 21. Printed numbering matches PDF through 17; page 21 is Addendum-Page 1. Bboxes remain null/unmeasured.

- Pages 4/5 distinguish recommended supplies and input thresholds from stress ratings; VCCI/VCCO definitions and fallback threshold notes stay attached. Only the 3-to-3.6 V threshold band is selected, not a reconstructed whole table.
- Page 6 selected equal-3 V loaded outputs preserve current polarity and input qualification. Ioff uses the grounded rail and applied voltage conditions, with separate 25 C/full-temperature maxima.
- Page 8 section 5.8 first VCCB column alone supplies selected 3.3-to-1.8 V timing; adjacent supply columns excluded. Footnote marks enable maxima as calculated. Page 12 rendered circuit, waveform thresholds and notes are part of those constraints.
- Pages 13/17 explicitly allow glitch-free sequencing in either order without ramp-order/rate requirements; this is preserved, not replaced with an invented sequencing restriction. The numerical Ioff tests nevertheless use 0 V, not floating rails.
- Page 14 direction table and page 16 external-system turnaround are distinct: external high-impedance steps are not a device OE feature. Page 17 enable formulas retain both disable and propagation terms.

## Exclusions and unresolved inputs

Wrong package/orderable, automatic direction sensing, swapped VCCA/VCCB/DIR domains, absolute maximum as recommended operation, Ioff without grounded-rail tests, DIR-low as A-to-B, typical/headline data rate as guaranteed timing, and enable time without load/threshold context are invalid mutations. Actual rail tolerances, controller/receiver levels, load/edges, drive overlap and timing budget remain unknown. No complete board-safe interface is certified.

## Executed draft replay

Fourteen exact CLI selections passed. Complete source/fact/warning payloads (not just counts), expected ordered IDs, canonical=false, DRAFT and NOT_LOCALLY_VERIFIED were checked against the draft. The latter is the CLI's lack of local verification context, not a denial that the collector checked actual source bytes. Independent reviewer must replay the final accepted payload. Integration and CI gates belong to the integrator and are not claimed here.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter supply_domains_thresholds
```
Expected and observed IDs: `["translate-app-01"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter output_drive_input_edges
```
Expected and observed IDs: `["translate-app-02"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter grounded_rail_isolation_Ioff
```
Expected and observed IDs: `["translate-app-03"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter power_sequence_layout_boundary
```
Expected and observed IDs: `["translate-app-04"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter direction_contention_turnaround
```
Expected and observed IDs: `["translate-app-05"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter selected_pair_switching_limits
```
Expected and observed IDs: `["translate-app-06"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter enable_time_equations
```
Expected and observed IDs: `["translate-app-07"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n
```
Expected and observed IDs: `["translate-app-01", "translate-app-02", "translate-app-03", "translate-app-04", "translate-app-05", "translate-app-06", "translate-app-07"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id translate-app-ti-dbvr-n
```
Expected and observed IDs: `["translate-app-floating_rail_numeric_unknown", "translate-app-rail_receiver_unknown", "translate-app-turnaround_load_unknown"]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --device SN74LVC1T45DCKR
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --device SN74LVC1T45DBVR.A
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --device SN74LVC1T45DBVRE4
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --device TXS0101DBVR
```
Expected and observed IDs: `[]`; exit 0.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id translate-app-ti-dbvr-n --parameter automatic_direction_sensing
```
Expected and observed IDs: `[]`; exit 0.

## Independent Agent acceptance

Reviewer `agent:/root/curate_translation_loadswitch_wave/review_translation_loadswitch` accepted at 2026-10-28T05:53:05.112326+00:00 under `OWNER_DELEGATION`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`. Canonical and human-review flags remain false.
This supersedes the historical pending checkpoints above and in collector evidence methods; it does not erase them.

Reviewed draft JSON SHA-256: `e29817a22e7206b131723c277457d38070b08ff2dc50ea531a69d740ee76b9d0`.
Accepted JSON SHA-256: `c5bc9a4b0a8f8442d662163452f2ec17133913d1e5cfe96aa37513dd96158f72`.

The reviewer independently recomputed actual PDF SHA-256 and byte size, checked page count, and inspected rendered PDF pages 4, 5, 6, 8, 12, 13, 14, 16, 17, 21.
All 7 complete annotations, 3 warnings, evidence locators, identity/revision/addendum distinctions and review prose were checked. No factual corrections were required.

Independent replay used 24 actual CLI calls for this pair: source-scoped full facts/issues, each exact parameter, wrong source/device/manufacturer/package and unsupported-property negatives. Complete source/fact/warning equality was checked, with noncanonical and `NOT_LOCALLY_VERIFIED` preserved. No skipped assertions. Final accepted replay is recorded below after execution. Retrieval integrity is not electrical reasoning or local-byte verification.

Final accepted-payload replay: PASS, exit 0, 49 CLI calls across the two reviewed pairs (25 load-switch, 24 translation), no skips. Complete accepted source/fact/warning payloads and metadata markers matched the independently constructed input-based oracle.
