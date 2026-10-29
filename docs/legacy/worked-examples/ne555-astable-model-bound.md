# NE555 astable: a nominal result bounded by its model

## Question and narrow result

With synthetic **RA = RB = 10 kohm**, **C = 100 nF**, constant **VCC = 5 V**
and **TA = 25 C**, what does the accepted NE555 nominal steady-state astable model predict?

The cited approximate frequency equation gives **about 480 Hz**. The separately
labeled fractions are **high time / period = 2/3** (about 66.67%) and
**low time / period = 1/3** (about 33.33%). The source's *output-driver duty*
means the latter, not the high fraction. These are nominal steady-state model results, not
guaranteed timing, a selected working capacitor, or a qualified oscillator.

This fixed synthetic example adds no source records, canonical facts, generic
solver, or hardware evidence. Its separate executable regression does not revise the frozen
[practical task evaluation](../../archive/receipts/practical-task-evaluation-2026-10-28.md).

## Supplied model inputs and scope

- RA and RB are positive, constant, ohmic model resistances. C is a constant
  model capacitance across the timing excursion. These are explicit synthetic
  operating inputs, not values proved for installed components.
- Use only the Figure 6-5 astable model in `timer-app-03`: nominal threshold/
  control conditions, valid reset state, charging through RA + RB and
  discharging through RB. No diode variant, altered control bias, or CMOS
  timer substitution is included. This is not a pin-wiring instruction.
- At the assumed 5-V supply, the nominal timing-capacitor excursion is about
  1.67–3.33 V (one-third to two-thirds of VCC); it is not a zero-bias test.
- The 5-V, 25-C point is within the recorded NE555 recommended 4.5–16 V and
  0–70 C ranges (`b004-ti-ne555-04`, `b004-ti-ne555-06`). Being in range is
  not an accuracy guarantee or proof of the complete circuit's operation.
- No real frequency target/tolerance, operating component intervals, output
  load, noise, supply variation, startup sequence, leakage or thermal history
  is supplied. We deliberately calculate **no hardware timing interval**.

The two 10-kohm labels do not select Vishay resistors, and the 100-nF label
**does not select or qualify C0603C104K5RACTU as the timing capacitor**. Their
accepted evidence below explains why nominal labels alone are insufficient.

## Derivation from the recorded approximate equations

`timer-app-03` records SLFS022K section 6.3.2, Figure 6-5, equations 1–6
(printed page 12). R is in ohms and C in farads:

```text
tH ≈ 0.693 (RA + RB) C = 1.386 ms
tL ≈ 0.693 RB C        = 0.693 ms
T  ≈ 0.693 (RA + 2 RB) C = 2.079 ms
f  ≈ 1.44 / ((RA + 2 RB) C) = 480 Hz

high fraction = tH / T = (RA + RB) / (RA + 2 RB) = 2/3
low fraction  = tL / T = RB / (RA + 2 RB)        = 1/3
```

The fractional equalities are algebra within the stated model, not claims
that physical duty fractions have no error. Always state which fraction is
meant: the source calls low fraction the output-driver duty and high fraction
the output-waveform duty. A bare “33.33% duty” would be ambiguous.

**Do not force the rounded equations to be exact reciprocals.** Inverting the
period expression gives `1 / 0.002079 ≈ 481.000481 Hz`, whereas the separately
rounded frequency coefficient gives 480 Hz. Indeed, `0.693 × 1.44 = 0.99792`,
not 1. This small numerical mismatch is visible in the source's approximate
coefficients; it is neither measured oscillator error nor a bound on total
model error. More arithmetic digits do not make either prediction physically
exact. This example reports 480 Hz from the explicitly identified frequency
formula rather than silently replacing its coefficient with `1 / 0.693`.

For positive inputs, that frequency expression decreases as RA, RB or C
increases. If a future application supplies justified operating endpoints,
the model's minimum uses all upper endpoints and its maximum all lower
endpoints. For C alone, a supplied symmetric fractional interval of width
`epsilon`, with `0 <= epsilon < 1`, would map to frequency multipliers
`1/(1+epsilon)` and `1/(1-epsilon)`, **not** symmetric `1 ± epsilon`.
No such interval is supplied here. Initial part tolerance is not silently
promoted to an operating interval, and approximation/model error would remain
outside even correctly calculated component-input intervals.

## Evidence applicability and unresolved quantities

### Timer

