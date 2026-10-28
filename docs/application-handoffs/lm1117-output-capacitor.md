# LM1117 output-capacitor application handoff

Issue #26 · author: `agent:/root/prepare_pcb_application_evidence_docs/author_lm1117_handoff` · authored/replayed 2026-10-28 UTC.

**Decision: input and qualification evidence are incomplete. A nominal 10 µF value alone does not establish compliance.** This is a reusable input handoff, not an electrical solver, capacitor recommendation, or board approval. Even a fully populated card is not circuit qualification.

## Blank input card

Fill unknowns explicitly; attach the evidence revision, page/test conditions, and accountable provider rather than guessing.

| Input | Supplied value / evidence (blank template) |
|---|---|
| Regulator manufacturer, full orderable MPN, adjustable/fixed/temperature variant, package | Unknown — obtain BOM/orderable and matching source |
| VIN nominal, minimum/maximum at regulator pins, ripple frequency/amplitude, startup and fault/transient envelope | Unknown — obtain supply and measured/required waveform bounds |
| VOUT target, allowed static/dynamic tolerance, resistor network and CADJ | Unknown — obtain schematic and accuracy budget |
| Load minimum/maximum, zero-load duration, explicit preload, startup and dynamic step magnitude/slew/duration | Unknown — obtain load profile, including regulator/divider contributions |
| Output capacitor exact manufacturer/MPN, technology, nominal C, tolerance, voltage rating, quantity and connection | Unknown — obtain BOM and manufacturer documentation |
| Effective output C across applied DC bias, temperature, tolerance and aging | Unknown — obtain applicable curves/limits and worst-case methodology |
| ESR versus frequency, temperature and bias; applicable manufacturer test method | Unknown — obtain applicable ESR/impedance data and stability-condition interpretation |
| Input capacitor identity, effective C/impedance, placement and supply impedance | Unknown — obtain schematic, layout and source evidence |
| Ambient range, junction limit, airflow, enclosure, copper area/weight/layers/vias and package/tab attachment | Unknown — obtain board geometry and thermal boundary conditions |
| Validation plan and owner | Unknown — define stability/transient, minimum-load, headroom and thermal verification |

## One synthetic filled example — not a user board

Every supplied value below is an **assumption for this example**, not a manufacturer claim or known user design. Unlisted information stays unknown.

| Field | Synthetic assumption / unresolved item |
|---|---|
| Regulator | Texas Instruments LM1117, adjustable, standard temperature, DCY SOT-223; exact full orderable unresolved; **not fixed LM1117-3.3** |
| Supply/output | Nominal VIN 5 V, range 4.75–5.25 V; target VOUT 3.3 V; ripple/transient envelope and output tolerance unknown |
| Load | 0–500 mA; zero-load behavior, preload and dynamic profile unknown |
| Ambient/layout | Ambient 50 °C; copper geometry, airflow, enclosure and junction temperature unknown |
| Capacitors | No CADJ; nominal 10 µF ceramic output capacitor; exact MPN, tolerance, voltage rating, effective-C and ESR evidence unknown; input capacitor unknown |

### Questions and work this example must hand off

1. **Missing manufacturer/source facts:** Which exact TI orderable and matching package/temperature variant will be purchased? Supply the capacitor manufacturer and exact MPN, technology, tolerance and rating. Supply effective-C limits over bias, temperature, tolerance and aging, plus ESR/impedance versus frequency and temperature and the applicable test methods. An MPN alone does not prove suitability. The bounded TI annotation does not establish qualification of this unspecified ceramic substitute. ST's missing numeric ESR envelope remains missing, not filled by TI's range.
2. **Missing board/user inputs:** Confirm the assumed values or replace them with actual requirements. What ripple/transients reach VIN? What VOUT error and load steps are permitted? Does zero external load have a documented preload/divider load? What input capacitor and interconnect impedance are present? What copper, airflow and enclosure determine heat removal? Ambient 50 °C is not junction temperature.
3. **Engineering analysis still required:** Establish applicable source limits for the actual part and capacitor, worst-case effective C and ESR, control-loop/stability and transient behavior, minimum load, VIN-to-VOUT headroom under tolerance/ripple/transients, and a board-specific dissipation/junction-temperature budget and validation. Typical dropout/current-limit numbers and a single thermal resistance are not continuous-current permission. No numerical board pass/fail is calculated here.

