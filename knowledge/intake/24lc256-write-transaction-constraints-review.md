# 24LC256 write-transaction constraints review

## Collector draft receipt

Issue: #17. Base: `a7cdf34` on main. Collector:
`agent:/root/curate_next_pcb_constraints/collect_eeprom_constraints`.
Collected 2026-10-28. Historical state at collection: **DRAFT**, not independently
accepted, not human-reviewed, not canonical. The independent review decision and exact draft hash appear below; collection alone is not acceptance.

Owned files are `24lc256-write-transaction-constraints.json` and this receipt.
No existing eight batch bytes, historical manifests, owner receipt or source
handling disposition are changed by this collector.

## Actual source evidence

The official Microchip DS20001203 download was acquired successfully and hashed:

- SHA-256: `37280f68ad38b83241cacfc3f470dcb9b2e787586beca22520f37d1c03a006db`
- Size: 727562 bytes; 48 PDF pages.
- This exactly matches the earlier interface-batch byte receipt. URL equality
  alone was not used as identity evidence.
- Revision Y, July 2022, is on Appendix A (PDF/printed page 43). The orderable
  `24LC256-I/SN` is explicitly example f on page 45: LC, industrial, SN SOIC.
- Collector inspected actual rendered pages 1, 5, 6, 10, 11, 12, 43 and 45.
  Page 5 timing/endurance columns and page 6 Stop-relative WP timing were checked
  visually; sections 5 through 7 on pages 10 through 12 supply transaction semantics.
- Page 1 constrains LC to 2.5 through 5.5 V; industrial range is -40 through +85 C.
  The broad family AC header's 1.7 V floor does not extend this device's operation.
- Originals remain in ignored content-addressed local evidence cache only. No PDF,
  page image, full extracted text or precise bbox is included in this handoff.
  Public reference is not an open redistribution license or canonical clearance.

## Bounded record plan and interpretations

Seven annotations cover address bit roles, physical-page wrap, protected command
ACK, Stop-relative WP timing, maximum internal write-cycle time, ACK polling and
partial-page refresh/endurance conditions. Existing pin/strap/rail/clock records
are referenced rather than copied. Three batch-local warnings retain unknown
controller transaction, persistence/power integrity and page-level lifetime inputs.

A synthetic four-byte request starting at `0x003E` would target `0x003E`, `0x003F`,
`0x0000`, `0x0001` within a single page-write transaction, not `0x0040`, `0x0041`.
This arithmetic illustrates the documented lower-six-bit wrap; it is not a
hardware test or implementation of a driver. A controller must avoid that crossing.

Command ACK is not programming confirmation: WP high can acknowledge without
starting a cycle. Polling is meaningful for the matching device and documented
post-Stop sequence; it indicates readiness, not byte readback or power-fail atomicity.
The 5 ms maximum is internal programming time, not bus-clock duration. Endurance
is per page, including refreshed unwritten bytes, with the numeric specification
restricted to +25 C, 5.5 V, page mode and characterization-not-tested caveat.

## Replay recipes and expected selections

Run from the repository root. Each command must exit 0. Results are noncanonical
candidates with `NOT_LOCALLY_VERIFIED`; even recorded past visual inspection does
not imply that the current reader verifies original bytes. Every selected candidate
must retain all three batch-local warnings, original conditions and provenance.

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter address_roles
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter page_write_boundary
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter protected_write_ACK
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter WP_sampling
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter write_cycle_time
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter write_completion_polling
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --parameter partial_page_refresh
python3 configs/pcbknowledge_agent.py --repo . intake issues --source-id eeprom-app-microchip-24lc256-y-sn
```

The seven searches select respectively `eeprom-app-01` through `eeprom-app-07`.
The issue query selects `eeprom-app-lifetime-unknown`,
`eeprom-app-persistence-unknown`, `eeprom-app-transaction-unknown` (deterministic ID order).
These are practical query recipes, not a system that interprets or approves a circuit.

The following exact source-plus-identity combinations must select no candidates:

```bash
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --device 24AA256-I/SN
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --device 24FC256-I/SN
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --device 24LC256-E/SN
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --package 'MS, 8-lead MSOP'
python3 configs/pcbknowledge_agent.py --repo . intake search --source-id eeprom-app-microchip-24lc256-y-sn --manufacturer 'Texas Instruments'
```

Semantic negatives require inspecting the complete payload, not expecting the CLI
to reason about a device: reject R/W inside the seven-bit address; reject array
capacity as a page size; reject ACK as persistence; reject a WP change after Stop
as cancellation; reject SCL speed as programming duration; reject characterized
page endurance as an all-condition system lifetime. Actual controller bus timing,
power continuity, address convention and integrity requirements remain unknown.

## Collector checks

At draft preparation, a subprocess-based replay of all 13 commands above passed
with exact fact IDs, three warning associations and noncanonical/nonverification
markers asserted. The one synthetic boundary calculation passed. No skips.
`python3 configs/check_english_repo.py` and
`python3 configs/check_public_repo.py` each exited 0. These collector checks do not
replace independent evidence review or final reconciled aggregate/CI gates.

Independent evidence, final-field and current-status review is recorded below. Main integration,
full Config/Build/Test/Package and exact-commit CI are owned by the #16 integrator.

## Independent Agent review

Current status: **AGENT_REVIEWED_UNDER_OWNER_DELEGATION**.
Reviewer: `agent:/root/curate_next_pcb_constraints/review_new_constraint_sources`; reviewed at `2026-10-28T03:29:20.726153+00:00`.
Original PDF hash independently recomputed; actual cited page renders, identity,
revision and all factual values/conditions/unknowns independently inspected.
No factual correction was necessary. Current evidence-method/status prose was
updated; historical DRAFT collection and unresolved engineering inputs retained.
This is delegated Agent review, not human acceptance, canonical clearance or
application qualification. No full original is published.

Reviewed draft JSON SHA-256: `096cef01542f2a66711ddbdba29081fc092ecd9821045c4fe0e392fa7c99eaa7`.
Reviewed final JSON SHA-256: `dcaa8eafd786aeeb42bc7871bfeb245511ea54f19cbef5be688e3abd165a532f`.

Independent replay: all 13 commands in this receipt returned exit 0 and valid
JSON. A separate 44-case check of all new successor selections asserted exact
IDs, unchanged complete fact/issue payloads, all warning associations and
noncanonical/NOT_LOCALLY_VERIFIED markers; all passed. The four new regression
tests passed after final review pins and the explicitly reviewed PGND lexical
expansion were integrated. The initial regression run failed on a stale draft
SHA pin before that integration; no facts were altered to fit test output.
