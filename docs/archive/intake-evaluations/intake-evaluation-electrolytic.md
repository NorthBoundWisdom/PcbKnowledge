# Aluminum electrolytic condition evaluation

This batch covers Vishay BCcomponents MAL214636471E3, 146 RTI, 470 uF / 25 V,
Form TFA, nominal 10 x 16 mm radial aluminum electrolytic. The 22-Mar-17
electrical revision is separate from the 2026 legal appendix. An explicit source
ordering example and separately hashed official identity listing support the
orderable; neither proves inventory or future supply. See the [source review](../../../knowledge/intake/146rti-bulk-capacitor-constraints-review.md)
for actual-byte identity and independent rendered-page review.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-electrolytic.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_electrolytic_replay -v
```

The small successor delta stores one new source pin and 30 recipes, referencing
the immutable PTC manifest by exact SHA-256. The preceding 648 retrieval recipes
and 31 batch pins are inherited, not copied or rewritten. The resolved aggregate
contains 678 retrieval cases plus the unchanged six dispositions. Thirty additions
cover seven exact parameters, all facts, all warnings, three kind selections,
twelve negative fact selections and six negative warnings. Expected IDs are
selected from independently reviewed source records, not refreshed CLI output.

## Useful bounded decisions

- Initial capacitance and tolerance have a measurement frequency and temperature;
  they do not establish aged, loaded or all-frequency effective capacitance.
- RMS ripple current retains 100-kHz / 125-C conditions. Selected frequency
  factors are not a qualified mixed-spectrum heating budget or arbitrary curve fit.
- Impedance magnitude is not ESR. A low-frequency dissipation-factor expression
  does not create guaranteed high-frequency ESR for this exact part.
- Rated voltage, surge/reverse bounds and timed leakage have different meanings.
  None supplies a permissible real-board surge duration, repetition or polarity.
- Exact TFA packaging and case dimensions do not establish a complete footprint,
  vent clearance, mounting procedure or solder-process approval.
- Case-specific endurance and useful-life tests differ in duration and applied
  conditions. Neither is guaranteed field lifetime; post-test change criteria
  are not the initial tolerance. No ten-degree doubling rule is synthesized.
- The source lifetime figure points to a different table number from the case
  duration table. The warning remains visible; no graphical lifetime estimate
  is inferred or source wording silently corrected.

Negative queries distinguish wrong source revision, vendor, orderable, voltage,
package and lead form. Additional absent-parameter probes check that no standalone
field-lifetime, broadband-ESR, mixed-spectrum, surge-duration, complete-footprint
or aged-capacitance guarantee is invented. Those nulls remain available inside
the complete applicable record. A no-match is unavailable scoped evidence, not
an electrical suitability or safety verdict.

Synthetic tests use invented identities and values. Immutable genuine CLI
baselines and fresh mutation copies verify that unchanged IDs cannot erase
conditions, transform impedance into ESR, equate surge with operating voltage,
or turn a life test into field-life approval. Complete source payloads, warnings
and unknowns are compared, not merely lexical hits or result counts. The compact
successor test also preserves every preceding case/pin and exact reviewed pair.

Original PDF, identity HTML, extracted text and rendered pages stay local and
untracked. Only original annotations and metadata are committed or packaged.
Independent Agent source review under owner delegation is not human acceptance,
canonical approval, new local PDF verification by a consumer, or board qualification.

Accepted JSON SHA-256: `823234d25f9b7881e072abfc3621d928c7df57f724e698a58394aeddf1e9a23b`.
Source-review receipt SHA-256: `80e6400736e9566c88cabb4cf131f458d1a99aa1c8e86382e7a2a25d4ddc79da`.
Original PDF SHA-256: `3a6ebd75687bd5c8207b0182c22367cfa3ebb94a5033c8e25f4bd087e37f084b`
(134,598 bytes, nine pages, not redistributed).

Local integration and remote exact-commit CI receipts are recorded separately;
source acceptance alone does not establish either verification stage.
