# Measurement, reference and timing application replay

This successor pins 16 batches, 27 batch-local source scopes and 184 annotations.
It includes 230 base cases plus six unchanged disposition cases.

This successor extends the independently reviewed signal/logic snapshot with the
INA219AIDCNR, TL431CDBZR and NE555DR application lanes. It preserves all prior
batch bytes, historical 100/125/148/162 manifests and receipts, the original owner
acceptance, and the MCP23017 disposition. MCP6002 was already integrated with its
exact reviewed handoff bytes in the preceding stage; it is not recollected here.

## Reproduce the bounded candidate checks

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-measurement-timing.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The successor retains earlier case definitions and expected selections where
unchanged. New selections are specified from reviewed source/parameter recipes
and frozen input records, never captured blindly from CLI output. The evaluator
compares complete candidate payloads with independent pinned-input projections:
identity, conditions, units, warnings, provenance, acceptance, evidence limitations,
noncanonical status and NOT_LOCALLY_VERIFIED remain intact. The separate six-case
MCP23017 disposition replay remains unchanged. Counts or matching IDs alone cannot
pass; changed dataset sets or bytes fail closed.

## Application questions and evidence boundaries

- INA219: distinguish raw signed shunt codes, bus data/status bits and calibrated
  current/power values. Register configuration and calibration do not establish
  shunt accuracy, analog headroom or a fresh measurement. Preserve A-grade scope,
  conversion-mode assumptions and unresolved source wording about CNVR clearing.
- TL431: preserve the reference-input-current term and the source's differing
  formula signs as an unresolved source-wording warning. The scoped DBZ stability
  plots are typical conditional observations, not measured universal capacitor
  boundaries or a complete feedback-loop stability certificate. Actual supply,
  load, divider, capacitance and thermal inputs remain unknown.
- NE555: distinguish monostable trigger/reset conditions from standard astable
  charge/discharge paths and the source duty convention. Nominal RC equations and
  specified timing tests do not guarantee arbitrary components, temperature,
  startup state, load or alternate topology.

Exact source/device/package and semantic negatives prevent adjacent variant,
grade and topology transfer. An empty query result is not permission and does not
prove that a source lacks a specification. Same-source, same-batch warnings remain
attached to every matching fact and independently available with `intake issues`.

## Independent review and synthetic corruption checks

Each new pair records a different Agent's inspection of actual source bytes,
rendered tables/circuits/plots and the complete final metadata. Source publication
dates and packaging-addendum dates remain separate. No precise bbox, human review,
newest-revision guarantee or hardware test is claimed. Original documents, renders
and extracted pages are excluded from Git, handoffs and packages.

`test_measurement_timing_replay.py` uses invented symbolic data to detect signed-code
and status-bit confusion, removed calibration dependency, ACK-to-freshness promotion,
wrong-grade transfer, dropped reference-current or cathode-budget conditions,
typical-curve-to-guarantee promotion, full-loop stability inference, wrong duty
convention, RC-to-guarantee promotion, changed trigger condition, invented startup
behavior and lost source warnings even when selected IDs remain unchanged.

Full Config/Build/Test, guards/validation, metadata-only package inspection and
exact-commit CI are separate publication gates; retrieval is not electrical reasoning.

## Local publication receipt (2026-10-28)

- Final replay: 236/236 full CLI cases passed (230 successor + 6 unchanged
  disposition cases), 184 annotations; all 39 historical pinned files unchanged.
- Config, Build (280 tests), Test (280 tests), Agent validate, English/public-source/
  PDF.js guards and workspace validation passed. Focused successor tests: 4/4.
- Metadata-only package `PcbKnowledge_c56bc0d8393529b5.zip` has 22 members: 16
  intake batches, one disposition, workspace metadata, three schemas and manifest.
  Every packaged intake/disposition byte matches its reviewed working-tree input;
  no original PDF, image or extracted text is included. Package SHA-256:
  `bfc5dfc6678160c93f5241855c3fe05964bf7b7ab1426878bad65b5363f86d11`.
- Exact published-commit CI is reported separately in the issue handoffs; this
  local receipt does not claim a CI result before publication.
