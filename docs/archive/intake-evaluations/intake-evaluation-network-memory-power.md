# Network, memory and power application replay

This successor pins eleven reviewed batches / 148 annotations. It retains all
64 query definitions and eight byte pins from the historical
125-annotation manifest without rewriting that file or its receipt. The original
100-record owner receipt, original batches and MCP23017 disposition also remain
byte-identical. New content has independent Agent review under owner delegation,
not inherited human acceptance, canonical approval or engineering sign-off.

This is now a historical snapshot; CI selects the
[current signal/logic aggregate](intake-evaluation-signal-logic.md).

## Exact replay

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-network-memory-power.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
```

At this stage, both CI jobs selected this successor plus the unchanged disposition manifest.
The evaluator rejects altered batch bytes/sets and compares full payloads,
including conditions, source warnings, identity, provenance, review status and
noncanonical/nonverification markers. No automatic expected-output capture,
subset fallback, pin relaxation or source-processing policy change was introduced.
Historical manifests replay their own snapshots, not the enlarged collection.

The 108 aggregate cases comprise the previous 64, 23 new source/parameter
selections, three source-warning selections, and 18 exact negative selections.
The unchanged six disposition cases bring this historical combined replay to 114.
Selections are specified from independently reviewed source-to-record mappings,
not learned from CLI output. One explicit successor-only lexical expansion was
independently reviewed: `TPS62160 PG` also selects `buck-app-05`, `buck-app-07`
and `buck-app-08` because their source-backed bypass, current-loop and ground
conditions contain PGND. Substring PG matching is lexical retrieval, not a power-good
answer. The old query/filter and historical manifest remain unchanged; exact
`parameter=PG` still selects only the old power-good record. Tests assert this
specific addition, while every other prior selection remains identical.

## Practical questions and boundaries

- CAN: termination placement and resistor fault rating; recommended receiver
  common-mode separately from stress; 230-specific slope/load loop delays and
  standby wake timing; source-scoped topology, fault and timing unknowns. Existing
  RS/standby pin records are referenced, not copied. No 231 receiver-off transfer,
  arbitrary topology, headline-rate cable budget or EMC sign-off.
- EEPROM: seven-bit address versus R/W and word-address roles; physical-page wrap;
  protected-command ACK versus programming; Stop-relative WP sampling; bounded
  write time and matching-device ACK polling; partial-page endurance caveats.
  The synthetic four-byte request at 0x003E wraps to 0x0000/0x0001, not the next
  page. Actual transactions, power integrity and persistence remain unknown.
- Buck: actual rendered Table 2 checked LC cells and stated tolerance assumptions;
  conditional peak/ripple/current considerations; effective versus nominal
  capacitance; current-loop placement and feedback/ground routing for adjustable
  DSG. Unchecked cells, nominal substitutions and an unseen board cannot become
  stability, EMI, thermal or continuous-current guarantees.

Each practical recipe is a source-plus-parameter selection in the manifest and
its collection review receipt. Three filter-only `issues` queries preserve all
nine new batch-local unknowns even without a matching fact. Wrong manufacturer,
orderable, grade, package, fixed variant and unsupported semantic kind yield no
candidates under the exact filters. Semantic limitations are preserved data,
not a circuit-analysis engine: zero matches never establish electrical permission.

## Independent evidence and regressions

The collection receipts record actual byte identities, revision/orderable checks,
rendered page evidence, corrections and real Agent provenance:

- CAN (`git show intake-final:knowledge/intake/sn65hvd230-network-constraints-review.md`)
- EEPROM (`git show intake-final:knowledge/intake/24lc256-write-transaction-constraints-review.md`)
- Buck (`git show intake-final:knowledge/intake/tps62160-component-layout-constraints-review.md`)

`test_network_memory_power_replay.py` uses invented synthetic records to detect
unchanged-ID semantic corruption: stress promoted to operation, wrong receiver
mode, page wrap changed to next-page continuation, ACK promoted to persistence,
WP timing changed, unchecked LC cells admitted, nominal substituted for effective,
application guidance promoted to a guarantee, unknown board asserted verified,
and missing inputs replaced by safety. It also checks full successor coverage
and immutable historical pins/queries. Existing application/evaluator/disposition
regressions retain their prior condition and warning/provenance checks.

Replay does not read or newly certify source PDF bytes. All originals, renders
and full text stay outside Git and packages. Package metadata retains the full
MCP23017 handling receipt without resolving the source-wording conflict or
upgrading any historical Nexperia evidence. Final local gates, metadata-only
package inspection and exact-commit CI are separate completion checks.
