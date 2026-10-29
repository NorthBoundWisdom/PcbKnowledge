# MH2029-601T application-card review

- Author: Agent `/root/document_ferrite_application_inputs`.
- Distinct reviewer: Agent `/root/document_ferrite_application_inputs/review_ferrite_card`.
- Reviewed at: 2026-10-29T01:27:08Z.
- Result: PASS for this bounded documentation handoff; no human or circuit approval.
- Card: [MH2029-601T rail-filter inputs](mh2029-rail-filter.md).
- Final card SHA-256: `9b3556b7352814b4c70296c36262ef2a8e9336ff80dd0da19e3b8baa05d4c953`.

## Independent evidence replay

I read the complete accepted source JSON and historical source review at pinned
technical commit `8d9e5b211e565067234e642d8f52309ac9bd07fb`, then independently
executed all five literal recipes in the card in clean detached checkouts of
that commit and drafting base `cfc4737c8a5be6a1a83903807adbd80d9286146f`.
Every command exited zero. Each command's UTF-8 SHA-256 (without newline) and
complete stdout SHA-256 (including newline) matched the card on both snapshots.

Source JSON SHA-256 on both:
`775888fa8e72583c65aa350d63ded06002a7142246db64ff92d976f7c936137b`.
The recorded PDF SHA-256 is
`359f5ab799d0f9d03b15a0b886e6b29818ee134304c104cebd79db1aeb5041c9`;
this is existing provenance, not a new byte audit.

The five selected facts are `mh2029-ferrite-01` through `mh2029-ferrite-05`.
I compared complete fact objects, source metadata, evidence and attached warnings
to the pinned JSON, not counts or lexical matches. CLI warning ordering is by
ID; comparison retained complete payloads after that ordering. The separate
issues output matches all three complete source issues and their provenance.
Search stdout SHA-256 is
`fc2d2282f811d6ee07954d6488e0b294732e9d4ed1f8fadcc1a8270f6a660bbb`;
issues stdout SHA-256 is
`5aa7ad2a041df2a4a3e56dbf243c447552e3d6abf0bb0d8fa5595f7bdbf20946`.

The three source-conjoined negatives are justified by structured identity:
MH2029-601T is not MH2029-601Y, Bourns is not Vishay, and the exact nominal SMD
package string is not 0603. All returned `[]` plus newline, SHA-256
`37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
They demonstrate scoped absence only, not compatibility, incompatibility or safety.

## Content findings and limits

I inspected the complete blank card and single synthetic case. All invented
application numbers are labeled synthetic. The five conditioned interpretations
preserve RF magnitude versus DCR, unknown amplitude convention/bias, 25 C DCR
limits, the current rating's 40 C rise basis, unknown hot-current mounting and
qualitative Z/R/X scope. Body dimensions are not promoted to a footprint.
All three warnings are complete with their status and provenance. No insertion
loss, dissipation, permitted voltage drop, approved current, circuit stability,
lifecycle or certification conclusion is derived. No correction was required.

Retrieval remains `canonical: false`, `human_reviewed: false` and
`NOT_LOCALLY_VERIFIED`. I did not retrieve or visually inspect a PDF, certify a
board, run the publisher's full repository gates, or perform maintainer acceptance.
Final latest-head reconciliation, package checks, nonforce publication and exact
terminal CI are the publisher's separate receipts. This review covers the hashed
card, not future edits.
