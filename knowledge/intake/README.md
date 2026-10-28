# Curated collection

This queue contains **22 reviewed batches, 33 batch-local source/device scopes, and 228 factual
annotations**. All are noncanonical and were Agent-reviewed under owner delegation.
For the original five batches only, the owner subsequently gave [batch-level content acceptance on 2026-10-28](../../docs/owner-acceptance-2026-10-28.md)
for the pinned 100-annotation snapshot. This is not per-fact human evidence
verification, canonical approval, or a complete component model. Original Agent
provenance and batch bytes are preserved.

| Batch | Source/device scopes | Annotations | Review evidence |
| --- | --- | ---: | --- |
| [TI pilot](ti-three-ic-pilot.json) | LM1117 adjustable/DCY; original LM358/D; SN74HC00/D | 20 | Original-byte hashes plus seven rendered pages reviewed |
| [Cross-manufacturer pilot](cross-manufacturer-pilot.json) | ST LD1117STR/SOT-223; Microchip MCP6002-I/SN; Nexperia 74HC00D/SO14 | 20 | Fourteen annotations have byte-identified and rendered-page review; six Nexperia annotations have official web text only |
| [Interface IC pilot](interface-ic-pilot.json) | ADS1115IDGSR/DGS; 24LC256-I/SN; SN65HVD230DR/D | 20 | Three original hashes and twelve rendered pages reviewed; Microchip revision date checked as text only |
| [Timer, reference and driver](timer-reference-driver-pilot.json) | NE555DR/D; TL431CDBZR/DBZ; ULN2003ADR/D | 20 | Three original hashes and eleven rendered pages reviewed, including three identity pages |
| [Power, monitor and GPIO](power-monitor-gpio-pilot.json) | TPS62160DSGR/DSG; INA219AIDCNR/DCN; MCP23017-E/SO | 20 | Three original hashes and twelve rendered pages reviewed; MCP23017 supply wording remains unresolved |
| [LDO application constraints](ldo-application-constraints.json) | TI LM1117 adjustable/DCY; ST LD1117STR/SOT-223 | 8 | Two actual hashes and 11 independently inspected pages; [review](ldo-application-constraints-review.md) |
| [ADC input/interface constraints](ads1115-input-interface-constraints.json) | ADS1115IDGSR/DGS | 9 | Actual hash and 12 independently inspected pages; [review](ads1115-input-interface-constraints-review.md) |
| [Driver load/protection constraints](uln2003a-load-protection-constraints.json) | ULN2003ADR/D | 8 | Actual hash and 9 independently inspected pages; [review](uln2003a-load-protection-constraints-review.md) |
| [CAN network constraints](sn65hvd230-network-constraints.json) | SN65HVD230DR/D | 8 | Actual hash and distinct rendered-page review; [receipt](sn65hvd230-network-constraints-review.md) |
| [EEPROM transactions](24lc256-write-transaction-constraints.json) | 24LC256-I/SN | 7 | Actual hash and distinct rendered-page review; [receipt](24lc256-write-transaction-constraints-review.md) |
| [Buck component/layout constraints](tps62160-component-layout-constraints.json) | TPS62160DSGR/DSG | 8 | Actual hash and rendered Table 2 cell review; [receipt](tps62160-component-layout-constraints-review.md) |
| [Op-amp signal-chain constraints](mcp6002-signal-chain-constraints.json) | MCP6002-I/SN | 7 | Actual hash and six independently inspected pages; [receipt](mcp6002-signal-chain-constraints-review.md) |
| [Logic input/output constraints](sn74hc00-input-output-constraints.json) | SN74HC00/D; full orderable unresolved | 7 | Actual hash and nine independently inspected pages; [receipt](sn74hc00-input-output-constraints-review.md) |
| [Current-monitor calibration](ina219-measurement-calibration-constraints.json) | INA219AIDCNR/DCN, A grade | 8 | Actual hash and distinct rendered-page review; [receipt](ina219-measurement-calibration-constraints-review.md) |
| [Shunt-reference regulation](tl431-feedback-regulation-constraints.json) | TL431CDBZR/DBZ, standard C grade | 6 | Actual hash and rendered stability/circuit review; [receipt](tl431-feedback-regulation-constraints-review.md) |
| [Timer application constraints](ne555-timing-application-constraints.json) | NE555DR/D | 8 | Actual hash and rendered circuits/timing tables; [receipt](ne555-timing-application-constraints-review.md) |
| [Reset supervisor constraints](tps3808-reset-supervisor-constraints.json) | TPS3808G33DBVR/DBV, fixed G33 | 8 | Actual hash and distinct rendered-page review; [receipt](tps3808-reset-supervisor-constraints-review.md) |
| [RS-485 interface constraints](sn65hvd75-rs485-interface-constraints.json) | SN65HVD75DR/D | 9 | Actual hash and HVD75-specific timing/load review; [receipt](sn65hvd75-rs485-interface-constraints-review.md) |
| [MOSFET drive constraints](ao3400a-gate-drive-constraints.json) | AOS AO3400A/SOT23; full orderable unknown | 8 | Exact independently reviewed maintainer handoff; [receipt](ao3400a-gate-drive-constraints-review.md) |
| [Rectifier constraints](vishay-ss14-rectifier-constraints.json) | Vishay SS14/SMA; full orderable unknown | 7 | Exact independently reviewed maintainer handoff; [receipt](vishay-ss14-rectifier-constraints-review.md) |
| [TVS pulse constraints](vishay-smbj5-0a-tvs-pulse-constraints.json) | Vishay SMBJ5.0A/SMB, unidirectional | 8 | Exact independently reviewed handoff; [receipt](vishay-smbj5-0a-tvs-pulse-constraints-review.md) |
| [Connector geometry](wurth-61300211121-connector-geometry.json) | Wurth 61300211121, straight two-position header | 4 | Exact independently reviewed handoff; [receipt](wurth-61300211121-connector-geometry-review.md) |

