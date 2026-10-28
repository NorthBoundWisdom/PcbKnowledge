# BZX84C5V1 Zener conditions

Six small original annotations cover exact Vishay **BZX84C5V1-E3-08**, C
voltage tolerance, commercial E3 grade, SOT-23, -08 reel packaging. This is
noncanonical source-bound knowledge, not a voltage-reference or clamp design.

## Actual source and processing scope

- Official PDF: https://www.vishay.com/docs/86338/bzx84_series.pdf
- Electrical document 86338, Rev. 1.1, 24-Jan-2024, five electrical pages.
- Downloaded PDF: 117,279 bytes, six pages, SHA-256
  `e9ce55f99308e0487ed8516ac4e0c1c88b010d7cb415df5b5d885ddafa432ca7`.
- Page 6 is legal notice 91000, 01-Jan-2026; not a newer electrical revision.
- Collector `agent:/root/continue_ntc_collection/curate_zener_conditions`
  viewed actual rendered pages 1 and 2, including multi-level table headings.
- Exact MAT_NO equality was verified in the official quality HTML at
  https://www.vishay.com/en/product/86338/tab/quality/, 824,432 bytes, SHA-256
  `c0be1f305b2c2dbf0309504f400ec527333febfc98c1bf79a457b0e59112788e`.
  This is identity support, not inventory, future supply or certification.

The legal notice was read before processing. It reserves rights, grants no
intellectual-property license and requires application validation; no explicit
prohibition of these limited original factual summaries was identified. This is
not an open-license assertion. Original PDF/HTML, extracted text and rendered
pages remain untracked local evidence, not in Git or packages. No whole table,
source prose or artwork is copied into this pair; bounding boxes remain unknown.

## Engineering interpretation limits

- Zener voltage has explicit minimum/nominal/maximum at 5 mA and 25 C. The
  separate primary-characteristic table calls its specification pulse current;
  a pulse duration and an arbitrary-current DC voltage guarantee are unknown.
- Dynamic resistance uses 1 kHz and two bias-current points. It is not DC V/I,
  a constant resistor, or permission to extrapolate the whole I-V curve.
- Leakage is a conditioned IR-at-VR entry. Its column lacks an explicit MIN/MAX
  label, unlike adjacent dynamic-resistance columns; no max label is invented.
- The temperature-coefficient interval includes both signs and retains its
  printed 10^-4/degC unit and test current. No zero drift or wide-range constant
  coefficient is inferred.
- Two absolute power rows use different thermal contexts. They do not qualify
  installed-board dissipation, and maximum power divided by nominal voltage is
  not a certified continuous Zener-current rating.
- Commercial E3 is distinct from automotive HE3_A; C and B tolerances and -08
  and -18 packaging must not be interchanged. Generic family qualification or
  ESD advertising does not confer qualification on this exact orderable/system.

Three full warnings retain bias/load/accuracy, fault/thermal protection and
source/grade boundaries. Ordinary retrieval remains NOT_LOCALLY_VERIFIED;
Agent acceptance is not human, canonical or circuit certification.

## Independent source review accepted

Draft JSON SHA-256:
`fa2a1883f2f07cd86f6446d16c64f6879bbf5db6087f1334fb2470ce3cc92231`.

Final accepted JSON SHA-256: `6cedd7a538975b627d609bdfd0fa1fdaeae3ecc9386250c84732e4a6b78352a1`.

Reviewer `agent:/root/continue_ntc_collection/curate_zener_conditions/review_zener_source` independently accepted at `2026-10-28T23:23:49.103057+00:00` after actual-byte hashes, exact orderable equality, rendered pages 1 and 2 and legal page 6. All six full facts and all three warnings were reviewed without technical corrections. The final acceptance transition changes review/status metadata only; canonical and human flags remain false.

This is Agent review under owner delegation, not canonical approval or human/circuit certification. Downstream integration, full gates, packaging and exact published-commit CI remain separate.
