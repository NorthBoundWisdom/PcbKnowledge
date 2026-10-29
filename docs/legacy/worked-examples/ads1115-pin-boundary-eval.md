# Executable ADS1115 fixed pin-rail examples

This is a small regression evaluation of **one engineering comparison**, not a
board checker or an answer engine. It uses the already reviewed ADS1115 evidence
and the [application input card](../../archive/application-handoffs/ads1115-input-acquisition.md).
It does not collect new facts or change that card's frozen receipt.

## Run

```sh
python3 configs/pcbknowledge_ads1115_boundary_eval.py --repo .
```

Only an explicit repository is accepted. There is no board-input, voltage-input,
configuration, schema, network, source-download or write operation. Fourteen fixed
synthetic scenarios are embedded in the executable. Exit 0 means all expected
regression outcomes matched; exit 1 means a wrong result; exit 2 means evidence
or evaluation input could not support running. CLI argument errors also exit 2.

The output separates `evaluation_status` from each case's narrow `outcome` and
`circuit_qualification: NOT_ESTABLISHED`. A PASS is **not an electrical pass**.

## What is actually calculated

For the exact ADS1115IDGSR / DGS 10-pin VSSOP / SBAS444E identity, the synthetic
state assumes steady powered operation, VDD exactly 3.3 V, GND exactly 0 V and
ambient exactly 25 C. PGA magnitude is fixed at 4.096 V. These are invented test
assumptions, not user-board measurements, tolerances or manufacturer guarantees.
They narrow this calculation; no general operating envelope is inferred.

Each input pin's supplied interval is compared independently with [0, 3.3] V.
Decimal strings are converted to exact rational numbers, so a value immediately
above 3.3 V cannot round down into the allowed interval. The comparison is derived
from the stored recommended pin rail, not the PGA range or absolute maximum.

| Synthetic variation | Expected narrow result |
|---|---|
| AINP 0-4 V, AINN 0 V | Recommended upper pin rail exceeded |
| Same evidence, AINP 0-3 V | No pin-rail violation in these stated intervals |
| AINP 4 V, AINN 3 V | Upper pin violation despite only 1 V differential |
| AINP 1 V, AINN -0.1 V | Lower pin violation despite a small differential |
| Both pins exactly at or between 0 and 3.3 V | Inclusive boundary comparison only |
| A pin just above 3.3 V or just below 0 V | Exact arithmetic detects violation |
| AINP 0 V, AINN 1 V | Negative difference alone is not a pin-rail violation |
| Missing pin, missing supply, malformed or reversed interval | Not evaluable; no default zero |
| Known violation plus another pin unknown | Violation and unknown both retained |
| Wrong package | Not evaluable; no family/package fallback |

No-violation is not a supply-range, PGA/differential-range, accuracy, settling,
interface or circuit approval. No input impedance, RC time constant, error budget,
component selection, clamp design, powered-off behavior or transient safety is
calculated. The 100-kohm sensor / 860-SPS / 1-mV target from the larger application
card remains outside this one predicate. Input intervals are assumed bounds, not
proof of real trajectories or sample coverage.

Malformed/nonfinite/bool/float/expression inputs cannot establish no violation;
they are returned as not-evaluable field names. The internal helper is used only
by fixed fixtures and tests, not exposed as a general user-input API. A missing
or different fixed operating assumption is likewise outside the example scope.

## Evidence and preservation

The evaluator binds these existing JSON bytes, retaining their full reviewed
source/fact objects, conditions, anchors, source-local warnings and verification
markers in its output:

- `knowledge/intake/interface-ic-pilot.json`, SHA-256
  `3738281495ba3e2fa1120e0f501239ab1608c6ce0781e7dc4b5c0f2b32b7ab55`.
  Selected reference `b003-ti-ads1115-e-07`, source `ti-ads1115-e`:
  `recommended_operating`, `analog_input_pin_voltage`, GND minimum / VDD maximum,
  SBAS444E printed page 4, section 5.3 and footnotes 1-2.
- `knowledge/intake/ads1115-input-interface-constraints.json`, SHA-256
  `746353eeab5df619970c2cc2767a440b7fe92e5914fa42577208fdb9e233b5e7`.
  All nine `ads1115-app-01` through `09` source candidates are retained as context,
  with the complete three application warnings. Only `ads1115-app-01` explains
  why PGA is not pin-voltage permission; the other evidence is not converted into
  a solved acquisition, timing, interface or startup analysis.

Both sources record original PDF hash
`eefff4d412ce2dcd7e659f47238edc9b2fa02e5971f2625af730502033701834`.
This run verifies **repository metadata bytes**, not that original PDF. The source
revision is SBAS444E, not a guarantee of global latestness. Full fact evidence
retains page references and unknown bounding boxes. Source/fact statuses remain
Agent-reviewed noncanonical intake; human acceptance is not inherited.

Missing/changed pinned files stop evaluation. Existing intake parsing rejects
malformed records and unsafe paths. Metadata is read again after evaluation to
reject observed changes; this is not a transactional filesystem snapshot, so use
a clean immutable checkout for reproducible work. The report records selected
file pins and a deterministic complete evidence projection hash. Other batches
are validated by the existing loader but are not evidence for this comparison.
No originals, new facts, source corrections or owner certification are produced.

## Verification scope

Focused tests exercise the fourteen cases, fixed-interface CLI exit codes,
independent-pin checks, exact arithmetic, missing/malformed/unsupported inputs,
known-violation-plus-unknown preservation, unchanged input objects, fresh fixture
instances, real pinned metadata, stale/missing/invalid bytes and read drift.
Mutation probes demonstrate that an always-no-violation answer or a fabricated
circuit qualification causes regression FAIL despite unchanged retrieved evidence.
All three application warnings remain attached on no-violation cases through the
shared complete evidence section, not silently resolved by this calculation.

The existing 539-case retrieval evaluation is a separate gate and remains
unchanged. This example does not measure general reasoning accuracy, complete
an autonomous circuit-design task or close the formal private pilot.

Independent reviewer: `agent:/root/assess_next_knowledge_increment/review_ads1115_boundary_semantics`,
2026-10-28, checked the implementation and complete evidence projections, ran all
16 focused tests without skips and independently compared 35 exact-arithmetic
pin pairs. This is Agent review under owner delegation, not source-byte re-audit,
human approval or circuit validation. Local full gates passed Build/Test each
339 tests, existing 539-case replay, English/public/vendor checks, workspace and
Agent validation, Config and metadata-only Package. Remote CI is a separate
exact-published-commit receipt, not asserted by this local result.