The second batch records eight rendered pages for ST and Microchip, including
identity/revision pages. Nexperia direct acquisition returned HTTP 403; it was not
retried or bypassed. Its source hash and byte size remain null and visual review
remains false. Review receipts preserve this difference rather than flattening all
items into a single evidence grade.

The [interface IC batch](interface-ic-pilot.json) adds ADS1115IDGSR,
24LC256-I/SN, and SN65HVD230DR: 20 annotations checked against three byte-identified
originals and 12 rendered pages (nine factual and three identity pages). Microchip
revision-date evidence on PDF page 43 was checked as text only. Electrical revision
and packaging-appendix dates remain distinct. See its [review](interface-ic-review.md).

The fourth batch preserves the distinction between ULN2003A maximum ON-state input
requirement and absolute maximum input rating. Saturation data does not establish
a simultaneous-channel current or thermal budget. See its [review](timer-reference-driver-review.md).

Across the original five batches, 94 annotations have recorded byte-identified and rendered-page
review; six Nexperia annotations have official-text-only evidence. This describes
recorded review work, not original-byte verification by each subsequent reader.

The fifth batch preserves `MCP23017-SUPPLY-TEMPERATURE-AMBIGUITY` as
`UNRESOLVED_SOURCE_WORDING`. Its cover and electrical table give different supply
versus temperature wording. No supply-envelope fact was inferred; acceptance of
unrelated pin annotations does not resolve the issue. See its [review](power-monitor-gpio-review.md).
A later [separate disposition](../../docs/mcp23017-source-disposition-2026-10-28.md)
rechecks official Revision E (July 2026), contains use to an explicit conservative
preliminary supply/ambient subset, and preserves the original wording conflict.
Normal reads expose both records; none of these 100 annotation bytes were changed.

