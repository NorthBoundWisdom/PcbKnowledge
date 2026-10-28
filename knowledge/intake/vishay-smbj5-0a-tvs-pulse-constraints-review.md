# Vishay SMBJ5.0A transient pulse constraints

Eight original noncanonical annotations and three source/application warnings.
Scope is Vishay General Semiconductor unidirectional SMBJ5.0A, SMB (DO-214AA),
not SMBJ5.0CA, another manufacturer, or circuit qualification.

## Source receipt

[Official source](https://www.vishay.com/docs/88392/smbj.pdf), document 88392, revision 09-Jan-2024.
Downloaded 2026-10-28; actual SHA-256 `1b65b57a4311128068c1dec747bbb99f6846ae932d77fcfd39904cb2d7a5cd50`, 129599 bytes, six pages.
Collector `agent:/root/collect_tvs_pulse_constraints` inspected all rendered pages. Technical pages 1-5 have the 2024
revision; page 6 is separate document 91000's 01-Jan-2026 legal notice.
No precise bounding boxes, latest-revision guarantee or human review is claimed.
No duplicate SMBJ or document 88392 record exists in the 184-record corpus at
`e4ce9305a4c48011eff9fa81cb751a0a5a5a87a8`.

Only this review and adjacent annotation JSON are delivery files. Source bytes,
text, images and logs stay local. Public reference is not open redistribution
permission or canonical licensing clearance.

## Review-critical boundaries

- 5-V stand-off and 800-uA leakage are separate from 6.4-7.07-V breakdown at
  10 mA (<=50-ms pulse test), and from 9.2-V maximum clamp at 65.2-A peak.
- 600 W describes the stated 10/1000-us transient, not DC or an inferred joule
  budget. Duration is measured at half-current decay, not a rectangle.
- The feature repetition headline and nonrepetitive rating note are preserved;
  neither grants arbitrary repeated-fault survival.
- The rating footnote uses TA but Figure 2 uses initial TJ with separate typical
  and safety-area curves. No reconciled numerical derating is manufactured.
- The 5-W power entry assumes an infinite heatsink at TA=50 C, not a normal PCB.
- KE occurs in both polarity columns; the unidirectional cathode band and exact
  procurement identity matter. No numbered footprint map is inferred.
- Capacitance curves are typical and condition-dependent; no numerical response
  time or guaranteed capacitance is invented. No USB/ESD/system certification.

## Independent review pending

A distinct Agent must inspect the actual source, recompute its hash and size,
review every complete annotation and warning, and test complete returned payloads
plus wrong-manufacturer/device/package/kind negatives. Review acceptance is only
Agent review under owner delegation, never human or canonical approval.

## Independent Agent acceptance

This section supersedes pending-review status above while retaining history.
Reviewer `agent:/root/collect_tvs_pulse_constraints/review_vishay_tvs` accepted the revised draft at 2026-10-28T04:51:15.609393+00:00.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION` under `OWNER_DELEGATION`.
Canonical and human-review flags remain false. The reviewer recomputed the actual
source hash, size and six-page count, inspected all six rendered images, and
reviewed all eight full annotation payloads and all three warnings. The live
HTTP download remains collector-attributed, not a reviewer download claim.

The initial wording was corrected to preserve separate rating conditions rather
than imply a demonstrated vendor contradiction or unconditional clarification
requirement. Review input JSON SHA-256: `c4302dbce21ce7f815ecadf567044595e35483104ac8d3c32931d7afa74169e8`.
Accepted JSON SHA-256: `54772a9aea101d79612815f88a317c8e2915391fa274eac16ca0d4a590f2a596`. No other numerical source changes were needed.

The independent replay passed 66 assertions across 26 CLI commands, no skips:
eight complete candidate objects (including full source and all three warnings),
one complete issues result, and 17 empty negative searches. Negative cases cover
wrong exact manufacturer, CA/sibling/orderable device, SMA/SMC package, wrong
kind, and unsupported compliance/continuous-fault properties. Exact filtering is
not electrical semantic qualification; visual source review establishes bounds.

Ordinary retrieval remains `NOT_LOCALLY_VERIFIED`; explicit evidence audit is
a separate operation. No raw PDF, extracted text, image or test log is delivered.

## Isolated final validation receipt

Final accepted payload was replayed independently: 66 assertions / 26 CLI
commands, zero skips; source evidence and facts/conditions/warnings were unchanged
apart from acceptance metadata. Collector full-object replay passed 48 assertions
across 22 CLI commands. Exact-filter negatives are not a compliance assessment.

Isolated baseline: `e4ce9305a4c48011eff9fa81cb751a0a5a5a87a8`.
The unchanged operational aggregate passes all 236 cases over 184 facts. Adding
this batch produces 17 batches / 192 annotations. Its deliberate replay against
`evals/intake-retrieval-measurement-timing-operational.json` exits 2 because the
batch set changes; this is an integration requirement, not a green aggregate.
No existing case manifest or disposition was edited.

Final accepted payload gates, all exit 0 unless noted above:

- `python3 configs/check_english_repo.py`, `check_public_repo.py`, and
  `check_pdfjs_vendor.py`.
- `python3 configs/pcbknowledge_workspace.py validate .`.
- Focused `test_intake*.py` unittest discovery: 117 tests, no skips.
- `python3 configs/pcbknowledge_workflow.py config`, `build`, `test`, `package`;
  Build and Test each pass 281 tests with no skips.
- `python3 configs/pcbknowledge_agent.py --repo . validate`.
- `git diff --cached --check` and Agent `change-scope`: DATA_ONLY.
- Agent `intake evidence-audit` with the explicit local original candidate:
  FOUND_MATCH for 129599 bytes and the pinned source hash; metadata unchanged.
  This checks bytes, not source licensing or electrical truth.

The 23-member package was inspected: every intake JSON exactly matches its
accepted local input, and no source original, image or extracted text is included.
Only this review and adjacent JSON comprise the delivery delta. No main ref move,
canonical approval, user-circuit qualification or remote CI pass is claimed.
The single integrator must generate a successor aggregate, reconcile current
main, rerun combined gates and observe exact-commit CI.
