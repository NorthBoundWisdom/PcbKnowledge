# Practical task coverage — 2026-10-28

## Decision summary

The 228 annotations are useful as **conditional evidence and mistake-prevention**, not a circuit-answer engine. Eight bounded questions below all retrieve relevant evidence; all eight still need application inputs, additional evidence or engineering analysis before implementation. Counting these as eight qualified designs would be false. Prioritize closing recurring application gaps over adding arbitrary device names.

Scope: immutable source tree of `0373a341d5e12d50778f899848a078621dfa4790` (`8c83b2cd3cc3a2443ab584ccd16768455c49dda0`), 22 batches / 33 batch-local scopes / 228 annotations. This documentation-only evaluation was initially prepared outside the repository at 05:45–05:51 UTC on 2026-10-28. Its publication changes no aggregate, CI, model, source record or issue. Existing model/intake records remain noncanonical; owner acceptance covers only the original 100-annotation snapshot, not this evaluation or later records. This is neither canonical human approval nor completion of the formal pilot.

Method: read current README/AGENTS/TODO, intake-report and historical/current evaluation contracts, original curated JSON and existing independent-review receipts. Execute exact CLI retrievals, inspect conditions and warnings, then manually assess the synthetic questions. No fresh manufacturer retrieval, original-byte audit, PDF visual re-review, simulation, hardware measurement or full repository gate was performed. Recorded source reviews are evidence provenance, not a claim that this reader verified original bytes. Outputs retain `canonical: false` and `NOT_LOCALLY_VERIFIED`.

## Bounded decision outcomes (not a circuit pass/fail score)

| Task | Useful decision supported now | Open next step |
| --- | --- | --- |
| LDO | Nominal 10-uF ceramic is insufficient evidence; TI ESR cannot be imported into ST. | Identify capacitor and operating/thermal conditions. |
| ADC | Reject 4-V pin input at stated 3.3-V supply despite ±4.096-V PGA. | Select an input-range solution, then budget settling/error. |
| GPIO | 3.3-V/+125-C case is not established; 5-V-tolerance case fits only the conservative supply/ambient screen. | Retain conflict and check bus/application constraints. |
| MOSFET | Threshold test cannot establish the proposed 1.8-V drive. | Obtain applicable drive evidence or reconsider driver/device. |
| Diode | Nonrepetitive 40-A surge cannot authorize the proposed pulse train. | Establish repetitive waveform and thermal applicability. |
| Reset | CT-open cannot guarantee the requested ≥25-ms delay. | Choose/review a timing option against actual receiver requirements. |
| RS-485 | Four per-node terminators do not follow the stated two-end cable guidance. | Correct proposed topology, then assess stubs/noise/timing. |
| Connector | Hole/pitch dimensions are available; production footprint/net mapping is not. | Obtain manufacturing and mapping inputs. |

These are eight supported narrow results, not eight failed circuits. The evaluation did not measure general precision/recall, autonomous answer accuracy or design completion.

## Replay and evidence convention

In a clean checkout of `0373a341d5e12d50778f899848a078621dfa4790`, define:

```bash
q() { python3 -B configs/pcbknowledge_agent.py --repo . intake "$@"; }
```

For each source ID below, run **both** commands; issue reads are essential even when fact retrieval is empty:

```bash
q search --source-id "$SOURCE"
q issues --source-id "$SOURCE"
```

Replace `$SOURCE` with the literal ID shown per case. These are complete supported CLI operations, not a natural-language reasoning API. IDs below denote noncanonical intake annotations, not canonical Facts. Source IDs are batch-local: preserve returned `path`, source revision/hash, full conditions, issues and dispositions rather than merging by device name. The [companion receipt](practical-task-evaluation-2026-10-28.json) records exact arguments, expected IDs and stdout SHA-256 values. Run commands from the pinned checkout; raw stdout and internal reviewer notes are not repository deliverables. Existing review receipts and the CLI output carry complete source hashes/page citations; abbreviated page references here are PDF pages unless noted.

