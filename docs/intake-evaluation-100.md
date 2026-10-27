# 100-annotation retrieval evaluation receipt

Evaluated on 2026-10-27 against the executable contract at `8515bf5` and the five
curated JSON batches in this data stage. The 23 actual CLI queries below all exited
0 and their exact fact IDs matched the independent evaluation replay. This is a
retrieval receipt, not electrical approval, human review, remote-publication proof,
or a claim that lexical hits are correct answers.

## Reproducible dataset

- 5 batches, 15 manufacturer/device/package scopes, 100 unique fact IDs.
- 14 source hashes; 94 annotations carry byte-identity and prior visual-review
  markers. Six Nexperia observations are official-text-only; no local hash or visual
  verification is invented. The independent evaluator recomputed all 14 available
  external-cache hashes, without changing reader `NOT_LOCALLY_VERIFIED` output.
- No measured bounding boxes; no complete component model or whole-circuit safety
  claim. The initial three scopes still lack full orderable SKU resolution.
- No exact duplicate source/kind/parameter/value/unit/condition payloads; this does
  not establish absence of fuzzy duplicates or contradictions.

Dataset fingerprint: `5e57577aa9d724f5fb5acd4e7fa70db8dc1f613dcf0b841ec248cdf7abf4ef5c`.
It is SHA-256 of `json.dumps(path_to_sha256, sort_keys=True).encode("utf-8")`, with
relative `knowledge/intake/*.json` keys and SHA-256 values of exact file bytes.
Only processed annotations and receipts are versioned; no PDFs, rendered pages,
full extracted text, or private absolute source paths are distributed.

## CLI replay

Run `python3 configs/pcbknowledge_agent.py --repo . intake search "<query>"`.
The non-ASCII query is displayed as Unicode escapes to preserve the repository's
English-source policy; decode those escapes before replaying it.

| Literal lexical query | Hits |
| --- | ---: |
| `LD1117STR adjustment` | 1 |
| `LM1117 absolute` | 2 |
| `LM1117 recommended VIN` | 3 |
| `LD1117STR input_voltage` | 2 |
| `LM1117 VIN_to_GND` | 2 |
| `LM358 total_supply` | 2 |
| `MCP6002 supply_voltage` | 1 |
| `ADS1115 ADDR SDA` | 2 |
| `24LC256 SCL_clock` | 1 |
| `SN65HVD230 standby` | 2 |
| `74HC00 ambient` | 2 |
| `SN74HC00 temperature` | 4 |
| `LM358 supply voltage` | 0 |
| `LM358B` | 0 |
| `LM1117 \u8f93\u5165\u7535\u538b` | 0 |
| `LM1117 dropout` | 1 |
| `NE555 VCC` | 3 |
| `TL431 minimum_cathode` | 1 |
| `TPS62160 PG` | 2 |
| `INA219 VS` | 3 |
| `MCP23017 supply` | 1 |
| `MCP23017 AMBIGUITY` | 0 |
| `MCP23017 output_only` | 1 |

## Findings that must remain visible

Substring matching searches fact and source prose, not exact structured identity.
LM1117 queries can return an ST negative-comparison mention; recommended-voltage
queries can include stress or pin observations; SN74HC00 temperature can include
Nexperia. `LM358 supply voltage` returns zero despite related stored facts, while
`LM1117 dropout` returns a caveat rather than a quantified dropout answer.
`TPS62160 PG` also matches PGND. These are demonstrated limitations, not successful
semantic answers. No count or exit-code metric overrides them.

`MCP23017 AMBIGUITY` returns zero because current search does not inspect the batch
`source_issues` collection. `intake list` exposes the unresolved source-wording
conflict; absence from search is not resolution. No normalized supply-temperature
envelope was fabricated. Exact source/manufacturer/device/package and parameter
filters plus source-warning propagation are tracked in
[issue #12](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/12), separately
from canonical MPN identity (#10) and pinned-snapshot parity (#11).

Next useful expansion should address one actual design task and its missing
conditions/pin map, not merely increase counts. Preserve source-specific caveats,
unknowns, and review evidence; this collection cannot establish drop-in equivalence.
