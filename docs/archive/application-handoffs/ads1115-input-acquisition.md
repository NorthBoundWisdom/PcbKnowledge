# ADS1115 input/acquisition application handoff

Issue #28 · author: `agent:/root/prepare_adc_mosfet_input_cards/author_ads1115_card` · authored/replayed 2026-10-28 at 08:26 UTC.

**Narrow result: the synthetic 4-V pin input exceeds the stated 3.3-V recommended pin rail. PGA scaling is not pin-voltage permission.** This card hands off missing inputs and evidence; it does not choose an attenuator, buffer, clamp or replacement ADC. An input-complete card is still **not circuit-qualified**.

## Blank input card

Keep unknowns explicit. Supply the accountable provider and evidence revision, page and test conditions with each answer.

| Required input | Supplied value / evidence (blank template) |
|---|---|
| Manufacturer, full orderable, ADC variant and package | Unknown — obtain BOM and matching source identity |
| Each AIN pin voltage versus ADC GND; common-mode and differential trajectories, extrema, overshoot and faults | Unknown — obtain bounded waveforms, not only differential amplitude |
| ADC/sensor/controller supply ranges and ripple, GND offsets, startup/shutdown sequence and powered-off pin states | Unknown — obtain schematic and all power-state requirements |
| Exact sensor identity, impedance versus frequency, bandwidth and signal dynamics | Unknown — obtain conditioned source evidence and signal bounds |
| External RC topology/values/tolerances; buffer identity, offset/bias/noise/dynamics; protection leakage and capacitance | Unknown — obtain schematic, BOM and applicable component evidence |
| PGA, rate, MUX history, continuous/single-shot mode, acquisition schedule and configuration-write/result timing | Unknown — obtain firmware sequence and result-to-configuration association |
| Accuracy, noise and settling targets; budget allocation, bandwidth and temperature range | Unknown — obtain requirements and evidence for each allocated error term |
| Controller thresholds/sink capability, pull-up rail/resistance, bus capacitance, measured edge timing and selected bus mode | Unknown — obtain controller and bus evidence, including power states |
| Bypass components/placement, supply stabilization and startup timing | Unknown — obtain layout and timing evidence |
| Analysis and validation owner/plan | Unknown — define operating/stress checks, acquisition/settling/error budget and validation |

## One synthetic worked input card — not a user board

All supplied values below are assumptions from the frozen practical report, not measured user-board data or newly established manufacturer guarantees. Unlisted information remains unknown.

| Field | Synthetic assumption / unresolved item |
|---|---|
| Device | Texas Instruments ADS1115IDGSR, ADS1115, DGS 10-pin VSSOP |
| Supply and pins | Nominal VDD 3.3 V, AINN=0 V, AINP=0–4.0 V; supply tolerance, GND offset, overshoot and power-state trajectories unknown |
| Configuration | PGA ±4.096 V; 860 SPS; MUX history, mode and configuration/acquisition timing unknown |
| Source/front end | Nominal 100-kohm sensor; impedance versus frequency, bandwidth and external RC unknown; buffer/protection presence and characteristics unknown |
| Performance | Desired error 1 mV, a synthetic requirement only; allocation, noise/settling targets, temperature and supporting evidence unknown |
| Interface and power | Controller, pull-ups, bus loading/timing, decoupling/layout and sequencing unknown |

### What must happen next, without designing a circuit here

1. **Manufacturer/source facts and missing guarantees:** Match the actual orderable and package to the source; obtain conditioned sensor, buffer, RC and protection evidence. The stored typical loading values do not establish a maximum source impedance or a guaranteed 1-mV error at 860 SPS. No qualified front end or worst-case settling guarantee is available from these annotations alone.
2. **Board/user inputs:** Replace or confirm every synthetic value; provide actual per-pin/common-mode/differential trajectories including overshoot, supply/GND offsets/ranges/sequencing and powered-off conditions. Provide sensor impedance versus frequency/bandwidth; RC values/tolerances, buffer errors/dynamics and protection leakage; acquisition mode/rate/channel/PGA history and write/result timing; accuracy/noise/settling targets and temperature. Controller/pull-up/timing/power-state questions remain required even for this analog-input handoff.
3. **Engineering analysis:** Check each pin against recommended operation separately from absolute stress. Establish a configuration-aware acquisition and error budget with sensor loading, RC/buffer dynamics, leakage, tolerances, noise and temperature, then define board-specific validation. Do not label an in-flight conversion with newly written channel/PGA settings. Input completion is not analysis completion or qualification.

