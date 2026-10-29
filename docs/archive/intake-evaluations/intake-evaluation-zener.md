# Zener condition evaluation

This batch covers the exact commercial Vishay BZX84C5V1-E3-08 in SOT-23.
The C tolerance, commercial E3 grade and -08 reel identity are not interchangeable
with B, HE3_A or -18 orderables. Electrical revision 1.1, 24-Jan-2024, is separate
from the 2026 legal appendix. See the source review (`git show intake-final:knowledge/intake/bzx84c5v1-zener-constraints-review.md`)
for actual-byte identity, exact official ordering evidence and independent
rendered-page review. Current stock, future supply and installed qualification
are not established by that identity evidence.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-zener.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_zener_replay -v
```

The compact successor contains one new batch pin and 30 recipes, referencing
the immutable thermistor manifest by exact SHA-256. Its 708 retrieval cases and
33 batch pins are inherited without copying or rewriting them. The successor
contains 738 retrieval cases plus the unchanged six disposition cases. Thirty
additions cover six exact parameters, all facts, all warnings, three kind
selections, twelve negative fact selections and seven negative warning selections.
Expected IDs are justified from reviewed scope, not blindly refreshed CLI output.

## Useful bounded decisions

- The nominal Zener voltage and tabulated min/max retain their test current,
  ambient and pulse-specification scope. Missing pulse duration stays unknown;
  none is a guaranteed continuous reference or arbitrary-load clamp voltage.
- Dynamic resistance is small-signal evidence at 1 kHz and specified bias
  currents. The two bias-current rows cannot be swapped or converted into a
  constant DC resistor or a global linear model of the Zener curve.
- The leakage column lacks an explicit min/max label in this source. A
  conditioned tabulated value is not promoted to a guaranteed maximum, a
  full-temperature limit, or leakage at the nominal Zener voltage.
- The temperature-coefficient interval includes both signs. It does not mean
  zero drift or supply a qualified wide-temperature reference error budget.
- Absolute power rows have different thermal conditions. Junction-to-lead and
  junction-to-ambient resistance are not interchangeable. No unspecified board
  mounting, ambient temperature or continuous current permission is invented.
- Commercial orderable identity is not automotive, assembly, ESD-system or
  safety qualification. A catalog marking does not establish a complete CAD
  footprint or an installed protection network.

Negative recipes exclude another revision/source identity, manufacturer,
voltage, tolerance, grade, reel and package. They also exclude unsupported
reference accuracy, hot leakage, fault-clamp, pulse-energy and safe-current
claims. Empty selection means no scoped candidate, not absence of all possible
evidence or permission to operate a circuit. Every selected fact retains full
source metadata and all three warnings about bias/load accuracy, pulse/thermal
protection and grade/source limitations.

## Semantic regression and limits

Synthetic test identity, values and conditions are invented, not copied from
source tables. Forty-three same-ID mutations exercise changed identity,
test-current changes, unknown pulse duration and temperature-span promotion,
dynamic-versus-DC resistance,
leakage-limit promotion, temperature extrapolation, thermal-boundary confusion,
absolute-to-recommended promotion, erased warnings and verification upgrades.
Genuine CLI responses are acquired once, stored immutably and deserialized afresh
for each mutation. IDs alone still match while the complete-payload check fails;
pristine replay and unchanged fixture bytes are checked separately.

The successor test checks the accepted pair hashes, exact parameter recipes,
all new facts and warnings, and byte-pinned preservation of prior cases. This
is retrieval and metadata-integrity validation, not a circuit solver or proof
of source truth. Independent source review is separate. Ordinary retrieval stays
canonical:false, human_reviewed:false and NOT_LOCALLY_VERIFIED. No original PDF,
HTML, complete extract or rendered page is committed or packaged. Full final
gates and exact published-commit CI are separate acceptance evidence.
