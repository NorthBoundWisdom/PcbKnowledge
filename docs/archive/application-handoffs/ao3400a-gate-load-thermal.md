# AO3400A gate/load/thermal application handoff

Issue #29 · author: `agent:/root/prepare_adc_mosfet_input_cards/author_ao3400a_card` · authored/replayed 2026-10-28 at 08:26 UTC.

**Decision: the nominal 1.8-V switching case is not qualified. Threshold is not useful-load drive, and input completeness is not circuit qualification.** This is one bounded input handoff, not a component solver, parts recommendation or new collection.

## Blank input card

Keep missing entries explicitly unknown. Supply the evidence revision, applicable conditions and accountable provider for each entry.

| Input | Supplied value / evidence (blank template) |
|---|---|
| Manufacturer, exact full orderable, package and source revision | Unknown — provide BOM identity and matching manufacturer evidence |
| Numbered terminal-to-function mapping, orientation and CAD footprint | Unknown — provide explicit exact-device evidence; generic SOT23 convention is insufficient |
| Topology and supply/load voltage at device pins | Unknown — provide schematic, tolerance, startup/shutdown and transient waveforms |
| Actual GPIO/driver VOH and VOL, source/sink capability under gate load and temperature | Unknown — provide controller limits and loaded dynamic behavior, not nominal logic rail alone |
| VGS trajectory, source bounce and controller/source ground offsets | Unknown — provide bounds including overshoot, negative excursions and powered-off states |
| Supply/enable sequencing and gate network | Unknown — provide sequencing, gate resistance/pull-down, driver impedance and parasitics |
| Load current waveform and inductive energy | Unknown — provide inrush, steady/pulsed/repetitive current, inductance and commutation conditions |
| Clamp/freewheel/protection behavior | Unknown — provide circuit and load-dependent voltage/current/energy waveforms |
| Rise/fall/delay, actual PWM duty/frequency and burst/history | Unknown — provide timing targets and actual gate/drain trajectories |
| Copper geometry/weight, stackup, mounting, thermal path, enclosure and airflow | Unknown — provide actual PCB boundary conditions; test-board resistance is not universal |
| Ambient range, junction limits/margin and thermal validation | Unknown — separate ambient from junction; provide analysis/measurement plan |
| Analysis and validation owner | Unknown — assign gate-drive, waveform/SOA, losses, thermal and identity verification |

## One synthetic filled example — not a user board

Every supplied value is an invented input from the frozen practical evaluation, **not a private board fact or manufacturer recommendation**. Missing values are not silently assigned defaults.

| Field | Synthetic assumption / unresolved item |
|---|---|
| Device/topology | Alpha & Omega Semiconductor AO3400A, SOT23, N-channel low-side switch; full orderable suffix and numeric terminal mapping unknown |
| Controller | Nominal 1.8-V GPIO; actual VOH/source/sink current versus load and temperature unknown |
| Supply/load | Nominal 12-V / 2-A load; supply tolerance, current/voltage trajectory, inductance, energy and protection unknown |
| Switching | Nominal 20-kHz PWM; duty, bursts, rise/fall/delay, source bounce, gate network and sequencing unknown |
| Thermal | Ambient 50 °C; junction temperature, copper/stackup, mounting, airflow/enclosure and thermal path unknown |

### Three distinct handoff queues

