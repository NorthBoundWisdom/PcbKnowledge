# Signal-chain and logic application replay

This successor pins thirteen reviewed batches, 24 batch-local source scopes and
162 annotations. The original five batches, owner acceptance, historical
100/125/148 manifests and MCP23017 disposition remain byte-identical. The new
MCP6002-I/SN and SN74HC00/D pairs have distinct Agent collection/review provenance;
they do not inherit the owner's acceptance of the original 100-record snapshot.
All candidates remain noncanonical, not engineering approval or a formal pilot pass.

## Reproducible selection and payload preservation

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-signal-logic.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

Both CI jobs select this aggregate and the unchanged, separately pinned
disposition manifest. There are **159 base cases plus six disposition cases**:

- All 108 earlier case definitions and selections are retained unchanged. The new
  sources add no matches to their unscoped lexical queries; old source-ID filters
  do not inherit the new scopes, including the older SN74HC00 temperature query.
- MCP6002: seven exact source/parameter selections, one complete-source selection,
  one complete-warning selection, fourteen wrong-identity search/issues selections,
  two unsupported guarantee/certification selections, and two retained historical
  supply/stress selections: **27 cases**.
- SN74HC00: seven exact source/parameter selections, one complete-warning selection,
  and sixteen wrong-identity/unsupported-parameter/semantic-kind selections:
  **24 cases**.

Expected record references are specified from the frozen reviewed JSON and its
source-to-record recipes, not captured from search output. Complete expected
candidate projections come from those pinned inputs independently of retrieval:
source identity, facts, conditions, all same-source warnings, provenance, evidence,
acceptance, `canonical: false`, `NOT_LOCALLY_VERIFIED`, and applicable complete
source-issue dispositions must match. IDs or counts alone cannot pass. Changed
batch sets/bytes, changed disposition bytes, missing explicit disposition pins,
missing expected references or mutations during replay still fail closed.

The historical manifests are for their own snapshots, not this enlarged checkout.
No data gate, source-processing policy or canonical review API was changed.

## Useful questions and limits

| Question | Source-scoped records and retained boundary |
| --- | --- |
| Does a nominal near-rail MCP6002 input/output fit? | `mcp6002-app-01/02/03`, envelope/sensor warnings, and old supply/stress records. Common-mode extension and saturated output endpoints are not arbitrary fault permission or precision linear rail swing. Preserve load, overdrive, supply, temperature and crossover conditions. |
| Does typical GBWP/slew qualify the signal bandwidth? | `mcp6002-app-04/05/06` and dynamics warning. Typical figures are not guaranteed minima; actual amplitude, noise gain, load and settling requirements remain unknown. |
| Is a sensor/cable/ADC buffer automatically stable? | `mcp6002-app-01/02/06/07` and all warnings. No universal capacitance limit, isolation resistor, source-impedance allowance or automatic circuit fit is supplied. |
| Does a controller meet SN74HC00 input requirements? | `sn74hc00-app-01/02/03` and input-system warning. Preserve exact supply points, ordinary CMOS edge limits and pull-network conditions. No 3.3-V interpolation, HCT equivalence or transfer of input termination to outputs. |
| How much current can the logic output drive? | `sn74hc00-app-04/05/06` and load/timing/power warning. Conditional loaded DC levels, stress limits, aggregate supply/ground limits and application capacitance guidance are distinct; none supplies unrestricted or all-output continuous drive permission. |
| Can the datasheet layout figure wire the D package? | `sn74hc00-app-07` and figure-scope warning. No: the RKS/20-pin Figure 11-1 is excluded from D/SOIC-14 pin/layout inference. Use the recorded section 5/Table 5-1 pin scope; textual bypass guidance remains separately bounded. No manufacturer correction is asserted. |

The logic batch contains two unresolved application-input warnings and one
unresolved source-scope mismatch; the op-amp batch contains three unresolved
application-input warnings. Each remains attached in full to every same-source
fact candidate and available through `intake issues`. Wrong vendor, grade,
orderable, package and semantic kinds yield empty results only under exact filters.
Missing hits are not electrical permission or proof that an uncurated specification
does not exist. SN74HC00 full orderable identity remains unresolved.

## Evidence and regression boundary

The [MCP6002 receipt](../knowledge/intake/mcp6002-signal-chain-constraints-review.md)
records independently verified cached source bytes and six rendered pages. The
[SN74HC00 receipt](../knowledge/intake/sn74hc00-input-output-constraints-review.md)
records independently verified cached source bytes and nine rendered pages,
including the source-figure mismatch. Those are prior review observations, not
new verification by the retrieval command. No precise bbox, newest-revision
guarantee, human evidence review or complete circuit model is asserted.

`test_signal_logic_replay.py` checks immutable historical manifest hashes, exact
prior-case/pin retention, all fourteen new facts and six warnings, and the new
negative-query coverage. Invented synthetic records exercise unchanged-ID
corruptions: typical-to-guaranteed promotion, reversed output bound, load-condition
loss, universal load-isolation claims, invented orderable identity, input/output
transition confusion, interpolated thresholds, Schmitt-trigger inference,
stress-to-drive entitlement, all-output permission, excluded-figure pin mapping,
forged source correction and warning loss. Existing application, disposition and
evaluator tests retain unknown-to-safe, provenance and complete-payload checks.

Original PDFs, renders and full extracted text remain outside Git and packages.
The full integrated gates, metadata-only package inspection and exact-commit remote
CI are separate completion checks; replay alone cannot attest to them.
