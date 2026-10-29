# Reset, RS-485 and discrete application replay

This coherent successor adds two independently collected issue lanes and two
immutable maintainer content handoffs. The historical measurement/timing
operational manifest, all earlier manifests and receipts, original owner
acceptance, existing intake bytes and MCP23017 disposition remain unchanged.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-reset-rs485-discretes.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The first 230 case definitions, expected selections and byte pins are preserved
from the previous operational successor. New exact source/parameter lookups,
complete source-warning queries and reviewed identity/semantic exclusions come
from the frozen input records and collection receipts, not captured search
outputs. Complete candidate objects retain identity, conditions, units, source
warnings, evidence/provenance, noncanonical status and NOT_LOCALLY_VERIFIED.
Counts or IDs alone cannot pass. Retrieval does not certify electrical suitability.

## Source boundaries

- TPS3808G33DBVR: the fixed G33 sense trip point is distinct from a nominal rail,
  stress limit or VDD supply. Reset release requires the recorded SENSE/MR/delay
  qualifiers. CT modes, low-supply output validity and receiver/pull-up domains
  remain conditional; missing board inputs are warnings, not assumed safe values.
- SN65HVD75DR: RS-485 common-mode, differential/failsafe and HVD75-specific timing
  rows retain their source test circuits and loads. Propagation, enable/disable
  and standby times are different quantities. Component ESD ratings do not
  establish system compliance, galvanic isolation or firmware arbitration.
- AO3400A: exact eight-record pair from `929c8f49b4e83134ff6a48764c90b07b9a7228d4`.
  Threshold is not full enhancement, and short-duration thermal/current context
  is not a continuous user-board rating. Numerical pin/orderable unknowns remain.
- Vishay SS14: exact seven-record pair from
  `c4d7c84b7860185e26ade55939dbfb477b8381ab`. Lead-temperature current conditions,
  nonrepetitive surge waveform and pulsed forward-voltage/leakage conditions
  remain explicit. No generic SS14 interchangeability or orderable is invented.

The two ready handoffs are integrated only as their exact JSON/review file deltas,
not by replacing newer code with their older base trees. Their original review
receipts remain byte-identical; this integration does not imply a new human or
canonical acceptance. Maintainer TVS/tool development is a separate lane and is
not claimed here. Manufacturer originals and rendered pages are not public data.

Synthetic tests use invented specifications, preserving equal IDs/counts while
mutating reset qualifiers, timing loads, stress/operating distinctions, failsafe
conditions, thermal/waveform assumptions and unknowns. The evaluator must reject
these changed payloads. These tests protect representation, not electrical truth.

## Executed validation receipt (2026-10-28)

- Collection: 20 batches, 31 batch-local source scopes, 216 annotations.
- Successor replay: PASS, 338 base cases plus six unchanged disposition cases
  (344 total); dataset SHA-256
  `43d2875e3039e9960cb57c07dd4b7e55b26e884bedef6af03b9091d4788c17cb`.
- Successor manifest SHA-256:
  `b42263d422cb1eb6b83ec616310cb8900a2d565e9706ad5db7aceb63202cf2e6`.
- Distinct reviewer: 15 reset and 16 RS-485 complete-payload checks, then all
  32 new parameter selections and six new synthetic/manifest tests passed.
- Config, Build and Test passed. Build/Test each ran 287 tests, no skips.
  The added semantic suite rejects 33 equal-ID/count payload corruptions.
- English/public-boundary/PDF.js guards, workspace validation, Agent metadata
  validation and diff whitespace checks passed. All 44 previously pinned
  historical intake, evaluation, disposition and owner-receipt files are unchanged.
- Package passed: 26 metadata-only members, exact intake/disposition bytes,
  no originals or rendered pages. ZIP SHA-256:
  `f49f88ec1efba26965a4c17a71e5520935ba0d509bc64383ce2ae510575b7b80`.

Local validation does not claim remote CI. Exact published commit and terminal
cross-platform CI results are reported in issues #22 and #23 after publication.
