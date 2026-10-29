# Thermistor condition evaluation

This batch covers Vishay BCcomponents NTCLE100E3103JB0, the exact no-A,
10-kohm, 5-percent R25, bulk-packaged radial NTC. The 07-May-2025 electrical
revision is separate from the 2026 legal appendix. The source ordering table
and an exact official identity listing identify this part without establishing
inventory, current regulatory compliance or suitability for a new design.
See the source review (`git show intake-final:knowledge/intake/ntcle100-thermistor-constraints-review.md`)
for byte identity and independently inspected rendered-page evidence.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-thermistor.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_thermistor_replay -v
```

The small successor delta stores only one new source pin and 30 recipes. Its
exact-hash reference preserves the preceding 678 retrieval recipes and 32 batch
pins without copying or editing that history. The resolved aggregate has 708
retrieval cases plus the unchanged six dispositions. Thirty additions cover
seven exact parameters, all facts, all warnings, one kind selection, thirteen
negative fact selections and seven negative warning selections. Expected IDs
are derived from reviewed record scope, not blindly refreshed CLI output.

## Useful bounded decisions

- R25 tolerance and B25/85 tolerance describe different quantities under their
  source conditions. Neither is a complete temperature-conversion error budget.
- Zero-power measurement is a source-defined power fraction, not literally zero
  self-heating. Maximum dissipation retains its ambient/derating conditions and
  does not become an excitation recommendation over the full temperature range.
- Approximate oil response and the informational thermal time constant are
  separate entries. They do not guarantee an installed-board response deadline;
  the medium for the latter entry is not established by the quick table.
- Informational dissipation factor is resistance-range dependent. The separate
  low-resistance row cannot be transferred to this 10-kohm part or made into a
  guaranteed installed self-heating error.
- Coating has no specified insulation properties; potted use is not intended.
  Dimensions and a mounting statement do not establish an insulation rating,
  complete board footprint or an audited soldering process.
- The separate A-suffix ordering column is preferred for new designs. The
  selected no-A part is not automatically discontinued, NRND, substitutable,
  safety-approved or compliant with a particular current regulation.

The source-bound negative recipes exclude another source/revision identity,
manufacturer, A suffix, tolerance code, packaging code, package and resistance.
Additional negatives exclude guarantees absent from this batch. An empty result
is absence of a scoped candidate, not proof that no evidence exists elsewhere,
not zero error, and not circuit safety. Full source and all three warnings stay
attached to selected facts.

## Semantic regression and limitations

Synthetic fixtures use invented identity, numbers and conditions, not copied
source text or tables. Forty-three same-ID mutations detect changed identity,
coating/potting/suffix assumptions, R/B conditions, unknown accuracy, typical-to-
guaranteed thermal promotion, dropped environment, maximum-to-operating power
promotion, erased warnings and unjustified verification upgrades. Genuine CLI
responses are captured once and freshly deserialized per mutation. A mutation
must fail despite keeping candidate IDs unchanged; pristine payloads still pass
and fixture bytes remain unchanged.

The successor test pins the accepted pair, preserves prior cases and pins, and
checks exact parameter recipes plus coverage of every new fact and warning.
This validates retrieval and unchanged metadata, not a temperature solver or
source truth by itself. Source review is separate; ordinary retrieval remains
canonical:false, human_reviewed:false and NOT_LOCALLY_VERIFIED. No original PDF,
HTML, source extract or rendered page is committed or packaged. Final full gates
and exact published-commit CI are separate checks; source counts alone are not
acceptance.