### 1. LDO: is a nominal 10-uF ceramic enough for 5 V → 3.3 V, 500 mA?

**Synthetic input:** TI adjustable LM1117, DCY SOT-223; VIN 4.75–5.25 V, output target 3.3 V, load 0–500 mA, ambient 50 C; no CADJ; proposed 10-uF ceramic has no part number/ESR/bias data. Copper and airflow unspecified. Compare ST LD1117STR only as a separate candidate, not a replacement.

**Retrieve:** `SOURCE=ldo-app-ti-lm1117-q` and `SOURCE=ldo-app-st-ld1117-r38`. TI SNOS412Q, pp. 6, 14–15, 18–19; ST DocID2572 Rev 38, pp. 1, 7, 14, 24. Key IDs: `ldo-app-ti-01`–`04`, `ldo-app-st-01`–`04`. Warnings: `ldo-app-ti-orderable-capacitor-gap`, `ldo-app-ti-operating-point-gap`, `ldo-app-st-capacitor-gap`, `ldo-app-st-operating-point-gap`.

**Established:** TI guidance combines at least 10-uF tantalum and 0.3–22-ohm ESR; nominal ceramic capacitance alone does not demonstrate compliance. The 500-mA TI maximum dropout entry is 1.25 V over TJ 0–125 C under its stated dropout criterion; it is not an output-accuracy guarantee. Minimum-load and thermal requirements remain relevant at the 0-mA end. ST's 10-uF stability statement does not supply a numerical ESR envelope; TI ESR cannot fill that absence.

**Still missing:** capacitor effective C/ESR versus bias/temperature/tolerance and TI orderable identity (facts); output tolerance/transients, actual preload, thermal path/junction temperature (inputs); coupled worst-case dropout/thermal/stability assessment (analysis). **Prohibited:** “10 uF passes,” “current limit permits 500 mA continuously,” or “TI and ST are interchangeable.”

### 2. ADC: does ±4.096-V PGA permit a 4-V input on a 3.3-V rail?

**Synthetic input:** ADS1115IDGSR, DGS VSSOP; VDD 3.3 V, AINN=0 V, AINP=0–4.0 V, PGA ±4.096 V, 860 SPS; 100-kohm sensor, external RC unknown, desired error 1 mV.

**Retrieve:** `SOURCE=ads1115-app-ti-e-dgs`; additionally `q search --device ADS1115IDGSR --parameter analog_input_pin_voltage`. SBAS444E, pp. 4–6, 14–15 and application sections. Key IDs: `ads1115-app-01`–`05`, `b003-ti-ads1115-e-07`; warnings `ads1115-app-range-uncertainty`, `ads1115-app-sensor-uncertainty`, `ads1115-app-controller-uncertainty`.

**Established:** PGA sets differential scaling, not pin-voltage permission; 4 V exceeds the 3.3-V recommended pin rail in this scenario. Single-ended span is limited by the lesser of VDD and positive full scale. Typical 6-Mohm common-mode / 4.9-Mohm differential loading applies at ±2.048 V, 8 SPS, 3.3 V, 25 C—not this configuration. One converter cycle does not establish external sensor/RC settling.

**Still missing:** suitable conditioned sensor/buffer/RC evidence (facts); actual pin trajectories, RC values, interface and power sequencing (inputs); acquisition-error and settling budget (analysis). **Prohibited:** authorizing 4 V from PGA, declaring the 100-kohm sensor accurate from typical impedance, or treating the next in-flight conversion as using a newly written channel/PGA.

### 3. GPIO expander: 3.3 V at +125 C versus a bounded 5-V screen

**Synthetic inputs:** exact MCP23017-E/SO, SOIC. A: actual VDD 3.135–3.465 V, ambient -40…125 C. B: actual VDD 4.75–5.25 V, same ambient. Controller and bus details unspecified.

