# Curated collection

This queue contains **5 reviewed batches, 15 source/device scopes, and 100 factual
annotations**. All are noncanonical and Agent-reviewed under owner delegation,
not human-approved or a complete component model.

| Batch | Source/device scopes | Annotations | Review evidence |
| --- | --- | ---: | --- |
| [TI pilot](ti-three-ic-pilot.json) | LM1117 adjustable/DCY; original LM358/D; SN74HC00/D | 20 | Original-byte hashes plus seven rendered pages reviewed |
| [Cross-manufacturer pilot](cross-manufacturer-pilot.json) | ST LD1117STR/SOT-223; Microchip MCP6002-I/SN; Nexperia 74HC00D/SO14 | 20 | Fourteen annotations have byte-identified and rendered-page review; six Nexperia annotations have official web text only |
| [Interface IC pilot](interface-ic-pilot.json) | ADS1115IDGSR/DGS; 24LC256-I/SN; SN65HVD230DR/D | 20 | Three original hashes and twelve rendered pages reviewed; Microchip revision date checked as text only |
| [Timer, reference and driver](timer-reference-driver-pilot.json) | NE555DR/D; TL431CDBZR/DBZ; ULN2003ADR/D | 20 | Three original hashes and eleven rendered pages reviewed, including three identity pages |
| [Power, monitor and GPIO](power-monitor-gpio-pilot.json) | TPS62160DSGR/DSG; INA219AIDCNR/DCN; MCP23017-E/SO | 20 | Three original hashes and twelve rendered pages reviewed; MCP23017 supply wording remains unresolved |

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

Across these batches, 94 annotations have recorded byte-identified and rendered-page
review; six Nexperia annotations have official-text-only evidence. This describes
recorded review work, not original-byte verification by each subsequent reader.

The fifth batch preserves `MCP23017-SUPPLY-TEMPERATURE-AMBIGUITY` as
`UNRESOLVED_SOURCE_WORDING`. Its cover and electrical table give different supply
versus temperature wording. No supply-envelope fact was inferred; acceptance of
unrelated pin annotations does not resolve the issue. See its [review](power-monitor-gpio-review.md).

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