TI's annotated output guidance includes capacitance **and ESR**, technology and CADJ dependence. Nominal 10 µF ceramic therefore remains unqualified. Do not transfer TI limits into ST, fixed-output, LM1117I, another package, or another orderable. The existing KEMET `C0603C104K5RACTU` record is **100 nF**, not evidence qualifying a matching 10 µF output capacitor. No capacitor search or substitute recommendation was performed.

## Frozen evidence and replay boundary

The [practical report](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.md), [machine receipt](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.json), and [LDO review/recipes](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/knowledge/intake/ldo-application-constraints-review.md) remain immutable. Replay uses source commit `0373a341d5e12d50778f899848a078621dfa4790`, tree `8c83b2cd3cc3a2443ab584ccd16768455c49dda0`, not the later moving main branch.

Author replay: clean `git archive` of that commit, initialized locally for CLI validation, with identical tracked tree and no source originals. This synthetic local commit is not asserted to be the historical commit. No manufacturer bytes were fetched or re-audited. Historical visual provenance stays historical; clean-checkout runtime evidence remains `NOT_LOCALLY_VERIFIED`. Selected wrappers and their facts preserve `canonical: false` and `human_reviewed: false`.

Input: `knowledge/intake/ldo-application-constraints.json` SHA-256 `defbd7220856312f4d7100c9122bb5ca33892412c37941bf7d24869b90757e53`.

### Literal frozen commands

Run from a clean checkout of the pinned commit. Exact UTF-8 stdout including trailing newline must match the frozen receipt, not just the count.

```sh
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id ldo-app-ti-lm1117-q
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id ldo-app-st-ld1117-r38
```

| Command order | Selected IDs | Exact stdout SHA-256 |
|---|---|---|
| 1 | `ldo-app-ti-01`, `ldo-app-ti-02`, `ldo-app-ti-03`, `ldo-app-ti-04` | `9928249839070cf0b64cf36f9c919b37f68fc04a0ffce91c543fa3daf38d2afd` |
| 2 | `ldo-app-ti-orderable-capacitor-gap`, `ldo-app-ti-operating-point-gap` | `182eec1d616c173d6a5ccba62b1367cdfacca021a63857b8ad73c1483e831e28` |
| 3 | `ldo-app-st-01`, `ldo-app-st-02`, `ldo-app-st-03`, `ldo-app-st-04` | `970a8abd1dc43d12275cab5d1bd54cb3c9636ca2b5c634654b719b8a131fd0fc` |
| 4 | `ldo-app-st-capacitor-gap`, `ldo-app-st-operating-point-gap` | `23896836c2353919b2c3e35abbc834e46f28bef5744f4b7d616f061176198aba` |

### Operating-point and exclusion recipes

The following are additional literal commands, using the same pinned checkout and prefix. Each positive query returns its complete fact, source and both source-local warnings, not a stripped value. The five identity exclusions return `[]`, not a substituted family result.

```sh
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter capacitor_requirements
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter dropout
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter load_and_current_limit
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --parameter thermal_budget
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter capacitor_requirements
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter dropout
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter load_and_output_current
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --parameter thermal_budget
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --manufacturer STMicroelectronics
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --device LM1117-3.3
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-ti-lm1117-q --device LM1117IMP-ADJ/NOPB
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --device LD1117SC-R
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ldo-app-st-ld1117-r38 --package DPAK
```

Author result: all 17 commands exited 0. The first four stdout hashes equal the frozen machine receipt. Each of eight parameter queries was compared by full JSON object equality against the pinned batch's fact, source, and complete source-local issue objects; wrapper flags and `NOT_LOCALLY_VERIFIED` were asserted. All five exclusions returned empty arrays. This tests retrieval and preserved boundaries, not physical behavior.

## Selected payloads: values and complete conditions

The following values and conditions are the existing repository annotations, not new source extraction. Full evidence objects remain in the pinned input and returned payloads; `bbox: null` and prior agent visual provenance are not human verification.

### `ldo-app-ti-lm1117-q`

Manufacturer: Texas Instruments; device: LM1117; variant: adjustable; standard temperature; not LM1117I or fixed output; package: DCY, SOT-223; full orderable: `null`. Revision: `SNOS412Q` (2023-01). Original SHA-256: `c117f5dd97fd15e62c0dee3adbf1af60480a128a10a0f9a9c28aafb8220ec3aa`. Latest revision is not guaranteed.