**Retrieve:** `SOURCE=microchip-mcp23017`. Key annotation `b005-microchip-mcp23017-01` is a supply-pin map, **not a supply envelope**. Issue `MCP23017-SUPPLY-TEMPERATURE-AMBIGUITY` and its linked disposition are the decisive evidence. Original pins remain DS20001952D; the separate disposition checked DS20001952E and errata without relabeling old facts.

**Established:** applying the recorded Agent-derived screen manually, A is `NOT_ESTABLISHED`; B lies within the conservative 4.5–5.5-V / -40…125-C supply/ambient subset. This is not an automatic CLI decision or manufacturer resolution. Both cover and electrical-table wording remain visible and their discrepancy remains unresolved.

**Still missing:** manufacturer clarification for the disputed mapping (fact/conflict); I2C thresholds/timing, loading, reset, power sequencing and self-heating evidence for the proposed board (inputs/analysis). **Prohibited:** intersecting unrelated extrema to approve A, declaring A unsafe solely because outside the screen, or treating B as a qualified circuit.

### 4. MOSFET: does a threshold below 1.8 V establish a 2-A PWM switch?

**Synthetic input:** AO3400A SOT23 low-side switch, 1.8-V nominal GPIO, 12-V / 2-A load, 20-kHz PWM, 50-C ambient. Actual GPIO VOH/current, source bounce, gate network, load inductance and PCB thermals unspecified.

**Retrieve:** `SOURCE=ao3400a-aos-r3p1-sot23`; Rev 3.1, pp. 1–3/5. Key IDs `ao3400a-drive-03`–`08`, plus terminal identity `01`; warnings `ao3400a-gate-load-transient-inputs-unknown`, `ao3400a-pcb-thermal-inputs-unknown`, `ao3400a-numbered-pin-identity-unknown`.

**Established:** 0.65–1.45-V threshold is tested at only 250 uA, VDS=VGS, TJ=25 C. Lowest tabulated RDS(on) drive is 2.5 V / 3 A / 25 C (48 milliohms maximum); that test current is not a load recommendation. No guaranteed 1.8-V drive or hot 2.5-V maximum follows. Short-duration thermal resistance and gate-charge test conditions cannot be substituted for continuous/PWM conditions.

**Still missing:** suitable 1.8-V/high-temperature operating evidence and numbered terminal mapping (facts); driver, load transient and thermal inputs; switching-loss/SOA/thermal analysis. **Prohibited:** “threshold means fully on,” generic SOT23 pin numbering, or deriving permissible PWM frequency from typical capacitance.

### 5. Rectifier: can 40-A surge authorize repetitive 2-A pulses?

**Synthetic input:** Vishay SS14 SMA (DO-214AC), 12-V system, proposed 2-A / 1-ms pulses at 100 Hz, 70-C ambient; waveform between pulses, reverse spikes and mounting thermal path unspecified.

**Retrieve:** `SOURCE=vishay-ss14-88746-20200423-sma`; document 88746, 23-Apr-2020, pp. 1–4. Key IDs `vishay-ss14-app-01`–`07`; warnings `vishay-ss14-app-application-waveform-unknown`, `vishay-ss14-app-thermal-design-unknown`, `vishay-ss14-app-identity-and-orderable-unknown`.

**Established:** 40 A is an 8.3-ms **single half-sine**, nonrepetitive surge superimposed on rated load, at rated lead temperature. It is not a repetitive pulse allowance. The 1-A average rating refers to lead temperature/derating and mounting, not 70-C ambient alone. VF ≤0.5 V at 1 A/25 C uses a 300-us, 1%-duty test; it is not a fixed drop for this scenario.

**Still missing:** repetitive pulse/energy applicability and exact ordering suffix (facts); actual forward/reverse waveform, lead temperature and thermal path (inputs); loss/transient/thermal analysis. **Prohibited:** accepting this pulse train from IFSM, average-current arithmetic alone, or a generic SS14 cross-vendor identity.

### 6. Reset: does CT-open guarantee 20 ms and reset low down to zero supply?

