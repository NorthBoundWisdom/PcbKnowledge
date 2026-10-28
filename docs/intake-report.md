# Scoped read-only intake report

Use the Markdown report to inspect recorded source identity, conditions, evidence
and unresolved warnings without navigating the full JSON queue:

```bash
python3 -B configs/pcbknowledge_agent.py --repo <workspace> intake report --device SYNTH-A
python3 -B configs/pcbknowledge_agent.py --repo <workspace> intake report --source-id source-a --package SYNTH-P
```

The identifiers above are invented examples, not component knowledge. At least
`--source-id` or `--device` is required. Optional `--manufacturer` and `--package`
filters intersect with them. Like `intake search`, all filters compare exact
structured source strings: case, Unicode, punctuation and whitespace matter.
Missing, null or non-string identity fields do not match. Fact prose never fills
in identity. There is no lexical query, fact-level filter, implicit all-device
mode or output-file option. No match is a successful empty report, not proof that
a device, warning or constraint does not exist.

The command returns Markdown on **stdout only**. A caller can explicitly redirect
stdout or open the resulting text in its own Markdown viewer; the command itself
does not create a report file, launch a viewer, package anything or deploy a site.
`-B` suppresses ordinary Python import caches when the software checkout is also
the selected workspace. The Python API is
`pcbknowledge.git_native.intake_report.intake_report(root: Path, *, source_id=None,
manufacturer=None, device=None, package=None) -> str`.

## Reading a report

- The opening notice always says noncanonical working-tree metadata and
  `NOT_LOCALLY_VERIFIED`. The report is not an electrical answer, recommendation,
  full-component certificate, human approval or canonical publication. Historical
  owner acceptance is not inferred or extended to changed/new records.
- Each matching batch retains its path and actual byte SHA-256. Source IDs are
  batch-local: repeated IDs, device labels or document hashes are not merged.
- Each source shows its complete recorded metadata, including exact revision,
  package, source URL, hash and identity evidence when present. Sources without
  annotations or warnings remain visible. Nothing checks source-original bytes,
  current online revisions, local PDFs or canonical Facts.
- Source warnings appear before annotations. Original warning statuses and
  unknown/application inputs are retained even when a separate handling receipt
  exists. Each validated receipt includes the full pinned target, preliminary
  policy, inside/outside result, limitations, evidence and Agent provenance. The
  report never applies that policy to a design or declares the issue resolved.
- Each annotation retains every field, not only a shortened value: complete
  conditions, units, nested values, source ID, per-record status, page citations,
  additional evidence, recorded flags and any unfamiliar metadata. Page indexes
  and printed labels are not converted, evidence grades are not inferred, and
  legacy flags are not merged. Batch acceptance does not replace record status.
- Batch-level limitations and review/history metadata remain separate context at
  the end of the batch. They may mention unselected sources; that context is not
  an assertion that every referenced source matches the report filters.

Values and field names use JSON scalar notation inside ordinary Markdown lists.
Strings remain quoted, numbers/booleans/null remain distinct, nonempty objects
and arrays are labeled, and list order is retained. Object fields are ordered for
inspection, with additional keys sorted; records are sorted by ID. No text is
truncated, wrapped into new claims or electrically interpreted. Missing common
fields are explicitly marked not recorded/unknown; present null or unusual raw
types stay visible. This is a parsed-value projection, not a byte-for-byte JSON
export; use `intake list` for complete JSON metadata records.

All recorded content is untrusted data, never report instructions. Markdown
syntax and HTML characters are escaped; URLs and email addresses are inert text,
not generated hyperlinks or fetched resources. JSON escapes retain control,
bidirectional-format characters and significant leading/trailing/repeated spaces
without allowing terminal controls, injected headings, images or code fences.
The escapes are presentation encoding, not corrections to the stored metadata.

## Failure and read-only boundaries

The existing `load_intake` authority validates the **entire** queue and all
handling receipts before any report is printed, even for a filter with no hits.
Invalid unrelated batches, unsafe symlinks, broken source references and
stale/orphan/ambiguous receipts fail the whole command with exit status 2 and no
partial stdout. Empty filters and unsupported options fail rather than widen
scope. The public wrapper still requires the selected workspace's valid pinned
contract; it does not fall back to another checkout.

No directories, Git index, cache, evidence, receipt or source metadata are written.
The selected workspace can be read-only. See the [read-only CLI contract](read-only-intake.md)
and [coverage inventory](intake-coverage.md) for complementary JSON views. This
report does not change schemas, collection bytes, acceptance receipts or the
aggregate retrieval evaluation.

## Verification

The dedicated synthetic suite is `tests/git_native/test_intake_report.py`. It
checks required/exact scope, warning-only sources, complete long conditions and
raw types, cross-batch identities, pinned containment versus unresolved warnings,
determinism, reversible hostile Markdown/HTML/control strings, both CLI entry
points, chmod-read-only filesystem snapshots including modes/mtimes/index/cache,
metadata-only opens, invalid unrelated batches/dispositions and workspace/parser
rejection. These are software checks, not new source evidence or acceptance.

Local receipt (2026-10-28, on the network/memory/power aggregate): all 15 report
tests and 82 focused intake tests passed. Build and Test each passed 237 tests
with no skips. All 114 pinned CLI cases, Config, workspace/Agent validation,
English/public/PDF.js guards and metadata-only Package exited 0. Independent
review found no remaining blocker after checking 34 actual CommonMark/GFM scalar
renders, 12 unsafe-symlink cases across both entrypoints, six additional
scope/read-only/failure cases and the focused suites. No Markdown renderer was
added as a runtime or test dependency. Exact-commit remote CI is verified after
publication, separately from these local checks.