At the synthetic upper endpoint, 4.0 V exceeds the recommended VDD-referenced upper rail of 3.3 V. The ±4.096-V PGA setting scales AINP minus AINN and does not permit either pin beyond its rail. This narrow comparison neither authorizes stress-limit operation nor chooses corrective components. The typical 6-Mohm common-mode / 4.9-Mohm differential loading is conditioned at ±2.048 V, 8 SPS, VDD=3.3 V, TA=25 C, not this synthetic configuration. One converter cycle is not proof of external sensor/RC/buffer settling. No complete 1-mV budget or accuracy claim is calculated.

## Frozen evidence boundary

The [practical report](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.md) and [machine receipt](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.json) were published at `b04fed50dff7853d5ad2663784eb0305bb02f331`. Technical replay instead uses immutable `0373a341d5e12d50778f899848a078621dfa4790`, tree `8c83b2cd3cc3a2443ab584ccd16768455c49dda0`.

Author replay used a clean `git archive` of the technical commit, initialized locally for CLI validation; tracked tree equality was checked. The synthetic local commit is not the historical commit. No original manufacturer bytes were fetched or re-audited. Runtime retrieval remains `canonical: false`, `human_reviewed: false` in source/fact payloads and `NOT_LOCALLY_VERIFIED`; historical Agent visual review is not new local byte verification, human acceptance or circuit qualification. `PUBLIC_REFERENCE` is not `OPEN_LICENSE`; restricted/unknown processing policies are not relaxed.

Pinned inputs (SHA-256):

- `knowledge/intake/ads1115-input-interface-constraints.json`: `746353eeab5df619970c2cc2767a440b7fe92e5914fa42577208fdb9e233b5e7`.
- `knowledge/intake/interface-ic-pilot.json`: `3738281495ba3e2fa1120e0f501239ab1608c6ce0781e7dc4b5c0f2b32b7ab55`.

The [existing application review](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/0373a341d5e12d50778f899848a078621dfa4790/knowledge/intake/ads1115-input-interface-constraints-review.md) retains its historical corrections and limitations. Scope is TI ADS1115IDGSR / ADS1115 / DGS 10-pin VSSOP, source `ads1115-app-ti-e-dgs`, electrical revision SBAS444E (December 2024). The October 14, 2025 packaging addendum is not a new electrical revision. Original byte identity recorded there is `eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834`; latest revision is not guaranteed.

## Literal retrieval and exclusion recipes

Run these seven commands from the clean pinned technical checkout. Exact UTF-8 stdout includes its trailing newline. Commands 1–3 must match the frozen machine receipt; 4–7 are additional structured exclusions, not new report cases.

```sh
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id ads1115-app-ti-e-dgs
python3 -B configs/pcbknowledge_agent.py --repo . intake search --device ADS1115IDGSR --parameter analog_input_pin_voltage
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --device ADS1015
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --device ADS1114
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --device ADS1115IDGST
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ads1115-app-ti-e-dgs --package 'RUG, 10-pin X2QFN'
```

| Command | Expected selection | Exact stdout SHA-256 |
|---|---|---|
| 1 | `ads1115-app-01`, `ads1115-app-02`, `ads1115-app-03`, `ads1115-app-04`, `ads1115-app-05`, `ads1115-app-06`, `ads1115-app-07`, `ads1115-app-08`, `ads1115-app-09` | `b62d31de68c7146b03018470bf284171984caff1382a1b41d08e2ad0d9965ade` |
| 2 | `ads1115-app-controller-uncertainty`, `ads1115-app-range-uncertainty`, `ads1115-app-sensor-uncertainty` | `5d70c4944687619c27e1dcb6708907d0fa2c1a62ae81510bf45494d9392a3fb3` |
| 3 | `b003-ti-ads1115-e-07` | `bdc52fe9afcc7ce28c2ba3c6aac16fd911bb1a167886f639e4d119916adfe1ed` |
| 4 | `[]` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 5 | `[]` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 6 | `[]` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 7 | `[]` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

Expected IDs follow the stored exact source scope: all nine `ads1115-app-01` through `ads1115-app-09` facts and all three source-local warnings. The exact device/parameter rail query selects only `b003-ti-ads1115-e-07` from the earlier interface pilot. ADS1015 and ADS1114 are different variants; ADS1115IDGST is not the selected full orderable; RUG 10-pin X2QFN is not DGS 10-pin VSSOP. Thus each scoped negative must return no candidates, not a family fallback. A no-match result means unavailable candidates in that scope, not compatibility, safety or proof that no other evidence exists. Neither exit zero nor a lexical match evaluates the synthetic circuit.