1. **Source facts and missing guarantees:** The 0.65–1.45-V threshold is tested at only 250 uA, VDS=VGS, TJ=25 °C. It does not guarantee useful load conduction. The lowest tabulated RDS(on) drive is 2.5 V, at 3 A and TJ=25 °C, with 48 milliohms maximum; the 3-A electrical test point is not a load recommendation. No guaranteed 1.8-V RDS(on), hot 1.8-V bound or hot 2.5-V maximum follows. Exact full ordering identity and numeric terminal mapping still need applicable evidence. Do not substitute AO3400, AO3400AL, AO3401A or another vendor.
2. **User/board inputs:** What loaded VOH/VOL and source/sink currents are guaranteed across temperature? What are actual gate-to-source waveforms, source bounce and ground offsets? How do supplies and enables sequence, and what gate resistance/pull-down/driver impedance are present? What load current/voltage waveforms, inductance, stored energy and clamp/freewheel paths apply? What duty/burst/history, rise/fall/delay and switching frequency apply? What copper/stackup/mounting/airflow and thermal path determine junction temperature? Which explicit terminal mapping and viewing orientation support the CAD footprint? Replace synthetic values with evidence rather than treating this card as a known design.
3. **Engineering analysis and validation:** Establish applicable gate-drive bounds, switching and conduction loss across actual trajectories, waveform/SOA/transient margins, protection energy and commutation, and a board-specific thermal/junction budget and validation. Nominal 12 V / 2 A alone establishes none of these. Typical capacitance does not establish a safe PWM frequency. Short-duration ratings do not approve continuous current. Ambient 50 °C is not junction temperature. No numerical circuit pass/fail, safe current, PWM limit or component choice is computed here.

Do not automatically select a driver, MOSFET, TVS or diode. A cataloged 5-V TVS is not thereby a 12-V switching-stage solution: actual clamp/load waveforms and conditions are required. Even all requested inputs supplied would not by itself qualify the circuit.

## Immutable evidence and exact replay

The [frozen report](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.md) and [command/ID/stdout receipt](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.json) were published at `b04fed50dff7853d5ad2663784eb0305bb02f331`. Their technical replay snapshot is separately `0373a341d5e12d50778f899848a078621dfa4790`, tree `8c83b2cd3cc3a2443ab584ccd16768455c49dda0`.

Author replay used a clean archive of that technical commit, Git-initialized for workspace validation; its committed tree matched exactly. The local synthetic commit is not asserted to be the historical public commit. No original manufacturer bytes were fetched, opened or re-audited. Historical source visual provenance is not new local byte verification, human review or circuit acceptance. Wrappers remain `canonical: false`; source/fact `human_reviewed: false`; retrieval `NOT_LOCALLY_VERIFIED`.

Pinned input: [ao3400a-gate-drive-constraints.json](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/0373a341d5e12d50778f899848a078621dfa4790/knowledge/intake/ao3400a-gate-drive-constraints.json), SHA-256 `2352020939f6f1c88dd714c31fb491672c6f5da300a76a41c5a5e1f7ec05b0ce`. Its [historical review](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/0373a341d5e12d50778f899848a078621dfa4790/knowledge/intake/ao3400a-gate-drive-constraints-review.md) remains unchanged.

Run these four literal commands from the clean pinned technical checkout:

```sh
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ao3400a-aos-r3p1-sot23
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id ao3400a-aos-r3p1-sot23
python3 -B configs/pcbknowledge_agent.py --repo . intake search --device AO3400
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ao3400a-aos-r3p1-sot23 --package SOT-223
```

| Command order | Expected selection | Exact UTF-8 stdout SHA-256, including trailing newline |
|---|---|---|
| 1 | `ao3400a-drive-01`, `ao3400a-drive-02`, `ao3400a-drive-03`, `ao3400a-drive-04`, `ao3400a-drive-05`, `ao3400a-drive-06`, `ao3400a-drive-07`, `ao3400a-drive-08` | `3574cfdf7585a8ec5a6ecd772a100261b05bfa29ac5fe4dae5301839518b94b9` |
| 2 | `ao3400a-numbered-pin-identity-unknown`, `ao3400a-gate-load-transient-inputs-unknown`, `ao3400a-pcb-thermal-inputs-unknown` | `521172a6cc201497cceddf508746d138d913d8d9939fac4997b29537b71f4fcb` |
| 3 | Empty array; no AO3400 candidate, no AO3400A substitution | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 4 | Empty array; excludes all eight IDs listed in row 1 | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

