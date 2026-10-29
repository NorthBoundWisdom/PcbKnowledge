# Once-only fuse condition evaluation

This slice concerns the exact Bourns SF-1206S050-2 once-only slow-blow fuse,
not a resettable PTC. This evidence does not establish interchangeability with
a fast-acting variant. The
source review (`git show intake-final:knowledge/intake/sf1206s-fuse-constraints-review.md`) is the
authority for byte identity, revision and independent source inspection.
This evaluation tests metadata preservation, not protection coordination.

## Reproduce

```sh
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-fuse.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_fuse_replay -v
```

## Successor coverage

The compact successor pins the unchanged ferrite manifest by SHA-256,
inheriting 780 retrieval cases and 36 batch pins. Fifteen new cases cover all
six exact parameters, all six facts, all three warnings and seven exclusions:
wrong orderable/package, unsupported AC-voltage, total-clearing-energy,
arbitrary-fault-time and hot-current guarantees, plus wrong-orderable warnings.
Expected exclusions follow the accepted scope, not blind CLI refresh. Total
replay is 795 retrieval cases plus six unchanged disposition cases. The test
invariant pins the accepted JSON/review pair and checks history preservation.

## Practical boundaries

- Rated current, rated voltage and interrupting rating are separate quantities.
  Interrupting current is not a permissible continuous load. Test voltage and
  ambient conditions remain attached; no unrestricted breaking capability is
  inferred.
- Cold DC resistance retains its measurement-current and temperature basis.
  It is not a guaranteed hot resistance or an installed thermal model.
- Opening/clearing time applies to its stated current multiple and conditions.
  A separate reliability fusing test retains its own current multiple and
  unspecified conditions; it is not silently merged into the clearing table
  or generalized to an arbitrary fault.
- Typical melting I2t is not maximum total-clearing I2t. Arc energy and an
  arbitrary protected device's withstand limit are not supplied by that number.
- Qualitative characteristic curves are not digitized into guaranteed limits.
  Actual prospective fault current, waveform, inrush, ambient, mounting and
  protected-device limits are necessary before system protection can be assessed.

Synthetic fixtures use invented identity, ratings and test conditions, not a
manufacturer table. Twenty-eight same-ID mutations detect lost conditions,
confused electrical ratings, reliability/clearing conflation, typical-to-maximum
and melting-to-total energy promotion, false protection claims, missing warnings
and authority promotion. Each mutation starts from fresh immutable genuine CLI
responses. Full objects are checked, not lexical overlap or matching IDs alone.

Ordinary retrieval remains canonical:false, human_reviewed:false and
NOT_LOCALLY_VERIFIED. Empty results do not prove safety or protection, and an
evaluation PASS is not electrical qualification. No raw PDF, source extraction,
graph image or manufacturer fixture is committed or packaged. Source acceptance,
regression testing and published-commit CI are separate evidence.