Source `timer-app-ti-ne555dr-slfs022k` is TI NE555DR, D / 8-pin SOIC,
SLFS022K (March 2026), with September 18, 2026 packaging addendum.
The pilot source `ti-ne555` identifies the same recorded PDF bytes.
[Official source reference](https://www.ti.com/lit/ds/symlink/ne555.pdf).

- `timer-app-05`, section 5.6 (page 7), covers VCC = 5–15 V and TA = 25 C
  unless noted. Its astable footnote gives RA = 1–100 kohm and C = 0.1 uF;
  it does **not** state an RB range. The selected RA and C match those stated
  conditions, but RB = 10 kohm does not acquire an invented test-coverage
  guarantee. The temperature coefficient concerns the recommended 0–70 C
  range. Its 150 ppm/C and 0.3%/V sensitivity values are typical only, with
  no maxima, and are characterized/by-design rather than production-tested.
  They cannot be turned into a worst-case timing budget for this example.
- `timer-app-06`, section 5.5 and page-6 footnote: timing-node currents and
  approximate resistance guidance do not supply external capacitor leakage
  or total error. No leakage correction or accuracy bound is computed here.
- `timer-app-03` recommends at most 100 kHz to reduce distortion. Being well
  below that guidance does not establish accuracy. `timer-app-07` edge times
  belong to CL = 15 pF, VCC = 5–15 V, TA = 25 C, not an arbitrary load.
- `timer-app-timing-budget-unknown` remains open: current section 5.6 has no
  initial timing-error specification; revision J removed it. Older limits
  cannot be imported. `timer-app-mode-duty-unknown` is resolved only for this
  synthetic choice of topology and labeled fractions, not a real requirement.
  `timer-app-startup-control-unknown` remains open. Reset and bypass guidance
  in `timer-app-08` does not establish startup or unwanted-trigger immunity.

### Resistor evidence is not an installed-resistance guarantee

Source `vishay-crcw060310k0fkea-20035-20260414`, Vishay document 20035,
14-Apr-2026, concerns exact CRCW060310K0FKEA.
[Official source reference](https://www.vishay.com/docs/20035/dcrcwe3.pdf).
`vishay-crcw060310k0fkea-rating-01` records 10 kohm, ±1% and ±100 ppm/K;
its TCR test sequences are 20 → -55 → 20 C and 20 → 155 → 20 C. Those
separate data are not a combined installed hot/aged resistance envelope.
`vishay-crcw060310k0fkea-rating-02` and
`vishay-crcw060310k0fkea-rating-03` retain endurance, mounting,
ambient derating and film-temperature conditions; no thermal or lifetime
calculation is made here. Issues `vishay-crcw060310k0fkea-application-inputs`,
`vishay-crcw060310k0fkea-ordering-scope`, and
`vishay-crcw060310k0fkea-rights` remain applicable. See the separate
[DC resistor arithmetic example](resistor-dc-bound.md) for its own supplied
operating interval; **that interval is not imported here**.

### MLCC evidence is not a constant timing-C guarantee

The exact KEMET C0603C104K5RACTU source is
`kemet-c0603c104k5ractu-specsheet-20261028` (generated October 28, 2026;
not an electrical revision), supplemented by `kemet-c1002-x7r-20260901`
(C1002_X7R, September 1, 2026).
[Exact-part source](https://yageogroup.com/component-documentation/download/specsheet/C0603C104K5RACTU?lang=en)
and [family source](https://yageogroup.com/content/datasheet/asset/file/KEM_C1002_X7R_SMD).

- `kemet-mlcc-cap-01`: 100 nF ±10% is a nominal-capacitance test at 1 kHz,
  1.0 Vrms, with a 48-hour referee reference. It is not a capacitance
  guarantee throughout the nonzero timing-node excursion above.
- `kemet-mlcc-cap-03`: the X7R ±15% temperature characteristic uses zero DC
  bias over -55–125 C relative to 25 C; it is not a combined bias/tolerance/
  aging envelope. `kemet-mlcc-cap-04` gives aging per decade-hour, not per
  hour; the actual age/thermal history is absent.
- `kemet-mlcc-cap-07` preserves a qualitative simulated DC-bias trend, not
  a guaranteed minimum or extracted numerical curve. `kemet-mlcc-cap-02`
  voltage rating/withstand information does not fill that gap.
- `kemet-mlcc-effective-c-unknown` remains unresolved. A real timing design
  needs justified capacitance behavior over its actual voltage excursion,
  temperature, age, signal conditions and leakage, not just a nominal label.
  No selected working capacitor, bypass adequacy or footprint qualification
  follows; `kemet-mlcc-pcb-and-decoupling-unknown` and
  `kemet-mlcc-procurement-and-revision-limits` are not closed by this example.

## Immutable accepted-metadata baseline

Remote main was observed at `4157176490d360692fc5b6d15e0be236a984c829` on
2026-10-28. The following JSON bytes were read from that immutable commit,
not inferred from a mutable working tree. Paths are under `knowledge/intake/`:

| Batch file | SHA-256 of accepted JSON |
| --- | --- |
| [`ne555-timing-application-constraints.json`](../../../knowledge/intake/ne555-timing-application-constraints.json) | `bac46b80f8a5bbd63c0974457f793e1d5929aa46350944b1f06acea1af6ce3b5` |
| [`timer-reference-driver-pilot.json`](../../../knowledge/intake/timer-reference-driver-pilot.json) | `e2539fa657705a79dc6245cedb1b98c1a2eb0237e865deb7afa064a5167fe695` |
| [`vishay-crcw060310k0fkea-rating-constraints.json`](../../../knowledge/intake/vishay-crcw060310k0fkea-rating-constraints.json) | `a8bb3d06470509605dee99d5b52f9854eac29a3c406781a7171a005505acb438` |
| [`kemet-c0603c104k5ractu-capacitance-constraints.json`](../../../knowledge/intake/kemet-c0603c104k5ractu-capacitance-constraints.json) | `e4cb0113234ed90ed6f9ef7e2c32cad842d6f9b7648ac017b16b2cbbe9903a1b` |

Recorded original-PDF identities (not JSON hashes):

| Source | Recorded PDF SHA-256 |
| --- | --- |
| TI SLFS022K, both named timer sources | `a3756e59fd06d0ba736edf9ffe71d99d2aae33fb7e49fedc86165a241179f4a6` |
| Vishay 20035 | `3e595b731fa5916bcdce5b28cd76b5eb0b0b3cdd7da474c677173264748cdf5f` |
| KEMET exact-part sheet | `f4b35dc168d8e66d40cd476e5cef8431524033dbdf9ac33d12f3ef2850b59a02` |
| KEMET family sheet | `d8e6ca6631862e31a19b90b6cfe13f1b20153c2efd6c8e30f1a5d5ba147aa908` |

These are existing noncanonical intake records accepted under Agent owner
delegation, not canonical approval or human review. This example inspects
accepted metadata and receipts; it claims no new manufacturer download,
source-byte/visual audit, latest-revision guarantee or redistribution license.
No original PDF, chart or manufacturer prose is reproduced.

## Reproduce the fixed-input arithmetic

Python 3 standard library only. Rational arithmetic checks the written decimal
coefficients and fractions, not the physical exactness of the source model.
This is one example, not a generic calculator or source validator.

```python
from fractions import Fraction as F

ra = rb = F(10000)
c = F(1, 10_000_000)  # Synthetic constant 100 nF, not a selected MLCC.
k_time, k_freq = F(693, 1000), F(144, 100)
th = k_time * (ra + rb) * c
tl = k_time * rb * c
period = k_time * (ra + 2 * rb) * c
frequency = k_freq / ((ra + 2 * rb) * c)
high, low = th / period, tl / period
assert th == F(693, 500000) and tl == F(693, 1000000)
assert period == th + tl == F(2079, 1000000)
assert frequency == 480
assert (high, low) == (F(2, 3), F(1, 3))
assert high + low == 1
assert 1 / period == F(1000000, 2079)
assert k_time * k_freq == F(6237, 6250) != 1
print("Nominal approximate-model frequency (Hz):", frequency)
print("Model high fraction:", high, "; low/driver fraction:", low)
print("Reciprocal of rounded model period (Hz):", float(1 / period))
print("Hardware timing accuracy: UNKNOWN; circuit qualified: False")
```

## Executable fixed-example regression

Run from the software checkout with an explicit intake workspace:

```sh
PYTHONPATH=src:. python3 configs/pcbknowledge_ne555_astable_eval.py --repo .
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_ne555_astable_eval -v
```

The standard-library evaluator pins the four accepted JSON files above and
returns full source/fact/condition/evidence payloads plus all source-local
warnings. The mixed timer pilot contributes NE555 records only, not TL431 or
ULN2003A claims. It retains `canonical: false`, `human_reviewed: false` and
`NOT_LOCALLY_VERIFIED`; inspecting committed metadata is not rechecking PDFs.
It neither mutates intake nor closes its unresolved application warnings.

Ten fixed regression cases comprise this nominal calculation and nine scope
refusals (CMOS substitution, diode topology, startup, altered control, unknown
reset, initial-tolerance substitution, missing C, hot operation and an invented
maximum error). No user circuit input is accepted. Changed or extra inputs are
outside this example, not a judgment that those circuits are impossible.
Semantic mutation tests detect swapped duty fractions, conflated rounded
formulas and promotions to hardware guarantees. The CLI exits 0 for regression
PASS, 1 for a result mismatch and 2 for missing/changed evidence or invalid
invocation. PASS never means a timing accuracy or component qualification.
Historical retrieval manifests and practical-task evaluation remain unchanged.
