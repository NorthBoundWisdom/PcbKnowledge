# KEMET C0603C104K5RACTU capacitance constraints

Eight small original noncanonical annotations and three unresolved-use warnings.
Scope is the exact KEMET commercial X7R orderable in 0603/1608, not an assumed
replacement, general MLCC model, procurement guarantee or decoupling sign-off.
KEMET is the manufacturer brand; YAGEO Group publishes the inspected documents.

## Source identity and byte receipt

- [Exact-part specification sheet](https://yageogroup.com/component-documentation/download/specsheet/C0603C104K5RACTU?lang=en):
  SHA-256 `f4b35dc168d8e66d40cd476e5cef8431524033dbdf9ac33d12f3ef2850b59a02`,
  289469 bytes, four pages. Page 1 prints the complete orderable and package.
  The actual footer says generated 2026-10-28; that is not a technical revision.
- [Commercial X7R family datasheet](https://yageogroup.com/content/datasheet/asset/file/KEM_C1002_X7R_SMD):
  SHA-256 `d8e6ca6631862e31a19b90b6cfe13f1b20153c2efd6c8e30f1a5d5ba147aa908`,
  3316643 bytes, 28 pages. Inspected pages identify C1002_X7R (2026-09-01).
  The initial draft's 22-page count was corrected using `pdfinfo`; the bytes,
  hash and cited page indices were unchanged.

The reviewer recomputed both hashes and sizes, checked PDF page counts and
inspected exact-part pages 1-4 and family pages 1, 2, 12, 14 and 16. Full original
files, text, drawings, curves, screenshots and CAD are not delivery content.
Live acquisition is collector-attributed; the reviewer did not redownload or
attest server behavior. Public reference is not redistribution permission.

## Independent decision

Reviewer: `agent:/root/collect_mlcc_effective_capacitance/review_kemet_mlcc`.
Review time: 2026-10-28T05:37:54.905442+00:00.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION` under `OWNER_DELEGATION`.
Human review and canonical approval remain false.

Input JSON SHA-256:
`1bc25be5d933c5d9e441a0e645026e8e9deae9c78616d9af8ed3c3662cf13b4b`.
Accepted full JSON SHA-256:
`e4cb0113234ed90ed6f9ef7e2c32cad842d6f9b7648ac017b16b2cbbe9903a1b`.

All eight complete values, conditions, identities and evidence links, plus all
three complete warnings, were reviewed. In addition to the page-count correction,
the PCB warning was associated with the family source so the family-backed land
pattern candidate retains its missing-input warning. Family page 2 was additionally inspected to link the K tolerance code explicitly
to its plus/minus meaning; the exact orderable is independently printed, not
constructed from this code table. No numerical electrical correction was needed. Review provenance was added without removing collection
history.

## Evidence and interpretation boundaries

| Annotation suffix | Exact-part PDF pages | Family PDF pages | Reviewed boundary |
| --- | --- | --- | --- |
| 01 | 1 | 2, 14 | Nominal measurement and referee conditions, not effective capacitance |
| 02 | 1 | 16 | Rated voltage versus brief dielectric-withstand test |
| 03 | 1 | 16 | Zero-bias temperature coefficient, not a combined operating envelope |
| 04 | 1 | 16 | Aging rate and referee time, not linear hourly loss |
| 05 | 1 | - | Body size, not PCB copper |
| 06 | - | 12 | Density-dependent land recommendations; no selected footprint |
| 07 | 2, 4 | - | Qualitative DC-bias simulation, not a minimum guarantee |
| 08 | 4 | - | Application adequacy unresolved |

The bias curve exists for this exact part, but no numerical curve samples were
extracted. Its qualitative trend is not a guaranteed capacitance bound at any
voltage. Temperature and AC-voltage plots were inspected without being digitized.
Neither the nominal label, a rating, a withstand test nor the simulations closes
unknown circuit, thermal-history, layout or impedance requirements. No combined
worst-case capacitance, derating percentage, qualification grade or near-rating
performance guarantee was invented. Exact orderable identity does not establish
stock, lifecycle or equivalence to the printed alias or other suffixes.

## Independent retrieval checks

A direct application-API replay passed 22 assertions with zero skips: eight
complete fact-candidate objects, two complete source-warning result sets and
12 empty exact-filter negative searches. Full object comparison included each
value, condition, evidence record, source, provenance and associated warning;
it was not an ID-only check.

Negatives covered Murata and publisher-as-manufacturer confusion; alias and
other orderable suffixes; wrong or incomplete package strings; wrong fact kinds;
and unsupported guaranteed-effective-capacitance, continuous-withstand-voltage
and qualification properties. Exact filtering is not semantic electrical proof.
Normal retrieval correctly retains `NOT_LOCALLY_VERIFIED`; recorded source review
does not mean each subsequent reader has checked original local bytes.

Repository-wide gates, aggregate integration and exact-commit remote CI are
separate integrator work; this independent review does not claim they passed.
Only this review and its adjacent JSON belong to the proposed delivery.

## Collector validation receipt

On isolated base `0373a341d5e12d50778f899848a078621dfa4790`, after the
independent source corrections and review:

- Real CLI complete-payload replay: 27 cases passed; 13 equal-ID/count semantic
  payload mutations were distinguished from the pinned correct output. These are
  preservation checks, not an electrical reasoning engine.
- Config, Build, Test, Agent and workspace validation passed. Build and Test each
  ran 314 tests with zero skips. PDF.js, English/public-boundary and whitespace
  guards passed; the two staged files also passed English/public-boundary checks.
- Explicit local source-byte audit returned `FOUND_MATCH` for both cached PDF
  originals. This does not replace the separate visual/source review above.
- The historical TVS/connector aggregate exited 2 as expected because the batch
  set changed. No historical pins, expected results or aggregate were rewritten.
  Successor aggregate integration remains separate integrator work.
- Package contained 23 intake batches and no PDF originals, chart images or text
  extracts; ZIP SHA-256 was
  `7e1944e79d673aaf5bc3405e1a20a49c9eaf61f3fa1e3b4fc8e4272c678f57a8`.

Only the reviewed JSON and this receipt are proposed for publication. No remote
CI, main-branch integration, canonical approval or end-product qualification is
claimed by these local results.
