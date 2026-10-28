# NTCLE100 thermistor sensing constraints

Seven original annotations cover **Vishay BCcomponents NTCLE100E3103JB0**:
10 kohm at 25 C, J tolerance, no-A B0 bulk, radial leaded bead. This is
noncanonical intake, not an approved temperature sensor circuit.

## Source receipt

- Official PDF: https://www.vishay.com/docs/29049/ntcle100.pdf
- Document 29049, electrical revision **07-May-2025**, 16 electrical pages.
- Actual PDF: **243,300 bytes, 17 pages**, SHA-256
  `f9d6153738198dc705ed681c3b55e70a6571f8fee13a4ed7b2b41e49973cb9c9`.
- PDF page 17 is legal notice 91000, 01-Jan-2026, not a newer electrical revision.
- Exact orderable derives from page 2's 10-kohm row, J code and page 16 bulk
  packaging. Official quality HTML contains an exact MAT_NO equal to the selected
  orderable, not merely a prefix of JB0A. Its URL/hash/size are retained in JSON.
- Collector: `agent:/root/continue_ntc_collection/curate_ntc_source`.
- Actual rendered pages 1, 2 and 16 inspected; measured bounding boxes unknown.

Legal notice reviewed before processing: rights reserved, no intellectual-property
license and customer application validation required. No explicit prohibition on
these limited original factual annotations was identified. No open-license claim.
PDF, HTML, extracts and renders stay in local untracked evidence; no source table,
artwork, full prose or original document enters Git or packages.

## Engineering boundaries

- R25 and B25/85 have separate tolerances; they are not a system temperature-error
  specification. No curve is copied or temperature calculator certified.
- Temperature range is conditioned on zero power. The source's one-percent
  measurement convention does not mean zero self-heating or a fixed permissible
  measurement power over the full temperature range.
- The 500-mW entry is at 55 C. The rendered derating curve is not a flat full-range
  rating; only labeled points and the plateau are retained, not digitized curves.
- Approximately 1.2 s response in oil and the informational 15 s time constant
  are different entries. No guaranteed installed response time is established.
- The informational 7 mW/K value applies to this scope; 8.5 mW/K is restricted to
  resistance values no greater than 680 ohm. Neither establishes actual error.
- Coating has no specified insulation properties; potting is not intended.
  Separate handling instructions are referenced but were not reviewed here.
- Green shading identifies A-column versions as preferred for new designs.
  The selected no-A part is not in that column, but this is not a discontinuation
  or NRND claim, nor authorization to substitute JB0A.

Three full warnings retain excitation/thermal, conversion/accuracy and mounting/
suffix uncertainties. Ordinary retrieval remains NOT_LOCALLY_VERIFIED; this
receipt does not imply canonical, human or circuit acceptance.

## Independent review accepted

Initial draft SHA-256: `9bb9853dc854d4c7a60c2e56c6cb00213479f7adf66dfac1b2d841254bcb1584`.
Revised reviewed draft: `caa8bf3cd064114c75feec882a0b8a4f3c48b86f8a8e1b62f66201da7d575484`.
Final accepted JSON: `085793b239cb1a67f455f327c7214fa87b5ffbb3df0161eaee72e34d8d514a5a`.

Reviewer `agent:/root/continue_ntc_collection/curate_ntc_source/review_ntc_source` accepted at `2026-10-28T23:01:46.898719+00:00` after independently recomputing actual PDF/HTML hashes, checking exact identity, viewing cited pages and reading legal page 17. All seven complete facts and all three warnings were reviewed. A precision correction retained the printed BMAX header alongside its 3.3 +/- 0.5 mm entry; no dimensional interpretation was invented. Review history is append-only.

This is AGENT_REVIEWED_UNDER_OWNER_DELEGATION, not human, canonical or circuit approval. Final integration, aggregate replay, package and exact published-commit CI remain separate downstream gates.
