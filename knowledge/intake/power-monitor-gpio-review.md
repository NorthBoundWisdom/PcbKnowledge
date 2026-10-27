# Batch 005 independent review

2026-10-27, `agent:verify_first_knowledge_batch`: **20/20 included annotations pass; one separate source-wording issue remains unresolved**. Agent-reviewed under owner delegation, not human-reviewed. Use `power-monitor-gpio-pilot.json`; repository integration validation remains separate.

## Actual evidence

Recomputed the hashes and byte sizes of all three cached official PDFs and matched the collector receipts. Read original text and inspected actual rendered pages for all facts, the source ambiguity, and all three exact orderable identities. No new downloads or blocked-source retries.

| Source | Bytes | PDF pages | One-based PDF pages visually inspected |
|---|---:|---:|---|
| TPS62160 SLVSAM2E | 2,784,747 | 42 | 4, 5, 30 |
| INA219 SBOS448G | 892,731 | 38 | 3, 5, 6, 14, 29 |
| MCP23017 DS20001952D | 1,019,348 | 40 | 1, 4, 11, 38 |

Twelve pages: seven factual pages, two ambiguity pages, three identity pages. TI identity pages 30/29 carry printed `Addendum-Page 1`; their dates are 2025-11-10 and 2026-03-05, separate from electrical revisions. MCP23017 June 2022 revision date was text-checked on page 37; that page was not visually rendered.

## Exact differences

No numeric value, pin assignment, address, unit, fact kind, or primary page/section changed. No facts added or dropped.

- TPS62160 fact 06: clarified `off_state` means the device switched off, not every out-of-regulation state while enabled. The source separately describes low PG for output below nominal regulation.
- INA219 fact 06: clarified +/-40 mV as the nominal bipolar full-scale endpoint representation, not a claim about the last quantized ADC code. Kept source settings, temperature, supply and input conditions.
- Added truthful independent agent-review metadata/evidence grades and actual visual identity checks; human-reviewed remains false. Recorded PDF page counts and precise printed identity labels; removed absolute cache paths. All bboxes remain null.
- Preserved `MCP23017-SUPPLY-TEMPERATURE-AMBIGUITY`, added independent visual confirmation and exact page/section/hash evidence. Replaced the extractor's future-review action with a manufacturer-clarification/superseding-evidence requirement. No supply-envelope fact was created.

## Confirmed source issue

MCP23017 page 1 lists operating-voltage envelopes conditioned on temperature, including 4.5–5.5 V through +125 C. Page 4's electrical-table header and D001 instead show 1.8–5.5 V with the header extending to +125 C. Both wordings are present in the same hash-identified Revision D source. No assumption resolves them here. Do not label the issue resolved merely because unrelated pin annotations passed. Suggested external task: obtain a manufacturer clarification or verified updated document, preserve both old observations, and explicitly supersede only the affected supply-envelope interpretation.

## Important scope checks

TPS62160 is adjustable DSG WSON: exposed pad to AGND and soldering requirement verified, not DGK. SW is not regulated-output sense; FB divider advice is not fixed-output FB-to-ground advice. Recommended input range uses junction-temperature limits, not ambient or the 20 V stress ceiling.

INA219A DCN pin mapping differs from SOIC. Bus voltage is measured from IN- to ground; shunt voltage is differential. Supply operating range is distinct from monitored bus range. Address 0x40 is seven-bit, not an eight-bit R/W address byte. No B-grade accuracy limit imported; no current calibration result inferred.

MCP23017 Revision D explicitly marks GPA7 and GPB7 output-only on page 1 and page 11; generic shared I/O wording does not override this part-specific restriction. MCP23S17 SPI functions do not apply to the target's NC pins. RESET is active-low and externally biased; interrupt modes remain configurable. The issue affects supply-envelope normalization, not these pin facts.

## Limits and stopping scope

Only 12 pages visually inspected, not all 120 document pages. No bbox, complete design model, current calibration, thermal qualification or substitution claim. Original PDFs/full text/renders remain cache-only, with no redistribution license asserted. Exact observed revisions do not guarantee global latestness. This completes the requested five-batch / 100-annotation pilot review; no additional batches are being collected by this reviewer. Evaluate coverage and remaining issues before expanding further.

Source review receipts are embedded in the companion JSON. Portable issue metadata uses `issue_status: UNRESOLVED_SOURCE_WORDING`, distinct from annotation review status; this naming normalization does not resolve the issue or promote a supply-envelope fact.