All four author commands exited 0. The first three exact stdout hashes match the frozen receipt. The fourth is an additional supported structured-package negative, not a retroactive addition to that receipt. Expected exclusions derive from inspecting the stored scope: all eight facts have device `AO3400A` and package `SOT23`, not `AO3400` or `SOT-223`. An empty result means no scoped candidate; it proves neither electrical safety/compatibility nor absence of every possible source. A hit or exit zero does not evaluate the synthetic operating point.

Author comparison checked all eight complete fact objects, their source objects and all three attached warning objects per result, plus all three complete issue-query objects and their source objects, for equality with the pinned input. It also checked noncanonical/nonhuman flags and `NOT_LOCALLY_VERIFIED`. No warning was reduced to its identifier for comparison. This is retrieval/documentation verification, not physical validation.

## Existing annotated payloads and complete conditions

The following are repository-owned annotations, not new source extraction. Exact source scope is Alpha & Omega Semiconductor AO3400A N-channel, SOT23; source ID `ao3400a-aos-r3p1-sot23`; full orderable MPN is `null`. Revision **Rev 3.1, July 2023** is not a latest-revision guarantee. Historical original SHA-256 is `9c60d0b6c1ddc7609a4b788a91181468d8ffe6c3e9ba425c3d8ffc5ba88c5033` (317848 bytes, five pages); this handoff does not repeat that byte audit. Public reference is not an open redistribution license; originals and full extracts remain excluded.

Complete source/fact provenance is retained in the linked immutable JSON and compared in replay. Each fact has `bbox: null`, historical `BYTE_IDENTIFIED_TEXT_AND_VISUAL` evidence, collector `agent:/root/collect_mosfet_drive_constraints`, reviewer `agent:/root/collect_mosfet_drive_constraints/review_ao3400a_constraints`, and `AGENT_REVIEWED_UNDER_OWNER_DELEGATION` status. The historical method records independent byte recomputation and page inspection using the collector-acquired original, not an independent fresh reviewer download or human verification. These historical claims are not upgraded by this card.

### `ao3400a-drive-01` — `terminal_identity_and_body_diode_orientation`

Kind: `pin`. Value payload:

```json
{
  "channel_type": "N-channel",
  "terminal_labels": [
    "G",
    "S",
    "D"
  ],
  "body_diode": {
    "anode": "S",
    "cathode": "D"
  },
  "numbered_pin_assignment": null
}
```

Complete conditions: The exact AO3400A SOT23 drawing distinguishes top and bottom views and labels gate/source/drain, but does not print numerical pin identifiers. No 1/2/3 assignment, land pattern, or symbol-to-footprint mapping is inferred from a generic SOT23 convention. This terminal-level observation is not a complete pin map.

