# 24LC256: bounded synthetic page-write geometry

## Question and result

For synthetic positive-length writes to a 24LC256-I/SN, how can a requested
contiguous in-device byte range be partitioned without crossing a physical
64-byte page? This is a planning model, not a driver, bus emulator, persistence
protocol or approved circuit. No data payload is transmitted or stored.

| Synthetic start | Requested bytes | Planned chunk lengths | Result |
| --- | ---: | --- | --- |
| `0x003E` | 4 | 2 + 2 | Geometry only |
| `0x0040` | 64 | 64 | Geometry only |
| `0x003F` | 66 | 1 + 64 + 1 | Geometry only |
| `0x7FFF` | 1 | 1 | Geometry only |
| `0x7FC0` | 64 | 64 | Geometry only |
| `0x7FFF` | 2 | none | Entire request rejected |

The model uses the source's A14..A0 in-device addressing scope: 32768 bytes,
with accepted addresses 0 through `0x7FFF`. It rejects rather than masks
out-of-range addresses; the high-byte MSB being a device don't-care bit does not
make a larger model address valid. It first validates the entire interval, then
uses `min(remaining, 64 - address % 64)` for each chunk. There is no truncation,
whole-device wrap or partial plan for an invalid interval. This *planner's*
all-or-nothing rejection says nothing about physical write atomicity.

Zero length is deliberately outside this example's local scope, not claimed to
be a device prohibition. Missing, boolean, non-integer, negative and out-of-range
geometry is refused. The public CLI accepts no user transaction input; its
internal pure calculation supports synthetic regression variations only.

## Three different address roles

Synthetic A2/A1/A0 = 0/0/0 implies seven-bit target `0x50`. Appending the R/W bit
gives write control byte `0xA0` and read control byte `0xA1`. These are not the
in-device word address. For example, in-device `0x1234` is encoded high byte
first as `[0x12, 0x34]`, separately from the target/control byte.

The report keeps all roles separate. An explicitly assumed seven-bit controller
convention would use `0x50`, while an explicitly assumed write-control-byte
convention would use `0xA0` for a write. These assumptions do not validate any
real controller API. Unknown A pins leave target/control values unknown;
unknown controller convention leaves its argument unknown. Geometry may still
be planned, but no usable hardware transaction or API acceptance is established.

Each chunk represents a separate page transaction requiring its own Stop and
matching-device readiness check before continuation. The geometry report only
states this requirement: it neither emits Stop, polls, waits nor captures a bus.
The retained source describes polling with Start and the matching **write**
control byte. Neither an unrelated ACK nor a read control byte substitutes for
that documented sequence.

## Why an unsplit write is not equivalent

The pre-existing `test_network_memory_power_replay.py` already demonstrates the
four-byte boundary hazard. This example retains that counterexample and adds
actual split planning, end-of-device rejection, address-role handling and
independent result oracles.

An unsplit four-byte transaction beginning at `0x003E` addresses
`0x003E, 0x003F, 0x0000, 0x0001` under the page-counter model, not
`0x003E, 0x003F, 0x0040, 0x0041`. A crossing wraps within the current page even
when the transaction contains fewer than 64 bytes. This is address-counter
behavior, not evidence that any bytes were actually programmed.

## What the plan does not establish

- Under the explicit assumption of WP held high across a valid sampling window,
  a command can ACK without an internal write cycle or programmed data. The
  model reports that conditional behavior without qualifying an actual WP pin.
- A matching write-poll ACK indicates readiness for a next command under its
  supplied assumptions, not byte verification. WP low plus ACK still does not
  prove persistence, power continuity, readback integrity or power-fail atomicity.
- The source's WP setup/hold requirements remain attached to the full fact:
  600 ns setup and 1300 ns hold around Stop, for LC industrial scope at
  2.5–5.5 V and -40–85 C. A post-Stop change does not retroactively change the
  sampled command. This tool computes or validates none of those timings.
- The 5 ms maximum is the condition-specific internal byte/page programming
  cycle starting at Stop for an unprotected write. It excludes serial transfer;
  this tool prescribes no fixed wait and predicts no end-to-end completion time.
- Partial writes refresh the physical page. The recorded endurance number is
  conditioned on 25 C, 5.5 V and page mode and is characterized, not tested.
  No system lifetime, retention interval or write-distribution model is derived.

All three source warnings remain unresolved and appear unchanged in the report.
No geometry result qualifies WP, supply, persistence, lifetime or the circuit.

## Evidence and reproduction

Only the existing accepted batch is used:
`knowledge/intake/24lc256-write-transaction-constraints.json`, SHA-256
`dcaa8eafd786aeeb42bc7871bfeb245511ea54f19cbef5be688e3abd165a532f`.
It identifies Microchip Technology 24LC256-I/SN, SN 8-lead SOIC, DS20001203Y.
All seven complete fact candidates and three complete issue candidates retain
source identity, revision, evidence anchors, conditions and warnings. The
recorded original PDF identity remains metadata, not a new byte audit.
This work performs no network or original-source access and adds no facts.

```sh
PYTHONPATH=src:. python3 configs/pcbknowledge_eeprom_page_eval.py --repo .
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_eeprom_page_eval -v
```

The fixed CLI evaluates 17 cases against independent literal expected outputs.
Ten tests include actual CLI execution, a grid checking exact contiguous
coverage without page crossings, strict refusals, source-byte pin failures,
mid-evaluation evidence changes and 17 output mutations (16 planning/status
mutations and one unsplit-wrap mutation). Full payloads are compared, not just
IDs or lexical hits. A missing/changed batch fails closed.

Exit 0 means regression PASS, 1 means a mismatch and 2 means invalid invocation
or unavailable evidence. Every report retains `canonical: false`,
`human_reviewed: false` and `NOT_LOCALLY_VERIFIED`. No raw document, new intake
record, historical evaluation change or source-warning closure is involved.
Independent review, full repository checks and exact-commit CI are separate gates.
