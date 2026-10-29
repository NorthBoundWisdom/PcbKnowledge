# WSLP2512 current-sensing application-input card

This bounded handoff for [issue #33](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/33)
contains one blank card and one invented case. It collects missing inputs;
completing a card is not thermal, measurement, pulse or circuit certification.

## Pinned evidence and scope

Use only **Vishay Dale WSLP2512R0100FEA**, nominal 10 milliohm, F initial
1% tolerance, EA lead-free tape/reel, no extra special suffix, two-terminal
2512 surface-mount metal-strip resistor. No alternate part or footprint is selected.
The source JSON (`git show intake-final:knowledge/intake/wslp2512-current-sense-constraints.json`)
and historical source review (`git show intake-final:knowledge/intake/wslp2512-current-sense-constraints-review.md`)
are pinned at `5cb96b866a941ad0ad905e6ce7f0d130477f5852`.
Source `wslp2512-vishay-30122-20240909-10mohm` is document 30122,
electrical revision **09-Sep-2024**, not the 01-Jan-2026 legal appendix or
PDF container date. The printed numbering example is WSLP1206; the accepted
exact WSLP2512 orderable also has separately recorded official HTML corroboration.
That historical identity entry is not inventory or quality certification.

- Source JSON SHA-256: `91abaf2e01f2cbd092e2e4e33f194a59bacf1eebcb33aeb07ff28b1ef775414b`.
- Historical PDF SHA-256: `d3dd7b4f590e713c84303e32530e8c8c6fd025617896e11d25599521771e4c13`.
  This is provenance only, not a fresh byte/visual audit or latest-revision claim.
- `canonical: false`, `human_reviewed: false` and ordinary consumer
  `evidence_verification: NOT_LOCALLY_VERIFIED` remain unchanged. Prior Agent
  review is not human acceptance, canonical approval or a new source-original audit.
- No original PDF, HTML, extract, render, private board data or external calculator
  is used or published in this handoff.

## Blank application-input card

For every field supply evidence, units, min/nom/max, conditions and uncertainty.
Leave absent information **UNKNOWN**, not filled from nominal assumptions.

| Input group | Actionable information to supply | Blank entry |
|---|---|---|
| Exact assembly | Manufacturer/orderable, marking, tolerance/packaging/suffix, two-terminal geometry, assembly and footprint verification | UNKNOWN |
| Current | Actual minimum/maximum DC and RMS, polarity, start/stop, transient/pulse/fault waveforms, duration/shape, duty/repetition, protection and recovery | UNKNOWN |
| Thermal path | Ambient range versus terminal/element temperature, self-heating, copper area/thickness/stackup, solder/mounting, airflow and coupled heat; acceptable margins and measurements/model | UNKNOWN |
| Sense connection | Exact takeoff positions/routing, power-path versus sensing copper/contact resistance, parasitics and temperature gradients; evidence for any proposed Kelvin layout and measured error | UNKNOWN |
| Analog chain | Low/high-side topology, common-mode and transient limits, exact amplifier/ADC, gain/offset/drift/noise, bandwidth/settling, reference, filtering and loading | UNKNOWN |
| Accuracy target | Error definition (reading/full-scale/absolute), current/temperature/time/bandwidth range, calibration method/conditions, initial tolerance versus drift and allocated uncertainty | UNKNOWN |
| Manufacturer evidence gaps | Applicable thermal implementation, operating-resistance bounds, qualified pulse/fault envelope and test-power clarification where needed | UNKNOWN |
| Engineering evidence | Worst-corner error budget, thermal validation, protection/recovery assessment and documented layout/measurement validation | UNKNOWN |

## Conditioned manufacturer facts

The selected IDs are `wslp2512-sense-01` through `wslp2512-sense-06`.
The following compact guide does not replace complete payloads and provenance
from the literal replay below.

| Fact suffix | Retained values and test scope | Interpretation boundary |
|---|---|---|
| 01 | Exact R0100 = 0.01 ohm, F = initial 1%, EA = lead-free tape/reel; no extra special suffix | Initial tolerance is not operating-temperature, self-heating, lifetime or total system accuracy |
| 02 | P70 = 3 W at reference ambient 70 C; straight-line ambient derating from 100% at 70 C to zero at 170 C; operating range -65 to 170 C | Not arbitrary-board safe power/current. Rating-test copper, stackup and airflow are unspecified; ambient is not terminal/element temperature |
| 03 | Component TCR magnitude maximum 75 ppm/C, measured -55 to 155 C, applicable resistance row 0.007 to 0.5 ohm; includes copper terminals. Alloy-only element coefficient stated less than 20 ppm/C | Use the component coefficient for this 10-milliohm part; no substitution of element value, arbitrary-temperature accuracy or expansion of WSLP2512 availability beyond its own row |
| 04 | Source working-voltage expression sqrt(P * R), P in W, R in ohm, result V | Allowable P/energy depends on real thermal and pulse conditions; no independent fixed voltage, continuous-current or pulse approval |
| 05 | 10 milliohm uses the 0.007–0.01-ohm terminal row: T = 0.762 +/- 0.254 mm; selected pad dimensions a = 1.65, b = 3.68, l = 4.06 mm; diagram labels typical sensing traces | Not a lower-resistance terminal row, four-terminal component, complete qualified CAD footprint or guaranteed sensing error; no layout is designed here |
| 06 | Load-life test: 1000 h, ambient 70 C, 1.5 h on / 0.5 h off; resistance-change limit +/- (1% + 0.0005 ohm) | Preserve additive term and test conditions. Applied test power is unstated, not silently 3 W; not initial tolerance, typical drift, guaranteed field life or system accuracy |

### Complete retained warnings

The following three full descriptions/statuses remain unresolved. All bind to
the source above, with historical provenance Agent
`agent:/root/resume_compact_evaluation/curate_current_sense_resistor`, recorded
`2026-10-28T21:32:16.236728+00:00`. That is not this card's review timestamp.

- **`wslp2512-thermal-inputs-unknown`** — `UNRESOLVED_APPLICATION_INPUTS`:
  PCB copper/stackup, soldering, airflow, ambient and terminal/element temperatures and actual DC/RMS current are unknown. P70 and ambient derating alone do not establish safe board dissipation or continuous current.

- **`wslp2512-measurement-inputs-unknown`** — `UNRESOLVED_APPLICATION_INPUTS`:
  Actual sense takeoff locations, copper/contact resistances, temperature gradients, amplifier gain/offset/bandwidth and required error budget are unknown. A typical sensing sketch, initial tolerance or element TCR does not establish system accuracy.

- **`wslp2512-pulse-envelope-not-established`** — `SOURCE_SCOPE_LIMITATION`:
  Page 3 pulse graphic is explicitly illustrative and directs readers to JouleWizard; no numerical pulse envelope is extracted. Repetition, waveform, energy and thermal recovery remain unknown; neither marketing pulse suitability nor average-power arithmetic qualifies a pulse load. No linked calculator or supplementary pulse source was evaluated.

## One explicitly synthetic filled case

These are invented scenario inputs, **not user-board facts, recommendations or
approved operating conditions**. No amplifier, resistor alternative or footprint
is selected and no Kelvin connection is certified.

| Field | Synthetic entry |
|---|---|
| Intended identity | Exact accepted WSLP2512R0100FEA, 10 milliohm, F, EA, two-terminal 2512; actual purchased assembly verification UNKNOWN |
| Current | Nominal 10 A DC only; actual min/max/RMS, polarity, transients/faults, pulse/repetition/protection/recovery UNKNOWN |
| Environment | Nominal ambient 50 C; range, copper/stackup/solder/airflow, actual terminal/element temperatures and operating resistance UNKNOWN |
| Sense/analog chain | Takeoff/routing/contact resistance, gradients, topology/common mode, exact amplifier/ADC/reference/filtering and calibration UNKNOWN |
| Desired result | 1% system current accuracy; error definition and current/temperature/time/bandwidth range, uncertainty allocation and life requirements UNKNOWN |

**Manufacturer evidence missing:** an application-usable thermal implementation
and supported operating-resistance/pulse limits; the source's concrete rating-test
PCB and load-life applied power are not specified. The illustrative pulse graph
is not a numerical envelope. No JouleWizard or supplementary source is consulted.

**Board/user inputs missing:** all UNKNOWN entries above. In particular, 50 C
ambient does not supply shunt temperature, and nominal DC does not characterize
start-up or fault currents. A typical trace sketch cannot replace takeoff geometry
and measured copper/contact/gradient error.

**Engineering analysis still required:** establish operating resistance and
self-heating from supported thermal conditions; separate initial tolerance,
component TCR, drift and calibration effects; propagate shunt, connections,
amplifier, ADC/reference, noise and settling uncertainties under a defined error
metric. Validate common-mode/transient behavior and the thermal/protection/pulse
case separately with applicable evidence. No executable solver is introduced.

For orientation only, treating the invented 10 A and nominal 0.01 ohm as exact
DC numbers gives V = I R = 0.1 V and P = I squared R = 1 W. These are nominal
arithmetic results, not operating bounds. Comparing 1 W with P70 does not prove
board suitability; 1% initial resistance tolerance does not prove 1% current
accuracy. The load-life test cannot be substituted for field error or lifetime.
**Outcome: thermal suitability, 1% system accuracy and a qualified pulse/fault
envelope are not established.** Input completion would still not certify them.

## Literal replay and independently justified negatives

Run from a clean detached checkout at the pinned technical snapshot above.
These metadata reads do not evaluate the synthetic circuit; hits/counts/exit zero
are not engineering qualification.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id wslp2512-vishay-30122-20240909-10mohm
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id wslp2512-vishay-30122-20240909-10mohm
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id wslp2512-vishay-30122-20240909-10mohm --device WSLP2512R0200FEA
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id wslp2512-vishay-30122-20240909-10mohm --package 1206
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id wslp2512-vishay-30122-20240909-10mohm --revision '09-Sep-2023'
```

| Recipe | Selected complete payload | Full stdout SHA-256, including final newline |
|---|---|---|
| Source search | Six facts 01–06, source/provenance and complete attached warnings | `008415d04d843b68da0bc20f00cf3e50bc85d5cc4c7b97954c24adcfacf4b099` |
| Source issues | Three complete warning objects and provenance | `6de24d2b3c8684806c20a78c5055479804e0c4bd6433f45fb77c9ec436ca72aa` |
| Wrong device | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong package | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| Wrong revision | Empty array | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |

The wrong-device control changes the exact nominal resistance identifier from
R0100 to R0200; it is not the accepted orderable. Package 1206 differs from the
stored two-terminal 2512 package. Revision 09-Sep-2023 differs from the stored
09-Sep-2024 electrical revision. Each conjunction excludes every scoped candidate;
empty means no scoped evidence, not safety, compatibility/incompatibility, proof
of nonexistence or a global evidence-absence claim.

Separately labeled current-base replay at `77440b29cb74ad2f55849ab3cddb830321e3396f` returned identical source JSON
and all five stdout hashes; it does not rewrite the pinned evidence. See the
[independent review](wslp2512-current-sensing-review.md) for command hashes,
actual reviewer/time and full-payload checks. Publication gates and exact-commit
CI are recorded separately in issue #33.
