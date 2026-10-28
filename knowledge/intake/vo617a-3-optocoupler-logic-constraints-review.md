# VO617A-3 optocoupler logic constraints

Eight small original annotations cover **Vishay Semiconductors VO617A-3,
standard DIP-4, CTR bin 3**. The purpose is to separate active-region CTR from
saturated logic pull-down capability and preserve the evidence needed to avoid
invented LED-resistor or signaling-rate approval. Other bins and package/safety
options are not interchangeable scope.

## Source receipt

- Official source: https://www.vishay.com/docs/83430/vo617a.pdf
- Document 83430, **Rev. 2.8, 22-Jan-2025**.
- Actual SHA-256:
  `145893b5422f68cc3f2016e2dddfc33f6ee26f0d2444fe8889d0dc0388f805a1`.
- **237,004 bytes; eleven PDF pages**, accessed 2026-10-28.
- PDF page 11 is the separate 01-Jan-2026 legal notice, not the electrical
  revision. No latest-revision guarantee is made.
- Collector: `agent:/root/continue_pcbknowledge_iteration/collect_low_voltage_mosfet`.
- Actual bytes were hashed; collector rendered and visually inspected pages
  1–4, including ordering-row alignment, selected characteristics and test
  circuits. Legal page 11 text was read first. No bounding boxes, complete
  footprint, all-page visual review or human review are claimed.

The legal notice reserves rights, grants no intellectual-property license and
requires application validation. No explicit prohibition on these small original
factual annotations was identified. Public reference is not an open license or
canonical licensing clearance. Under ADR-021 only this original receipt and the
adjacent original annotation JSON are delivered. The original PDF, source text
and images remain outside Git; no source table, prose section or artwork is
redistributed. Gated third-party CAD data was not used.

## Review-critical distinctions

- Pages 1–2: exact VO617A-3 standard DIP-4 orderable and numbered schematic;
  no option suffix, VDE status, top/bottom footprint view or land pattern inferred.
- Page 2: selected LED and collector absolute maxima are stress limits, not
  simultaneous operating permission or recommended current.
- Page 3: LED forward-voltage values belong to a 60-mA test; there is no invented
  5-mA maximum for resistor design.
- Page 4: bin-3 CTR belongs to 5-mA LED current and 5-V collector-emitter voltage
  at 25 °C; it is not guaranteed saturated sink capability or lifetime/hot CTR.
- Page 3: saturation voltage belongs to the separate 1-mA collector-current
  test. Leakage is selected from the exact bin-3 row, not a lower-bin row.
- Page 4: non-saturated turn-off is typical, at the stated load and source
  conditions. Scope loading is separate from circuit load; no bit-rate guarantee.

## Source conflict and conservative disposition

The page-4 saturated switching rows specify a 5-mA LED current. The adjacent
Figure 3, also labeled saturated operation, marks a 10-mA LED current. The page
provides no explicit reconciliation of those two setups. The intake records
both source locations and leaves resolved current and qualified saturated delay
unknown. It does not silently pick one, copy a typical delay into a guaranteed
rate, or rewrite the source. Manufacturer clarification or characterization of
the intended circuit is required before using a saturated delay as established
for that circuit. The independent reviewer must investigate this relationship.

Three warnings preserve this source conflict, unknown practical logic margins,
and unassessed isolation/package-option suitability. Family isolation headlines
are not continuous working-voltage or system safety certification. This intake
contains no mains-isolation design recommendation.

## Independent Agent review pending

A distinct reviewer must independently hash/count the same source bytes,
rerender cited pages, inspect row/circuit context and legal notice, verify every
complete fact and warning, and inspect the final amended payload. Acceptance
is Agent review under owner delegation only; canonical and human-reviewed stay
false. Exact structured retrieval and deliberately wrong identity/bin/package/
revision cases must test actual payloads, not keyword hit counts.

Only this pair is collection-owned. Existing accepted pairs, shared tests,
manifests, docs, main publication and CI are outside this task's write scope.

## Independent Agent review accepted (2026-10-28 UTC)

This section supersedes the historical pending request. Actual reviewer:
`agent:/root/continue_pcbknowledge_iteration/collect_low_voltage_mosfet/review_vo617a3`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; authority: `OWNER_DELEGATION`.
Canonical and human-reviewed remain false.

I independently recomputed the exact source hash, 237,004-byte size and eleven
pages, read legal page 11 before processing, independently rerendered pages
1–4 and inspected all four images. I verified ordering-row alignment, numbered
schematic, selected stress and electrical rows, CTR bin, source note distinguishing
min/max from typical, and the switching circuits. No all-page visual review or
independent attestation of the collector's HTTP download is claimed.

No electrical fact correction was needed. The draft's warning storage keys
`issues` / `status` were corrected to the existing loader's `source_issues` /
`issue_status`. Before correction, the loader refused the unsupported acceptance
status; after correction, all three complete warnings are attached to every
retrieved fact. This was a schema-shape repair, not removal or resolution of
any warning. Review history preserves the draft and correction.

Both saturated contexts are explicitly labeled on page 4, but the table has
5 mA and Figure 3 has 10 mA. There is no explicit instruction reconciling the
row to that figure. The records correctly retain this unresolved setup
ambiguity instead of claiming a manufacturer's typo or that either setup's
saturated delay is established. Withholding that qualification while seeking
clarification or circuit characterization is the accepted conservative
engineering disposition; it is not a claim that the raw source is corrected.

Review input JSON SHA-256:
`e6598744935d92fe5a35c5e6e7a7a866742817241f1bca8d36af7c94fc6dfb8e`.
Accepted JSON SHA-256:
`adc2ce86339add3ad91ee96225abdc2bc4343dd6e994afc0e4e50f35ae60e64c`.

The final amended JSON was read back and tested through the intake CLI. All
eight complete returned fact payloads and their complete source and three
warnings matched exactly. Eight parameter-plus-kind queries returned the
correct complete fact. Seven wrong manufacturer, generic/sibling/option device,
package, legal-appendix revision and kind cases returned no matches. Assertions
also preserved the distinct CTR/saturation tests and unresolved saturated
current/delay fields. The local review script exited 0. Ordinary reads remain
`NOT_LOCALLY_VERIFIED`; this receipt does not give consumers cached bytes.

`python3 configs/check_public_repo.py` and
`python3 configs/check_english_repo.py` both exited 0. No aggregate gate or CI
pass is claimed. Only this pair was amended; no shared files, commits or remote
refs were changed by the reviewer.
