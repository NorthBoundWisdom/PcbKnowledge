# 100-annotation retrieval evaluations

## Historical structured-retrieval replay (2026-10-28)

This manifest remains pinned to the original five-batch snapshot. The current
expanded collection uses the [signal/logic aggregate replay](intake-evaluation-signal-logic.md).
Running the old manifest against the expanded checkout intentionally fails the
batch-set gate; use the original snapshot for this historical replay. Its pins and
owner-acceptance coverage have not been rewritten.

The original 100 annotations are unchanged. A reviewed, pinned
18-case manifest (`evals/intake-retrieval-100.json` at tag `intake-final`) now replays actual Agent CLI
commands, rather than leaving the retrieval observations as a prose-only receipt:

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . --cases evals/intake-retrieval-100.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The later [MCP23017 handling supplement](../receipts/mcp23017-source-disposition-2026-10-28.md)
adds separately pinned receipt metadata and six cases; the original 18-case
manifest and five batch pins are unchanged. The current command runs 24 cases.
Without supplements, the original command needs no `--dispositions`; when any
supplement exists, omitting its explicit pins fails closed.

The evaluator checks the exact ordered `batch-path#record-id` selections and the
complete original source/fact/warning projections, including all conditions,
evidence metadata, acceptance, `canonical: false`, and `NOT_LOCALLY_VERIFIED`.
Expected selections were chosen from the stored annotations and documented issue
acceptance criteria, not captured automatically from search output. Preservation
expectations come directly from the pinned inputs, independently of search code.
Synthetic evaluator tests deliberately corrupt source selection, omit warnings,
drop conditions/provenance, forge verification, and reorder/add/remove candidates;
each must fail rather than pass on matching counts or IDs alone.

| Task or hazard | Expected result |
| --- | --- |
| Unfiltered `LM1117 absolute` | Both the ST negative mention and TI stress candidate remain visible as a lexical limitation |
| Source `ti-lm1117-q` + `absolute`, or TI manufacturer + `LM1117 absolute` | Only `ti-lm1117-q-04` |
| Device `LM1117` + kind `recommended_operating` + parameter `VIN_to_GND` | Only `ti-lm1117-q-05`; no pin or stress candidate |
| Source `ti-sn74hc00-h` + `temperature` | Three TI candidates; temperature remains a condition, not a new specification |
| Device `LD1117STR` + parameter `input_voltage` | Both `b002-st-ld1117-r38-05/06`, with distinct original conditions intact |
| Unfiltered `TPS62160 PG` versus exact parameter `PG` | Two lexical candidates versus only `b005-ti-tps62160-06`; its switched-off condition remains intact |
| Exact `TPS62160DSGR`, structured package, and `PG` | One candidate; the shortened `TPS62160` device filter returns none |
| Package `DCY` on initial TI source, unknown `LM358B`, lowercase `lm1117` | No match; no identity inference or normalization |
| `MCP23017 supply` | Supply-pin candidate with the full same-source unresolved warning |
| `MCP23017 AMBIGUITY` | No fact candidate; one separate `SOURCE_ISSUE` through `intake issues` |
| Filter-only source-warning lookup | MCP23017 warning is discoverable; TPS62160 does not inherit it |

The command emits a deterministic JSON receipt with dataset/manifest fingerprints,
per-case results, and a nonzero exit for any mismatch. Empty case sets, changed
batch sets/bytes, absent expected IDs, CLI errors/timeouts and changes during replay
cannot produce a pass. CI runs the replay on the existing OS/Python matrix. A future
curation change must explicitly review the cases and update the byte pins; do not
blindly regenerate expectations to make a failure green. This is a bounded
retrieval regression set, not a general precision/recall benchmark or an answer
engine. No originals are opened, downloaded, packaged, or newly verified.

## Historical lexical baseline (2026-10-27)

Evaluated on 2026-10-27 against the executable contract at `8515bf5` and the five
curated JSON batches in this data stage. The 23 actual CLI queries below all exited
0 and their exact fact IDs matched the independent evaluation replay. This is a
retrieval receipt, not electrical approval, human review, remote-publication proof,
or a claim that lexical hits are correct answers.

### Reproducible dataset

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

### CLI replay

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

### Findings that must remain visible

Substring matching searches fact and source prose, not exact structured identity.
LM1117 queries can return an ST negative-comparison mention; recommended-voltage
queries can include stress or pin observations; SN74HC00 temperature can include
Nexperia. `LM358 supply voltage` returns zero despite related stored facts, while
`LM1117 dropout` returns a caveat rather than a quantified dropout answer.
`TPS62160 PG` also matches PGND. These are demonstrated limitations, not successful
semantic answers. No count or exit-code metric overrides them.

At this historical baseline, `MCP23017 AMBIGUITY` returned zero because search did
not inspect the batch `source_issues` collection. `intake list` exposed the unresolved
source-wording conflict; absence from search was not resolution. No normalized
supply-temperature envelope was fabricated. Structured filters and separate warning
retrieval were subsequently implemented in `f79ed20` and independently accepted in
[issue #12](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/12). The current
replay above covers that improvement without pretending the unfiltered lexical
limitations disappeared. Canonical MPN identity (#10) and pinned-snapshot parity
(#11) have separate synthetic acceptance suites; intake replay does not attest to
canonical identity or a formal publication pilot.

Next useful expansion should address one actual design task and its missing
conditions/pin map, not merely increase counts. Preserve source-specific caveats,
unknowns, and review evidence; this collection cannot establish drop-in equivalence.
