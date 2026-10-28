# Human owner content acceptance: existing 100 annotations

## Decision and actors

- **Acceptance date:** 2026-10-28 (UTC).
- **Decision:** human owner batch-level content acceptance of the existing five
  curated intake batches, scoped to the immutable snapshot below.
- **Reviewer / decision-maker:** `HUMAN`, the repository owner who instructed the
  assistant in conversation. No personal name, account identity, or signature is
  inferred or claimed.
- **Recorder:** `AGENT`, Ethan (the assistant), recording the owner's expressed
  decision rather than making a human review decision on the owner's behalf.
- **Basis:** the owner's direct instruction on that date. Faithful English
  paraphrase: "I have broadly reviewed the knowledge above and found no problems;
  please record acceptance of that review. Going forward, you and the external
  team you direct through issues should continue expanding it according to your
  plan."

The owner accepted the existing content as a batch. The instruction does not state
that the owner individually checked every annotation, original PDF, source hash,
page rendering, or bounding box. This receipt records the expressed acceptance,
not a certificate, cryptographic signature, identity attestation, or engineering
safety certification. It does not retroactively identify the owner as the author
of earlier Agent evidence checks.

## Exact accepted snapshot

- Repository commit: [`9530c0d66d497e284a5887b37a5558d22aa8a9c0`](https://github.com/NorthBoundWisdom/PcbKnowledge/commit/9530c0d66d497e284a5887b37a5558d22aa8a9c0).
- Dataset: **5 batches, 15 source/device scopes, 100 unique annotation IDs**.
- Existing byte manifest: [`evals/intake-retrieval-100.json`](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/9530c0d66d497e284a5887b37a5558d22aa8a9c0/evals/intake-retrieval-100.json).
- Manifest file SHA-256:
  `d4a166b49de4f421a0e08fae2eb636d43a500e515ca1b2db8c9c6f36d9c934b4`.
- Dataset fingerprint:
  `5e57577aa9d724f5fb5acd4e7fa70db8dc1f613dcf0b841ec248cdf7abf4ef5c`.
  This is SHA-256 of `json.dumps(path_to_sha256, sort_keys=True).encode("utf-8")`
  using the manifest's `files` mapping; each mapped value hashes exact batch bytes.

| Pinned batch | Source/device scopes | Annotations | Exact file SHA-256 |
| --- | ---: | ---: | --- |
| [cross-manufacturer-pilot.json](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/9530c0d66d497e284a5887b37a5558d22aa8a9c0/knowledge/intake/cross-manufacturer-pilot.json) | 3 | 20 | `e13060b1ac0a2b03ee742bf06c6b019cd04f46e74974d7b087408bfd6442bc97` |
| [interface-ic-pilot.json](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/9530c0d66d497e284a5887b37a5558d22aa8a9c0/knowledge/intake/interface-ic-pilot.json) | 3 | 20 | `3738281495ba3e2fa1120e0f501239ab1608c6ce0781e7dc4b5c0f2b32b7ab55` |
| [power-monitor-gpio-pilot.json](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/9530c0d66d497e284a5887b37a5558d22aa8a9c0/knowledge/intake/power-monitor-gpio-pilot.json) | 3 | 20 | `32ac40f0a7e5e35e2840a032e2575394c1dc1e5ef26e1fbe3bacaa7133f02e2a` |
| [ti-three-ic-pilot.json](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/9530c0d66d497e284a5887b37a5558d22aa8a9c0/knowledge/intake/ti-three-ic-pilot.json) | 3 | 20 | `33de0de3404f1c81e540dab4dceb72ae1f14de242a1ec7fd9fac53a618a4be08` |
| [timer-reference-driver-pilot.json](https://github.com/NorthBoundWisdom/PcbKnowledge/blob/9530c0d66d497e284a5887b37a5558d22aa8a9c0/knowledge/intake/timer-reference-driver-pilot.json) | 3 | 20 | `e2539fa657705a79dc6245cedb1b98c1a2eb0237e865deb7afa064a5167fe695` |

The linked retrieval manifest identifies the accepted dataset; the owner's
instruction is not a claim that the owner ran or reviewed every evaluation case.
The existing [retrieval evaluation](intake-evaluation-100.md) is a separate Agent
verification receipt. Future records or changed bytes are not covered by this
acceptance merely because they use the same paths or identifiers.

## Evidence limits of the accepted snapshot

These statements describe the accepted snapshot at the decision date. Any later
resolution needs a separate evidence-backed change; it does not rewrite this
receipt or retroactively strengthen that snapshot.

- All accepted annotations remain **noncanonical** (`canonical: false`). No
  canonical `Source`, `Entity`, or `Fact` approval/publication is performed here.
  The formal typed/visual pilot remains open.
- The prior Agent receipts cover byte-identified and rendered-page checks for 94
  annotations. The six Nexperia observations remain official-web-text-only:
  direct PDF acquisition returned HTTP 403, source hash and byte size remain
  null, and visual review remains false. This receipt neither retries nor
  bypasses that restriction and adds no new source verification.
- No precise bounding boxes have been annotated. The initial TI batch's full
  orderable identities remain unresolved. Complete pinouts, procurement fitness,
  thermal design, cross-vendor substitutability, latest-revision guarantees and
  whole-circuit safety have not been established.
- `MCP23017-SUPPLY-TEMPERATURE-AMBIGUITY` remains
  `UNRESOLVED_SOURCE_WORDING`. Acceptance of its unrelated pin annotations does
  not resolve the cover/electrical-table discrepancy or establish a supply versus
  temperature envelope.
- Unknowns, conflicts, original conditions, license/redistribution limitations,
  and per-reader `NOT_LOCALLY_VERIFIED` remain unchanged. Original PDFs, rendered
  pages and full extracted text remain outside Git and packages.

## Recording policy and subsequent work

This is a separate, append-only documentary receipt. The five batch JSON files,
original `AGENT_REVIEWED_UNDER_OWNER_DELEGATION` statuses, Agent actor provenance,
`human_reviewed: false` fields and evidence receipts are intentionally unchanged.
Those fields continue to describe the earlier recorded checks; they are not
rewritten into an unsupported assertion that the owner individually verified each
source or fact. This receipt adds the later, narrower human content acceptance.

The intake reader's executable status contract does not support this scoped human
batch acceptance as a canonical or per-fact decision. Therefore no schema/status
extension, workbench human-decision API call, or alternate authority write path is
introduced. Readers and packages still expose the original noncanonical intake;
this Markdown receipt is not a machine-authority upgrade.

Preserve this receipt and its accepted snapshot. A correction, withdrawal, or
later acceptance should add a dated, explicitly linked successor receipt rather
than silently edit the original decision or extend it to new records. Continued
curation remains subject to [the lightweight contract](lightweight-knowledge.md)
and [the active application-question milestones](../TODO.md#next-application-question-milestones).
