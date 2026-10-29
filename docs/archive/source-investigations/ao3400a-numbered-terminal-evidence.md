# AO3400A numbered-terminal evidence investigation

## Result and scope

**Not established by the fixed official source set.** This bounded investigation
for [issue #27](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/27)
does not establish a numbered-terminal-to-function mapping. It does not resolve
`ao3400a-numbered-pin-identity-unknown`, change its history, or add an intake fact.
Unknown remains the appropriate result; completion of this investigation is not
completion of footprint, ordering-code, circuit, or procurement qualification.

Author: Agent `investigate_ao_terminals`, under owner delegation.
Inspection date: 2026-10-28 UTC. Independent review is recorded in the issue
handoff against the final document hash; this document is not human approval.

## Fixed source set and actual-byte receipt

The [official AO3400A product page](https://www.aosmd.com/products/mosfets/low-voltage-mosfets-12v-30v/ao3400a)
was retrieved at `2026-10-28T06:32:17.974013Z`: 132025 HTML bytes,
SHA-256 `7c73c9a32e879e52a201041004ea0531c6ca2e49fb4916f9cba5632fd7790204`.
Its actual HTML links to the following three PDFs. Other product-page links were
not followed. Each requested PDF URL was also its final response URL.

| Source and official URL | Visible revision | Retrieved UTC | Actual bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| [AO3400A datasheet](https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf) | Rev 3.1, July 2023 | 2026-10-28T06:32:34.206285Z | 317848 | `9c60d0b6c1ddc7609a4b788a91181468d8ffe6c3e9ba425c3d8ffc5ba88c5033` |
| [SOT23 package drawing](https://www.aosmd.com/sites/default/files/res/package/SOT23.pdf) | PO-00001, N; visible revision date not stated | 2026-10-28T06:32:36.681097Z | 276341 | `b6fac64d55f133ce74dd85ddddc618c3d5408e9531cb21e660f6a8ef3d8c5408` |
| [AO3400A marking description](https://www.aosmd.com/sites/default/files/res/markings/AO3400A.pdf) | PD-00659, C; visible revision date not stated | 2026-10-28T06:32:39.089910Z | 142348 | `1509889690255bbb7e1a88d3aeb722672bd5f9b4d9194688f0e55283e633fa19` |

Hashes and byte counts were computed from downloaded bytes, not inferred from
URLs. The newly linked datasheet has the same bytes as the historical source
`ao3400a-aos-r3p1-sot23`, despite its different URL path. This does not rewrite
that historical receipt or assert that a URL will always serve these bytes.

Each PDF is retained only in the ignored local cache at
`.pcbknowledge/evidence/sha256/<first-two-hash-characters>/<sha256>.pdf`.
Public availability is `PUBLIC_REFERENCE`, not `OPEN_LICENSE`. Processing here
is limited to this small original metadata/interpretation note under
[ADR-021](../../adr/ADR-021-lightweight-curation-local-evidence.md); no originals,
extracted pages, or rendered images are published.

## Inspected anchors and orientation

The author ran `pdftotext -layout` on each actual PDF and rendered PDF page 1 of
each with `pdftoppm -f 1 -singlefile -r 140 -png`; all six commands exited 0.
The three rendered pages were opened and visually inspected. Fontconfig emitted
cache-directory warnings, but the rendered views were legible. This is a
page-specific visual receipt, not a claim of rendering every datasheet page.

| Actual source anchor | Explicit evidence | Orientation and remaining limitation |
| --- | --- | --- |
| Datasheet, PDF page 1 / printed page 1 of 5, SOT23 package illustrations and separate transistor symbol | Package illustrations label G, S and D; the separate symbol also labels functions. No terminal numbers accompany these illustrations. | The package illustrations explicitly distinguish top and bottom views. D is the lone lead; G/S appear on the paired-lead side and reverse visually between the two views. The top-view dot is not explicitly assigned a terminal number. Neither dot nor geometric position supplies a number. |
| Package drawing, PDF page 1 / unnumbered printed sheet, PO-00001 N; plan/section views and recommended land pattern | Mechanical outline, dimensions and pad geometry; no numbered-function table or G/S/D terminal labels. | The plan view has a lone lead above a paired-lead side, but no explicit top/bottom caption identifies a terminal-number view. Section views show mechanical planes. Dimension letters are not transistor functions; in particular dimension D is not drain evidence. The land pattern has no numbered/function assignment. |
| Marking description, PDF page 1 / unnumbered printed sheet, PD-00659 C; marked-face illustration and code table | Marking fields and part-code table, not terminal numbers or functions. | The marked-face illustration has a lone lead above a paired-lead side, without an explicit top/bottom caption or numeric pin orientation. The table includes both AO3400A and AO3400AL with the same part code, so that code alone is not unique full-device identification. No substitute-variant mapping is imported. |

## Explicit mapping versus derived correspondence

There is **no explicit numbered-terminal mapping established** by these inspected
anchors. The datasheet supports function labels in its own stated views. A
geometric comparison might align the lone lead across drawings, but that is a
derived correspondence, not an official numbered mapping. None of these anchors
provides the missing numeric identifiers needed to complete the chain. Mirroring
between top and bottom views adds a further reason not to invent a numeric
assignment from appearance. A generic SOT23 convention, CAD symbol, third-party
source, or related device is not evidence for this source-scoped question.

A future resolution would need source-scoped evidence explicitly connecting
terminal numbers to functions and defining the viewing orientation for the exact
device/package, followed by independent review. This note neither searches beyond
the fixed set nor authorizes an annotation change on that hypothetical basis.

## Preserved boundaries and review handoff

The existing AO3400A batch, numbered-pin warning, review history, frozen practical
report, evaluation manifests and all other knowledge remain unchanged. Locally
checking these source bytes does not promote historical retrieval receipts:
noncanonical retrieval remains `canonical: false`, `human_reviewed: false`, and
any existing `NOT_LOCALLY_VERIFIED` label remains unchanged. This note is not a
replacement retrieval receipt, canonical Fact, or new human acceptance.

Independent reviewer: `agent:/root/prepare_pcb_application_evidence_docs/review_application_evidence_docs`,
reviewed 2026-10-28 at 06:37 UTC. Independently recomputed the three PDF byte
counts and SHA-256 hashes, checked page counts (5, 1, 1), inspected the actual
product HTML links, and opened all three page-1 rendered anchors. The stated
orientation limitations and distinction between function labels and numeric
identifiers are supported. The reviewer accepts the bounded not-established
result; no numbered mapping or warning resolution is approved. Only the cited
page-1 anchors were visually reviewed, not all five datasheet pages. This is
agent documentation review, not human acceptance. The external issue handoff
records the final document SHA-256 and publication commit, avoiding a
self-referential document hash.
