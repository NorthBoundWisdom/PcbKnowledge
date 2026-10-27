# Batch 003 independent review

2026-10-27, `agent:verify_first_knowledge_batch`: **20/20 factual annotations pass with documented limitations**. Agent-reviewed under owner delegation; human-reviewed false. Use `interface-ic-pilot.json`; repository schema validation remains separate.

## Evidence actually inspected

Recomputed all three source SHA-256 values and byte counts; they match the collector receipts. Original files remain in the local source cache outside the repository. No network fetch or blocked-source retry needed.

| Source | Original size | PDF pages | Actual rendered PDF pages visually reviewed |
|---|---:|---:|---|
| ADS1115 SBAS444E | 2,654,255 bytes | 57 | 3, 4, 20, 42 |
| 24LC256 DS20001203Y | 727,562 bytes | 48 | 1, 4, 7, 45 |
| SN65HVD230 SLOS346O | 812,033 bytes | 43 | 4, 5, 6, 36 |

All nine factual pages and three orderable-identity pages were inspected as actual images as well as original-PDF text. Microchip's July 2022 revision date was additionally checked in original text on page 43; that page was not visually rendered. TI electrical revision dates are distinct from their packaging appendices: ADS1115 appendix 2025-10-14; SN65HVD230 appendix 2026-03-05. PDF identity pages 42/36 are printed `Addendum-Page 1`, not printed pages 42/36.

Rendering emitted fontconfig cache-write warnings on supplementary identity renders but exited successfully and produced readable images that were inspected. No installation or change outside the allowed cache was attempted. No missing-image pass claimed.

## Exact differences

**No numeric value, address, pin mapping, unit, fact kind, or primary page/section changed. No facts added or dropped.**

- ADS1115 fact 05 now links the SDA address choice directly to fact 06's >=100 ns SDA-low hold requirement after SCL goes low, and retains the source preference for GND/VDD/SCL first. This prevents a detached address mapping from hiding a necessary timing qualification. Address values remain seven-bit 0x48/49/4A/4B, without R/W bit.
- ADS1115 facts 04/07 now explicitly state the section 5.3 recommended ambient range (-40 to 125 C).
- 24LC256 fact 04 now explicitly states the selected industrial I-grade range (-40 to 85 C).
- SN65HVD230 facts 03/06 now explicitly state section 8.3's recommended free-air range (-40 to 85 C).
- Batch/source/fact review statuses changed to `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`, human review remains false. Added actual reviewer/method, source page counts and identity-page evidence. Absolute local cache paths removed from portable copy; SHA and byte identities retained. All bboxes remain null.

## Distinctions verified

ADS1115 pin/table selection excludes adjacent ADC variants. Programmable differential full-scale range is not substituted for each analog pin's GND..VDD recommended voltage. Bus pull-ups are required but no universal resistance value inferred.

24LC256 SOIC has functional A0/A1 pins; the MSOP exception does not apply. WP must have a defined rail connection. LC's 2.5 V minimum, 400 kHz ceiling and 600 ns clock-high minimum are not AA low-voltage or FC 1 MHz specifications. Pull-up examples remain explicitly typical, not guaranteed universal limits.

SN65HVD230 low-power mode disables the driver while retaining the receiver; SN65HVD231's sleep behavior is not imported. RS pin 8 and its slope-control resistor/standby threshold are kept distinct; supply-voltage limits are not CAN bus voltage limits.

## Remaining limits

No complete component model, circuit/system qualification, or drop-in equivalence. No measured region coordinates. Only 12 pages visually reviewed, not whole documents. Source links may change; preserve hash-specific receipts. Original PDFs, extracted full text, and images must not be committed or redistributed. Source revision observations are not a guarantee of global latestness.

Independent source receipts are embedded under `source_review_receipts` in the companion batch JSON; originals and raw text are not included.
