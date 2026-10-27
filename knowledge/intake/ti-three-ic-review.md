# Independent review: TI three-IC pilot

Reviewed 2026-10-27 by `agent:verify_first_knowledge_batch`.
Decision: **20/20 factual annotations pass with documented scope limits; agent-reviewed under owner delegation, not human-reviewed.** The reviewed annotations are in `ti-three-ic-pilot.json`. Canonical schema promotion is a separate check.

## Actual evidence work

Downloaded three official TI PDFs into a local cache outside the software repository. Used existing `curl`, `pdfinfo`, `pdftotext`, `pdftoppm` and `view_image`; no installation, no denied/pending download. Seven actual page renders were viewed: LM1117 printed pages 3–4, LM358 pages 3–5, SN74HC00 pages 3–4. Those pages contain all 20 claims. Footers agree with claimed document IDs/revisions/dates; page counts are 47, 68, 39. SHA-256/size receipts are in the embedded `source_review_receipts` in the batch JSON.

## Exact semantic differences from the intake draft

- **No numeric value, unit, pin assignment, fact kind, cited section, or page index was changed.** All 20 facts match the scoped official original tables.
- `ti-lm358-ab-07`: added that the original LM358 ambient range 0–70 degC also appears in section 5.3 on printed page 5. Kept its existing `absolute_maximum_table` kind because its primary citation is section 5.1. Do not mislabel as junction temperature or extend to B/BA.
- `ti-sn74hc00-h-05`, `-06`, `-07`: made the relevant SN74HC00 free-air range explicit (-40 to 85 degC), as stated in section 6.3. Retained VCC = 4.5 V for both logic thresholds and did not substitute SN54HC00's temperature range.
- Batch/source/fact statuses now say `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; added truthful agent-review metadata (`human_reviewed: false`). This is acceptance of the curated annotations under the user's delegation, not proof of human factual inspection.
- Added source SHA-256 and byte sizes; `pdf_local_path` remains null in portable intake to avoid publishing environment-specific paths. Updated every evidence method to actual local byte-identified text-plus-rendered-page review; `bbox` remains null, no region/coordinate claims invented.
- Replaced stale missing-hash/missing-image limitations with the real remaining limits.

## Verified distinctions

LM1117 DCY is the four-terminal SOT-223 representation: ADJ 1 (adjustable only), VIN 3, VOUT 2 and 4; WSON numbering is different. Its 20 V stress limit is not its 15 V recommended input ceiling; 0–125 degC is junction temperature for LM1117, not the LM1117I -40 lower limit. No minimum input was invented.

Original LM358 D is 8-pin SOIC: OUT1 1, IN1− 2, IN1+ 3, V− 4, V+ 8. Original-part 32 V total-supply stress limit and 3–30 V recommended range are not B/BA limits. Ambient temperature was not confused with the 150 degC junction stress limit.

SN74HC00 D is 14-pin SOIC, not FK: channel 1 A/B/Y is 1/2/3; GND/VCC is 7/14. Supply stress range -0.5–7 V differs from recommended 2–6 V (nominal 5 V). VIH minimum 3.15 V and VIL maximum 1.35 V are input requirements at VCC 4.5 V, not output-drive guarantees.

## Limits and publication boundary

Exact orderable SKUs remain unresolved; this is family-plus-package knowledge, not a purchasing identity. Only seven relevant pages were visually reviewed, not all 154 pages. No full pinout, application readiness, thermal design, or complete electrical characterization is claimed. Source links may mutate; preserve these hashes and distinguish original-byte availability from metadata validity. Source redistribution license remains unknown; no PDF, extracted full text, or screenshot belongs in the commit. Only the small factual annotations and review receipts should be integrated.