**Synthetic input:** TPS3808G33DBVR, DBV; supervisor VDD and monitored SENSE both connected to the nominal 3.3-V rail, CT open, MR high; RESET pull-up 100 kohm to 3.3 V, 50-pF load. Receiver requires at least 25-ms release delay; rail ramp and low-voltage receiver behavior unknown.

**Retrieve:** `SOURCE=reset-app-ti-g33-dbv-n`; SBVS050N, electrical/switching tables and sections 7.3–7.4. Key IDs `reset-app-01`, `03`, `06`, `07`; warnings `reset-app-delay_drive_unknown`, `reset-app-rail_receiver_unknown`, `reset-app-footnote_mapping`.

**Established:** CT-open delay is 12/20/28 ms min/typ/max under VDD 1.7–6.5 V, TJ -40…125 C and the stated test load/qualifying waveforms. Thus the record does not guarantee this receiver's 25-ms minimum. Release also requires SENSE above threshold plus hysteresis and MR high. RESET is open-drain; below VPOR it is undefined. VPOR's 0.8-V maximum row has its own 15-uA / 0.2-V test, not arbitrary loading.

**Conflict handling:** rendered-page footnote markers and note texts mismatch. Retain `reset-app-footnote_mapping`; do not silently swap markers to manufacture a ramp/load guarantee. **Missing:** manufacturer clarification (fact/conflict); ramp, receiver limits and domain sequencing (inputs); timing/pull-up/startup assessment (analysis). **Prohibited:** typical 20-ms guarantee, reset-low to zero VDD, or ignoring the warning because the row retrieved successfully.

### 7. RS-485: terminate each node and omit bias because of failsafe?

**Synthetic input:** four SN65HVD75DR nodes, D SOIC, 3.3-V rails, 120-ohm-characteristic cable, 30-m trunk, 1-m stubs, 1 Mbps; proposed 120-ohm termination at every node, no external bias. Ground offset/noise/turnaround unspecified.

**Retrieve:** `SOURCE=rs485-app-ti-sllse11h-d`; SLLSE11H, sections 7.3/7.5/7.8, 9.3 and 10.2. Key IDs `rs485-app-01`–`05`, `07`, `09`; warnings `rs485-app-network-unknown`, `rs485-app-timing-unknown`, `rs485-app-ground-protection-unknown`.

**Established:** typical parallel-cable guidance places termination at the two cable ends, matched to cable impedance—not every node. This does not approve the 1-m stubs. Failsafe high for open/short/idle requires enabled receiver and operating limits; an A-B short is not a short to arbitrary supply/ground. Individual bus pins and differential input must both stay within their own limits. Standby wake timing is microseconds, distinct from nanosecond propagation.

**Still missing:** actual termination tolerances/load, cable propagation, noise/offset, controller thresholds and DE/RE scheduling (inputs); transmission-line, bias-margin and turnaround assessment (analysis). **Prohibited:** universal permission to omit bias, 20-Mbps device rating as network qualification, or “failsafe” as fault/EMC immunity.

### 8. Connector: can the hole drawing become a production footprint?

**Synthetic input:** Wurth 61300211121, two-position 2.54-mm straight through-hole header, 5 V / 2 A; request a footprint for a 1.6-mm board using 1.1-mm holes. Pad dimensions, plating process, board-side view, mate and net mapping unspecified.

**Retrieve:** `SOURCE=wurth-61300211121-003000-20230108`; drawing 003.000, 2023-01-08, pp. 1–2/5. Key IDs `wurth-61300211121-mech-01`–`04`; warning `wurth-61300211121-application-inputs-unknown`.

**Established:** identity is two positions at 2.54-mm pitch. Recommended hole diameter is 1.1±0.15 mm; adjacent pitch 2.54±0.05 mm and overall span 2.54±0.1 mm are distinct retained callouts. Neither board side, pad diameter, drill/plating process nor CAD coordinates is established. Endpoint labels do not prove net polarity. Recorded 3-A rating lacks a current-test temperature; it does not qualify this 2-A assembly.

