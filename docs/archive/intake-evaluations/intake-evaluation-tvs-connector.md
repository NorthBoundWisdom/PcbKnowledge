# TVS and connector immutable-handoff integration

This successor applies only the two accepted metadata pairs from immutable
`c380f458e1eb4c24a11e1501d7df7b3318611d2f` (Vishay SMBJ5.0A) and
`e05013d478b63e43e97ceccf7044803a97c9334a` (Wurth 61300211121).
All four file SHA-256 values are executable pins in
`tests/git_native/test_tvs_connector_replay.py`. No source recollection, original
upload, new human acceptance or canonical approval is implied.

## Replay

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-tvs-connector.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The previous 338 recipes and all previous file pins remain exactly unchanged in
this successor. Its 54 additional cases select each of the twelve parameters,
all four batch-local warnings, and explicit source/device/package/kind/parameter
exclusions. Expected IDs come from the reviewed inputs, not captured CLI outputs.
The evaluator independently compares complete candidate payloads, including
conditions, units, provenance, source warnings and nonverification markers.
Negative matches do not prove safety, compatibility or absence of source warnings.
The old 216-record manifest and receipt remain historical, not overwritten.

## Semantics retained

- TVS stand-off, breakdown test and clamp-at-peak-current are separate quantities.
  The pulse waveform, half-current duration, temperature reference, nonrepetitive
  note and typical/SOA distinctions remain explicit. Neither peak power nor ideal
  heatsink power authorizes arbitrary DC faults. Marking alone does not prove
  polarity; full orderable, thermal path, system limits and fault inputs remain
  unknown. No numerical capacitance, response-time or end-product guarantee is
  inferred. Different rating references are not declared a vendor contradiction.
- Connector exact article identity and explicit dimensions do not yield a complete
  footprint, board side, pin map, mating part or electrical polarity. Working
  voltage is not the one-minute withstand voltage; unspecified current test
  temperature and application thermal conditions remain unknown. Source rights
  restrictions remain recorded; no drawing, CAD file or source original ships.

The original accepted pair receipts preserve their collector/reviewer provenance.
The integration reviewer checks unchanged metadata and retrieval; this is not a
new claim to have fetched or visually inspected manufacturer originals.
Synthetic tests use invented devices/values and reject 22 equal-ID/count payload
corruptions, including pulse-to-DC, typical-to-guaranteed, inferred geometry,
withstand-to-working and dropped-warning promotion. They test preservation, not
an electrical reasoning engine.

## Validation

Executed locally on the final code/data tree:

- Config, Build and Test: PASS; Build and Test each ran 290 tests, zero skips.
- English/public-source/PDF.js guards, workspace and Agent validation, and diff
  whitespace checks: PASS.
- Aggregate replay: 398/398 PASS (392 successor cases plus six unchanged
  disposition cases); 22 batches, 33 source scopes and 228 annotations.
- Independent integration review: 40 real CLI complete-payload checks PASS;
  three new tests PASS, including 22 equal-identity semantic mutations rejected.
  The 338 previous recipes/pins and 56 protected historical files are unchanged.
- Package: `build/package/PcbKnowledge_1105d7871a2491ab.zip`, metadata-only;
  no source originals, drawings or CAD files included.

Reproducibility SHA-256 values:

| Item | SHA-256 |
| --- | --- |
| Successor manifest | `f46488a1b24f666a4ea7fcfa4e9730ed166c09a1e925c3860692ade5e5a973fd` |
| Intake dataset | `bb61b8da76d95bb20aea377f70148075fa46d3eec599a804f7d8f87da87a2912` |
| Disposition manifest | `ce8007f9dbe35f07281ddd232d426b25003d31b38f54ee89e301775c93f48ce5` |
| Disposition data | `16749c32bfcf13febb41be8d37bb5aa6664d92fbbb75025ce26e02465922fa5f` |
| Package ZIP | `322763cbfdf76805e123d18e49f4f09ff575b431a93f3a3ff5aa7c16d8f79e24` |

Exact published commit and terminal remote CI are reported in the issue delivery,
not presumed from local checks. All records remain noncanonical,
`human_reviewed=false`, and `NOT_LOCALLY_VERIFIED` in retrieval.
