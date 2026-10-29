# Read-only intake coverage inventory

```bash
python3 configs/pcbknowledge_agent.py --repo <workspace> intake coverage
```

This command reports what the selected working-tree intake **records**, including
missing metadata and unresolved warnings. It does not measure complete component
coverage, recommend a device, or establish electrical readiness. It reads the
whole queue; filters are intentionally unavailable. Use `intake search` and
`intake issues` for narrower inspection and `intake list` for complete originals
of the metadata records, not original source documents.

The deterministic JSON format is `pcbknowledge-intake-coverage-v1`. Its top-level
`canonical: false` and `evidence_verification: NOT_LOCALLY_VERIFIED` apply to the
entire inventory. No PDF, network source, local evidence cache or canonical Fact
is read. No workspace directories, indexes or receipts are created. The Python
API is `pcbknowledge.git_native.intake_coverage.intake_coverage(root: Path)`.

## Reading the output

- `summary.batch_count` counts discovered batches, not approved components.
- `batch_local_source_scope_count` counts `(batch path, source ID)` occurrences.
  Repeated source IDs, document hashes and devices in other batches are not merged.
- `device_labels` groups exact nonempty structured `(manufacturer, device)` strings
  and retains every batch/source reference. Case, Unicode, punctuation and
  whitespace remain significant. These labels are not full orderable/package
  identities or equivalence claims. Missing/null/non-string labels are not inferred
  from prose; `source_scopes_without_device_labels` counts those ungrouped scopes.
- `recorded_metadata.record_count` counts batch-local annotation occurrences, not
  globally unique IDs. `record_statuses` retains individual recorded statuses;
  batch acceptance is not silently applied to every record. `fact_kinds` and
  `evidence_levels` are raw-value histograms.
  Each histogram entry has `value` and `count`; null means absent or explicitly
  null. Non-string values remain visible as raw JSON, not silently normalized.
- `visual_checked` and legacy `visual_page_review` remain separate histograms.
  They are recorded flags, not this reader's verification or a combined grade.
  Missing/non-object evidence is counted explicitly. Reviewer/collector histograms,
  original batch review/history/source-review receipts, source metadata and
  limitations preserve recorded provenance; use `intake list` for full per-record
  conditions and evidence objects before any reuse.
- Each batch has its exact byte SHA-256, source rows, sorted record IDs and metadata
  histograms. Reordering input records changes that byte hash even when the
  inventory's sorted counts and selections are otherwise identical.
- Source rows retain complete original `source_issues` with separately attached
  validated disposition receipts. `explicitly_unresolved_source_issue_count` counts
  only string statuses beginning `UNRESOLVED_`; all raw statuses remain in
  `source_issue_statuses`. `handled_disposition_count` is independent: a contained
  issue still counts as unresolved. Unknown/untyped statuses are not declared
  resolved, and zero recorded warnings does not establish an absence of gaps.

The existing `load_intake` validation runs before output. Malformed batches,
unsafe symlinks, broken source links and stale/orphan/ambiguous dispositions fail
the entire read; there is no partial-success inventory or fallback workspace.
The public CLI wrapper also validates the selected workspace contract.

## Historical acceptance is not inferred

The [2026-10-28 owner receipt](../../archive/receipts/owner-acceptance-2026-10-28.md) covers only its exact
five-batch, 100-annotation historical snapshot. It is a documentary batch-content
acceptance, not per-fact evidence certification or canonical approval. The later
three application batches at `98113c3` add 25 Agent-reviewed records outside that
receipt. Future records and changed bytes do not inherit it either.

The inventory intentionally does not parse Markdown acceptance receipts, treat an
evaluation manifest as approval, or count records as owner-accepted by mutable
path. It preserves recorded Agent review statuses and explains this boundary.
See the [lightweight contract](lightweight-knowledge.md) for authority and source
processing policy.

At `98113c3`, a useful interpretation is 8 batches / 19 batch-local source scopes /
125 records, with 12 explicitly unresolved warnings and 1 separate containment
receipt. Recorded fact evidence labels are 99 `BYTE_IDENTIFIED_TEXT_AND_VISUAL`,
6 `OFFICIAL_WEB_TEXT_ONLY`, and 20 unspecified. The older TI batch separately
records 20 `visual_page_review: true` flags: unspecified labels do not erase those
receipts, and the inventory does not invent labels for them. These dated counts
are an example, not a target, a live guarantee, or a completeness percentage.

## Verification receipt (2026-10-28)

Thirteen synthetic coverage tests exercise exact labels, raw/missing metadata,
stable ordering, cross-batch IDs, preserved provenance, containment versus
resolution, whole-read failure, stale/orphan receipts, unknown options and a full
before/after filesystem snapshot for both CLI entry points. All 57 focused intake
tests passed. Build and Test each passed 208 tests with no skips; the 70 pinned CLI
cases, Config, workspace/Agent validation, English/public/PDF.js guards and
metadata-only Package exited 0. Exact-commit remote CI is checked separately after
publication; these are local results, not new source evidence or owner acceptance.