**Still missing:** full footprint/mating/thermal evidence (facts); fabrication process, mounting side, net map and ambient (inputs); CAD mapping/DFM and thermal assessment (tools/analysis). **Prohibited:** inventing a production footprint from image scale, conflating test-withstand with working voltage, or assuming mating compatibility from pitch.

## Explicit negatives and retrieval limitations

Executed: `q search --device AO3400` → no matches (must not substitute AO3400A); `q search --device 61300211121 --package SOT23` → no matches (wrong package); `q search --device LM1117 --parameter capacitor_requirements` → only `ldo-app-ti-01` (not ST). Empty results mean unavailable scoped candidates, **not** compatibility, safety, or proof no relevant source exists. Exact structured device/source fields precede lexical search; full orderable identity remains unknown where the source records say so. Neither a lexical hit nor a successful exit evaluates the synthetic numerical inputs.

## Three priorities for the next plan

1. **Application-completeness handoff, not more ratings.** Across all eight tasks, distinguish missing source facts from user/board inputs, preserve conflict/unknown warnings, and provide exact scoped evidence. Keep the existing read-only/preflight work in its assigned lane; do not duplicate it. Success is a reproducible bounded question with explicit missing fields and prohibited inference, not a larger annotation total. No electrical solver is proposed.
2. **Conditioned passives and interfaces, already in progress.** Resistor/MLCC/inductor lanes directly address capacitor effective-C/ESR, pull-up/termination and converter-component constraints. Evaluate their delivered scopes against cases 1, 2, 6 and 7 before claiming they close a gap; a reviewed passive at one condition does not qualify a chosen part or board. Do not open duplicate collection issues. Coordination observation at 05:56 UTC on 2026-10-28: reviewed resistor handoff `988743b2` and MLCC handoff `890c9b92` were delivered but not integrated into this snapshot; the Bourns SRP4020TA-4R7M draft remained under review. None is counted as evidence in the frozen 228 annotations. These are dated observations, not current status promises.
3. **Conflict and identity closure before automatic implementation.** MCP23017's lower-voltage/high-temperature region and TPS3808 footnote applicability require authoritative clarification, not more extrapolation. AO3400A numerical terminals and connector CAD/board-side mapping remain incomplete. Separate these missing facts from missing computation capability: retrieval cannot create measured thermal paths, simulate a transmission line, establish PCB manufacturability or perform human approval. Route existing assignments rather than creating another framework or changing canonical models based on these examples alone. Wisdom #24 (SN74LVC1T45DBVR translation) and #25 (TPS22918DBVR load-switch constraints) are assigned/planned, not yet collected or accepted as of the 05:45 UTC coordinator check on 2026-10-28. They may inform later interface/sequence questions but do not resolve any result in this frozen evaluation.

## Verification receipt and limits

The external local snapshot was Git-initialized only because CLI workspace validation requires Git. Its committed tree equals `0373a341d5e12d50778f899848a078621dfa4790` exactly; the local synthetic commit hash is not the public commit. Twenty-two CLI commands exited 0. Eighteen source-scoped fact/issue outputs matched independently selected record-ID sets; the four additional commands retrieved the stated ADC rail annotation, two empty negatives and the TI-only capacitor annotation. Complete stdout was retained in the preparation workspace; it is not required or implied to exist in this repository. The published machine-readable receipt retains commands, expected IDs and output hashes. This is scoped evidence-selection verification plus manual task analysis, not a rerun of the 398-case aggregate, mutation suite, source-original audit, formal pilot, full software gate or circuit validation.

Independent Agent review replayed all 22 commands and matched their complete stdout hashes; it additionally compared all returned source and fact/issue objects with the stored batches (62 fact appearances and 21 issue appearances). No blocking evidence/overclaim finding remained after explicitly distinguishing reset VDD/SENSE and clarifying the RS-485 bias wording. This is metadata/interpretation review, not a new source-byte or human review.
