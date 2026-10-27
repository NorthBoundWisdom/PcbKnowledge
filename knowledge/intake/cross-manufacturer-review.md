# Batch 002 independent review

2026-10-27, reviewer `agent:verify_first_knowledge_batch`. Result: **20 reviewed factual annotations accepted under owner delegation, with mixed evidence levels**. Human review: false. Use `cross-manufacturer-pilot.json`, not the unreviewed pilot. Original PDFs, page renders and full extracted text must remain outside the repository.

## Evidence actually examined

- ST LD1117STR: recomputed the cached official PDF SHA-256, matched extractor receipt; 1,634,512 bytes, 46 pages. Read text and visually inspected actual page renders 6, 7, 44 and 45. Confirmed SOT-223 adjustable order code and revision 38 / 2025-01-27. All seven facts supported, including the strict IOUT < 20 mA condition on the 18 V stress exception; did not import TI's different maximum voltage or tab numbering.
- Microchip MCP6002-I/SN: independently matched hash; 931,340 bytes, 50 pages. Read text and inspected actual renders 3, 11, 45 and 47. SOIC industrial grade and revision L / March 2020 confirmed. All seven facts supported with date-code qualifications and DC-table conditions. Offset and quiescent current are 25 C specifications, not guaranteed industrial-range limits; quiescent current is per amplifier.
- [Nexperia official PDF](https://assets.nexperia.com/documents/data-sheet/74HC_HCT00.pdf): independently examined already-available official web PDF text, pages 1, 3 and 4. Revision 11 / 2025-04-29 and SO14/SOT108-1 identity verified. All six facts match the text. In particular the HC recommended range is not HCT's, and the VOH minimum selected is from the -40..125 C column. This is **text-only**, not byte-identified or visually verified evidence. Prior direct download returned HTTP 403; no retry, alternative-byte-route, or bypass was attempted. No source hash/byte count is invented.

## Exact changes

No value, unit, pin assignment, fact category or primary page/section changed. No facts added or dropped.

1. `b002-microchip-mcp6002-l-05`: added the DC table's explicit default conditions (TA=25 C, VSS=GND, VCM and VL at half supply, 10 kohm load to VL, output approximately half supply), retaining the 6 V date-code screening qualification.
2. `b002-microchip-mcp6002-l-06`: clarified older production date codes as before YYWW=0449. Revision history page 45 independently confirms the new offset limit starts at 0449; avoids ambiguous prose about December/week 49.
3. Status changed to `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; human review remains false. Added reviewer/method and explicit evidence levels at source/fact scope.
4. Added byte counts/page counts, verified source hashes, and extended the visually reviewed page lists to include identity/revision evidence. Nexperia hash and byte count remain null; visual flags remain false.
5. Removed absolute local cache paths from the portable reviewed copy and replaced stale waiting-for-review limitations with actual remaining limits.

## Remaining limitations

No measured bboxes; no complete pinout or application model; no equivalence claims. Nexperia packing suffix unresolved. Exact accessed revisions do not establish global latestness. Source redistribution permission remains unknown; original binaries and renders are cache-only. Reviewed factual intake still needs separate schema integration validation. The Nexperia byte-acquisition limitation does not block publication of clearly marked text-supported annotations or the 14 stronger-evidence facts.

Source review receipts are embedded under `source_review_receipts` in the companion batch JSON. No original documents or extracted full pages are included.