Author replay: all seven CLI commands exited 0. The first three exact stdout hashes matched the frozen receipt. Complete returned source/fact/issue objects were compared with pinned JSON, including additional evidence, conditions, all source-local warnings and noncanonical verification markers. All four negatives returned empty arrays. An initial local assertion helper used the wrong issue-wrapper key; it was corrected to `source_issue` before the complete passing replay. No repository code changed.

## Retained application values and complete conditions

These are existing small repository annotations, not new source extraction or new Fact records. Complete provenance remains in the pinned JSON and full replay payload. Historical `bbox: null` and Agent visual evidence are not human verification.

### `ads1115-app-01` — `PGA_full_scale`

Kind: `configuration_constraint`; unit: `V`. Value payload:

```json
{
  "magnitudes": [
    6.144,
    4.096,
    2.048,
    1.024,
    0.512,
    0.256
  ],
  "quantity": "AINP minus AINN",
  "control": "Config.PGA[2:0]"
}
```

Complete conditions: ADC scaling, not permission to exceed either input rail. With VDD=3.3 V and FSR=+/-4.096 V, differential magnitudes above 3.3 V are unavailable. Use existing recommended pin-rail record b003-ti-ads1115-e-07; stress limits do not authorize operation.

Evidence locator: 7.3.3; Table 7-1; printed page 15. Additional locators: 5.1 versus 5.3 (printed page 4). Existing references: `b003-ti-ads1115-e-07`.

### `ads1115-app-02` — `single_ended_range`

Kind: `application_guidance`; unit: `V`. Value payload:

```json
{
  "lower": 0,
  "upper": "lesser of VDD and positive full scale"
}
```

Complete conditions: ADS1115 single-ended MUX selection measures against GND and uses the positive half of differential scaling. Negative differential readings do not permit a negative pin voltage. Application guidance is not a new guaranteed specification.

Evidence locator: 9.1.2; Figure 9-2; printed page 29.

### `ads1115-app-03` — `input_loading`

Kind: `typical_characteristic`; unit: `Mohm`. Value payload:

```json
{
  "FSR_magnitude_V": 2.048,
  "common_mode_Mohm": 6,
  "differential_Mohm": 4.9
}
```

Complete conditions: VDD=3.3 V, DR=8 SPS, TA=25 C; typical only, not bounds. Switched-capacitor loading depends on PGA range. Common-mode measurement shorts AINP/AINN; differential measurement holds one input at 0.7 V. High source impedance can cause error; a buffer can add its own errors. No universal sensor-impedance allowance follows.

Evidence locator: 5.5 analog input; printed page 5. Additional locators: 7.3.2; Figure 7-5 (printed page 14).

### `ads1115-app-04` — `conversion_settling`

Kind: `conversion_behavior`; unit: `s`. Value payload:

```json
{
  "DR_SPS": [
    8,
    16,
    32,
    64,
    128,
    250,
    475,
    860
  ],
  "conversion_time": "1 / actual DR",
  "DR_variation_percent": [
    -10,
    10
  ]
}
```

Complete conditions: Config.DR[2:0] selects output rate. Converter settling is one conversion cycle; this does not certify settling of an external sensor, RC network or buffer. Data-rate tolerance is from electrical characteristics, all data rates; min/max apply TA=-40..125 C at VDD=3.3 V and FSR=+/-2.048 V unless otherwise noted.

Evidence locator: 7.3.6; printed page 15. Additional locators: 5.5 DR variation (printed page 5).

### `ads1115-app-05` — `configuration_change`

Kind: `conversion_behavior`; unit: `null`. Value payload:

```json
{
  "continuous": "in-flight conversion uses old settings; subsequent conversions use new settings",
  "single_shot": "OS starts one conversion from power-down; approximate 25 us wake-up precedes conversion"
}
```

Complete conditions: Config.MODE=0 continuous, MODE=1 single-shot. Channel/PGA changes must not relabel the current result as new-configuration data. Writing OS during an active conversion does not restart it. Approximate wake-up is not a guaranteed worst-case system latency.

Evidence locator: 7.4.2.1-7.4.2.2; printed page 18.

### `ads1115-app-06` — `digital_interface_voltage`

Kind: `electrical_limits`; unit: `V`. Value payload:

```json
{
  "VIH_min": "0.7 * VDD",
  "VIH_max": 5.5,
  "VIL_min": "GND",
  "VIL_max": "0.3 * VDD",
  "VOL_max_at_IOL_3mA": 0.4
}
```

Complete conditions: Electrical table VDD=3.3 V, DR=8 SPS, FSR=+/-2.048 V unless otherwise stated; min/max TA=-40..125 C. VOL condition IOL=3 mA. Controller thresholds, sink capability, supply state and pull-up rail still require comparison; not blanket level-shifter compatibility.

Evidence locator: 5.5 digital input/output; printed page 5. Additional locators: 5.3 digital input operating range (printed page 4).

### `ads1115-app-07` — `I2C_fast_mode_timing`

Kind: `timing_requirement`; unit: `null`. Value payload:

```json
{
  "fSCL_MHz": [
    0.01,
    0.4
  ],
  "tLOW_min_ns": 1300,
  "tHIGH_min_ns": 600,
  "tR_max_ns": 300,
  "tF_max_ns": 300,
  "tSUDAT_min_ns": 100,
  "tHDDAT_min_ns": 0,
  "tBUF_min_ns": 600,
  "tHDSTA_min_ns": 600,
  "tSUSTA_min_ns": 600,
  "tSUSTO_min_ns": 600
}
```

Complete conditions: Fast-mode table, VDD=2.0..5.5 V over operating ambient temperature (-40..125 C). All timings, rise/fall behavior and bus loading matter; frequency alone is insufficient. High-speed mode has different limits and requires its controller-code entry sequence; this annotation does not qualify Hs operation.

Evidence locator: 5.6; Figure 5-1; printed page 6. Additional locators: 7.5.1.3 (printed page 20).

### `ads1115-app-08` — `I2C_pullup_selection`

Kind: `application_guidance`; unit: `kohm`. Value payload:

```json
{
  "example_typical_kohm": [
    1,
    10
  ],
  "dependency": [
    "bus capacitance",
    "bus speed",
    "driver low-level capability"
  ]
}
```

Complete conditions: Typical application example only, not a permitted resistor interval for every board. Larger values slow edges; excessively small values can prevent a valid low level. Existing pin/pull-up connection and SDA-address hold records remain authoritative references. Application section does not provide a board qualification.

Evidence locator: 9; 9.1.1; Figure 9-1; printed page 28. Additional locators: 9.1.6; Figure 9-4 (printed page 31). Existing references: `b003-ti-ads1115-e-02`, `b003-ti-ads1115-e-06`.

### `ads1115-app-09` — `decoupling_and_startup`

Kind: `power_supply_guidance`; unit: `null`. Value payload:

```json
{
  "minimum_decoupling_uF": 0.1,
  "startup_wait_approx_us": 50
}
```

Complete conditions: Place low-ESR/ESL MLCC close to VDD with low-impedance GND connections. Wait approximately 50 us after VDD stabilizes before communication. This recommendation does not prove a particular board noise or startup margin.

Evidence locator: 10.1-10.2; Figure 10-1; printed page 37.

### Existing rail reference — not a duplicated annotation

`b003-ti-ads1115-e-07`, source `ti-ads1115-e`, is the separate `recommended_operating` / `analog_input_pin_voltage` record: each selected input separately has GND minimum and VDD maximum references, in volts. Its full conditions state that differential full-scale range is not permission to exceed supply rails and recommended ambient is −40 to 125 C (section 5.3). Locator: SBAS444E, printed page 4, section 5.3 analog-input row and footnotes 1–2. This reference does not relabel stress limits as operating permission or alter the original record.

## Complete unresolved warning payloads

All three remain `UNRESOLVED_APPLICATION_INPUTS`. Synthetic values do not resolve these warnings. Complete existing issue objects below preserve their question, missing inputs, conclusion and historical evidence/provenance; each of the nine application candidates carries all three.

### `ads1115-app-controller-uncertainty`

