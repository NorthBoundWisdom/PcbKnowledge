# P0.4a Pilot Evaluation

P0.4a is the first stage that intentionally uses real engineering documents. The
public PcbKnowledge repository therefore provides the evaluation **harness and
contract**, while real Sources, Facts, PDFs, observations, and review receipts stay
in a separately controlled private workspace or private evaluation location.

The purpose of the pilot is not to prove that a synthetic fixture can pass the
model. It is to expose schema, evidence-anchor, revision, package, review, and
license assumptions before the knowledge model expands.

## Authority versus evaluation inputs

Canonical engineering authority remains:

```text
pcbknowledge.workspace.json
schemas/
knowledge/sources/
knowledge/entities/
knowledge/facts/
evidence/sha256/
Git history
```

Deliberately wrong or ambiguous test scenarios are **not authority**. A wrong MPN,
wrong package, wrong revision, expected license block, or anchor-drift scenario must
not be inserted as a false Component or Fact merely so the evaluator can find it.

Pilot evaluation metadata uses the separate format:

```text
pcbknowledge-pilot-eval-v1
```

A template is available at:

```text
evals/pilot-evaluation.example.json
```

Real evaluation manifests should remain private when their observations, IDs, notes,
or selected vendor material disclose non-public engineering work.

## Basic workflow

Create and commit a private workspace contract first:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData --init-git
cd ../PcbKnowledgeData
git add pcbknowledge.workspace.json schemas knowledge evidence
git commit -m "initialize PcbKnowledge workspace"
cd ../PcbKnowledge
```

Create an evaluation manifest outside canonical authority:

```bash
python3 configs/pcbknowledge_pilot.py scaffold \
  --output ../PcbKnowledgeData-pilot-evaluation.json
```

The scaffold is intentionally incomplete. Replace the placeholder Source/Fact IDs
only after real ingestion has created the corresponding private authority.

During ingestion and review, inspect current coverage without claiming completion:

```bash
python3 configs/pcbknowledge_pilot.py metrics \
  --workspace ../PcbKnowledgeData
```

Evaluate all pilot gates:

```bash
python3 configs/pcbknowledge_pilot.py report \
  --workspace ../PcbKnowledgeData \
  --manifest ../PcbKnowledgeData-pilot-evaluation.json
```

At the closure checkpoint, require every mandatory gate to pass:

```bash
python3 configs/pcbknowledge_pilot.py report \
  --workspace ../PcbKnowledgeData \
  --manifest ../PcbKnowledgeData-pilot-evaluation.json \
  --output build/pilot-report.json \
  --require-pass
```

`--require-pass` returns exit code `3` when the manifest is structurally valid but
one or more required pilot gates are incomplete or failed. Invalid workspace or
manifest contracts return exit code `2`.

## Working authority and Published Knowledge

The report intentionally measures two snapshots:

```text
working
  mutable selected workspace

published
  fully validated committed ref, HEAD by default
```

This catches an important failure mode:

```text
all Source/Fact records APPROVED in working tree
                  !=
Published Knowledge
```

The `published-matches-working` gate passes only when reviewed working Source,
Entity, and Fact counts are present in the committed published snapshot. This keeps
the existing Git publication boundary visible during the pilot.

Use another committed ref when required:

```bash
python3 configs/pcbknowledge_pilot.py report \
  --workspace ../PcbKnowledgeData \
  --manifest ../pilot-evaluation.json \
  --ref refs/tags/pilot-review-1
