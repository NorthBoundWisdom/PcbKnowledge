# VO617A-3 logic-interface application-input card

This handoff for [issue #32](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/32)
collects missing evidence; it does not design or qualify a circuit. One blank
card and one explicitly synthetic case follow. Completing fields is not proof
of adequate logic margin, timing, lifetime or isolation safety.

## Pinned evidence and its limits

Reuse only **Vishay Semiconductors VO617A-3, CTR bin 3, standard DIP-4 without
an option suffix**, source `vo617a-3-vishay-83430-2-8-dip4`, document 83430,
**Rev. 2.8, 2025-01-22**. The separate 2026 legal appendix does not revise the
electrical specifications. The source JSON (`git show intake-final:knowledge/intake/vo617a-3-optocoupler-logic-constraints.json`)
and source review (`git show intake-final:knowledge/intake/vo617a-3-optocoupler-logic-constraints-review.md`)
are reused, not recollected. Pinned technical snapshot:
`f97bb140134de4463284287bb13b6aa6b58eb7c3`.

- Source JSON SHA-256: `adc2ce86339add3ad91ee96225abdc2bc4343dd6e994afc0e4e50f35ae60e64c`.
- Historical PDF SHA-256: `145893b5422f68cc3f2016e2dddfc33f6ee26f0d2444fe8889d0dc0388f805a1`.
  This identifies prior provenance, not a fresh PDF-byte audit or visual check.
- `canonical: false`, `human_reviewed: false`, and consumer
  `evidence_verification: NOT_LOCALLY_VERIFIED` remain explicit. Prior Agent
  review under owner delegation is not human acceptance or canonical approval.
- No original PDF, extract, image or real board input is included. No latest
  source revision, complete CAD footprint or safety-option approval is asserted.

## Blank application-input card

Record evidence links, units, min/nom/max and applicable conditions for each
field. Leave unavailable fields **UNKNOWN**, not nominal guesses.

| Input group | Required board/user evidence | Blank entry |
|---|---|---|
| Identity and assembly | Manufacturer, full orderable, CTR bin, package/options, purchased marking, schematic polarity and validated footprint/view/geometry | UNKNOWN |
| LED source and driver | Supply limits/transients, driver type/compliance/output limits, current waveform and min/nom/max including start/stop, rise/fall, pulse width and duty | UNKNOWN |
| Input resistor and LED voltage | Existing resistor value/tolerance/TCR/power, driver losses, forward-voltage bounds at actual current and temperature, current-budget evidence | UNKNOWN |
| Collector pull-up | Actual rail min/nom/max/transients, existing resistance/tolerance/TCR, emitter reference and receiver connections | UNKNOWN |
| Receiver | Exact part/revision, VIL/VIH conditions, input leakage across temperature/power states, input and interconnect capacitance, required noise margins | UNKNOWN |
| Load trajectory | Collector current and VCE across on/off/transitions, saturation depth, capacitive charging, receiver loading, allowed dissipation | UNKNOWN |
| Signaling | Desired rate, encoding, shortest high/low pulses, duty/bursts, timing budget, required delay/jitter/edge limits and startup behavior | UNKNOWN |
| Environment and lifetime | Ambient/device temperature range, thermal path, coupled heat, aging/LED degradation evidence, service life and required end-of-life margins | UNKNOWN |
| Evidence gaps | Manufacturer-supported low-VCE transfer, hot leakage, relevant VF bounds and worst-case switching conditions; resolution of table/Figure 3 current conflict | UNKNOWN |
| Isolation boundary | Whether isolation is required; exact option, applicable agency evidence, continuous working-voltage basis, insulation/board geometry/environment | UNKNOWN; no safety design approval |

## Manufacturer facts, separately conditioned

The eight selected IDs are `vo617a-3-logic-01` through `vo617a-3-logic-08`.
Complete payloads, including provenance and every condition, are available through
the replay below. This compact reading guide does not replace them.

| Fact suffix | Retained values and conditions | Boundary for this card |
|---|---|---|
| 01 | Exact VO617A-3 bin 3, standard DIP-4; schematic 1 anode, 2 cathode, 3 emitter, 4 collector | Numbered symbol/order entry is not a complete CAD footprint; no other bin, SMD, wide-lead or safety option inferred |
| 02 | Selected absolute maxima: LED reverse 6 V, forward 60 mA; collector-emitter 80 V, collector 50 mA; Tamb 25 C unless specified | Stress ratings, not simultaneous operating permission or drive/pull-up targets; selected steady limits do not replace pulse/power/temperature budgets |
| 03 | VF min/typ/max 1 / 1.35 / 1.65 V at IF 60 mA, Tamb 25 C; maximum at 5 mA unknown | Typical is informational, min/max are test requirements; do not transfer these bounds to 5-mA resistor design |
| 04 | Bin-3 CTR min/max 100 / 200%, typical unknown; IF 5 mA, VCE 5 V, Tamb 25 C | Active-region ratio is not guaranteed saturated logic-low sink, full-temperature/lifetime minimum or another current/bin; low-VCE guaranteed CTR unknown |
| 05 | VCEsat typical 0.25 V, maximum 0.4 V at IF 5 mA, IC 1 mA, Tamb 25 C; maximum at IC 5 mA unknown | Separate saturation test, not the CTR test; receiver VIL, actual pull-up load, temperature and aging must be established |
| 06 | Bin-3 off-state ICEO typical 5 nA, maximum 100 nA at VCE 10 V, Tamb 25 C; hot maximum unknown | Not a lower-bin value or proof of high-state margin with actual receiver leakage/pull-up/environment |
| 07 | Non-saturated turn-off typical 2.3 us, maximum unknown; IF 5 mA, VCC 5 V, RL 75 ohm, Tamb 25 C. Figure 2: 50-us pulse, duty ratio 0.01, generator 50 ohm, scope 1 Mohm / 20 pF | Scope impedance differs from circuit load; typical is not worst-case or saturated timing, nor a qualified bit rate with another load/receiver |
| 08 | Saturated table IF 5 mA versus Figure 3 IF 10 mA; figure supply 5 V, load 1000 ohm; reconciled current and qualified saturated turn-off unknown | Both contexts label saturation but no explicit reconciliation is given; do not choose either setup, interpolate, or establish typical saturated timing for either |

### Complete retained warnings

All three are attached to the exact source above. Their historical provenance is
Agent `agent:/root/continue_pcbknowledge_iteration/collect_low_voltage_mosfet`,
recorded at `2026-10-28T20:45:23.407142+00:00`; that is not this card's review.

- **`vo617a-3-saturated-test-current-conflict`** — `UNRESOLVED_SOURCE_CONFLICT`:
  Page 4 saturated rows specify IF=5 mA while Figure 3 labels IF=10 mA. Retain both locations and do not assign a reconciled current or qualified saturated delay. Safe disposition is to withhold rate/saturated timing approval, request manufacturer clarification or characterize the intended circuit; no source correction is invented.
- **`vo617a-3-logic-margin-unknown`** — `UNRESOLVED_APPLICATION_INPUTS`:
  LED driver/current and tolerances, actual pull-up supply/resistance, receiver thresholds/input leakage, loading/capacitance, temperature and lifetime degradation are unknown. CTR at VCE=5 V cannot approve a logic-low saturated pull-down; no resistor, bit rate or logic margin is qualified.
- **`vo617a-3-isolation-option-not-qualified`** — `UNRESOLVED_APPLICATION_INPUTS`:
  Family isolation headline and option-specific approval text do not qualify the selected standard DIP-4 for an application or establish continuous working voltage. Exact safety-option, applicable agency evidence, insulation system, board geometry and operating environment are not assessed. No safety or mains-isolation design approval is given.

## One explicitly synthetic filled case

These invented evaluation inputs are **not user-board facts, recommendations or
approved operating conditions**. No resistor or replacement device is selected.

| Field | Synthetic entry |
|---|---|
| Intended identity | VO617A-3, bin 3, standard DIP-4 without option suffix; actual purchased identity/footprint verification UNKNOWN |
| LED drive | Nominal 5 mA only; driver/supply/compliance, resistor, tolerances, waveform, temperature and VF evidence UNKNOWN |
| Output | Nominal receiver rail 3.3 V and proposed nominal collector pull-up 1 kohm; tolerances, receiver part, VIL/VIH, leakage, capacitance and emitter-reference evidence UNKNOWN |
| Signaling goal | Desired 10 kbit/s; encoding, pulse width/duty, timing budget and required margins UNKNOWN |
| Environment/lifetime | Ambient/device temperatures, thermal path, life/degradation requirements UNKNOWN |
| Isolation | Application requirement, approved option and insulation evidence UNKNOWN; no mains/safety design considered qualified |

**Manufacturer evidence missing:** a bound usable at the actual low VCE,
LED current, temperature and lifetime; appropriate VF and hot-leakage evidence;
qualified switching across the intended load/drive corners; and reconciliation
of the saturated table/Figure 3 current conflict. The nominal 1-kohm example
matching Figure 3's resistance does not make the setup equivalent or resolve it.

**Board/user inputs missing:** every UNKNOWN above, including the exact receiver
and worst-case drive/pull-up/load trajectories. A nominal target does not supply
a waveform, threshold, tolerance or lifetime bound.

**Engineering analysis still required:** establish LED-current bounds from real
driver/compliance/VF/resistor evidence; evaluate low-state sink versus receiver
VIL and high-state leakage versus VIH over all corners; assess transient
capacitance, saturation/storage, timing and noise margins with supported
worst-case data or a justified characterization plan. Treat stress, power,
temperature and any isolation qualification separately. Do not use 100% CTR to
approve a 5-mA saturated sink, substitute 0.4 V at another collector current,
or use 2.3-us typical timing to approve 10 kbit/s. No average/nominal arithmetic
here substitutes for missing corner evidence. Outcome: **inputs incomplete;
logic margins, rate, circuit suitability and safety remain unqualified**.

## Literal evidence replay and negative controls

Run from a clean checkout detached at the pinned snapshot above. These commands
read metadata only; lexical hits, counts and exit zero do not evaluate the case.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vo617a-3-vishay-83430-2-8-dip4
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id vo617a-3-vishay-83430-2-8-dip4
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vo617a-3-vishay-83430-2-8-dip4 --device VO617A-2
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vo617a-3-vishay-83430-2-8-dip4 --package SMD-4
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id vo617a-3-vishay-83430-2-8-dip4 --revision 'Rev. 2.7'
```

| Recipe | Selected payload | Full stdout SHA-256 (including final newline) |
|---|---|---|
| Source search | All eight complete facts 01–08, source provenance and attached complete warnings | `643177c2c5998cdcd3a78e5c4b108802705d1f4db1e4cd10010f81d6d9e929ec` |
| Source issues | All three complete warning objects and provenance listed above | `cd2e432bedfa68831c9c77402fd43bc7e192218ba7fabea5ce7c5a077214b7ac` |
| Wrong bin/device | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong package | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong revision | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

These exclusions are independently justified by the stored exact **VO617A-3**
identity (not bin-2 VO617A-2), **DIP-4** package (not SMD-4) and **Rev. 2.8**
evidence revision (not Rev. 2.7). They are no scoped candidates, not compatibility,
safety, proof that another revision/device does not exist, or global evidence
absence. No alternative source is substituted.

Separately labeled current-base replay at
`e442b8e1ab9144f1c1c19b6b6b4b74c70b00ae61` produced the same source JSON and five
stdout hashes. The pinned receipt is not rewritten. See the
[independent card review](vo617a-3-logic-interface-review.md) for actual reviewer,
command hashes, complete-payload checks and limitations. Publication gates and
exact-commit CI are recorded in issue #32, separately from content review.