```json
{
  "id": "ads1115-app-controller-uncertainty",
  "source_id": "ads1115-app-ti-e-dgs",
  "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
  "question": "Is the proposed controller/pull-up/bus electrically compatible?",
  "missing_inputs": [
    "controller thresholds and sink-current limits",
    "pull-up voltage/resistance",
    "total bus capacitance and measured edge timing",
    "power sequencing and selected bus mode"
  ],
  "conclusion": "Not established for an unspecified system. PGA scaling does not relax pin operating limits; source candidates and zero matches are not electrical permission.",
  "evidence": {
    "url": "https://www.ti.com/lit/ds/symlink/ads1115.pdf",
    "revision": "SBAS444E",
    "pdf_page_index": 5,
    "printed_page": 6,
    "section": "5.6",
    "bbox": null,
    "visual_checked": true,
    "collector": "agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints",
    "source_sha256": "eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834",
    "evidence_level": "BYTE_IDENTIFIED_TEXT_AND_VISUAL",
    "method": "Collector and separate Agent reviewer inspected actual SHA-identified original PDF text and cited rendered pages; unresolved application inputs remain unknown.",
    "reviewer": "agent:/root/curate_pcbknowledge_constraints/review_constraint_batches"
  },
  "collector": "agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints"
}
```

### `ads1115-app-range-uncertainty`

```json
{
  "id": "ads1115-app-range-uncertainty",
  "source_id": "ads1115-app-ti-e-dgs",
  "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
  "question": "Can the selected PGA accept a signal above the ADC supply?",
  "missing_inputs": [
    "actual per-pin voltage and common-mode trajectory",
    "supply and overshoot bounds"
  ],
  "conclusion": "Not established for an unspecified system. PGA scaling does not relax pin operating limits; source candidates and zero matches are not electrical permission.",
  "evidence": {
    "url": "https://www.ti.com/lit/ds/symlink/ads1115.pdf",
    "revision": "SBAS444E",
    "pdf_page_index": 14,
    "printed_page": 15,
    "section": "7.3.3",
    "bbox": null,
    "visual_checked": true,
    "collector": "agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints",
    "source_sha256": "eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834",
    "evidence_level": "BYTE_IDENTIFIED_TEXT_AND_VISUAL",
    "method": "Collector and separate Agent reviewer inspected actual SHA-identified original PDF text and cited rendered pages; unresolved application inputs remain unknown.",
    "reviewer": "agent:/root/curate_pcbknowledge_constraints/review_constraint_batches"
  },
  "collector": "agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints"
}
```

### `ads1115-app-sensor-uncertainty`

```json
{
  "id": "ads1115-app-sensor-uncertainty",
  "source_id": "ads1115-app-ti-e-dgs",
  "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
  "question": "Can the high-impedance sensor meet settling and accuracy after channel/PGA changes?",
  "missing_inputs": [
    "sensor impedance versus frequency",
    "external RC and buffer dynamics",
    "chosen PGA/rate/mode and temperature",
    "permitted error and acquisition timing"
  ],
  "conclusion": "Not established for an unspecified system. PGA scaling does not relax pin operating limits; source candidates and zero matches are not electrical permission.",
  "evidence": {
    "url": "https://www.ti.com/lit/ds/symlink/ads1115.pdf",
    "revision": "SBAS444E",
    "pdf_page_index": 13,
    "printed_page": 14,
    "section": "7.3.2",
    "bbox": null,
    "visual_checked": true,
    "collector": "agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints",
    "source_sha256": "eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834",
    "evidence_level": "BYTE_IDENTIFIED_TEXT_AND_VISUAL",
    "method": "Collector and separate Agent reviewer inspected actual SHA-identified original PDF text and cited rendered pages; unresolved application inputs remain unknown.",
    "reviewer": "agent:/root/curate_pcbknowledge_constraints/review_constraint_batches"
  },
  "collector": "agent:/root/curate_pcbknowledge_constraints/collect_ads1115_constraints"
}
```

## Independent review and publication

Independent reviewer: `agent:/root/prepare_adc_mosfet_input_cards/review_adc_mosfet_cards`, separate from the author, reviewed on 2026-10-28 at 08:25–08:28 UTC. The reviewer independently replayed all seven declared commands in a clean checkout of exact `0373a341d5e12d50778f899848a078621dfa4790`. The first three full stdout hashes matched the frozen receipt; complete source/fact/issue objects matched stored JSON. All four scoped negatives returned `[]` with the declared identity/package exclusions. The reader reviewed the blank card, single synthetic example, all nine facts, rail reference and three complete warnings. No original-byte verification, human acceptance or circuit qualification was performed. Final combined-tree gates remain separate from these documentation/retrieval checks. The coordinator records the final document SHA-256 and exact published commit/tree, preservation diff, actual gate results and terminal exact-commit CI in the external issue receipt; a document cannot embed its own stable byte hash. No pending check is a pass. No annotation acceptance, warning, source policy or historical receipt is changed by this handoff.