No precise bbox was annotated in any batch. These are scoped observations, not
full pinouts, procurement guarantees, thermal designs, cross-vendor replacements,
or proof of the latest available revision. See each batch's limitations and review
notes before reuse. The formal typed/visual pilot is still open.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake list
python3 configs/pcbknowledge_agent.py --repo . intake search MCP6002
```

Reader `NOT_LOCALLY_VERIFIED` means that read has not verified original local bytes;
it does not erase prior independently recorded evidence work. Original PDFs, page
renders, and full extracted text are excluded from Git and packages. The current
contract is [lightweight knowledge](../../docs/lightweight-knowledge.md).

## Application-question extension

The three application batches add 25 condition-preserving annotations in four
batch-local source scopes, with 11 explicit unresolved application warnings. They
reuse device lanes but do not merge identities or inherit prior owner acceptance.
A distinct Agent checked four actual original hashes and 32 cited rendered pages.
All 25 have byte-identified, item-specific visual review receipts; no precise bbox
or hardware qualification is claimed. TI full orderable identity, ST numeric ESR
and unprovided sensor/controller/load/thermal inputs remain explicitly unknown.

The [125-annotation aggregate replay](../../docs/intake-evaluation-125.md) pins all
eight batches and retains separately pinned source dispositions. The original
100-record manifest and owner receipt remain immutable historical baselines.
Candidate retrieval is not electrical permission, typical-to-guaranteed conversion,
cross-vendor interchangeability, or a complete protection/thermal design.

## Network, memory and power extension

Three further reviewed batches add 23 bounded annotations and nine unknown-input
warnings. CAN timing/topology, EEPROM write semantics and buck effective-component
constraints remain conditional candidates, not network qualification, persistence
assurance or PCB sign-off. A distinct Agent inspected actual source hashes and
cited rendered pages, including the checked LC matrix cells. Its historical
[successor replay](../../docs/intake-evaluation-network-memory-power.md) retains
historical 100/125 manifests and the separately pinned MCP23017 disposition.

## Signal-chain and logic extension

Two independently reviewed batches add fourteen conditional annotations and six
source warnings. MCP6002 common-mode, output swing, typical dynamics, load isolation
and bypass guidance retain the exact I/SN scope. SN74HC00 input thresholds/edges,
unused inputs, loaded output levels, current stress and bypass guidance retain the
D/SOIC-14 scope without inventing a full orderable. Its RKS/20-pin Figure 11-1 is
explicitly excluded from D-package pin/layout inference; two other warnings retain
unknown interface/load/timing/power inputs. No manufacturer correction is asserted.

The [historical signal/logic replay](../../docs/intake-evaluation-signal-logic.md)
retains the historical 100/125/148 manifests and unchanged MCP23017 disposition.
All 162 annotations remain noncanonical; the owner's earlier 100-record acceptance
does not cover these additions. Missing circuit inputs and the source-figure
mismatch are not resolved by retrieval or by the separate local byte-audit command.

## Measurement, reference and timing extension

Three independently reviewed application lanes add 22 annotations and ten warnings.
INA219 calibration/register/readiness, TL431 divider/current/stability and NE555
mode/timing constraints retain exact grade/package and source test conditions.
Two source-wording discrepancies remain unresolved: INA219 CNVR clearing language
and TL431 reference-current equation signs. No correction or circuit permission is
inferred. The [historical replay](../../docs/intake-evaluation-measurement-timing.md)
preserves all earlier snapshots and the separate MCP23017 disposition. New records
do not inherit the owner's original 100-record acceptance.

## Reset, interface and discrete stage

The [historical aggregate replay](../../docs/intake-evaluation-reset-rs485-discretes.md)
adds the TPS3808G33 and SN65HVD75 issue lanes plus the exact reviewed AO3400A and
SS14 handoff pairs. No old annotation or review receipt was rewritten. Reset
validity, interface timing/load, gate-drive, waveform and thermal conditions are
not universal board guarantees. Missing inputs remain batch-local warnings;
source wording conflicts are not resolved by Agent acceptance.

## TVS and connector handoff integration

The [current aggregate replay](../../docs/intake-evaluation-tvs-connector.md)
adds twelve original annotations and four warnings from exact accepted handoffs.
Pulse/current/thermal conditions are not DC or system protection guarantees.
Connector dimensions do not constitute a complete footprint, numbered pin map or
electrical polarity. Original source rights and missing application inputs remain
explicit. Both JSON/review pairs and all prior receipts stay byte-identical.
