# MCP23017 supply/temperature ambiguity: bounded disposition

## Outcome

The recorded source conflict is **handled by a conservative subset**, not declared
manufacturer-resolved. The original issue remains `UNRESOLVED_SOURCE_WORDING`.
The [separate machine-readable receipt](../knowledge/intake-dispositions/mcp23017-supply-temperature-2026-10-28.json)
records `CONTAINED_BY_CONSERVATIVE_SUBSET`, `manufacturer_confirmed: false`, and
an Agent-derived preliminary supply/ambient screen for **MCP23017-E/SO only**:

- Actual operating supply: **4.5 through 5.5 V**, inclusive.
- Ambient temperature: **-40 through +125 C**, inclusive.
- Inside: `WITHIN_CONSERVATIVE_SUPPLY_AMBIENT_SUBSET`, not design approval.
- Everywhere outside: `NOT_ESTABLISHED` by this narrow policy, not a declaration
  that the device is unsafe or cannot operate there. In particular, do not infer
  approval for 3.3 V at +125 C from separate parametric extrema.

These limits must cover actual supply and ambient extremes, not just nominal
labels. This does not settle I2C timing/speed, logic levels, loading, current,
power/reset sequencing, transients or thermal design. Those constraints require
independent checks. No complete recommended-operating envelope, canonical Fact,
whole-circuit safety recommendation or automatic component recommendation is added.

## Current official evidence recheck

Checked 2026-10-28, with actual downloaded bytes hashed and cited PDF page images
inspected. All originals and full extracted text remain outside Git and packages.

| Official source | Revision | Bytes | SHA-256 | Visually inspected PDF pages |
| --- | --- | ---: | --- | --- |
| [Previously cited datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-Data-Sheet-DS20001952.pdf) | DS20001952D, June 2022 | 1,019,348 | `63cb5f2bec44434cdeeada1790d0316c9dc06b33febb489ad87bb0e2d540496a` | 1, 3, 4, 37, 38 |
| [Current product-linked datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-MCP23S17-16-Bit-IO-Expander-with-Serial-Interface-DS20001952.pdf) | DS20001952E, July 2026 | 2,033,164 | `955825379d383249df4c1784f6598c252ccab121ef3aff6065ec6d8bf0cbc34b` | 1, 3, 4, 39, 40 |
| [Current linked silicon errata](https://ww1.microchip.com/downloads/en/DeviceDoc/80252A.pdf) | DS80252A, November 2005 | 149,256 | `3c1729362c9333f3bf991d02660c9bf741ed788ed254bf24f859d49ac075f230` | 1, 2 |

The [official product page](https://www.microchip.com/en-us/product/mcp23017)
links Revision E at a different URL; the old URL still serves Revision D. The
retrieved HTML was 680,954 bytes, SHA-256
`fa7b578e39f6692cc661b44d5a8de1b17dfc1bd66873ba9411f9e724ff507d39`.
This dated observation is not a perpetual latest-revision guarantee.

Revision E still lists temperature-conditioned cover ranges, including 4.5-5.5 V
through +125 C; its page 4 table header and D001 still imply the broader 1.8-5.5 V
range through +125 C. The two lower-temperature cover bullets are not explicitly
mapped. Page 39 identifies Figure 3-2/layout changes, not a supply correction.
Page 40 identifies the E/SO orderable and cautions that the E suffix does not remove
voltage/temperature conditions. Page 3 stress limits are not operating permission.
The errata addresses an early-silicon I2C acknowledgement issue, not this conflict.

The narrow high-voltage rectangle is an explicit **Agent inference** common to the
relevant cover and electrical-table wording. Choosing it avoids guessing the
unlabeled lower-voltage mapping. Manufacturer clarification is still needed to
establish the disputed lower-voltage/high-temperature region and intended mapping.
No manufacturer was contacted. No other uniquely recorded source issue was found
in the five historical intake batches; this is not proof that those sources contain
no other undiscovered inconsistency.

## Preservation and reader behavior

The five accepted JSON batches, the 100 annotation IDs, original warning payload,
[owner acceptance](owner-acceptance-2026-10-28.md), and original
[18-case manifest](../evals/intake-retrieval-100.json) remain byte-identical.
Existing MCP23017 pin facts are not relabeled as Revision E-reviewed.

The supplement pins the exact historical batch path/hash, issue ID, source
ID/hash/revision, device and package. `intake list`, normal fact/issue reads,
validation and Package validate all supplemental links. Stale, orphan, malformed
or ambiguous links fail the read; there is no silent fallback. Matching results
add `source_issue_dispositions` while retaining the complete original warning.
Issue lexical search includes the handling receipt, but fact lexical search does
not turn policy prose into a fact. Source IDs reused in other batches do not
inherit the policy. Reader evidence remains `NOT_LOCALLY_VERIFIED`.

Version 1 deliberately supports one receipt per exact issue target. A future
successor requires an explicitly reviewed lifecycle extension preserving this
receipt, not silently replacing it or pretending the current reader accepts a
supersession chain.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake issues CONTAINED_BY_CONSERVATIVE_SUBSET
python3 configs/pcbknowledge_agent.py --repo . intake search 'MCP23017 supply'
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-100.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The separate disposition manifest pins the added bytes and six new retrieval
cases. Replay preserves the historical dataset fingerprint and checks all 24
cases, including full additive receipt metadata. Omitting the supplement pins
when supplements exist is an explicit error. Packages include validated metadata,
never the source PDFs/HTML or rendered pages.

## Verification receipt

Independent reviewer `agent:verify_mcp23017_conflict_resolution` checked the
source hashes, every PDF page cited above, new product-page link, exact scope and
final code/evidence contract. Earlier review findings about unsupported successor
semantics, evidence linkage, huge numeric values and review timestamps were fixed
before acceptance. Independent full tests: 191 passed, no skips; all 24 real CLI
cases passed with the original dataset fingerprint unchanged.

Local staged checks exited 0: 44 focused tests; English/public-source/PDF.js guards;
workspace validation; Config; Build and Test (191 tests each, no skips); Agent
validation; the 24-case replay; and metadata-only Package. The five historical
batch files, original retrieval manifest and owner receipt were diff-checked
unchanged. Remote CI is a separate exact-commit publication check, not inferred
from these local results.
