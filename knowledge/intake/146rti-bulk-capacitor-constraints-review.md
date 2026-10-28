# 146 RTI bulk-capacitor constraints

Seven original annotations cover **Vishay BCcomponents MAL214636471E3**:
470 uF, 25 V, nominal 10 x 16 mm radial case, Form TFA. This is exact-part
noncanonical knowledge, not a generic electrolytic model or installed design.

## Source receipt and limits

- Official source: https://www.vishay.com/docs/28401/146rti.pdf
- Electrical document 28401, **22-Mar-17**, eight electrical pages.
- Actual unchanged PDF: **134,598 bytes, nine pages**; SHA-256
  `3a6ebd75687bd5c8207b0182c22367cfa3ebb94a5033c8e25f4bd087e37f084b`.
- Page 9 is legal document 91000, 01-Jan-2026. That date and PDF container
  metadata are not newer electrical revisions.
- Collector: `agent:/root/resume_compact_evaluation/curate_current_sense_resistor`.
- Cited pages 1, 2, 3, 4, 6, 7 and 8 were visually inspected from actual bytes.
  Legal page 9 was read before processing. No measured bounding boxes claimed.
- The exact orderable is explicitly shown in the page-3 ordering example and
  Table 2. Its presence was also checked in official product-quality HTML at
  https://www.vishay.com/en/product/28401/tab/quality/; hash/size are retained in
  the source supplemental receipt. Neither this listing nor an accessible
  current product page guarantees future production or inventory.

The legal notice reserves rights, grants no intellectual-property license and
requires application validation. No explicit prohibition on these small original
factual annotations was identified. This is not an open-license assertion.
Only original selected facts and review metadata enter Git. PDF, HTML, text and
renders remain untracked local evidence; no source table, plot, full prose
section or artwork is redistributed.

## Engineering boundaries

- Initial capacitance is specified at 100 Hz; its tolerance is not an aged,
  arbitrary-frequency or loaded effective-capacitance guarantee.
- Ripple is RMS at 100 kHz and 125 C. Only selected 25-V frequency multipliers
  are retained; no mixed-spectrum heating or life prediction is invented.
- The 100-kHz impedance limits are not renamed ESR. The source ESR expression
  uses dissipation factor and capacitance under their own frequency conditions.
- Surge/reverse entries do not authorize continuous overvoltage, reverse wiring
  or an unspecified pulse schedule. Leakage is a two-minute test result.
- The exact case is code 15, Form TFA. CA/CB lead-length definitions must not
  silently become TFA mounting or board-footprint instructions.
- Case-specific endurance and useful-life durations differ. Their loads and
  post-test criteria also differ; neither is a field-lifetime warranty. The
  source itself limits lifetime statements to estimates.
- Figure 12's footnote points to Table 4 while case durations appear in Table 3.
  This source cross-reference remains explicit; no graphical life multiplier
  is evaluated or silently corrected.

Three warnings preserve ripple/thermal, voltage/mounting and life/impedance
interpretation gaps. No source claim is upgraded to human, canonical or circuit
approval. Ordinary retrieval remains NOT_LOCALLY_VERIFIED.

## Independent review pending

A distinct Agent must independently verify source and supplemental bytes,
render/read the cited pages, review all seven complete facts and three warnings,
and validate exact retrieval plus wrong-part/package/revision exclusions.
Only then may the pair become AGENT_REVIEWED_UNDER_OWNER_DELEGATION.
Parent integration owns aggregate evaluation, main publication and CI.

## Independent review accepted, 2026-10-28

This section supersedes the historical pending state above without erasing it.
Reviewer: `agent:/root/resume_compact_evaluation/curate_current_sense_resistor/review_146rti_source`.
Decision at `2026-10-28T22:24:32.533515+00:00`:
`AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; not human or canonical approval.

The reviewer independently recomputed the PDF and supplemental HTML SHA-256
and byte sizes, confirmed nine PDF pages, inspected actual rendered pages
1, 2, 3, 4, 6, 7 and 8, read legal page 9, and checked the exact orderable in
HTML. HTML SHA-256 is
`285e1f07638edfb9f74da4f16905fb4805dd2bde43342ba14b90461c59bee984`
(813,868 bytes). All seven complete facts and three complete warnings were
checked; no engineering correction was required. In particular, the reviewer
confirmed RMS/frequency/temperature scope, Z versus ESR, separate endurance
and useful-life conditions, post-test versus initial limits, TFA versus CA/CB,
and the uncorrected Figure 12 cross-reference. No original source is added.

- Reviewed draft JSON SHA-256:
  `99a93a1d43c4cc0fd52079c663379f490316459360712ba218abc48705d6a249`.
- Accepted JSON SHA-256:
  `823234d25f9b7881e072abfc3621d928c7df57f724e698a58394aeddf1e9a23b`.

### Reviewer execution receipt

Using `python3 -B configs/pcbknowledge_agent.py --repo . intake`:

- `search --source-id 146rti-vishay-28401-20170322-470uf25v-tfa`:
  all seven complete fact objects and source objects equal the accepted JSON.
- `issues --source-id` with the same ID: all three complete warning and source
  objects equal the accepted JSON, matched by ID rather than array position.
- Each of seven exact `--parameter` queries returns its one complete fact.
- Both search and issues return no rows for wrong device `MAL214656471E3`,
  package `Form CA`, revision `01-Jan-2026`, or manufacturer `Other`.
- Noncanonical state and `NOT_LOCALLY_VERIFIED` remain intact. These are full
  payload assertions, not mere lexical-hit checks.
- Final comparison script: exit 0. An initial reviewer script wrongly assumed
  warning output retained input order and failed; correcting the comparison
  to use warning IDs passed without changing product code or knowledge.
- `python3 configs/check_english_repo.py`: exit 0.
- `python3 configs/check_public_repo.py`: exit 0, index and worktree boundary OK.

These checks do not claim aggregate evaluation, package verification, main
publication or CI; those remain parent integration responsibilities.
