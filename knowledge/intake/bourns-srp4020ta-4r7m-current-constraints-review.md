# Bourns SRP4020TA-4R7M current-constraint intake review

## Scope and provenance

Six original annotations; noncanonical and not human-reviewed. Collector:
`agent:/root/collect_inductor_current_constraints`. The historical draft was
pending distinct review; the accepted decision and final condition-scope
clarification are recorded below.

Official Bourns PDF: https://www.bourns.com/docs/Product-Datasheets/SRP4020TA.pdf

Actual source: 590,377 bytes, four pages, SHA-256
`601b2bd60f01531d3dd98df00eab15635fa971ebc03cf7ae4ccb5679faf03485`.
Revision 07/20 is visible on page 3; no exact day invented. Exact orderable row
and model/value-code ordering key appear on page 1. Collector inspected rendered
pages 1, 3 and 4; originals, extracts and artwork stay outside Git.

## Duplicate and boundary check

Isolated base: `0373a341d5e12d50778f899848a078621dfa4790`. Search of current
knowledge found no SRP4020TA/4R7M or Bourns source. Existing buck annotation
`buck-app-02` concerns converter peak-current selection and is linked, not
duplicated or treated as proof that this inductor fits that converter.

Review must distinguish 3.5-A inductance-drop current from 2.6-A heating current,
retain test conditions and milliohm units, and not elevate qualification badges
to system certification. Page 1 has height and land spans, not a complete CAD
footprint. No curve is digitized. All three warnings accompany every fact.

## Delivery and validation boundary

Only the adjacent JSON and this review note are intended for delivery. No shared
manifest, schema, aggregate or code is changed. Existing pinned aggregate must
refuse the changed batch set; exit 2 is expected refusal, not a green pass.
An unreferenced metadata-only commit may follow independent acceptance; the
single integrator owns main publication, combined aggregate and final CI.

## Independent review accepted

This section supersedes the pending request above while preserving its history.
Reviewer: `agent:/root/collect_inductor_current_constraints/review_bourns_inductor`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; authority: `OWNER_DELEGATION`.
No human review, canonical approval or application qualification is asserted.

The reviewer independently recomputed the PDF hash and byte count, checked four
pages with `pdfinfo`, rendered all four pages with `pdftoppm`, and inspected all
four actual images with `view_image`. The source receipt above matches. Live
HTTP retrieval remains the collector's observation, not the reviewer's.

All six facts were checked against page 1, including the exact manufacturer
part-number row and ordering key, +/-20% tolerance, 100-kHz/1-V test, 25-C table,
95/105-milliohm typical/maximum resistance, and distinct Isat/Irms definitions.
The height tolerance and three land spans were checked against arrow endpoints;
no pad pitch, mask/paste/courtyard or complete footprint was inferred. Pages 3
and 4 establish revision and the limits of the AEC-Q200/automotive-grade claim.

### Source conditions remain unresolved

Independent review identified that page-2 curve applicability cannot be reconciled
with the page-1 2.6-A/40-C criterion from the supplied information. Matched sample,
mounting and curve-test conditions are unknown; this does not establish that the
table or curve is erroneous. The table criterion is retained. The curve is not
digitized or substituted as a higher current rating. The third fact and the
geometry-and-curves warning expose this missing comparability and preserve the
need for manufacturer clarification and application thermal verification. All
three complete warnings remain attached to every candidate. No numerical table
value changed. The tolerance prose was also made explicitly symmetric (+/-20%).
The append-only JSON history retains the earlier review and this clarification.

Accepted JSON SHA-256:
`e81420e76cbf4665ba891979d6c3e3b5c082970144225d3cae15473d2e368303`.

### Exact retrieval and exclusion replay

On isolated base `0373a341d5e12d50778f899848a078621dfa4790`, the reviewer ran
23 CLI commands, all exit 0, with no skipped case. Six parameter-specific searches
matched the complete expected candidate object: full fact, full source, all
three sorted complete warnings, path, acceptance status, `FACT_CANDIDATE`,
`canonical: false`, and `evidence_verification: NOT_LOCALLY_VERIFIED`. The issues
command matched all three complete `SOURCE_ISSUE` objects. No keyword-only
comparison was used.

Sixteen negative searches returned exactly `[]`: Coilcraft or Vishay manufacturer;
SRP4020-4R7M, SRP4020TA-3R3M, SRP4020TA-5R6M or bare SRP4020TA device; 0402,
SRP4020 or Axial package; wrong kinds for saturation, thermal current or geometry;
and nonexistent universal-current, guaranteed-hot-DCR, automotive-approval or
complete-CAD parameters. These establish exact-filter retrieval, not semantic
circuit reasoning or proof that no uncurated specification exists.

Commands used the following forms:

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search \
  --source-id bourns-srp4020ta-0720-4r7m --parameter PARAMETER
python3 -B configs/pcbknowledge_agent.py --repo . intake issues \
  --source-id bourns-srp4020ta-0720-4r7m
python3 -B configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-measurement-timing-operational.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The historical measurement-timing-operational aggregate command exited **2**
with `dataset bytes or batch set changed; review cases before updating pins`.
That aggregate was not the active pin at base 0373a341; its refusal does not
isolate the effect of this new batch and is not a passing check. The active
baseline aggregate is `intake-retrieval-tvs-connector.json` (22 batches, 228
annotations, 398 cases); the collector's pristine-baseline comparison is recorded
separately below. No pins, manifests, schemas, code, remote refs or source artifacts were
changed by the reviewer. An initial replay correctly failed because the new
review metadata used `reviewer` instead of required `actor_id`; provenance was
corrected and the entire replay rerun successfully. The initial aggregate
provenance error is not substituted for the final changed-batch refusal.

