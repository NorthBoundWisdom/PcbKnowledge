# Ferrite bead condition evaluation

This slice covers the exact Bourns MH2029-601T high-current chip bead. The
[source review](../knowledge/intake/mh2029-ferrite-constraints-review.md) records
actual PDF bytes, electrical revision 09/23 separately from the legal appendix,
and independent rendered-page review. It does not establish lifecycle status,
certification, filter selection or an installed circuit's performance.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-ferrite.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_ferrite_replay -v
```

The compact successor pins the unchanged photodiode manifest by SHA-256,
inheriting 764 retrieval cases and 35 source-batch pins. Sixteen new recipes
cover five exact parameters, all five facts, all three warnings, incorrect
source/device/package/manufacturer selections and unsupported network attenuation,
hot-ambient current or biased-impedance guarantees. Expected exclusions derive
from the source scope, not blind refresh of CLI output. Total replay is 780
retrieval cases plus six separate unchanged disposition cases.

## Practical boundaries

- Impedance magnitude at the stated frequency, small signal and temperature
  is not DC resistance, an attenuation value or a flat frequency response.
  The signal amplitude convention and applied DC bias are not invented.
- Maximum DC resistance remains separately conditioned. No full-temperature
  bound is inferred from a room-temperature entry.
- Rated current uses the source's temperature-rise criterion. The operating
  temperature range and rated current do not by themselves permit their
  simultaneous endpoints; mounting, self-heating and ripple remain relevant.
- The frequency plot illustrates Z, R and X for the exact part. It is not
  digitized into guaranteed limits, relabeled typical without source support,
  or used to predict arbitrary DC-bias behavior.
- Actual source/load impedances, noise spectrum, capacitor parasitics and
  layout are missing. Neither a ferrite impedance rating nor a source hit
  establishes system attenuation, stability or a qualified supply rail.

Synthetic fixtures use invented identity, values and conditions. Twenty-five
same-ID mutations test dropped qualifiers, confusion between impedance and DCR,
unknown-to-known upgrades, false hot-current and attenuation claims, lost
warnings and authority promotion. Complete source/fact/warning objects are
compared; immutable genuine CLI baselines are freshly copied for each mutation.
This is metadata preservation testing, not an electrical circuit simulator.

The successor invariant separately binds the accepted source pair and prior
history. Ordinary retrieval remains canonical:false, human_reviewed:false and
NOT_LOCALLY_VERIFIED. No raw PDF, complete source extract, graph image or
manufacturer table is committed or packaged. Source review, full repository
gates and exact published-commit CI are distinct evidence.
