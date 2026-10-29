# SN65HVD75 topology, termination and bias input handoff

This is one blank input card and one explicitly synthetic case, not a network
design, resistor selection or circuit qualification. Completing inputs does not
close evidence gaps or qualify a network. No new source collection is performed.

## Blank application-input card

For each field, retain unknowns and record the provider, units, tolerances,
conditions, revision or measurement/model method and uncertainty.

| Required input | Supplied value / evidence (blank template) |
|---|---|
| Exact manufacturer/orderable, package, symbol, pin mapping and assembled orientation | Unknown; provide BOM and matching identity/assembly evidence |
| Actual topology, cable endpoints, node positions and removable-node states | Unknown; identify every trunk, stub, branch and termination in every configuration |
| Cable impedance and propagation versus frequency, temperature and tolerances | Unknown; provide cable evidence and actual trunk/stub lengths, connectors and discontinuities |
| Driver edge rates, data rate and complete signal trajectories | Unknown; provide bounded operating waveforms, not data rate alone |
| Termination locations, values, tolerances and power/loading conditions | Unknown; identify endpoints rather than assuming every node needs termination |
| Total device, protection and connector loading | Unknown; include powered/unpowered nodes, bias networks, leakage and capacitance |
| Idle states, external bias network, tolerances and noise margins | Unknown; evaluate every relevant power/driver state; failsafe alone does not settle bias suitability |
| Ground offsets, individual A/B voltages and differential trajectories | Unknown; provide noise, transients, fault exposure, protection, isolation and power sequencing |
| Controller thresholds, output drive/loading and supply range | Unknown; compare actual interfaces under their respective conditions |
| DE/RE polarity, scheduling, active/standby transitions and contention control | Unknown; identify receiver-enabled/disabled and driver-enabled/disabled states explicitly |
| Cable delay, turnaround and sampling budget | Unknown; separate propagation, enable, disable and standby wake, with margins and units |
| Ambient/junction range, self-heating and validation plan | Unknown; identify analysis owner, evidence gaps and board-specific operating/EMC checks |

## One synthetic case: frozen practical report case 7

These are invented evaluation inputs, **not actual user-board data**:

| Field | Synthetic input or explicit unknown |
|---|---|
| Nodes | Four Texas Instruments SN65HVD75DR, D / 8-pin SOIC |
| Rails | 3.3 V nominal; actual tolerance, sequencing and temperature envelope unknown |
| Cable | 120-ohm characteristic impedance, 30-m trunk, 1-m stubs; propagation, tolerances, endpoint identities and actual layout unknown |
| Data | 1 Mbps; edge rates, waveforms, controller thresholds and sampling budget unknown |
| Proposal | 120-ohm termination at **every node**, no external bias |
| Other conditions | Ground offset, noise and turnaround unspecified; protection, isolation, loading and removable-node configurations unknown |

Typical parallel-multipoint guidance terminates the **two cable ends**, matched
to characteristic impedance, not every node. That observation does not select
resistors for this case, certify the 1-m stubs or approve an arbitrary star.
No topology endpoints, delay, tolerance or waveform are silently supplied here.
The proposed every-node termination and omission of external bias are **not
approved**. There is no network rate, node-count, noise, timing or fault guarantee.

### Three separate handoffs

1. **Manufacturer/source facts and remaining evidence:** Use the exact conditioned records below and their cited test fixtures. Obtain any additional applicable evidence needed for actual cable/loading/protection and operating conditions. Existing component tests do not establish board-level IEC/EMC qualification, arbitrary fault survival or every required system guarantee.
2. **Missing board/user inputs:** Complete the blank fields, particularly actual topology/endpoints/removable nodes, cable propagation, trunk/stub lengths and edge rates, termination tolerances, total loading, idle/bias/noise margins, per-pin and differential trajectories, ground offsets/protection/isolation/power sequencing and controller DE/RE/sample scheduling. Synthetic values do not supply missing board evidence.
3. **Remaining engineering analysis:** Assess transmission-line reflections and loading, bias/noise margins over tolerances and states, interface compatibility, separate bus-pin/common-mode and differential limits, contention and turnaround/sample budgets, and thermal/transient/protection behavior. Then validate the actual assembly. This handoff does not perform or certify that analysis; listing a question does not resolve its warning.

## Source-bound constraints

Scope is **Texas Instruments SN65HVD75DR**, **D / 8-pin SOIC**, source
`rs485-app-ti-sllse11h-d`, electrical revision **SLLSE11H, March 2019**.
The packaging addendum dated **15 July 2026** is separately dated, not a new
electrical revision. Latest revision is not guaranteed. No SN65HVD72DR,
SN65HVD78DR or DGK / 8-pin VSSOP substitution follows.