Evidence locator: SOT23 top/bottom illustrations and transistor symbol; PDF page index 0, printed page 1; supporting PDF pages [1]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-02` — `voltage_and_junction_stress_limits`

Kind: `absolute_maximum`. Value payload:

```json
{
  "VDS_max_V": 30,
  "VGS_min_V": -12,
  "VGS_max_V": 12,
  "TJ_min_C": -55,
  "TJ_max_C": 150
}
```

Complete conditions: Absolute-maximum stress ratings, TA=25 C unless noted; not an allowed continuous operating envelope, recommended gate drive, or avalanche-energy qualification. VGS is gate relative to source, not necessarily gate relative to system ground. Actual switching overshoot, supply tolerance and source movement remain unprovided.

Evidence locator: Absolute Maximum Ratings; PDF page index 0, printed page 1; supporting PDF pages [1]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-03` — `gate_threshold_test_not_full_enhancement`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "VGS_threshold_V": {
    "min": 0.65,
    "typ": 1.05,
    "max": 1.45
  },
  "test_ID_uA": 250,
  "test_voltage_relation": "VDS=VGS",
  "TJ_C": 25
}
```

Complete conditions: These values describe the low-current threshold test, not the gate voltage needed for an intended load, a guaranteed low RDS(on), or proof of compatibility with a controller. No 1.8-V, 2-V, or 3.3-V drive guarantee is derived from threshold or a typical transfer curve. Use the separate conditioned RDS(on) bounds rather than treating threshold as fully on.

Evidence locator: Electrical Characteristics VGS(th) row; Figure 2 typical transfer curve; PDF page index 1, printed page 2; supporting PDF pages [2, 3]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-04` — `on_resistance_maxima_at_specified_drive`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "test_points": [
    {
      "VGS_V": 10,
      "ID_A": 5.7,
      "TJ_C": 25,
      "RDS_on_typ_mOhm": 18,
      "RDS_on_max_mOhm": 26.5
    },
    {
      "VGS_V": 10,
      "ID_A": 5.7,
      "TJ_C": 125,
      "RDS_on_typ_mOhm": 28,
      "RDS_on_max_mOhm": 38
    },
    {
      "VGS_V": 4.5,
      "ID_A": 5,
      "TJ_C": 25,
      "RDS_on_typ_mOhm": 19,
      "RDS_on_max_mOhm": 32
    },
    {
      "VGS_V": 2.5,
      "ID_A": 3,
      "TJ_C": 25,
      "RDS_on_typ_mOhm": 24,
      "RDS_on_max_mOhm": 48
    }
  ]
}
```

Complete conditions: The maximum column provides conditioned bounds; typical values are not maxima. Current entries are electrical test points, not recommended load currents. The 125-C row applies to VGS=10 V and ID=5.7 A only: no elevated-temperature maximum at 2.5 V or 4.5 V is invented. No interpolation to a guaranteed 3.3-V value or extrapolation beyond stated conditions is made. Page-3 curves are typical; note E describes their <300-us pulses and <=0.5% duty, not a continuous-load qualification.

Evidence locator: Electrical Characteristics RDS(ON) rows; note E; Figures 3-5; PDF page index 1, printed page 2; supporting PDF pages [2, 3]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-05` — `drain_current_and_power_rating_context`

Kind: `absolute_maximum`. Value payload:

```json
{
  "continuous_ID_max_A_at_TA_C": {
    "25": 5.7,
    "70": 4.7
  },
  "cover_ID_gate_condition_VGS_V": 10,
  "pulsed_ID_max_A": 30,
  "PD_max_W_at_TA_C": {
    "25": 1.4,
    "70": 0.9
  },
  "PD_basis": {
    "TJ_max_C": 150,
    "thermal_interval_max_s": 10
  }
}
```

Complete conditions: The cover associates its 5.7-A summary with VGS=10 V; the absolute-maximum current rows are not a PCB load recommendation or proof of continuous 5.7-A operation on an arbitrary board. The 1.4/0.9-W dissipation ratings use the <=10-s junction-to-ambient resistance, not the steady-state value. Note C limits repetitive pulses by junction temperature, with low-frequency/duty conditions keeping initial TJ=25 C. No numerical usable pulse width, SOA point, avalanche capability or simultaneous VDS/current permission is inferred.

