# Curated collection

This queue contains **11 reviewed batches, 22 batch-local source/device scopes, and 148 factual
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
cited rendered pages, including the checked LC matrix cells. The current
[successor replay](../../docs/intake-evaluation-network-memory-power.md) retains
historical 100/125 manifests and the separately pinned MCP23017 disposition.