```

The CLI validates both the working workspace contract and the selected ref contract
before evaluation.

## Structural dataset gates

The first pilot intentionally stays small. Required automatic gates include:

- 3–5 distinct `Component` entities;
- 20–40 total typed Facts;
- at least one `ComponentPinFactV1`;
- at least one `ParameterLimitFactV1`;
- at least one Component represented across multiple Package identities;
- at least one explicit Source revision `supersedes` relationship;
- fully reviewed working Source/Fact authority;
- no unresolved working semantic Fact conflict;
- published Source/Entity/Fact counts matching reviewed working authority.

The report also records, without making every metric a hard gate:

- manufacturer and package counts;
- multi-anchor Fact count;
- conditional/applicability Fact counts;
- incomplete Source/Fact counts;
- DRAFT / READY_FOR_REVIEW / REJECTED counts;
- blocked-license Source count;
- Fact and Source supersedes counts.

These measurements are intended to expose modeling pressure before adding another
Fact family.

## Scenario receipts

Each `cases[]` entry records one explicit expected/observed outcome:

```json
{
  "id": "case_wrong_mpn",
  "category": "WRONG_MPN",
  "status": "PASS",
  "expected_code": "UNKNOWN",
  "observed_code": "UNKNOWN",
  "related_ids": ["ent_..."],
  "notes": "Wrong MPN remained unresolved."
}
```

`PASS` is only valid when `observed_code == expected_code`. `FAIL` must record a
different observed code, and `NOT_RUN` cannot carry an observation. The harness does
not silently reinterpret a failed observation as a new baseline.

Supported categories include:

```text
WRONG_MPN
WRONG_PACKAGE
WRONG_REVISION
ABS_MAX_VS_RECOMMENDED
UNKNOWN
SUPERSEDE
CONFLICT
LICENSE_BLOCK
ANCHOR_DRIFT
REVIEW_HISTORY
UNCOMMITTED_APPROVAL
MIXED_COMMIT
WRONG_WORKSPACE
TABLE_PIN
FOOTNOTE_LIMIT
```

The first pilot requires 5–10 negative/ambiguous scenarios. `TABLE_PIN` and
`FOOTNOTE_LIMIT` are coverage receipts rather than negative-count entries, and both
must pass before pilot closure.

`related_ids` may point only to canonical Source/Entity/Fact IDs that actually exist
in the selected working workspace. Raw intentionally wrong inputs belong in private
notes or the test procedure, not as fake authority IDs.

## Unknown handling

At least one `UNKNOWN` scenario must pass. This is not an invitation to keep an
invalid Fact in Published Knowledge. The unknown scenario represents a query,
ingestion, or review input whose correct result is explicit uncertainty.

The expected behavior is:

```text
unstated / unsupported input
        -> UNKNOWN
        -> no guessed Fact
        -> evaluation receipt records PASS
```

This lets the working authority itself finish fully reviewed and publishable while
the evaluation suite still proves that unknowns are preserved.

## Visual evidence acceptance

Synthetic HTTP tests can prove route, CSP, PDF.js asset, source-policy, page, and
bbox contracts. They cannot prove that a real vendor PDF looks correct on a human
desktop browser.

`visual_acceptance[]` records that missing human receipt:

```json
{
  "id": "visual_real_anchor",
  "source_id": "pk_...",
  "fact_id": "fact_...",
  "page": 12,
  "characteristics": ["TABLE", "RESIZE_ZOOM", "ROTATED_OR_CROPPED"],
  "status": "PASS",
  "notes": "BBox stayed aligned at 80%, 100%, and 125% browser zoom."
}
```

A PASS receipt is accepted only when:

- Source and Fact exist in the selected working authority;
- the Fact has an anchor for the exact Source and page;
- at least one matching anchor is complete;
- the Source has PDF evidence;
- Source policy permits the evidence-review path.

Required pilot visual coverage includes at least one PASS receipt and a
`RESIZE_ZOOM` characteristic. `ROTATED_OR_CROPPED` or `COMPLEX_FONT` is reported as
an advisory gate because a particular 3–5 IC pilot may not contain either PDF
characteristic. Prefer including one when available.

Other useful characteristics are:

```text
TABLE
FOOTNOTE
MULTI_LINE
MULTI_ANCHOR
RESIZE_ZOOM
ROTATED_OR_CROPPED
COMPLEX_FONT
```

Visual receipts are human acceptance evidence, not a substitute for the canonical
Fact anchor or PDF hash.

## Publication checkpoint

A P0.4a pilot is ready to close only after this sequence succeeds:

```text
real Sources/PDFs ingested
        ->
exact Entities resolved
        ->
typed Facts extracted
        ->
visual anchors inspected
        ->
human Source/Fact review completed
        ->
knowledge/evidence data commit
        ->
Published Knowledge validates
        ->
pilot report --require-pass
```

Do not stage or commit from the evaluator. Git publication remains an explicit human
repository action.

## Schema-change rule

The pilot exists to discover where the current contract fails. When a real case
cannot be represented safely:

1. record the failing scenario before changing the model;
2. distinguish a real schema gap from a bad extraction/review procedure;
3. keep the original Source/PDF evidence immutable;
4. make schema/model/validator/UI changes in the public software repository;
5. migrate the private workspace contract explicitly;
6. rerun the same pilot scenario and preserve the before/after receipt privately.

Do not add a broad free-text Fact escape hatch simply to make the pilot green.

## Public repository safety

The public repository contains only the evaluator implementation, tests, and a
synthetic example manifest. It must not receive:

- real vendor PDF originals;
- real production Source/Entity/Fact authority;
- internal engineering rules or customer material;
- private pilot observations that disclose non-public design work;
- credentials or authenticated download URLs.

`python3 configs/check_public_repo.py` remains the primary public-source data guard.
