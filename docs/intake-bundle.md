# Scoped machine-readable intake bundle

`intake bundle` captures complete selected working-tree intake metadata and exact
per-record references in one JSON result. It complements the human-readable
[Markdown report](intake-report.md) and the single-record
[reference commands](intake-workbench.md). It is not a circuit answer, source
original audit, canonical export, formal pilot pass or new approval.

```bash
python3 -B configs/pcbknowledge_agent.py --repo <workspace> intake bundle --device SYNTH-A
python3 -B configs/pcbknowledge_agent.py --repo <workspace> intake bundle \
  --source-id synthetic-source --manufacturer "Synthetic Maker" --revision R1
```

These names are synthetic examples. At least `--device` or `--source-id` is
required. Optional `--manufacturer`, `--package` and `--revision` filters are
conjunctive exact structured-string comparisons. Case, Unicode and whitespace
are significant; missing, null and non-string fields do not match. Duplicate
options, abbreviated options, lexical queries and fact-only filters are rejected.
There is no filter that removes a matching source's warnings while retaining
only selected facts. Wrong exact identity returns an empty bundle, not a device
compatibility or absence-of-constraints conclusion.

## Complete selected context

The `pcbknowledge-intake-bundle-v1` projection contains:

- explicit `canonical: false`, `CAPTURE_CURRENT_METADATA` operation,
  `NOT_LOCALLY_VERIFIED` evidence status and limitations;
- the exact source filters and batch/source-scope/fact/issue counts;
- every matching source object, including sources with no facts or warnings;
- each selected batch path and hash of its actual JSON bytes;
- full batch-level metadata in `batch_context`, not falsely scoped per-record
  approval (it can mention sources outside the selected source filter);
- complete matching fact and warning candidates, each with existing
  `pcbknowledge-intake-reference-v1` capture projection and exact item selectors;
- complete validated source issue handling receipts for selected sources.

Fact candidates retain all same-source warnings and handling receipts. Warning
candidates retain their existing issue-specific handling context. All nested
conditions, unknowns, evidence, additional evidence, review/provenance fields and
raw JSON types remain unchanged. Batch-local IDs are not merged across batches
or across fact and issue types. Handling a warning does not resolve it.

The loader validates the whole queue, including unselected batches and handling
receipts, before emitting JSON. Malformed input fails with status 2 and no partial
stdout. Records that cannot be represented by the bounded exact-item selector
contract also fail rather than emitting unusable pins. There is no output-file
option or write operation; callers may explicitly redirect stdout themselves.

## Reuse and integrity limits

Each `facts` or `issues` entry contains a `reference` object. Its keys are exactly
the options for `intake item`: `batch`, `id`, `type`, `sha256`, and `context`.
Pass these as separate literal argument values; do not execute record text or
interpolate untrusted strings into a shell. `intake item` verifies both metadata
pins and returns the complete current candidate or refuses a stale reference.
It never refreshes the old pin silently. The existing local workbench item route
uses the same selector contract.

`bundle_sha256` fingerprints the complete result excluding that field, using
UTF-8 JSON with sorted keys, `ensure_ascii=False`, `allow_nan=False`, and compact
separators `(',', ':')`. This includes filters, limits, counts, batch context,
sources, receipts and all candidate projections, not just IDs or values. It is
a deterministic integrity aid, not a signature or proof of trusted provenance.
The software does not ingest a saved bundle as authority.

One validated loader result supplies all candidates and pins; the command does
not independently reread a batch for each record. This avoids mixing a displayed
candidate with a later hash. It does **not** lock the workspace or provide an
atomic cross-file filesystem snapshot. A later addition in another batch may
change the complete selected collection without invalidating existing item
pins. Verifying individual items therefore does not verify continued selection
completeness. Capture a new bundle deliberately when reviewing current scope,
and compare the complete results without calling the old bundle refreshed.

No PDF, canonical Source/Entity/Fact, cache, index or network is accessed by this
projection. The public wrapper checks the selected workspace and pinned schemas;
no fallback workspace is used. Python interpreter cache creation is separately
suppressed with `-B`. Historical evidence and owner acknowledgements remain
recorded provenance; neither is renewed by capture or item verification.

## Regression coverage

`tests/git_native/test_intake_bundle.py` covers full candidate parity and item
resolution, deterministic whole-projection fingerprints, exact/missing/raw
filters, empty and warning-only sources, duplicate batch-local IDs, out-of-scope
source exclusion with full batch context, single-load consistency, stale byte
pins, disposition-only changes, unusable selector refusal, invalid unselected
batches, parser failures and actual public-wrapper selected-workspace reads.
Successful and failed wrapper calls leave the selected workspace tree unchanged.
These software checks are not source-original review or engineering validation.
