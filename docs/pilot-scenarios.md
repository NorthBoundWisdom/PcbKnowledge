# Executable Pilot Scenarios

P0.4a uses real private engineering material, but most negative and regression
checks do not need to remain manual. The executable scenario runner turns common
pilot questions into deterministic, read-only queries against one explicitly
selected knowledge workspace.

The runner does **not** create Source, Entity, Fact, evidence, review, or Git state.
Intentionally wrong MPNs, packages, revisions, and other test inputs remain
evaluation data outside canonical authority.

## Files and formats

The public software repository defines two independent evaluation contracts:

```text
pcbknowledge-pilot-eval-v1
    structural gates
    human visual-acceptance receipts
    manual or executable pilot-case receipts

pcbknowledge-pilot-scenarios-v1
    read-only executable scenario inputs
    one scenario -> one pilot case

pcbknowledge-pilot-scenario-report-v1
    observed scenario results
    bound to working authority + Git state + published commit
```

A scenario report can be overlaid onto the normal pilot evaluation at report time.
The evaluation manifest itself does not need to be rewritten after every run.

## Scaffold

Create the normal pilot manifest:

```bash
python3 configs/pcbknowledge_pilot.py scaffold \
  --output ../pilot-evaluation.json
```

Create an executable scenario suite:

```bash
python3 configs/pcbknowledge_pilot.py scenario-scaffold \
  --output ../pilot-scenarios.json
```

Both scaffold commands are idempotent only while the existing file is still the
exact repository template. They refuse to overwrite an edited evaluation file.

Replace placeholder IDs only after the private workspace contains the corresponding
canonical records.

## Run scenarios

```bash
python3 configs/pcbknowledge_pilot.py scenario-run \
  --workspace ../PcbKnowledgeData \
  --suite ../pilot-scenarios.json \
  --output ../pilot-scenario-report.json \
  --require-pass
```

The command validates the working workspace and selected published ref before
executing any query.

`--require-pass` returns exit code `3` when the suite is structurally valid but one
or more scenarios observe a code different from `expected_code`.

The runner is read-only. It never:

- creates or edits authority;
- imports a PDF;
- changes review state;
- stages Git;
- commits or pushes;
- switches to another workspace;
- fills an unknown result from a similar part.

## Use executable results in the P0.4a gate

```bash
python3 configs/pcbknowledge_pilot.py report \
  --workspace ../PcbKnowledgeData \
  --manifest ../pilot-evaluation.json \
  --scenario-report ../pilot-scenario-report.json \
  --require-pass
```

For every executable result, `pilot_case_id` must name an existing case in the
evaluation manifest. The case category and scenario kind must be compatible, and
both contracts must use the same `expected_code`.

A case with `status: NOT_RUN` is materialized in memory as PASS or FAIL from the
scenario result. The source manifest is not rewritten.

If the evaluation manifest already contains a manual PASS/FAIL receipt for the same
case, it must agree exactly with the executable result. A disagreement is a contract
error rather than a silent override.

## Stale-result protection

Scenario output is not reusable after the evaluated state changes.

Each report binds to:

```text
suite_sha256
working_fingerprint
git_state_fingerprint
published_commit
```

`working_fingerprint` hashes canonical Source, Entity, and Fact JSON from the
validated working authority.

`git_state_fingerprint` binds current Git change scope plus knowledge/evidence Git
status. It exists because a `CHANGE_SCOPE` scenario can become stale even when
canonical authority bytes did not change.

`published_commit` binds every `PUBLISHED` scenario and publication-visibility
result to the exact immutable Git snapshot used during the run.

When any binding changes, `report --scenario-report` rejects the old result instead
of treating it as current evidence.

## Scenario kinds

### COMPONENT_LOOKUP

Parameters:

```json
{
  "manufacturer_id": "ent_...",
  "raw_mpn": "TPS5430DDAR"
}
```

Observed codes:

```text
EXACT
UNKNOWN
CONFLICT
```

Lookup uses the same deterministic normalized exact-key semantics as canonical
Component identity. It performs no suffix guessing or fuzzy search.

Typical pilot categories:

```text
WRONG_MPN
UNKNOWN
```

### PACKAGE_LOOKUP

Parameters:

```json
{
  "raw_name": "SOIC-8"
}
```

Observed codes:

```text
EXACT
UNKNOWN
CONFLICT
```

Typical categories:

```text
WRONG_PACKAGE
UNKNOWN
```

### SOURCE_REVISION_LOOKUP

Parameters:

```json
{
  "document_number": "SNVS632",
  "revision": "G",
  "publisher": "Texas Instruments"
}
```

`publisher` is optional. Document number and revision are exact fields; the runner
does not guess that two similar document names refer to the same revision.

Observed codes:

```text
EXACT
UNKNOWN
CONFLICT
```

Typical categories:

```text
WRONG_REVISION
UNKNOWN
```

### SOURCE_LICENSE_GATE

Parameters:

```json
{
  "source_id": "pk_..."
}
```

Observed codes:

```text
ALLOWED
BLOCKED
UNKNOWN
```

The code is derived from the Source license taxonomy. It does not open the PDF.

Typical category:

```text
LICENSE_BLOCK
```

### SOURCE_SUPERSEDES

Parameters:

```json
{
  "source_id": "pk_new...",
  "target_source_id": "pk_old..."
}
```

Observed codes:

```text
MATCH
NO_RELATION
MISMATCH
UNKNOWN
```

Typical category:

```text
SUPERSEDE
```

### PIN_FACT_LOOKUP

Parameters:

```json
{
  "component_id": "ent_...",
  "package_id": "ent_...",
  "pin_number": "7"
}
```

Only active, non-superseded `ComponentPinFactV1` records participate.

Observed codes:

```text
EXACT
UNKNOWN
CONFLICT
```

Useful categories:

```text
WRONG_PACKAGE
UNKNOWN
CONFLICT
TABLE_PIN
```

### PARAMETER_LIMIT_LOOKUP

Parameters:

```json
{
  "component_id": "ent_...",
  "parameter": "Input voltage",
  "limit_kind": "ABSOLUTE_MAXIMUM"
}
```

Observed codes:

```text
EXACT
UNKNOWN
CONFLICT
```

The limit kind is part of the exact query, preventing an absolute maximum from
being returned as a recommended operating value.

### PARAMETER_LIMIT_DISTINCTION

Parameters:

```json
{
  "component_id": "ent_...",
  "parameter": "Input voltage"
}
```

Observed codes:

```text
DISTINCT
MISSING_SIDE
CONFLICT
```

`DISTINCT` requires exactly one active absolute-maximum Fact and one active
recommended-operating Fact for the requested parameter.

Typical category:

```text
ABS_MAX_VS_RECOMMENDED
```

### FACT_CONFLICT

Parameters:

```json
{
  "fact_id": "fact_..."
}
```

Observed codes:

```text
CONFLICT
CLEAR
UNKNOWN
```

The runner reads the existing semantic-conflict projection. It never chooses a
winner.

### ANCHOR_INTEGRITY

Parameters:

```json
{
  "fact_id": "fact_...",
  "source_id": "pk_...",
  "page": 12,
  "quote_sha256": "..."
}
```

`quote_sha256` is optional.

Observed codes:

```text
MATCH
DRIFT
INCOMPLETE
UNKNOWN
```

This is a structural anchor check. Human pixel-level PDF acceptance remains a
separate `visual_acceptance` receipt.

Typical category:

```text
ANCHOR_DRIFT
```

### REVIEW_HISTORY

Parameters:

```json
{
  "record_id": "fact_...",
  "actions": [
    "SUBMITTED",
    "REJECTED",
    "SUBMITTED",
    "APPROVED"
  ]
}
```

The required sequence is exact and ordered.

Observed codes:

```text
MATCH
MISMATCH
UNKNOWN
```

Typical category:

```text
REVIEW_HISTORY
```

### PUBLICATION_VISIBILITY

Parameters:

```json
{
  "record_id": "fact_..."
}
```

Observed codes:

```text
PUBLISHED
WORKING_ONLY
PUBLISHED_ONLY
MISSING
```

This scenario always compares both working authority and the selected published
snapshot. It is useful for proving that working-tree approval is not publication.

Typical category:

```text
UNCOMMITTED_APPROVAL
```

### CHANGE_SCOPE

Parameters:

```json
{}
```

Observed code is exactly one of:

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

The scenario never stages files. To test `MIXED`, prepare the intended Git state
before running the suite.

Typical category:

```text
MIXED_COMMIT
```

## Working versus published queries

Most lookup scenarios may select:

```json
"snapshot": "WORKING"
```

or:

```json
"snapshot": "PUBLISHED"
```

This makes it possible to prove cases such as:

```text
working conflict exists
published snapshot remains exact
```

`PUBLICATION_VISIBILITY` and `CHANGE_SCOPE` always use working context and reject a
`PUBLISHED` selector.

## Manual-only pilot cases

Not every P0.4a case should be forced into this runner.

Keep these manual where appropriate:

- real browser resize/zoom bbox acceptance;
- complex-font visual rendering;
- subjective table-cell readability;
- a deliberately invalid external workspace path;
- process or policy observations that are not deterministic repository queries.

The purpose of executable scenarios is to reduce repeated manual bookkeeping, not
to fake automation for inherently visual or procedural checks.

## Closure flow

A typical private pilot now becomes:

```text
ingest real Source/PDF
        ->
resolve exact Entities
        ->
extract typed Facts
        ->
run executable scenarios
        ->
inspect visual evidence
        ->
human approve/reject
        ->
commit Published Knowledge
        ->
rerun executable scenarios
        ->
pilot report --scenario-report --require-pass
```

If the last command fails, record the real failure before changing schema or
relaxing an expected result.
