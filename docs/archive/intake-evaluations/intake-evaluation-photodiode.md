# Photodiode condition evaluation

This batch covers the exact Vishay BPW34 bulk non-automotive orderable, not
BPW34S tube packaging or a different supplier. Electrical revision 2.1,
23-Aug-2011, is separate from the 2026 legal appendix. The
[source review](../../../knowledge/intake/bpw34-photodiode-constraints-review.md)
records actual bytes, official identity evidence and independent rendered-page
review. Identity does not establish availability, current compliance or system
qualification.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-photodiode.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_photodiode_replay -v
```

The compact successor pins the immutable Zener manifest by SHA-256, inheriting
738 retrieval cases and 34 batch pins without rewriting or duplicating them.
Its 26 additions cover seven exact parameters, all facts, all warnings, four
kind selections, nine negative fact selections and four negative warning
selections. The result is 764 retrieval cases plus six unchanged disposition
cases. Expected IDs derive from reviewed source scope, not refreshed query
output. The source pair contains seven annotations and three warnings.

## Useful bounded decisions

- Radiometric and photometric test rows remain separate. Wavelength and
  irradiance are not illuminance units. The photometric row's unstated
  illuminant spectrum stays unknown; neither row defines a universal lux,
  irradiance or ADC conversion. Typical current is not a maximum.
- The dark-current maximum retains reverse bias, darkness and ambient
  temperature. It is not a full-temperature limit or frontend noise budget.
- Capacitance retains frequency, illumination and its own bias row. The
  biased maximum cannot be copied into the zero-bias row, whose maximum is
  unknown. Diode capacitance is not total TIA input capacitance or stability.
- Rise and fall times retain load, bias, wavelength and typical status.
  Unstated optical amplitude and edge thresholds stay unknown. These rows do
  not establish installed bandwidth, maximum settling time or ADC accuracy.
- Typical spectral bounds at a relative-response threshold are not a flat
  gain passband or calibrated lux response. Optical angle, window and spectrum
  require application evidence.
- Absolute reverse voltage and thermal limits are not recommended operating
  bias. The ambient and connection conditions are not arbitrary PCB cooling.

Negative recipes exclude an incorrect source revision, supplier, BPW34S
orderable and SOT-23 package, including warning queries. Other exclusions cover
unsupported universal lux conversion, full-temperature leakage, zero-bias
capacitance maximum, TIA bandwidth and recommended bias. Empty selection means
no scoped candidate, not zero, permission to operate, or proof that no other
source exists. Every selected fact retains all three application/source warnings.

## Semantic regression and limits

Synthetic identity, numbers and conditions are invented, not copied from vendor
tables. Forty-seven same-ID mutations check radiometric/photometric confusion,
unknown illuminant promotion, typical-to-maximum promotion, bias/frequency/load
corruption, borrowed zero-bias maxima, invented optical amplitude and edge
thresholds, flat-passband claims, absolute-to-recommended upgrades, removed
warnings and false verification. Genuine CLI results are stored immutably and
freshly deserialized for each mutation: IDs still match, but full-payload
validation fails. Pristine replay and unchanged fixture bytes are checked.

The successor invariant checks accepted source-pair hashes, all parameter
recipes and warnings, and preservation of prior pins and cases. This validates
retrieval and metadata integrity, not a photometric solver, source truth or
installed circuit performance. Source review is independent. Ordinary retrieval
remains canonical:false, human_reviewed:false and NOT_LOCALLY_VERIFIED. No
original PDF, HTML, full text extract or rendered page is committed or packaged.
Full repository gates and exact published-commit CI are separate receipts.