Final focused check on accepted JSON:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover \
  -s tests/git_native -p 'test_intake*.py' -q
```

Exit **0**, **141 tests in 7.220 seconds**, no failures, errors or skips. The
initial run also passed 141 tests in 7.301 seconds; the final run is the delivery
receipt. Collector full policy/workflow gates, remote byte verification and
integrator successor aggregate/main/CI remain separate responsibilities.

## Collector final gates

On the same isolated base and accepted JSON, all following commands exited 0:

- `python3 configs/check_english_repo.py`
- `python3 configs/check_public_repo.py` (staged index and worktree)
- `python3 configs/check_pdfjs_vendor.py`
- `python3 configs/pcbknowledge_workspace.py validate .`
- Focused intake unittest discovery: 141 tests, no skips.
- `python3 configs/pcbknowledge_workflow.py config`
- `python3 configs/pcbknowledge_workflow.py build`: 314 tests in 47.343 seconds.
- `python3 configs/pcbknowledge_workflow.py test`: 314 tests in 48.305 seconds.
- `python3 configs/pcbknowledge_agent.py --repo . validate`
- `python3 configs/pcbknowledge_workflow.py package`
- `python3 configs/pcbknowledge_agent.py --repo . change-scope`: DATA_ONLY.
- `git diff --cached --check`

No build/test failures, errors or skips occurred. Collector replay additionally
passed 22 complete-payload CLI commands, including 15 negative filters. An
explicit evidence-audit against the local official PDF returned one FOUND_MATCH
for the pinned bytes; this does not alter ordinary NOT_LOCALLY_VERIFIED reads.

The package contains 23 intake batches and 234 annotations, including the six
new facts. The original PDF, text extract and artwork are excluded. The packaged
new JSON is byte-identical to the independently accepted payload. Package hash:
`8f1592e79d9eae16445467883607a4e905c14affd2cc8341606b2584e045e7f6`.

The existing `intake-retrieval-tvs-connector.json` aggregate with dispositions
exited 2 for changed dataset bytes/batch set. This is intentional fail-closed
refusal, **not a passing successor aggregate**. The integrator must incorporate
this slice and review new pins/cases before main publication. No main ref change
or remote CI success is claimed here. Final guards and exact-payload replay are
rerun after this note; only the two named intake files enter the delivery delta.

### Final condition-scope clarification

On 2026-10-28 the reviewer refined the current warning to
`UNRESOLVED_SOURCE_CONDITIONS`, not a proved source contradiction. The supplied
information does not establish matched samples, mounting or curve-test setup;
therefore neither table nor curve is declared erroneous. The existing criterion,
unknown application thermal behavior and prohibition on curve-derived replacement
ratings remain unchanged. Prior review history is retained as superseded wording.
All **23 exact-payload/exclusion commands passed again** on this amended JSON,
with **16 negative cases**, exit **0** and no skips. The earlier focused-test
receipt applies to the pre-clarification metadata; collector final gates must
verify the amended delivery bytes.

## Amended delivery-byte gate receipt

The full collector gate list above was rerun on amended JSON
`e81420e76cbf4665ba891979d6c3e3b5c082970144225d3cae15473d2e368303`.
All policy, workspace, focused, Config, Build, Test, Agent validation, Package,
change-scope, whitespace and explicit byte-audit checks exited 0. Focused tests
passed 141 cases; Build and Test each passed 314, with no failures or skips.
The old aggregate again refused the changed batch set with exit 2, not a pass.
Collector complete-payload replay again passed all 22 commands.

The final package contains 29 JSON-only members; the new intake member equals
the amended JSON byte for byte. This supersedes the earlier package receipt.
Final package SHA-256: `001d9bc39010a29542c6ce206f4334604465956b6fa1c55f1eaf621c38b114f5`.

## Active pinned baseline and added-batch comparison

A clean isolated archive of `0373a341d5e12d50778f899848a078621dfa4790`
was initialized for the baseline check. Its complete Git tree exactly matched
`8c83b2cd3cc3a2443ab584ccd16768455c49dda0`, the original commit tree.
The active aggregate command was:

```bash
python3 -B configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-tvs-connector.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

On that unchanged baseline it exited **0**, status **PASS**, with **398 cases**
(392 base plus six disposition cases), **22 batches and 228 facts**. Baseline
manifest SHA-256:
`f46488a1b24f666a4ea7fcfa4e9730ed166c09a1e925c3860692ade5e5a973fd`.
The same command on the isolated delivery checkout containing this added batch
exited **2** with `dataset bytes or batch set changed; review cases before
updating pins`. This separately verified comparison establishes active-baseline
success and added-batch refusal; the older operational-manifest check does not.
The new set has 23 batches and 234 facts. No aggregate pins were modified.

### Independent final receipt review

The distinct reviewer inspected the corrected complete note and collector logs,
parsed all 398 baseline case results as passed, and checked the 22-batch/228-fact
counts and manifest hash above. The pristine baseline tree matches the original
0373a341 tree. The added-batch log records the active tvs-connector pin refusal.
Historical pending-review wording and the nonactive operational-manifest refusal
are now explicitly distinguished from current acceptance and the active baseline
comparison. This note is accepted under the same Agent/owner-delegation scope.
JSON remains unchanged at the amended hash above; no remote action was performed.
