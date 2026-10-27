# Batch 004 independent review

2026-10-27, reviewer `agent:verify_first_knowledge_batch`. **20/20 annotations pass with documented limits**, accepted under owner delegation; human-reviewed false. Use `timer-reference-driver-pilot.json`. Integration into the software schema requires separate validation.

## Evidence actually examined

All three original SHA-256 values and byte counts independently recomputed and matched collector receipts. Read original PDF text and viewed actual page images for all 20 facts and all three orderable identities. No new network request or blocked-source retry.

| Source | Bytes | Total PDF pages | Visually inspected one-based PDF pages |
|---|---:|---:|---|
| NE555 SLFS022K | 2,258,813 | 39 | 3, 4, 21 |
| TL431 SLVS543S | 3,087,819 | 85 | 4, 5, 6, 41 |
| ULN2003A SLRS027T | 1,850,862 | 42 | 1, 3, 5, 23 |

Eleven pages total: eight factual pages plus three identity pages. Identity PDF pages 21/41/23 are printed Addendum-Page 1/8/1 respectively. The packaging appendices are dated 2026-09-18, independently of electrical revisions March 2026 / May 2024 / March 2025. Exact selected codes NE555DR, TL431CDBZR and ULN2003ADR match their stated packages.

## Exact differences

No numeric value, pin assignment, unit, fact category, primary page or cited section changed. No facts added or dropped.

- NE555 fact 04: made its stated free-air temperature scope explicit as 0 to 70 C.
- ULN2003A fact 05: clarified that the maximum ON-state input-voltage entry bounds the input requirement under its stated test conditions; it is not an absolute maximum permitted input voltage.
- ULN2003A fact 06: replaced the unnecessarily specific phrase `single tested channel` with a conservative warning that this datum does not establish a simultaneous-channel current budget. No unverified production-test concurrency claim remains.
- Review statuses now agent-reviewed under owner delegation, human flag false. Added actual independent reviewer/evidence grade, page counts, identity-page visual evidence and distinct appendix dates. Removed absolute cache paths from portable copy. All bboxes stay null.

## Important distinctions checked

NE555's recommended 4.5–16 V supply range is distinct from its 18 V stress ceiling and SE555's operating limit. Reset pin 4 is active low; discharge pin 7 is open collector. Ambient range is not junction temperature.

TL431 DBZ uses cathode 1, reference 2, anode 3, unlike TL432 DBZ. Standard TL431C reference limits at 25 C are not A/B accuracy limits. The 1 mA maximum of the minimum-current requirement is not an allowed-current upper bound; recommended continuous cathode current remains 1–100 mA with power/temperature constraints. Voltage and current maxima do not automatically apply simultaneously.

ULN2003A's 2.7 kohm base resistor is a descriptive design value with no claimed tolerance. COM is the clamp-diode common cathode, not a logic supply. Electrical values retain 25 C, specified collector/input currents and the ULN2003A rather than adjacent ULN2002A/2004A table columns. No concurrent-channel current or thermal rating is derived from isolated saturation-voltage data.

## Remaining limits

Only the 11 listed pages visually reviewed, not the entire 166-page source collection. No bounding boxes, complete component model, TL431 stability qualification, or driver thermal/concurrent-channel design approval. These are source-specific annotations, not interchangeability claims. Exact accessed revisions are not a claim of global latestness. Original PDFs, full text and page images stay outside the repository and deliverable; original redistribution permission is not asserted.

Independent source receipts are embedded under `source_review_receipts` in the companion JSON. No raw originals, extracted pages or duplicate receipt authority are included.
