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

## Verify complete current selection

After explicitly capturing a bundle, pass its `bundle_sha256` and the **same
exact source filters** to the read-only verification command:

```bash
python3 -B configs/pcbknowledge_agent.py --repo <workspace> intake verify-bundle \
  --device SYNTH-A --sha256 <captured-bundle-sha256>
```

The digest must be exactly 64 lowercase hexadecimal characters. Each filter and
the digest may occur only once. There is no saved-file input, automatic lookup
of an expected digest, fallback workspace or implicit refresh. The caller owns
the provenance of the expected digest; a match does not authenticate it.
**The digest is not a signature. This command does not authenticate a saved
bundle file, verify manufacturer originals, or create an atomic snapshot.**

Success returns `pcbknowledge-intake-bundle-verification-v1`, operation
`VERIFY_CURRENT_METADATA_SELECTION`, the expected digest, and the complete
unchanged captured-format bundle under `bundle`. Both layers remain noncanonical
and `NOT_LOCALLY_VERIFIED`. The inner capture operation is deliberately not
relabelled, which would change its fingerprint. Verification performs one
validated load and compares its whole selected projection to the expected hash.
It does not reread or lock metadata after hashing and makes no atomic snapshot
or later-state guarantee.

A mismatch returns status 2, `STALE_INTAKE_BUNDLE`, and no stdout or replacement
digest. Review the current scope before separately running `intake bundle` to
capture new metadata. Invalid workspace, malformed metadata and invalid digest
syntax fail through their existing validation paths, not a misleading success
or drift conclusion. No output or receipt file is written automatically.

Unlike checking old `intake item` references one by one, this operation detects
new matching batches, sources, facts and warnings, removed selected records,
changed batch bytes/context and changed handling receipts. It also detects an
empty selection becoming nonempty. Exact filter arguments themselves are hashed:
replacing `--device` with a `--source-id` that currently returns the same records
is not the same expected bundle. Missing/null/non-string structured fields never
match through fallback. Unmatched new batches do not change the selected bundle,
but whole-queue validation still rejects an invalid unselected batch.

The source batch's full byte hash and batch context are deliberately retained,
so even an edit to an unselected record **inside a selected batch** invalidates
the bundle. This conservative behavior is not a semantic electrical comparison.
A matching digest proves only equality of the current validated projection with
the supplied fingerprint. It does not prove that the selection is sufficient,
that no gaps exist, or that source originals or the circuit have been verified.

## Regression coverage

`tests/git_native/test_intake_bundle.py` covers full candidate parity and item
resolution, deterministic whole-projection fingerprints, exact/missing/raw
filters, empty and warning-only sources, duplicate batch-local IDs, out-of-scope
source exclusion with full batch context, single-load consistency, stale byte
pins, disposition-only changes, unusable selector refusal, invalid unselected
batches, parser failures and actual public-wrapper selected-workspace reads.
Successful and failed wrapper calls leave the selected workspace tree unchanged.
These software checks are not source-original review or engineering validation.

`tests/git_native/test_intake_bundle_verification.py` adds complete selection
addition/removal, filter binding, empty-to-nonempty selection, unchanged old item
pins despite new matching batches, byte/context/receipt-only drift, unselected
batch validation, one-load behavior, malformed/duplicate digest and filter
refusal, explicit stale errors without refresh, and real public-wrapper success
and failure with unchanged selected-workspace file bytes and directory layout.
