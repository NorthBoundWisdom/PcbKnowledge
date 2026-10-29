# Translation and load-switch application constraints

This successor adds independently collected and reviewed exact TI
SN74LVC1T45DBVR and TPS22918DBVR annotations. It also integrates the accepted
Vishay CRCW060310K0FKEA pair from immutable
`988743b28a3e63fad3e49942749325c7cf2ff41d` byte-for-byte; the synthetic integration
test pins both handoff files. Resistor evidence was not recollected.
All records remain noncanonical and `human_reviewed=false`; this is not canonical
approval, an original-source license, or per-fact human evidence verification.

## Replay

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-translation-loadswitch.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

The preceding 392 cases and all previous intake pins remain exactly unchanged.
New recipes select every new parameter and batch-local warning, and reject exact
wrong-device, manufacturer, package and unsupported-guarantee selections. Expected
IDs are specified from reviewed inputs rather than copied CLI output. Complete
payload comparison retains conditions, units, provenance, warnings and retrieval's
`NOT_LOCALLY_VERIFIED` markers. An empty negative result does not prove safety.
Historical 100/125/148/162/184/216/228 snapshots and the separate MCP23017 disposition
remain unchanged. Both CI replay jobs use this successor plus that disposition.

## Conditions and unknowns

- Translation: A and DIR use VCCA, B uses VCCB. Operating thresholds and loaded
  output limits retain their rail/test conditions. Grounded-rail isolation and
  Ioff numbers do not apply to arbitrary floating or ramping rails. The source
  separately describes glitch-free power sequencing without ramp-order/rate
  requirements after applying ground; this does not prove controller-direction
  handover or board compatibility. Contention and automatic direction sensing
  are not authorized. Selected rail-pair timing,
  load and min/typ/max qualifiers do not constitute a system data-rate guarantee.
  Controller sequencing, overlap, loads and timing budgets remain unknown.
- Load switch: VIN, ON, current and thermal restrictions remain distinct. CT and
  rise-time/inrush relationships retain their test conditions and external-load
  dependence. ON-before-VIN loses slew control. QOD is a configured discharge
  path, not reverse isolation; slew control is not current limiting. The source
  warns about the reverse body-diode path. Actual source impedance, prebias,
  backfeed and thermal inputs remain unknown. Printed example capacitance units
  conflict with another example; this remains unresolved, not silently corrected.
- Resistor: standard and extended rated dissipation retain different drift
  criteria. Mounted thermal derating, voltage/power and short-term overload
  qualifications do not authorize arbitrary board power or total accuracy.
  Body dimensions are not a certified footprint; solder-pad guidance stays scoped.

Distinct source review inspected identified TI bytes and rendered tables/footnotes;
full-payload checks covered all fifteen TI facts and seven warnings. The resistor
handoff preserves its original collector and reviewer evidence. Synthetic invented
values reject 26 equal-identity/count mutations of domains, timing, thermal limits,
QOD/reverse/current claims and unknowns. They verify preservation, not an electrical
reasoning engine. No source PDF, extracted text, drawing or image is published.

## Validation

Executed locally on the final code/data tree:

- Config, Build and Test PASS; Build and Test each ran 317 tests, zero skips.
- English/public-source/PDF.js guards, workspace and Agent validation, local
  Markdown link targets and staged/worktree whitespace checks PASS.
- Aggregate replay 470/470 PASS: 464 successor cases and six unchanged disposition
  cases; 25 batches, 36 source scopes and 250 annotations.
- Independent source/full-payload review: 49 real CLI calls across the two TI
  pairs; all 72 added successor recipes inspected. Three synthetic/integration
  tests PASS, including 26 equal-identity mutation rejections.
- All 57 protected historical files and 392 historical recipes/pins unchanged.
- Package: `build/package/PcbKnowledge_c385615a1b775e0f.zip`; 31 metadata-only
  members (25 batches, one disposition, workspace, three schemas, derived manifest).
  Archive input members equal local bytes; no source originals included.

| Item | SHA-256 |
| --- | --- |
| Successor manifest | `32f4123ea6134e6f38495e4f8350e0d6b59a8f8a7d298dff54ce5e9d5af3509a` |
| Intake dataset | `e6890706993caf99887c8df078e9d092b586d5fddf4e3b0e89b86699d6cc9960` |
| Disposition manifest | `ce8007f9dbe35f07281ddd232d426b25003d31b38f54ee89e301775c93f48ce5` |
| Disposition data | `16749c32bfcf13febb41be8d37bb5aa6664d92fbbb75025ce26e02465922fa5f` |
| Package ZIP | `e9bfb268e966586013e6d576215d61f1c2dd57d0aa6b5e5d91e0ed89353b7513` |

Exact published commit and terminal remote CI are reported in the issue delivery,
not presumed from local checks.
