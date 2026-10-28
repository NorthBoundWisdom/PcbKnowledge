# Synthetic DC resistor bound: CRCW060310K0FKEA

## Question and narrow result

For an explicitly synthetic steady-DC voltage interval of **4.75–5.25 V**
across one resistor, and an independently supplied operating-resistance
interval of **9800–10200 ohm**, what current and dissipation bounds follow?

Under those assumptions, current is enclosed by **0.465686–0.535715 mA**
and dissipation by **2.212009–2.812500 mW**, with displayed endpoints rounded
outward. The exact upper dissipation is **2.8125% of the source's standard
0.10-W P70 reference**. This is a positive bounded arithmetic result, **not
approval of a part, PCB, thermal design, or continuous working rating**.

This example responds to the application-input gap identified by the
[practical task evaluation](../practical-task-evaluation-2026-10-28.md).
It does not alter that frozen evaluation, its eight cases, or their outcomes.
It adds no annotation, new source fact, canonical approval, or human acceptance.

## Supplied assumptions, not manufacturer guarantees

- This is DC across the resistor terminals, not a nominal supply before wiring
  drops and not an RMS shorthand for an unspecified waveform. Each modeled
  operating point has positive constant voltage in `[19/4, 21/4] V`.
- The resistor is modeled as ohmic, with positive operating resistance in
  `[9800, 10200] ohm` **at every modeled operating point**. This interval is
  invented for the example and supplied independently; it is not measured
  hardware evidence or a manufacturer's operating-resistance guarantee.
- The resistance interval is deliberately **not derived from the initial
  nominal 10-kohm ±1% tolerance**. That tolerance does not silently include
  temperature, self-heating, assembly effects or aging. No reference-temperature
  tolerance is promoted to a hot/aged guarantee here.
- All combinations in the V/R rectangle are allowed. Unknown correlation cannot
  make the bounds narrower; if a real joint operating domain is smaller, these
  bounds remain conservative provided both supplied intervals still hold.
- No actual ambient temperature, film temperature, mounting, copper, airflow,
  service life, accuracy target or transient waveform is supplied. The synthetic
  resistance assumption does not establish any of these physical conditions.

A real application must justify its operating-resistance interval over its
actual temperature, self-heating and service-life domain before reusing these
numbers. Without that evidence, only the conditional arithmetic is established.

## Accepted evidence and its limits

The existing noncanonical intake batch is
[`vishay-crcw060310k0fkea-rating-constraints.json`](../../knowledge/intake/vishay-crcw060310k0fkea-rating-constraints.json),
introduced on main at `a68ac1c5858e8ce39aa14b901077713dbaccd4ba`.
Example baseline: `b04fed50dff7853d5ad2663784eb0305bb02f331`; the
accepted source JSON has the same Git blob
`7872d07a42954061e581424479c315a120e4e646` in both commits.
Accepted JSON SHA-256:
`a8bb3d06470509605dee99d5b52f9854eac29a3c406781a7171a005505acb438`.

