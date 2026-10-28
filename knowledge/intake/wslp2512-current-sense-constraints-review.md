# WSLP2512 current-sense constraints

Six small original annotations cover Vishay Dale **WSLP2512R0100FEA**, a
10-milliohm, 1% WSLP2512 with EA packaging and no extra special suffix.
They are noncanonical source-bound facts, not a qualified shunt design.

## Source and identity

- Official PDF: https://www.vishay.com/docs/30122/wslp.pdf
- Document 30122, electrical revision **09-Sep-2024**, pages 1-4.
- Actual bytes: **146,445**, five PDF pages; SHA-256
  `d3dd7b4f590e713c84303e32530e8c8c6fd025617896e11d25599521771e4c13`.
- PDF page 5 is separate legal document 91000 dated 01-Jan-2026; neither its
  date nor the PDF container date is an electrical revision.
- Collector: `agent:/root/resume_compact_evaluation/curate_current_sense_resistor`.
- Collector read actual PDF text and rendered/inspected pages 1-3 for table
  alignment, diagram meaning, test conditions and footnotes. The legal notice
  was read before technical processing. No measured bounding boxes claimed.
- PDF page 1 explains codes but its printed example uses WSLP1206. Exact
  WSLP2512R0100FEA is separately corroborated by an exact part entry in official
  product-quality HTML at https://www.vishay.com/en/product/30122/tab/quality/.
  Its actual-byte hash and size are in the source's supplemental identity
  receipt. Only identity is used; no inventory or quality certification inferred.

The legal notice reserves rights, grants no intellectual-property license and
requires application validation. No explicit prohibition on these small
original factual annotations was identified; this is not an open-license
claim. PDF, HTML, extracted text and renders remain local and untracked. No
source table, full prose section, artwork or complete document is published.

## Useful distinctions

- The 3-W P70 reference and ambient derating graph do not establish allowable
  power or current on an unknown board. A concrete rating-test PCB stackup,
  copper area and airflow are not specified in the cited datasheet.
- Component TCR includes copper terminals. For this 10-milliohm scope its
  75-ppm/C magnitude bound cannot be replaced by the alloy-only <20 figure.
- The working-voltage formula depends on allowed power/energy; it is not a
  free-standing pulse-current authorization.
- The 10-milliohm terminal/pad row differs from other WSLP2512 resistances.
  A two-terminal body plus typical sensing traces is not a four-terminal part,
  a complete footprint or a guaranteed sense-error budget.
- The load-life change limit retains its additive 0.0005-ohm term and exact
  1000-hour, 70-C, 1.5-hour-on/0.5-hour-off conditions. It does not establish
  lifetime accuracy; this row does not state test power.
- The pulse plot is expressly illustrative. No numeric envelope is read from
  it, and the linked calculator was not used. Three warnings preserve actual
  thermal, measurement and pulse-envelope gaps.

## Independent review pending

A distinct Agent must verify the same actual PDF and supplemental HTML bytes,
inspect cited rendered pages, review all six full fact payloads and all three
warnings, and validate retrieval. Only after that review may this draft become
AGENT_REVIEWED_UNDER_OWNER_DELEGATION. Canonical and human flags stay false.
Only this pair is owned; parent integration owns aggregate tests and publication.

## Independent Agent review accepted

The historical pending request above is superseded by this actual review.
Reviewer: `agent:/root/resume_compact_evaluation/curate_current_sense_resistor/review_wslp_source`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`, under `OWNER_DELEGATION`.
Neither canonical nor human-review flags were promoted.

I independently recomputed the 146,445-byte PDF SHA-256 and rerendered and
visually inspected pages 1-3, including merged table rows, terminal/pad geometry,
ambient derating endpoints and the illustrative-pulse label. I read legal page 5.
I also recomputed the supplemental HTML's 995,279-byte size and SHA-256
`c0157173c05441b5a134af06e103bd94f39484f9c1f1c98478c37809cb8b14da`
and verified the exact MAT_NO entry WSLP2512R0100FEA rather than its suffixed
neighbors. I did not reattest the collector's HTTP download transaction.

All six complete fact payloads and three warnings were accepted without
numerical correction. The PDF numbering example's different model is explicit,
not silently treated as the selected exact part. Component versus element TCR,
selected resistance-specific geometry, conditioned P70, test-time conditions
and additive resistance drift remain distinct. Missing test PCB and load-life
power are not invented; no pulse calculator or application qualification added.

Review-input JSON SHA-256:
`f25a83e53464d4a392b094b79e8daf4d6bf1f5944291a0430f6eda9b2ed4a554`.
Accepted JSON SHA-256:
`91abaf2e01f2cbd092e2e4e33f194a59bacf1eebcb33aeb07ff28b1ef775414b`.

Actual validation: source-filtered CLI retrieval preserved each full fact and
source object and all three full warnings (the CLI's documented deterministic
ID order differs from the input warning order). Six parameter selections each
returned their intended full fact. Six scoped wrong-device/suffix/manufacturer/
package/revision/kind negatives returned no matches. Explicit checks retained
unknown qualified board power/current, component75 versus element20, two-terminal
identity and the additive0.0005-ohm test term. The reviewer check exited 0;
English and public-boundary checks also exited 0. The first reviewer harness
asserted unsorted warning-list equality and was corrected to compare all complete
objects in deterministic ID order; no production data or assertion coverage was
removed. These are focused source-review results, not aggregate or CI evidence.
