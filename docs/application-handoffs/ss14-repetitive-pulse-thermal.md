# SS14 repetitive-pulse and thermal application handoff

Issue [#30](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/30).
Author: `agent:/root/document_ss14_application_inputs`, 2026-10-28, 17:24 UTC.

**Narrow result: the stored nonrepetitive surge rating does not qualify the proposed repetitive pulse train.** This is one blank input card and one synthetic case, not a component selection, circuit design or source collection. Input-complete never means circuit-qualified. No diode, MOSFET, clamp or board design is selected.

## Blank application-input card

Keep each unknown explicit. Record its accountable provider, units, bounds,
source revision/page/test conditions or measurement method, and uncertainty.

| Required input | Supplied value / evidence (blank template) |
|---|---|
| Exact manufacturer, full orderable suffix, grade, procurement identity and package | Unknown; obtain BOM and matching manufacturer identity evidence |
| Polarity, symbol, footprint, assembled orientation and terminal-to-pad mapping | Unknown; verify banded cathode against the actual assembly; do not assume numbered pads |
| Forward and reverse current **and** diode-voltage waveforms across all operating, startup, shutdown and fault states | Unknown; provide complete synchronized traces or bounded models, not peak current alone |
| Pulse shape, rise/fall time, baseline and between-pulse waveform | Unknown; specify every interval, including reverse conduction/leakage and transient behavior |
| Repetition frequency, duration, duty definition, bursts, burst spacing and lifetime pattern | Unknown; identify worst-case tolerances and operating envelope |
| Supply range/tolerance, reverse peaks/spikes/ringing and inductive energy | Unknown; describe topology, energy source, clamp behavior and where energy is dissipated |
| Ambient, lead and junction temperature ranges, initial conditions and measurement/model basis | Unknown; distinguish all three temperatures and transient from steady state |
| Copper geometry, pad dimensions, stackup, mounting, airflow and coupled heat sources | Unknown; provide actual board and enclosure thermal path, not package name alone |
| Applicable repetitive-current/energy, reverse-transient and thermal evidence | Unknown; identify manufacturer-supported conditions and unresolved guarantees separately from board inputs |
| Engineering analysis, margins and validation owner/plan | Unknown; define waveform/loss/thermal/stress analysis and board-specific validation without treating input completion as approval |

## One synthetic case: frozen practical report case 5

These are invented evaluation inputs, **not actual user-board data**:

| Field | Synthetic input or explicit unknown |
|---|---|
| Identity scope | Vishay General Semiconductor SS14, SMA (DO-214AC); full orderable suffix/grade/procurement identity unknown |
| System | 12 V; tolerance, diode reverse waveform, spikes/ringing and power-state trajectories unknown |
| Proposed forward pulses | 2 A, 1 ms, 100 Hz; shape, rise/fall, baseline, between-pulse waveform, bursts and inductive energy unknown |
| Temperature | Ambient 70 C; lead/junction temperatures, initial state and mounting thermal path unknown |
| Assembly | Actual footprint, symbol/polarity mapping, copper/stackup/mounting/airflow and coupled heat unknown |

There is **no average-current conclusion** from these incomplete waveforms. The
1-ms duration and 100-Hz repetition do not define the missing waveform or losses.
This handoff deliberately makes no rectangular/zero-baseline arithmetic assumption.

The 40-A maximum applies to an **8.3-ms single half-sine nonrepetitive surge,
superimposed on rated load, at rated lead temperature**. Figure 2 is explicitly
nonrepetitive and its cycle-count curve is not a repetitive switching permission.
A lower peak, a shorter/differently shaped pulse, or an arithmetic average below
1 A does not establish a repetitive rating. No extrapolated energy or safe pulse
train is calculated.

### Three separate handoffs

1. **Missing manufacturer evidence:** Obtain applicable, conditioned repetitive-current/energy and thermal evidence for this exact device and waveform. No repetitive-operating-current value or nonrepetitive reverse-surge/avalanche allowance is established by these annotations. Obtain justified loss behavior and transient/steady-state thermal applicability rather than substituting typical curves or a single-pulse rating. Full orderable identity still needs its own proof; the SS16 ordering example is not SS14 proof.
2. **Missing board/user inputs:** Provide every blank-card field, especially complete forward/reverse current and voltage waveforms, shape/rise/fall/baseline, between-pulse states, repetition/bursts/duty, inductive energy/clamp behavior, reverse spikes/ringing, supply tolerance, exact identity/polarity/footprint and actual ambient/lead/junction and mounting conditions. The synthetic 12 V, 2 A, 1 ms, 100 Hz and 70 C do not substitute for measured/bounded application data.
3. **Engineering analysis:** Once evidence and inputs exist, assess reverse-voltage stresses separately from forward surge; evaluate conditioned forward and reverse losses over complete waveforms and couple them to the actual transient/steady-state thermal path and temperature dependence. Establish appropriate operating/stress margins and a validation plan. This document performs none of that qualification, and missing evidence is not resolved by input completion.

## Source-bound constraints to carry into that analysis

All seven facts below are from source `vishay-ss14-88746-20200423-sma`,
Vishay General Semiconductor SS14 / SMA (DO-214AC), document **88746,
Revision 23-Apr-2020**. Technical pages 1-4 have that electrical revision;
page 5 is separately dated legal notice 91000, 01-Jan-2026, not a 2026 electrical
revision. Latest revision is not guaranteed. No cross-vendor SS14, alternate
package, SS12/SS13/SS15/SS16 or full orderable substitution is established.

| Fact | Conditioned observation and retained limit |
|---|---|
| `vishay-ss14-app-01` | Maximum VRRM=40 V, VDC=40 V, VRMS=28 V; table default TA=25 C unless noted. These are not design margins or breakdown/avalanche ratings. Nonrepetitive reverse-surge voltage is unknown. Supply tolerance and reverse spikes need separate assessment. |
| `vishay-ss14-app-02` | IF(AV) maximum 1 A refers to Figure 1, **lead temperature TL**, and its PCB mounting with 5x5-mm copper pads. Current falls toward zero as TL approaches 150 C. No numerical curve knee is digitized. Ambient alone does not determine allowed current or lead/junction temperature. |
| `vishay-ss14-app-03` | IFSM maximum 40 A, 8.3-ms single half-sine superimposed on rated load; Figure 2 initial condition is rated TL. Its decreasing surge limit versus cycle count at 60 Hz remains nonrepetitive. Continuous current, arbitrary pulse-train energy and repetitive-operating current are not inferred. |
| `vishay-ss14-app-04` | VF maximum 0.5 V at IF=1 A, TA=25 C, **300-us pulse / 1% test duty**. It is not a constant drop at 2 A or arbitrary temperature, nor steady-state thermal evidence. Figure 3 typical curves are not guaranteed limits; the SS15/SS16 0.75-V group is not transferred. |
| `vishay-ss14-app-05` | Reverse-leakage maxima at rated DC blocking bias **40 V**: 0.2 mA at TA=25 C and 6 mA at TA=100 C, **test pulse width at most 40 ms**. No all-temperature interpolation, zero-leakage assumption or continuous-loss qualification follows. Figure 4 is typical; the SS15/SS16 5-mA hot row is not transferred. |
| `vishay-ss14-app-06` | Typical RthetaJA=88 C/W and RthetaJL=28 C/W on stated **5x5-mm copper pads**, table default TA=25 C. They are not guaranteed layout-independent resistances. TJ and storage ranges are each -65 to 150 C, but storage range is not operating permission, and 150-C junction limit is not 1-A-at-150-C-ambient permission. Forward/reverse losses and actual thermal paths remain required. |
| `vishay-ss14-app-07` | Color band identifies cathode; verified package SMA (DO-214AC). Terminal number assignment is unknown. Verify actual symbol/footprint orientation, full order suffix and assembled polarity; no numbered-pad convention or manufacturer/package interchangeability is inferred. |

## All three unresolved warnings

The complete stored warning descriptions follow unchanged. Each has status
`UNRESOLVED_APPLICATION_INPUTS` and source ID `vishay-ss14-88746-20200423-sma`.
Each records actor `agent:/root/collect_rectifier_application_constraints` at
`2026-10-28T04:36:45.423185+00:00`. These are preserved historical provenance,
not new observations about an actual board.

- **`vishay-ss14-app-identity-and-orderable-unknown`** (evidence: `88746 pages 1, 2, 4`): Full SS14 orderable suffix, qualification grade, procurement identity and user footprint are unresolved. Page 2 illustrates SS16 ordering only. Do not transfer these values to another manufacturer, package, SS12/SS13/SS15/SS16 or assume a numbered pad map.
- **`vishay-ss14-app-application-waveform-unknown`** (evidence: `88746 pages 1, 3`): Actual reverse waveform/spikes, average and peak forward current, pulse repetition, duty cycle, switching frequency and inductive energy are unspecified. Flyback, SMPS, freewheel, polarity-protection or pairing with any MOSFET remains UNKNOWN; generic application labels or ratings alone do not qualify a circuit.
- **`vishay-ss14-app-thermal-design-unknown`** (evidence: `88746 pages 1-3`): Ambient/lead/junction temperatures, copper geometry, stackup, airflow and coupled heat sources are unprovided. Typical thermal values, pulsed VF/leakage tests and nonrepetitive IFSM cannot certify continuous loss, repetitive surges or thermal stability. No precise Figure 1 knee or missing reverse-surge/avalanche capability is invented.

## Frozen evidence and literal replay recipes

The [practical report](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.md)
and [machine receipt](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/b04fed50dff7853d5ad2663784eb0305bb02f331/docs/practical-task-evaluation-2026-10-28.json)
remain frozen at `b04fed50dff7853d5ad2663784eb0305bb02f331`. The technical replay
uses clean immutable commit `0373a341d5e12d50778f899848a078621dfa4790`, tree
`8c83b2cd3cc3a2443ab584ccd16768455c49dda0`, not the report-publication commit.

Reuse the [source JSON](../../knowledge/intake/vishay-ss14-rectifier-constraints.json)
and its [historical review](../../knowledge/intake/vishay-ss14-rectifier-constraints-review.md).
Source JSON SHA-256: `6537e3323bd556482167c9a268c799f1d8527e8f4d23d610ccfc88b0f2654407`.
The recorded original PDF hash is `b32a2d93d2d2cf9f48d6cf678ab03713956b7501029c0424c6a554425df562da`
(1,174,123 bytes); this task does **not** retrieve or freshly verify that PDF.
Historical byte/visual Agent review is not fresh PDF-byte/visual verification or
human acceptance. Retrieval retains `canonical: false`, source/fact
`human_reviewed: false`, and `NOT_LOCALLY_VERIFIED`. Public reference is not a
redistribution license; no originals, extracts or images accompany this handoff.

Run these literal commands from the clean pinned technical checkout:

```sh
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vishay-ss14-88746-20200423-sma
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id vishay-ss14-88746-20200423-sma
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vishay-ss14-88746-20200423-sma --device SS16
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vishay-ss14-88746-20200423-sma --package 'SMB (DO-214AA)'
```

| Command | Expected selection | SHA-256 of exact UTF-8 stdout, including final newline |
|---|---|---|
| 1 | All seven `vishay-ss14-app-01` through `07` facts | `2b240cabea81aeba45c6068d7386d5ffd1af1fc642da5c812efa7dc155bb39be` |
| 2 | All three full source warnings above | `7abbcf043f9c9c19fd30c3f5601a286c0a4f80dcf31093df34492061ef52b835` |
| 3 | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 4 | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

The negatives use supported exact structured filters, independently motivated by
the selected source metadata: SS16 is a different device, and SMB (DO-214AA) is
not the selected SMA (DO-214AC). Their empty results mean only **no scoped
candidates**, not compatibility, safety or global absence of evidence. They do
not establish electrical answers by lexical matching.

Author replay at 17:24 UTC: all four frozen commands exited 0. The two required
stdout hashes match the frozen receipt. Complete seven fact payloads, source
provenance, conditions and every source-local warning matched the source JSON;
the issues command returned each complete warning. Noncanonical/nonverification
markers remained intact. Both negatives returned empty arrays.

**Separate current-head observation:** the same four commands at
`fdab8e988097f47e08f167409e8c70bf67cbea8f` also exited 0 with byte-identical stdout
and source JSON. This is not a rewrite of the frozen receipt. Distinct Agent
review, final document hash and publication gates are recorded in the companion
[review receipt](ss14-repetitive-pulse-thermal-review.md); remote CI is reported
against the actual published commit in issue #30. No human acceptance or circuit
qualification is claimed.