Source ID: `vishay-crcw060310k0fkea-20035-20260414`.
The recorded source is Vishay document 20035, revision 14-Apr-2026,
[official PDF reference](https://www.vishay.com/docs/20035/dcrcwe3.pdf).
Recorded PDF SHA-256:
`3e595b731fa5916bcdce5b28cd76b5eb0b0b3cdd7da474c677173264748cdf5f`
(150402 bytes, 13 pages). This example uses the accepted metadata and its
review receipt; it does not claim a fresh PDF download, local byte audit,
visual review or guarantee that the recorded revision is latest.

The exact orderable is CRCW060310K0FKEA: CRCW0603, 0603 imperial / RR1608M
metric, 10 kohm, F tolerance, K TCR, EA packaging. Relevant record IDs:

- `vishay-crcw060310k0fkea-rating-01` (pages 2, 3, 8): identity, ±1% tolerance
  and ±100 ppm/K TCR. TCR test sequences are 20 → -55 → 20 C and
  20 → 155 → 20 C. This is not a combined accuracy envelope.
- `vishay-crcw060310k0fkea-rating-02` (pages 2, 8): standard P70 = 0.10 W
  and distinct extended P70 = 0.125 W, referenced to 70 C ambient. The summary
  concerns stability class 1 at P70/Umax; the endurance procedure cycles
  1.5 h on / 0.5 h off and has separate permissible changes with additive ohmic
  terms. Extended 8000-hour drift is unspecified, not zero. This example uses
  **only the standard 0.10-W number as a numerical reference**, not as an
  unconditional allowance and not as a drift bound.
- `vishay-crcw060310k0fkea-rating-03` (pages 1, 6, 8): separate derating curves
  start falling above 70 C ambient and reach zero at 155 C; film temperature
  must not exceed 155 C. Temperature rise depends on resistor plus PCB, and
  test mounting references EN 60115-8 5.2.2. No user-PCB thermal path is supplied.
- `vishay-crcw060310k0fkea-rating-04` (pages 1, 2, 8): 75-V AC-RMS/DC ceiling
  is not permission to apply 75 V at every resistance. The recorded square-root
  voltage formula belongs to the endurance-test context. It is not used to
  derive a permissible continuous voltage in this example.
- `vishay-crcw060310k0fkea-rating-05` (pages 5, 9): overload/pulse tests retain
  their own duration, repetition, power, voltage and drift conditions. They are
  not imported into the DC calculation.

All three batch warnings remain applicable: `vishay-crcw060310k0fkea-rights`,
`vishay-crcw060310k0fkea-application-inputs`, and
`vishay-crcw060310k0fkea-ordering-scope`. Public reference is not redistribution
permission; application conditions are unresolved; ordering-code interpretation
is not procurement availability or transfer to other parts. Accepted Agent
review under owner delegation remains noncanonical and not human review.

## Exact calculation

For positive V and R, both `I = V/R` and `P = V^2/R` increase with V and
decrease with R. Thus the lower bound uses Vmin/Rmax and the upper uses
Vmax/Rmin; no statistical independence or probability claim is needed.

```text
Imin = (19/4) / 10200 = 19/40800 A
Imax = (21/4) / 9800  = 3/5600 A
Pmin = (19/4)^2 / 10200 = 361/163200 W
Pmax = (21/4)^2 / 9800  = 9/3200 W = 0.0028125 W
Pmax / (1/10 W) = 9/320 = 0.028125 = 2.8125%
```

The percentage is a ratio to a source reference, **not thermal headroom,
operating margin, a reliability prediction, or a pass/fail verdict**. Being
numerically below P70 does not establish the film-temperature limit, applicable
derating, assembly suitability or long-term resistance stability.

## Reproduce with Python's standard library

Run the following fixed-input script with Python 3. It is a calculation check
for this single example, not a generic calculator, solver or source validator.
It uses rational arithmetic throughout. Decimal displays use integer scaling:
floor for lower endpoints and ceiling for upper endpoints (six decimal places
in mA/mW). The exact fractions remain authoritative.

```python
from fractions import Fraction as F
import json

v_lo, v_hi = F(19, 4), F(21, 4)
r_lo, r_hi = F(9800), F(10200)
p70 = F(1, 10)  # Standard reference only; not application permission.
assert 0 < v_lo <= v_hi and 0 < r_lo <= r_hi
current = (v_lo / r_hi, v_hi / r_lo)
power = (v_lo**2 / r_hi, v_hi**2 / r_lo)
assert current == (F(19, 40800), F(3, 5600))
assert power == (F(361, 163200), F(9, 3200))
for v in (v_lo, v_hi):
    for r in (r_lo, r_hi):
        assert current[0] <= v / r <= current[1]
        assert power[0] <= v**2 / r <= power[1]
assert power[1] / p70 == F(9, 320)
assert power[1] < p70  # Numerical comparison only.

def outward_milli(value, upper):
    scaled = value * 1000 * 10**6
    n, d = scaled.numerator, scaled.denominator
    ticks = -(-n // d) if upper else n // d
    rounded = F(ticks, 1000 * 10**6)
    assert rounded >= value if upper else rounded <= value
    return f"{ticks // 10**6}.{ticks % 10**6:06d}"

receipt = {
    "example": "synthetic-resistor-dc-bound",
    "current_A_exact": [str(x) for x in current],
    "power_W_exact": [str(x) for x in power],
    "current_mA_outward": [outward_milli(x, i == 1)
                           for i, x in enumerate(current)],
    "power_mW_outward": [outward_milli(x, i == 1)
                         for i, x in enumerate(power)],
    "power_upper_over_standard_P70_exact": str(power[1] / p70),
    "board_qualified": False,
}
assert receipt["current_mA_outward"] == ["0.465686", "0.535715"]
assert receipt["power_mW_outward"] == ["2.212009", "2.812500"]
print(json.dumps(receipt, indent=2, sort_keys=True))
```

## Explicit exclusions

No zero-ohm jumper/current rating, pulse or overload qualification, AC/RMS
waveform inference, thermal suitability, total accuracy budget, long-term drift
bound, safety/compliance certification, footprint approval or other-part
substitution follows. TCR, actual film temperature, long-term drift, waveform
and mounting remain separate engineering inputs/evidence. The calculation does
not solve for temperature or prove that the supplied resistance interval holds.

## Executable fixed-case regression

Run `python3 configs/pcbknowledge_resistor_dc_eval.py --repo .` to reproduce
this example with the complete pinned seven-fact batch and all three warnings.
The script accepts an explicit metadata workspace, but no user scenario input.
It does not download or reverify the original PDF. The fixed regression includes
14 synthetic cases covering the example, zero-voltage arithmetic, missing or
invalid intervals, initial-tolerance substitution, identity mismatch and rejection
of AC/pulse interpretations. Negative voltage is outside this bounded example;
its refusal is not a claim that a resistor cannot operate with negative voltage.

`CONDITIONAL_DC_BOUNDS` means only that the stated nonnegative DC and positive
operating-resistance assumptions support the arithmetic. The output independently
retains `NOT_ESTABLISHED` for operating-resistance guarantee, thermal qualification
and circuit qualification. Even a zero-power calculation does not certify the
part or the assumptions. The standard-P70 comparison is numerical only; it is
never an allowed-power decision. `PASS`/exit 0 describes expected regression
outcomes, including expected refusals, not application acceptance.

The regression uses exact rational endpoints and outward six-decimal mA/mW
displays. Source metadata is bound by its recorded JSON SHA-256; changed bytes,
missing warnings or different source identity require review rather than automatic
pin refresh. Full original facts, source conditions and warnings accompany results.
This is an execution of the existing conditional example, not new manufacturer
knowledge, canonical approval, human review or hardware verification.

Focused implementation verification: 14 unit tests passed on 2026-10-28, including
441 exact-arithmetic grid points, display enclosure, wrong-arithmetic and false
qualification mutations, full evidence preservation and evidence-change refusal.
Full repository gates and published-commit CI are recorded by the publication
coordinator separately; this focused receipt does not claim they ran.

Independent Agent review on 2026-10-28:
`agent:/root/check_and_resume_knowledge/review_resistor_eval` replayed all
14 focused tests, independently checked 20 endpoint/rounding combinations and
compared the complete seven facts and three warnings to the pinned metadata.
No blocking findings remained. Author:
`agent:/root/check_and_resume_knowledge/implement_resistor_boundary_eval`.
This review is under owner delegation, not a human or source-original audit.