The 2026-06-08 packaging addendum and 2026-08-10 package-material appendix do not replace the January 2023 electrical revision.

#### `ldo-app-ti-01` — `capacitor_requirements`

Kind: `application_guidance`. Value payload:

```json
{
  "input_example_uF": 10,
  "input_example_technology": "tantalum",
  "output_min_uF": 10,
  "output_technology": "tantalum",
  "output_ESR_ohm": [
    0.3,
    22
  ],
  "output_with_CADJ_uF": 22
}
```

Complete conditions: Adjustable LM1117. Input is recommended guidance, not a universal minimum. Output requirements include capacitance AND ESR; CADJ changes output requirement. Application section is not a warranted component specification. Equal nominal ceramic capacitance alone is insufficient.

Evidence locator: 9.2.1; 9.2.2.1.1 and 9.2.2.1.3; printed pages [14, 15].

#### `ldo-app-ti-02` — `dropout`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "load_mA": [
    100,
    500,
    800
  ],
  "typ_V_at_TJ_25_C": [
    1.1,
    1.15,
    1.2
  ],
  "max_V_over_TJ_0_to_125_C": [
    1.2,
    1.25,
    1.3
  ]
}
```

Complete conditions: LM1117, not LM1117I. Dropout criterion: output 100 mV below its nominal value at VIN=VOUT+1.5 V. Typical columns are not worst-case limits; do not interpolate a new guarantee or substitute an untested load/temperature.

Evidence locator: 7.5 dropout rows and footnotes 1,2,4; printed pages [6].

#### `ldo-app-ti-03` — `load_and_current_limit`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "minimum_load_typ_mA": 1.7,
  "minimum_load_max_mA": 5,
  "current_limit_min_mA": 800,
  "current_limit_typ_mA": 1200,
  "current_limit_max_mA": 1500
}
```

Complete conditions: Minimum load: adjustable, VIN=15 V, typical TJ=25 C, maximum over TJ=0..125 C. Current limit: VIN-VOUT=5 V, TJ=25 C. Current-limit value is not continuous-load thermal entitlement.

Evidence locator: 7.5 minimum load/current limit and footnote 5; printed pages [6].

#### `ldo-app-ti-04` — `thermal_budget`

Kind: `application_guidance`. Value payload:

```json
{
  "dissipation_expression": "PD=(VIN-VOUT)*IL+VIN*IG",
  "required_thermal_resistance_expression": "RthetaJA<=(125-TAmax)/PD",
  "SOT223_design_aid_examples": [
    {
      "top_copper_in2": 0.0123,
      "bottom_copper_in2": 0,
      "RthetaJA_C_per_W": 136
    },
    {
      "top_copper_in2": 1,
      "bottom_copper_in2": 0,
      "RthetaJA_C_per_W": 66
    }
  ]
}
```

Complete conditions: LM1117 TJ=0..125 C. Table 9-2/Figure 9-11 design aid: SOT-223, 1-oz copper, tab on topside copper, still air, TA=25 C for thermal-resistance curve. These are test-layout guidance, not universal board metrics. Actual ambient, copper, airflow, dissipation and load remain required.

Evidence locator: 9.5 thermal design; equations 2-5; Table 9-2 and Figure 9-11; printed pages [18, 19].

Source-local unresolved warnings (neither resolved by supplying synthetic inputs):

- **`ldo-app-ti-orderable-capacitor-gap`** — `UNRESOLVED_APPLICATION_QUALIFICATION`: Full TI orderable remains unknown. Capacitor ESR/effective capacitance over bias, temperature and tolerance are unverified; same nominal value or ceramic substitution is not established. Do not transfer fixed-output, LM1117I, ST or another-package claims.
- **`ldo-app-ti-operating-point-gap`** — `UNRESOLVED_APPLICATION_QUALIFICATION`: Requested VIN/VOUT/load, junction/ambient range, board copper and airflow are unspecified. Low headroom or high dissipation cannot be approved from typical dropout/current limit or one thermal metric. Prior pin/stress records remain separate, not operating permission.

### `ldo-app-st-ld1117-r38`

Manufacturer: STMicroelectronics; device: LD1117STR; variant: adjustable; standard temperature; not C grade or fixed output; package: SOT-223; full orderable: `LD1117STR`. Revision: `DocID2572 Rev 38` (2025-01-27). Original SHA-256: `4fd8415a20d932fdc1de5be99e1aa5d2af1546f05c0a785a047ff93420364348`. Latest revision is not guaranteed.