The table is a compact interpretation map, not a replacement for the complete
nine fact/source objects returned by the replay below. Retain every recorded
min/typ/max, null, unit, condition and provenance field. A null minimum is unknown,
not zero; a typical value is not a guaranteed bound.

| Fact | Conditioned observation and retained boundary |
|---|---|
| `rs485-app-01` | Supply 3/3.3/3.6 V min/nom/max; individual bus-pin or common-mode range -7 to 12 V **and** differential input -12 to 12 V both apply. VIT+ min/typ/max = null/-70/-20 mV, VIT- = -200/-150/null mV, hysteresis = 50/80/null mV; the threshold footnote relates VIT+ to VIT- under its conditions. Driver differential output at RL=54 ohm = 1.5/2/null V. Sections 7.3/7.5 apply together, ambient -40 to 125 C and junction -40 to 150 C with self-heating. Stress/ESD limits do not extend normal operation. |
| `rs485-app-02` | HVD75 bus current at +12 V = null/75/150 uA, at -7 V = -100/-40/null uA, with DE=0 V and VCC=3..3.6 V or 0 V. Logic high 2..VCC V and low 0..0.8 V require powered recommended operation. Receiver VOH at -8 mA = 2.4/(VCC-0.3)/null V; VOL at 8 mA = null/0.2/0.4 V. Receiver load is 3/20 unit load. The at-most-213-transceivers discussion is loading-only, not arbitrary rate/cable/topology permission; HVD78 loading is excluded. |
| `rs485-app-03` | DE high enables D-controlled polarity (D high: A high/B low); DE low/open gives driver high impedance. Active-low RE low enables receiver; RE high/open gives output high impedance. D open with DE high selects A high/B low through internal pullup. Standby means **both** disabled; no-load current null/0.1/2 uA requires DE=GND, RE=VCC, D open. Receiver-enabled/driver-disabled is not standby. Tri-state alone does not establish scheduling or contention avoidance. |
| `rs485-app-04` | Enabled receiver high for disconnected bus, A-B short or idle terminated bus requires RE low and operating limits satisfied. VID=VA-VB above VIT+ selects high, below VIT- selects low, between thresholds indeterminate. The section 9.3 example uses VIT+=-20 mV and VHYS=50 mV with 140-mV peak-to-peak differential noise in bus-idle/bus-short conditions. It is not universal noise immunity, permission to omit bias, or survival of shorts to arbitrary power/ground. |
| `rs485-app-05` | Typical parallel-multipoint guidance places impedance-matched termination at both cable ends and keeps stubs short relative to driver edges/cable propagation. It neither prescribes universal 120-ohm values nor every-node termination/star approval. The 20-Mbps device ceiling and cable-length examples do not establish 20 Mbps over 1200 m or qualify this network. |
| `rs485-app-06` | Driver rise/fall min/typ/max 2/7/14 ns, propagation 7/11/17 ns, pulse skew null/0/2 ns. Figure 12: RL=54 ohm +/-1%, CL=50 pF +/-20%, D=0..3 V, DE=VCC; propagation from input 50% to differential zero crossing, edges differential 10%/90%. |
| `rs485-app-07` | Driver disable null/12/50 **ns**; enable with receiver enabled null/10/20 **ns**; enable with receiver disabled null/3/7 **us** (standby wake). Figures 13/14 use RL=110 ohm +/-1% to ground (high) or 3 V (low), CL=50 pF +/-20%; DE=0..3 V, input 50%, enable output 50%. High-output disable has VOH minus 0.5 V marker (also 90% label); low-output disable 10%; D selects A/B polarity. This differs from the differential propagation load. |
| `rs485-app-08` | Receiver rise/fall null/5/10 ns, propagation null/60/70 ns, skew null/0/6 ns. Figure 15: CL=15 pF +/-20%, RE=0 V, B=1.5 V, A=0..3 V; propagation input/output 50%, edges output 10%/90%. |
| `rs485-app-09` | Receiver disable null/15/30 **ns**; enable with driver enabled null/10/50 **ns**; enable with driver disabled null/3/8 **us** (wake). Figures 16/17: 1 kohm +/-1% to ground (high) or VCC (low), CL=15 pF +/-20%; RE=0..3 V, input 50%, enable output 50%, disable high 90%/low 10%. Figure 16 DE=3 V and D selects polarity; Figure 17 driver disabled, A/B=1.5/0 V (high) or 0/1.5 V (low). Propagation is neither enable nor disable. |

