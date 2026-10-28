# Si2342DS low-voltage gate-drive constraints

Six small original factual annotations describe **Vishay Siliconix
Si2342DS-T1-GE3, SOT-23 (TO-236)**. This is a noncanonical exact-device intake,
not a generic SOT-23 substitution rule or approval of an AO3400A replacement.

## Source receipt and processing limits

- Official source: https://www.vishay.com/docs/63302/si2342ds.pdf
- Electrical document 63302, **S11-1388-Rev. A, 11-Jul-11**.
- Actual source SHA-256:
  `eba3913f3b9856077dd8ba9b1e81d691fbe958c759075b89ff7fcb605f0e0a03`.
- **208,998 bytes; nine PDF pages**, accessed 2026-10-28.
- Electrical pages 1–6 carry the 2011 revision; PDF page 9 is separate legal
  document 91000 dated 01-Jan-2026, not a newer electrical revision.
- Collector: `agent:/root/continue_pcbknowledge_iteration/collect_low_voltage_mosfet`.
- Collector inspected extracted source text and rendered pages 1 and 2.
  No measured bounding boxes or whole-document visual review are claimed.
- Poppler reported `xref num 103 not found but needed, try to reconstruct`.
  Extraction/rendering succeeded with reconstruction in memory; unchanged
  bytes were hashed and cited pages were legible. This is not clean-container
  validation. The source-processing warning remains explicit in the intake.

The separate legal notice reserves rights, grants no IP license and requires
application validation. No explicit prohibition on these small original factual
annotations was identified; this is not an assertion of an open license or
canonical redistribution clearance. Under ADR-021 only original annotations
and this receipt are delivered. Source PDF, text and renders stay outside Git;
no source table, prose section, artwork or whole document is redistributed.

## Engineering distinctions preserved

- Exact orderable and numbered top-view terminals do not define a complete CAD
  footprint or establish compatibility with another manufacturer's SOT-23.
- The 8-V drain-source and ±5-V gate-source ratings are absolute stress limits,
  not operating recommendations. A hypothetical 12-V drain-source exposure
  exceeds that stress limit; low gate-drive capability cannot make it suitable.
- Threshold is tested at 250 µA and is not the resistance specification.
- Selected resistance conditions distinguish 1.8-V from 1.2-V gate drive,
  their different test currents, 25 °C junction temperature, and the pulse
  duration/duty limit. They do not establish hot continuous operation.
- Ambient transient thermal resistance, ambient steady-state resistance and
  drain-foot resistance have distinct reference points and durations. The
  reference FR4 board is not the user's unknown board.
- Selected gate charge belongs to 2.5-V gate drive and its stated drain voltage
  and current. It is design-guaranteed rather than production-tested; it is
  not a 1.8-V charge value or a qualified PWM frequency.

Three warnings retain unknown driver/load/waveform inputs, unknown actual
thermal implementation, and the PDF reconstruction limitation. No safe load,
frequency, overshoot margin, hot resistance or replacement approval is invented.

## Independent Agent review pending

A distinct reviewer must independently verify the same actual source bytes,
render and inspect cited pages, evaluate all six complete fact payloads and
three warnings, and check precise identity/revision boundaries. Acceptance is
Agent review under owner delegation only; `human_reviewed` and `canonical`
remain false. No earlier user review is attributed to this new intake.

Only this JSON/receipt pair is owned by this collection task. Aggregate eval,
shared documentation, main publication and CI belong to the parent integrator.

## Independent Agent review accepted (2026-10-28 UTC)

This section supersedes the historical pending-review request above. Reviewer:
`agent:/root/continue_pcbknowledge_iteration/collect_low_voltage_mosfet/review_si2342ds`.
Decision: `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`; authority: `OWNER_DELEGATION`.
`canonical: false` and `human_reviewed: false` remain unchanged.

I independently recomputed the stated source hash, 208,998-byte size and
nine-page count; independently rendered and visually inspected pages 1 and 2,
including row alignment and footnotes. I read legal page 9 text and electrical
revision footers on pages 3–6. I did not independently attest the original HTTP
transaction or perform all-page visual review. Poppler's xref-103 reconstruction
warning was reproduced and remains explicit. All six complete facts and three
warnings were checked; no factual corrections were required. Exact-device
identity, stress versus operation, threshold versus resistance, pulse/temperature
conditions, thermal reference/duration and charge test conditions were preserved.
No source table/artwork is included in this original annotation pair.

Review input JSON SHA-256:
`686df148a73bae539baf93115451483d8acc0e97b31240c26a18953e1d75e0e0`.
Accepted JSON SHA-256:
`7dee5cb9349c408a9dc01b39edd6b65bfe6f93f5429b17f13146dd0ae3b1664a`.

### Actual review validation

The reviewer reran the Agent intake CLI against the accepted pair and compared
all six returned fact payloads for exact equality, including every value,
condition and evidence field. Six parameter-plus-kind queries each returned
the intended complete payload. Six deliberately incorrect manufacturer,
device/suffix, package, legal-appendix revision and kind queries returned no
matches. The reviewer additionally asserted the 8-V stress limit, both selected
resistance rows, unknown hot resistance and unknown 1.8-V gate charge. Ordinary
retrieval remains `NOT_LOCALLY_VERIFIED`; an Agent receipt does not assert that
a consumer has the cached source bytes.

The local review script exited 0. `python3 configs/check_public_repo.py` and
`python3 configs/check_english_repo.py` both exited 0. No aggregate gate or CI
pass is claimed here; the changed batch set requires parent integration. This
review did not edit the existing AO3400A source, shared tests, manifests or docs,
and did not commit or push.