#### `ldo-app-st-01` — `capacitor_requirements`

Kind: `application_guidance`. Value payload:

```json
{
  "output_stability_min_uF": 10,
  "adjustable_example_input_uF": 10,
  "adjustable_example_output_uF": 10,
  "optional_R2_bypass_uF": 10,
  "optional_R2_bypass_technology": "electrolytic",
  "guaranteed_ESR_range_ohm": null,
  "general_input_minimum_uF": null
}
```

Complete conditions: ST adjustable lane. Cover gives stability minimum; Figure 10 input/output values are application examples. R2 bypass improves ripple rejection. No numeric ESR envelope or ceramic-replacement qualification established by inspected source. Do not import TI ESR requirements.

Evidence locator: Description; section 7, Figures 10-11; printed pages [1, 24].

#### `ldo-app-st-02` — `dropout`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "load_mA": [
    100,
    500,
    800
  ],
  "typ_V": [
    1,
    1.05,
    1.1
  ],
  "max_V": [
    1.1,
    1.15,
    1.2
  ]
}
```

Complete conditions: Table 8 adjustable standard-temperature device; TJ=0..125 C, CO=10 uF, refer to test circuits unless otherwise specified. No transfer to fixed output/C grade or another package/orderable; typical values are not maximum guarantees.

Evidence locator: 5, Table 8 dropout rows and heading; printed pages [14].

#### `ldo-app-st-03` — `load_and_output_current`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "minimum_load_typ_mA": 2,
  "minimum_load_max_mA": 5,
  "output_current_min_mA": 800,
  "output_current_typ_mA": 950,
  "output_current_max_mA": 1300
}
```

Complete conditions: Table 8: CO=10 uF. Minimum load at VIN=15 V, TJ=0..125 C. Output-current characteristic at VIN-VOUT=5 V and TJ=25 C, labeled Output current by source, not a continuous board entitlement. Do not silently rename it a guaranteed current-limit threshold.

Evidence locator: 5, Table 8 minimum load and Output current rows; printed pages [14].

#### `ldo-app-st-04` — `thermal_budget`

Kind: `thermal_metric`. Value payload:

```json
{
  "RthJC_C_per_W": 15,
  "RthJA_C_per_W": 110,
  "table_board_geometry": null,
  "table_airflow": null,
  "qualified_continuous_load_mA": null
}
```

Complete conditions: Table 2 SOT-223 only. Board/airflow details are not supplied there; 110 C/W is not a universal board value. Standard-grade junction bounds are in existing stress record and must not become an unconditional operating permission. No proposed board/ambient/load budget is available.

Evidence locator: 3, Table 2; Table 1 context; printed pages [7].

Source-local unresolved warnings (neither resolved by supplying synthetic inputs):

- **`ldo-app-st-capacitor-gap`** — `UNRESOLVED_APPLICATION_QUALIFICATION`: ST numeric ESR envelope, general input-capacitor minimum and ceramic replacement qualification remain unavailable in this bounded source. TI capacitor conditions cannot fill these gaps; component effective-capacitance/ESR evidence is missing.
- **`ldo-app-st-operating-point-gap`** — `UNRESOLVED_APPLICATION_QUALIFICATION`: Requested operating point and board conditions are unspecified. Table 8 output-current characteristic and Table 2 thermal numbers do not establish continuous safe current. Table 1 total power/stress limits are not operating permission; no TI or C-grade substitution.

## Review and publication receipt

Independent reviewer: `agent:/root/prepare_pcb_application_evidence_docs/review_application_evidence_docs`, reviewed 2026-10-28 at 06:37 UTC. Independently replayed all 17 literal commands in a detached clean checkout of `0373a341d5e12d50778f899848a078621dfa4790`: four exact stdout hashes matched the frozen receipt, eight parameter results matched complete selected JSON objects, and five identity exclusions returned empty arrays. Reviewed the blank card, single synthetic example, all selected values/conditions, source separation and unresolved warnings. No manufacturer originals were fetched or visually re-audited for this review; this is documentation/retrieval review, not human approval or physical qualification. Final document SHA-256 and exact publication commit belong in the external issue/review receipt (a document cannot contain its own stable byte hash). No annotation acceptance status or source warning is changed by this handoff.