For **all timing rows 06-09**, retain SN65HVD75 section 7.8 recommended-operation
conditions, bit time >=50 ns, and section 8 generator conditions: 100 kbps,
50% duty, edges <6 ns, 50-ohm output, fixture/instrument capacitance included.
Missing minima stay unknown. Distinct loads and thresholds are not interchangeable.
Microseconds are not nanoseconds. These device tests are not a controller/cable
turnaround budget, collision-free protocol guarantee or qualification at 1 Mbps.

## Three complete unresolved warnings

All have source `rs485-app-ti-sllse11h-d`, status
`UNRESOLVED_APPLICATION_INPUTS`, historical actor
`agent:/root/curate_reset_rs485_wave/collect_rs485_constraints`, recorded at
`2026-10-28T04:58:22.856360+00:00`. Their complete stored descriptions follow:

- **`rs485-app-network-unknown`** (evidence `SLLSE11H 10.2;10.2.1.1-10.2.1.4`): Actual cable impedance/length/stubs/topology, termination placement and tolerances, node loading and bias network are unspecified. Bus loading, failsafe and typical topology facts do not validate a complete network.
- **`rs485-app-timing-unknown`** (evidence `SLLSE11H 7.3;7.8;8 Figures 12-17;9.4`): Controller logic thresholds, output loading, supply sequencing, data rate, cable delay, DE/RE scheduling and turnaround/sample budget are unspecified. Neither 20 Mbps nor propagation/enable maxima proves collision-free communication.
- **`rs485-app-ground-protection-unknown`** (evidence `SLLSE11H 7.1-7.3;9.3;10.2`): Ground offset, individual bus-pin waveform, differential noise, transient exposure, protection circuit and isolation needs are unspecified. Normal operating, absolute-maximum and component ESD tests are distinct; no board-level IEC/EMC qualification or arbitrary fault survival is established.

## Frozen evidence and literal replay

The [practical report, case 7](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.md)
and [JSON receipt](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.json)
remain frozen. The clean immutable technical replay snapshot is
`0373a341d5e12d50778f899848a078621dfa4790`, not report publication `b04fed50`.
Reuse the [source JSON](../../../knowledge/intake/sn65hvd75-rs485-interface-constraints.json)
and [historical review](../../../knowledge/intake/sn65hvd75-rs485-interface-constraints-review.md).
JSON SHA-256: `e1aa5c7e7e42abddb165b8268b767a9573ebb72e210384f9d1a75493fa43c549`.
Recorded original PDF SHA-256:
`b46f5803fa8302f98d7461799d078be59a41112191461519bcf4c464743e60a6`
(1,554,999 bytes). No PDF is retrieved or freshly verified here. Historical
byte/visual provenance is preserved, not claimed as new work or human acceptance.
Retrieval retains `canonical:false`, `human_reviewed:false` and
`NOT_LOCALLY_VERIFIED`. Public reference is not redistribution permission;
no originals, images or source extracts accompany this handoff.

From the clean pinned technical checkout, run:

```sh
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id rs485-app-ti-sllse11h-d
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --device SN65HVD72DR
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --device SN65HVD78DR
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --package 'DGK, 8-pin VSSOP'
```

| Command | Selection | Exact stdout SHA-256 (including final newline) |
|---|---|---|
| 1 | All nine complete `rs485-app-01` through `09` objects | `f13dae62ebba6aa34b7d05250d6a0f2269d99cf13614733c5ae40a27d21e8aaa` |
| 2 | All three complete warnings above | `67224068450f1b737beff34259da264acdc022154c6c2f3d130705e4c777ccd2` |
| 3-5 | Empty arrays | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` each |

Exact negatives are independently motivated by device/package identity: HVD72 and
HVD78 are distinct variants excluded by this source scope; DGK VSSOP is not D
SOIC. Empty means **no scoped candidate**, not compatibility, safety or global
absence of evidence. Lexical selection is not an electrical inference.

Author replay at 2026-10-28 20:26 UTC: all five commands exited 0 in the clean
frozen snapshot; required stdout hashes match the frozen receipt. Full payload
and warning comparisons are covered by the distinct review receipt.
**Separate current-head observation:** the same commands at
`7cf4b663daf6301e6d2030ae60ab2eb6cce9746c` exited 0 with identical stdout and source
JSON bytes. This does not rewrite the frozen report. Actual Agent identities,
final document hash and independent comparisons are in the
[review receipt](sn65hvd75-topology-termination-bias-review.md); publication gates
and exact-commit CI are reported in issue #31. No human or circuit approval follows.
