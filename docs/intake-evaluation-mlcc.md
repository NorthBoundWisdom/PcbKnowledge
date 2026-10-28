# Exact reviewed MLCC handoff integration

This bounded successor adds eight KEMET C0603C104K5RACTU annotations and three
application unknowns from immutable `890c9b92cc88d80695cd0bfd4081104a91b698f4`.
Only its two metadata files are applied to the current main; its old base tree is
not restored. Both supplied hashes remain exact. Source evidence was already
independently reviewed; this integration does not recollect or claim a new PDF
inspection. Canonical approval, per-fact human approval and circuit qualification
remain false. The later Bourns handoff is not included in this bounded successor.

## Reproducible retrieval

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-mlcc.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_mlcc_replay -v
```

The 464 preceding recipes and all prior file pins are unchanged. Forty-six new
recipes explicitly select all eight facts, both source-scoped fact/warning sets,
and two bounded warning queries. Thirty-two exact-filter exclusions cover wrong
manufacturer (including publisher confusion), suffix, package and unsupported
qualification kinds/parameters. Expected IDs are specified from reviewed inputs,
not regenerated from CLI outputs. Complete payload comparison retains conditions,
source warnings, evidence, provenance, acceptance and `NOT_LOCALLY_VERIFIED`.
An empty result is not electrical permission or proof of no uncertainty.

Nominal test capacitance is not effective in-circuit capacitance. The short
withstand test is not continuous operation; zero-bias temperature and decade-hour
aging are not a combined operating envelope. Typical qualitative simulation has
no guaranteed minimum or digitized replacement limit. Body dimensions are not
selected copper pads. The family land-pattern record retains its own PCB warning;
the exact-part records retain their effective-capacitance/procurement warnings.
The unchanged lexical policy searches serialized prose, including provenance:
a term in a collector identity can match without constituting a technical answer.

Independent integration review checks the exact pair, complete retrieved objects,
new selections/exclusions, semantic mutation coverage and metadata-only package.
The synthetic tests use invented values, not copied source fixtures. Twenty-three
equal-ID/count mutations must fail for dropped conditions, unsupported guarantees,
changed time bases, promoted simulations/footprints and removed unknowns.
The historical 250 snapshot and all earlier intake/evaluation/owner/disposition
receipts remain byte-identical. Both CI jobs select this successor and the same
six-case MCP23017 disposition; the manufacturer conflict is not relabeled resolved.

## Verification receipt

Local Config, Build and Test PASS; Build and Test each ran 320 tests with no
skips. English/public-source/PDF.js guards, workspace and Agent validation,
local Markdown targets and whitespace checks PASS. Aggregate replay is 516/516
PASS: 510 successor cases and six unchanged disposition cases, covering 26
batches / 38 source scopes / 258 annotations. Independent review exercised 27
real CLI checks, inspected all 46 new recipes, and passed the three synthetic /
integration tests including 23 mutation rejections.

All 70 protected historical files match the prior 250-stage bytes. Reconciliation
also preserves the practical-task evaluation documents and exact TODO section
from `b04fed50dff7853d5ad2663784eb0305bb02f331`.

The metadata-only package is `build/package/PcbKnowledge_c188402dd9492564.zip`.
Independent package review verified all 32 members (26 batches, one disposition,
workspace, three schemas and derived manifest); all 31 input hashes, sizes and
bytes match. No source originals are included. Exact published commit and terminal remote CI
are reported separately in the issue delivery, not inferred from local checks.

| Item | SHA-256 |
| --- | --- |
| Exact handoff JSON | `e4cb0113234ed90ed6f9ef7e2c32cad842d6f9b7648ac017b16b2cbbe9903a1b` |
| Exact handoff review | `da3bb353c8452ebedc0f7629452cd98d0d09e6a9b2db986e8efacec027f626b4` |
| Successor manifest | `bf86efdd08c7b2c6734ee5dd885d8a16cbfeb81520b3ef1f7746b377ddb1d8d2` |
| Intake dataset | `cddbeca5149203d3e1f2ef153acb11fde0fd840a0bd6deddb892573a06ed2ce0` |
| Disposition manifest | `ce8007f9dbe35f07281ddd232d426b25003d31b38f54ee89e301775c93f48ce5` |
| Disposition data | `16749c32bfcf13febb41be8d37bb5aa6664d92fbbb75025ce26e02465922fa5f` |
| Package ZIP | `fe3f065e13892e62ff9f1299be97cffa286a93a17447e7797f2554d41ee78a41` |
