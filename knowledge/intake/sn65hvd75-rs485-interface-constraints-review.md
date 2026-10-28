# SN65HVD75DR RS-485 interface-constraint receipt

Historical collection status: **DRAFT**, independent Agent review was pending at collection.
Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**; see final review below.
Issue #23; collector `agent:/root/curate_reset_rs485_wave/collect_rs485_constraints`.
Base main `e4ce9305a4c48011eff9fa81cb751a0a5a5a87a8`; collected 2026-10-28 UTC.
Scope is this receipt and its JSON pair only. Noncanonical and not human-reviewed;
no circuit, protocol, isolation or board compliance sign-off is claimed.

## Actual evidence

Official URL: https://www.ti.com/lit/ds/symlink/sn65hvd75.pdf . Actual acquisition
succeeded, 1,554,999 bytes, SHA-256
`b46f5803fa8302f98d7461799d078be59a41112191461519bcf4c464743e60a6`.
Electrical revision SLLSE11H, March 2019; packaging addendum separately dated
15 July 2026. PDF page 29 (index 28), Addendum-Page 2, identifies exact
SN65HVD75DR, SOIC D, 8 pins. No HVD72/HVD78 or DGK/DRB substitution and no
latest-revision/procurement guarantee. No other source was consulted.

Ignored local original:
`.pcbknowledge/evidence/sha256/b4/b46f5803fa8302f98d7461799d078be59a41112191461519bcf4c464743e60a6.pdf`.
Ignored text/render aids: `.pcbknowledge/review/rs485/source.txt` and
`page-N.png`. Collector actually viewed rendered PDF pages 5, 6, 7, 8, 11, 12,
13, 14, 15, 16, 18, 19, 29, not merely render exit status. Electrical printed
page numbers match PDF page numbers. No precise bounding box was measured.
No original, extracted document or rendered image is included in delivery.
PUBLIC_REFERENCE is not OPEN_LICENSE; this is owner-authorized noncanonical
factual curation, not canonical processing or redistribution clearance.

Nine bounded annotations `rs485-app-01` through `rs485-app-09` distinguish:
operating envelope/thresholds, loading/logic, controls/standby, conditional
failsafe, topology, driver propagation, driver enable/disable, receiver
propagation, receiver enable/disable. Three batch-local warnings preserve
missing network, timing/controller and ground/protection inputs.

Source-specific care: section 7.8 HVD75 only, not neighboring speed variants;
unknown minima stay null. Driver propagation uses 54-ohm differential load,
whereas enable/disable uses 110-ohm pull load. Receiver timing uses 15 pF and
enable/disable uses the depicted 1-kohm loads. Figure 13 high-output disable
carries a VOH-minus-0.5-V marker and 90% label; Figure 14 uses low-output 10%.
Enable and propagation are separate, and microsecond standby wake rows cannot
be replaced by nanosecond propagation values. Stub qualitative guidance is
kept without converting the prose/equation into a universal length guarantee.

## Replay recipes (integration gate pending)

From repository root, expected IDs are -01 through -09 in this order:

```bash
for parameter in bus_operating_envelope bus_loading_and_logic_levels enable_polarity_and_standby conditional_receiver_failsafe termination_and_topology driver_propagation_and_edges driver_enable_disable_timing receiver_propagation_and_edges receiver_enable_disable_timing; do
  python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --parameter "$parameter"
done
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id rs485-app-ti-sllse11h-d
```

Expected warning IDs: `rs485-app-ground-protection-unknown`,
`rs485-app-network-unknown`, `rs485-app-timing-unknown`. Every selected fact must
retain its complete value, conditions, source, all warnings, canonical false,
and reader NOT_LOCALLY_VERIFIED disposition. Reader retrieval is not source
rehashing. These recipes are proposed checks, not claimed passed before review.

Identity negatives, each expected empty for this source:

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --device SN65HVD72DR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --device SN65HVD78DR
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --package 'DGK, 8-pin VSSOP'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --package 'DRB, 8-pin VSON'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d --manufacturer Nexperia
```

Engineering questions and required negative boundaries:

1. Can idle bus reception omit external bias? Retrieve -01/-04 plus warnings:
   enabled receiver, voltage envelope and bounded noise context must survive;
   arbitrary ground shifts/noise are not approved.
2. Can a fixed 120-ohm resistor be installed at every node? Retrieve -02/-05:
   cable-end impedance matching and unknown network inputs rule out a universal
   resistor recipe or load-count-to-network guarantee.
3. Can 20 Mbps or 17 ns propagation define half-duplex turnaround? Retrieve
   -03/-06/-07/-08/-09 plus warnings: separate enable/disable and microsecond
   wake maxima, loads, thresholds and controller/cable unknowns remain mandatory.
4. Does component ESD data establish board IEC qualification? Retrieve -01 and
   ground-protection warning: no; normal operation, stress and system tests differ.

Suggested semantic mutations must fail aggregate regression, not refresh expected
outputs: swap HVD78 timing into -06/-08; change driver wake max7 us to7 ns;
replace receiver wake max8 us with50 ns; drop 110-ohm/1-kohm timing loads; turn
null timing minima into0; change DE/RE polarity; erase failsafe operating
conditions; promote stress to normal common-mode range; make termination universal;
claim collision-free or board IEC/isolation approval; remove any batch warning.

## Historical collector handoff

JSON parse succeeded. Source SHA/size were measured and cited renders inspected.
No acceptance, aggregate successor update, publication, test-suite or CI success
is claimed by this DRAFT receipt. Separate reviewer must inspect actual source
bytes/rendered evidence and the full payload before appending review provenance.

## Independent final review and executed replay

At 2026-10-28T05:00:07.586809+00:00, distinct reviewer `agent:/root/curate_reset_rs485_wave/review_reset_rs485_sources` independently verified the actual 1,554,999-byte source SHA above and inspected rendered pages 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 and 29. Complete JSON fields, evidence/supporting-page references, warnings, limitations, historical provenance, status and this prose were reviewed, not just selected IDs or counts.

One factual omission was corrected with collector agreement: `rs485-app-02` now retains the page 6 receiver high-output typical expression `VCC - 0.3` V at -8 mA, alongside minimum 2.4 V; it was incorrectly null in the draft. The public JSON local-path hint is now null; the exact ignored-cache path above remains reproducible without bundling original bytes. Draft JSON SHA-256 was `5b2c0f2960d668174a11523ba415a4232c28b353f6ac961aa48b464474f4ac1b`. Current methods no longer claim review is pending; DRAFT history is preserved.

The reviewer executed all nine exact parameter commands, the warnings command and five identity negatives above, plus:

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id rs485-app-ti-sllse11h-d
```

All 16 commands exited 0. Exact ordered IDs and complete source/fact/warning object equality passed against the final JSON, including all three warnings on each fact. The all-facts query returned `rs485-app-01` through `rs485-app-09` in order. Acceptance is `AGENT_REVIEWED_UNDER_OWNER_DELEGATION`, explicit AGENT/OWNER_DELEGATION provenance, `canonical=false`, `human_reviewed=false`; every output retains `NOT_LOCALLY_VERIFIED` (the reader's cache-verification label, separate from this documented source inspection). Final JSON SHA-256: `e1aa5c7e7e42abddb165b8268b767a9573ebb72e210384f9d1a75493fa43c549`.

No original source, extract or image is public. HVD75 rows and their distinct loads/crossings, nanosecond versus microsecond wake conditions, no arbitrary failsafe/no-bias guarantee, and the three unresolved application-input warnings remain intact. No system design qualification or CI success is asserted by these targeted checks; aggregate and exact-commit CI are separate integration gates.
