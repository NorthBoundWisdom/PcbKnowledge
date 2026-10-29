# INA219: fixed register decoding and conditional scale arithmetic

## Scope

This example reuses accepted metadata for Texas Instruments INA219AIDCNR,
DCN (SOT-23, 8 pins), SBOS448G. It adds concrete numeric regression, not new
manufacturer knowledge. Existing `test_measurement_timing_replay.py` already
checks preservation of calibration and readiness semantics; this example does
not replace that coverage or claim those topics were previously untested.

The evaluator has no device I/O, arbitrary user-input CLI, driver, register-state
emulator, timing sequence or physical accuracy model. Synthetic current and
power codes are supplied **independently** of shunt and bus codes. They are not
asserted to be a mutually consistent physical measurement. The tool does not
predict the chip's shunt-times-CAL arithmetic, rounding, saturation or overflow.

## Fixed arithmetic example

Assume the supplied 16-bit shunt word `0xFF9C` has already been correctly
sign-extended for its PGA representation. Its signed code is -100, so the
recorded 10-uV scale gives **-1000 uV**. This assumption is essential: the tool
is not a universal decoder for every raw PGA representation.

Bus word `0x1F42` gives `(word >> 3) * 4 = 4000 mV`, with CNVR=1 and OVF=0.
All three low bits are excluded from voltage data, including reserved bit 2.
Neither CNVR=1 nor OVF=0 proves analog validity, accuracy, freshness or coherence.
Raw-voltage arithmetic remains separate from calibration-dependent outputs.

For synthetic `Current_LSB = 0.001 A` and `RSHUNT = 0.1 ohm`:

```text
ideal candidate = 0.04096 / (0.001 * 0.1) = 409.6 = 2048/5
truncated candidate = 409
fixed-zero FS0 effective value = 408
```

The report keeps these three quantities separate. Integer truncation precedes
clearing the fixed-zero bit. Out-of-range truncated values are rejected before
that operation; overflow is never silently masked into a register value.
Effective zero is unusable for conditional scaling. No ideal-gain assertion
follows from matching an explicitly supplied actual CAL to 408.

With **independently supplied** current register `0xFF9C`, power register 250,
and actual calibration 408, the declared scaling arithmetic is:

```text
signed current code = -100; current = -100 * 0.001 A = -0.1 A
unsigned power code = 250; Power_LSB = 20 * 0.001 W = 0.02 W
power = 250 * 0.02 W = 5 W
```

These deliberately independent inputs are not a claim that the shunt/bus codes
above generate those current/power codes. The power register is treated as
unsigned; signed-current interpretation is not applied to power. At the numeric
boundaries, signed code `0x8000` scales to -32.768 A and unsigned power word
`0xFFFF` scales to 1310.7 W under the same declared LSB. Those are arithmetic
results, not allowable currents, actual loads or achievable operating points.

## Refusals and unresolved requirements

- Unknown actual calibration, zero calibration, a mismatch with the planned
  effective value, missing/invalid positive scale inputs, or OVF=1 suppress
  interpreted current and power. Raw voltage arithmetic can remain available.
- Zero current/power after reset with zero CAL does not mean zero physical load.
  Actual CAL is an explicitly supplied assumption here, not a register readback.
  Odd actual-CAL values are rejected because fixed FS0 cannot be one.
- Register words must be integers in 0..65535, not booleans, strings or floats.
  Positive scale inputs use bounded decimal strings and exact rational
  arithmetic; expressions, NaN, infinity, zero and negatives are refused.
- Consistency means only that supplied actual CAL matches the plan and declared
  scaling is applied. It does not establish gain accuracy, shunt resistance
  validity, PGA headroom, wiring, Kelvin layout, clipping or thermal behavior.
- CNVR=0 does not prevent arithmetic on supplied codes, but no result is called
  fresh. CNVR=1 cannot resolve the accepted source's page-10/page-23 readiness
  wording conflict. A guaranteed poll/read/clear sequence remains **BLOCKED**
  in every case, including CNVR=1/OVF=0. Intervening accesses and sample coherence
  are not modeled, and no timing or device-side-effect contract is invented.

All results retain `physical_accuracy: UNKNOWN`, `analog_validity: UNKNOWN`,
`freshness_and_coherence: UNKNOWN` and `circuit_qualification: NOT_ESTABLISHED`.
All three original source warnings, including the readiness conflict, remain
unchanged and unresolved.

## Pinned evidence and reproduction

The sole batch is
`knowledge/intake/ina219-measurement-calibration-constraints.json`, SHA-256
`9b5206cb30d221dffcb9b5b036a67e2ee623ea07f15ad43fca4de81d46d2e3cb`.
All eight full facts and three full warnings preserve source identity, exact
revision, evidence anchors and conditions. Original PDF identity is recorded
metadata, not a new source-byte audit. This work performs no network or raw-source
access and establishes no fresh source-access or legal clearance.

```sh
PYTHONPATH=src:. python3 configs/pcbknowledge_ina219_register_eval.py --repo .
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_ina219_register_eval -v
```

Ten fixed CLI cases have independent literal result oracles. Ten tests cover
signed/unsigned boundaries, every low-bit combination, odd/even CAL, range and
zero rejection, independent supplied-register scaling, full source payloads,
byte pins, evidence changes during execution, input immutability, actual CLI
execution and 15 numeric/authority output mutations. Invalid evidence fails
closed. Exit 0 means regression PASS, 1 a mismatch and 2 invalid invocation or
unavailable evidence; none means hardware validation.

Reports remain `canonical: false`, `human_reviewed: false` and
`NOT_LOCALLY_VERIFIED`. This example changes no intake records, source issues,
historical evaluation or source policy. Independent review, full repository
checks and published-commit CI remain separate gates.
