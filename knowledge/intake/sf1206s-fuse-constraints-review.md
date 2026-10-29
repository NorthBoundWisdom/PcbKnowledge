# SF-1206S050-2 fuse condition review

Six small original annotations address exact Bourns SF-1206S050-2, not the
related -W, -M or -R families. Three warnings keep application gaps explicit.

## Source and access

- Official current product page: https://www.bourns.com/products/circuit-protection/product-detail/singlfusethinfilmchipfuses/sf1206sseries
- Its actual linked PDF: https://www.bourns.com/docs/product-datasheets/sf-1206s04ec4f2c90e165f58a72ff000066632f.pdf
- Download returned HTTP 200, 215,457 bytes and five pages. SHA-256:
  `c3f0ce8a2261275ec124d674df021da3998f1ab2a28a1b7830e7dd87a2ca6086`. Electrical revision is `REV. 10/26` on PDF page 4.
- Collector `agent:/root/finish_bpw34_stage/curate_ferrite_conditions` read the current legal disclaimer first and inspected the
  embedded legal page 5 (`K2540 08/26R`) before preparing factual annotations.
  No explicit prohibition of these limited original factual annotations was
  identified; no open license or source redistribution is claimed.
- Current linked document supersedes the search-discovered `sf-1206s.pdf`
  document, which returned electrical `REV. J 04/21`; old bytes are not used
  as evidence in this batch.
- Collector inspected actual rendered pages 1-5. Pages have no printed page
  numbers, so physical PDF ordinals are used. Raw PDFs, text and page images
  remain local and untracked. No vendor table, drawing or prose is reproduced.

## Essential distinctions

Exact current/voltage/interrupt values are separate categories. Conditioned
typical resistance retains its tolerance and low-current measurement footnote.
The 25 C series clearing specification and separate reliability fusing criterion
are preserved independently: different conditions are not automatically a
contradiction, nor do they justify a universal replacement guarantee.

Melting I2t is typical and calculated at ten times rated current. Average
pre-arcing/I2t curves do not establish total clearing energy or repeated-pulse
endurance. The thermal derating graph is present, but no points or tolerance
bands are fabricated. Fault coordination, actual heat rise and safety approval
remain unestablished.

## Independent review

Draft JSON SHA-256: `41cc936906f97f2f42ed73faefe5b8519f9422859a7c2b097b6dac03c1580a43`.

Independent reviewer `agent:/root/finish_bpw34_stage/curate_ferrite_conditions/review_fuse_source` accepted at `2026-10-29T01:15:05.295392+00:00` after independently recomputing
the actual PDF hash and 215,457-byte count, verifying five pages, and inspecting
all rendered pages including the legal notice. The saved official product-page
HTML links the exact source URL. All six full facts and three warnings were
reviewed. No numeric or test-condition corrections were required. One wording
correction replaced a blanket assertion that other families are not substitutes
with the narrower statement that this evidence does not establish substitution.

Final accepted JSON SHA-256: `51516aa7067cd9e06867f423378aaeaae8e7363e446d48bfda040d7999eab3dc`.

Acceptance is Agent review under owner delegation, not human, canonical or
circuit approval. Full integration and exact published-commit CI remain separate.