Evidence locator: Product Summary; Absolute Maximum Ratings; notes B/C/F; Figure 9 context; PDF page index 0, printed page 1; supporting PDF pages [1, 2, 4]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-06` — `junction_to_ambient_board_and_time_conditions`

Kind: `thermal_characteristic`. Value payload:

```json
{
  "RthetaJA_C_per_W": {
    "at_t_le_10_s": {
      "typ": 70,
      "max": 90
    },
    "steady_state": {
      "typ": 100,
      "max": 125
    }
  },
  "RthetaJL_steady_C_per_W": {
    "typ": 63,
    "max": 80
  },
  "measurement_board": {
    "material": "FR-4",
    "area_in2": 1,
    "copper_oz": 2,
    "air": "still",
    "TA_C": 25
  }
}
```

Complete conditions: Note A describes the measured board and explicitly makes junction-to-ambient resistance board-dependent. The cited 1-in2 board does not specify a transferable copper-pour geometry, layer stack, enclosure, airflow or heatsink for a proposed PCB. Do not substitute the short-duration resistance for continuous dissipation or treat a typical resistance as the maximum. Actual board thermal resistance and available junction-temperature margin remain UNKNOWN; no safe load current is calculated.

Evidence locator: Thermal Characteristics; notes A/B/D; PDF page index 0, printed page 1; supporting PDF pages [1, 2]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-07` — `body_diode_forward_and_recovery_conditions`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "VSD_V": {
    "typ": 0.7,
    "max": 1,
    "test_IS_A": 1,
    "test_VGS_V": 0
  },
  "body_diode_continuous_IS_max_A": 2,
  "reverse_recovery": {
    "trr_typ_ns": 8.5,
    "Qrr_typ_nC": 2.6,
    "test_IF_A": 5.7,
    "test_dI_dt_A_per_us": 100
  },
  "TJ_C": 25
}
```

Complete conditions: VSD has a maximum only at its stated test point; recovery entries are typical, not worst-case limits. The 2-A diode-current entry does not qualify a board for continuous diode heating or prove an inductive load is protected. The internal diode conducts from S toward D; it is not an automatically adequate flyback path for every external circuit. Actual commutation, dead time, inductance, pulse energy, transient voltage and thermal conditions remain unknown.

Evidence locator: Transistor symbol; Electrical Characteristics diode rows; diode-recovery test circuit; PDF page index 0, printed page 1; supporting PDF pages [1, 2, 5]. Source URL/revision/hash and historical provenance are the common values above.

### `ao3400a-drive-08` — `gate_charge_and_capacitance_test_dependencies`

Kind: `electrical_characteristic`. Value payload:

```json
{
  "gate_charge_nC": {
    "Qg_typ": 6,
    "Qg_max": 7,
    "Qgs_typ": 1.3,
    "Qgd_typ": 1.8
  },
  "gate_charge_test": {
    "VGS_V": 4.5,
    "VDS_V": 15,
    "ID_A": 5.7
  },
  "capacitance_typ_pF": {
    "Ciss": 630,
    "Coss": 75,
    "Crss": 50
  },
  "capacitance_test": {
    "VGS_V": 0,
    "VDS_V": 15,
    "frequency_MHz": 1
  },
  "TJ_C": 25
}
```

Complete conditions: Only Qg has a tabulated maximum here; Qgs, Qgd and capacitances are typical. Gate charge belongs to the listed voltage/current excursion, and capacitances are bias-dependent as Figure 8 illustrates; no fixed gate capacitance or worst-case 10-V gate charge is inferred. The generic page-5 gate-charge waveform is not substituted for the page-2 4.5-V table condition. Actual driver source/sink impedance, gate resistance, frequency and parasitics are unprovided; no GPIO drive capability, switching time/loss, or maximum PWM frequency is claimed.

Evidence locator: Electrical Characteristics dynamic and charge rows; Figures 7/8; gate-charge test circuit; PDF page index 1, printed page 2; supporting PDF pages [2, 4, 5]. Source URL/revision/hash and historical provenance are the common values above.

## Complete unresolved source warnings

The following complete warning objects remain attached to each selected fact. Synthetic inputs and the later bounded investigation resolve none of them.

```json
[
  {
    "id": "ao3400a-numbered-pin-identity-unknown",
    "source_id": "ao3400a-aos-r3p1-sot23",
    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
    "description": "The selected official Rev 3.1 PDF contains unnumbered G/S/D illustrations, not an explicit numerical terminal table. Numbered pins, land pattern and full ordering/packing identity remain UNKNOWN. Do not transfer a generic SOT23 map, AO3400, AO3401A or another vendor identity.",
    "provenance": {
      "actor": "agent:/root/collect_mosfet_drive_constraints",
      "recorded_at": "2026-10-28T04:19:22.291337+00:00"
    },
    "evidence_references": [
      "Rev 3.1 page 1 SOT23 illustrations"
    ]
  },
  {
    "id": "ao3400a-gate-load-transient-inputs-unknown",
    "source_id": "ao3400a-aos-r3p1-sot23",
    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
    "description": "Controller output levels at load, gate/source waveform, driver impedance, gate network, drain load, switching frequency, inductive energy and transient margins are unprovided. Threshold is not full enhancement; conditioned on-resistance and charge data do not qualify the proposed interface, diode protection, switching loss or PWM rate.",
    "provenance": {
      "actor": "agent:/root/collect_mosfet_drive_constraints",
      "recorded_at": "2026-10-28T04:19:22.291337+00:00"
    },
    "evidence_references": [
      "Rev 3.1 pages 1-5"
    ]
  },
  {
    "id": "ao3400a-pcb-thermal-inputs-unknown",
    "source_id": "ao3400a-aos-r3p1-sot23",
    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
    "description": "Actual PCB copper geometry/stackup, mounting, ambient/enclosure/airflow, pulse duty/history and thermal path are unprovided. No safe continuous or pulsed load current, junction temperature, power budget or board SOA has been established. Do not use the <=10-s thermal resistance as steady-state or assume the test-board result transfers to the design.",
    "provenance": {
      "actor": "agent:/root/collect_mosfet_drive_constraints",
      "recorded_at": "2026-10-28T04:19:22.291337+00:00"
    },
    "evidence_references": [
      "Rev 3.1 pages 1-2 notes A-F; page 4 thermal/SOA plots"
    ]
  }
]
```

## Later documentary negative — a separate evidence lane

The accepted [#27 numbered-terminal investigation](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/33575820e208d3986e0732ac5f0bbe44157719b3/docs/source-investigations/ao3400a-numbered-terminal-evidence.md) is pinned separately at `33575820e208d3986e0732ac5f0bbe44157719b3`. It did not exist in the older technical snapshot and is not represented by the replay hashes above. This handoff reuses its documented conclusion without fetching new sources or claiming a new visual audit.

Within that fixed official source set (product page and its linked datasheet, package drawing and marking description), numerical terminal mapping was **not established**. The datasheet shows G/S/D roles with explicit top/bottom views but no numbers. Package and marking geometry do not connect numeric identifiers to functions; dimension D is not drain evidence, a dot is not an assigned number, and the shared AO3400A/AO3400AL marking code is not unique full identity. A geometric correspondence is derived, not an official numbered map. No generic SOT23 numbering, CAD symbol or silent footprint mapping is permitted. Research completion does not close `ao3400a-numbered-pin-identity-unknown`.

## Independent review and publication boundary

Distinct reader assigned: `agent:/root/prepare_adc_mosfet_input_cards/review_adc_mosfet_cards`; coordinator: `agent:/root/prepare_adc_mosfet_input_cards`. Independent reviewer replayed all four declared commands in a clean checkout of `0373a341d5e12d50778f899848a078621dfa4790` on 2026-10-28 at 08:25–08:28 UTC. All commands exited 0; the first three complete stdout hashes matched the frozen receipt. All eight complete facts, three complete warnings and source objects matched the stored JSON; both negative interpretations were verified. The later `33575820e208d3986e0732ac5f0bbe44157719b3` documentary negative was reviewed separately. The reader found no substantive evidence or interpretation blocker. This is agent documentation/retrieval review, not original-byte, human or circuit verification. The final external issue receipt must record the completed review, timestamp, final document SHA-256, exact combined publication commit/tree, remote readback, preservation diff, actual gate commands/exits/counts/skips and terminal exact-commit CI. A document cannot contain its own stable final byte hash. No pending/unrun gate is claimed passed here; final publication belongs to the coordinated root CI slot, not the author. Independent maintainer acceptance closes the issue, not this handoff.
