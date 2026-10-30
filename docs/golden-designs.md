# Golden designs

> Status: target accepted by [ADR-022](adr/ADR-022-board-generation-knowledge.md).
> Machine-readable briefs live in [`evals/golden-designs/`](../evals/golden-designs/).
> The [brief](../schemas/design-brief.schema.json) and [block-graph](../schemas/block-graph.schema.json)
> schemas define their structure; this page explains their purpose and acceptance levels.

Golden designs are original, synthetic design packages in the style of a simple
hardware-competition task. They decide what knowledge to collect next and how to
measure progress. Knowledge that no golden design needs waits.

## Design brief format

The brief schema defines JSON sections for the following requirements:

```text
id, title, summary              short natural-language task statement
power                           sources (USB-C 5 V, battery, terminal block), ranges, budget
functions                       required functions (MCU, sensing, actuation, communication, UI)
interfaces                      connectors and external signals with electrical limits
mechanical                      board outline limit, mounting holes, connector edges, height
manufacturing                   fab profile ID, layer count, assembly side, preferred package sizes
constraints                     cost or part-count limits, banned parts, environment
acceptance                      checks the generated design must pass (see below)
```

The synthesis step turns a brief into a **block graph** (blocks, parameters and
port connections). `expand` turns the block graph into a design intent. PcbAtlas
turns the design intent into a routed board and fabrication outputs.

## Acceptance levels

| Level | Meaning | Owner |
|---|---|---|
| A1 Knowledge closure | Every block and part the design needs exists with `AGENT_VERIFIED` or better; `expand` produces no refusal | PcbKnowledge |
| A2 Electrical checks | Every IC power and ground pin is connected and decoupled; no floating required input; block calculator checks pass | PcbKnowledge (`expand` checks) |
| A3 Layout constraints | Placed and routed board satisfies every constraint in the design intent | PcbAtlas (checker reads the constraint set) |
| A4 DRC | Zero violations against the named fab profile | PcbAtlas / PcbCore |
| A5 Fabrication outputs | Gerber, drill, BOM and pick-and-place files generated and opened in an independent viewer | PcbAtlas |
| A6 Hardware | Fabricated board passes bring-up: correct rails, programmer connects, functional test | Owner |

A1 and A2 can be reached with a hand-written block graph before any AI synthesis.

## G1: sensor logger node (first target)

Digital, low power, two layers. This is the minimal end-to-end target.

- Power: USB-C receptacle as a 5 V sink only (CC pull-down resistors), PTC or
  fuse, TVS, reverse-current Schottky, 3.3 V LDO, power LED.
- MCU: one 32-bit MCU in LQFP-48 or smaller with its crystal, reset network,
  decoupling and SWD header. Default family: STM32F103C8T6 (owner may replace;
  see the roadmap's owner decisions).
- Functions: two user LEDs, one user button, I2C bus with pull-ups, INA219 power
  monitor, 24LC256 EEPROM, one 4-pin I2C expansion header, one UART header.
- Mechanical: at most 50 mm x 50 mm, four M3 holes, USB-C and headers on edges.
- Manufacturing: generic two-layer 1.6 mm profile, single-side assembly,
  0603 passives.

The G1 catalog now has independently verified records. Concrete selected parts
and operating decisions are recorded in the reference graph and `TODO.md`;
this overview is not a substitute for those versioned inputs.

## G2: motor and actuator controller

Adds switching power and high current.

- Power: 7-12 V adapter input, fuse, SS14 reverse protection and polymer bulk
  capacitance; TPS5430DDA supplies nominal 3.3 V through a TDK 100 uH inductor.
- Actuation: two ULN2003AIPWR relay channels and a separate RQ5E025TNTL/SS14
  low-side channel, each with its own external load connector.
- INA219 measures all protected-input branches through a Kelvin 0.1 Ohm shunt.
- Layout: buck hot loop, Kelvin sense, power-net widths and thermal copper.
- Reuses the G1 MCU core with three explicit GPIO control requirements and SWD.

## G3: analog acquisition front end

Adds analog layout discipline.

- NTCLE100 thermistor divider, BPW34 photodiode with MCP6002 transimpedance stage,
  TL431 reference, ADS1115 ADC on I2C, MH2029 ferrite rail filter.
- SN65HVD75 RS-485 link with termination and bias options.
- Layout: analog and digital return paths, guard and keepout, short sensitive nets.

## Progress metric

For each golden design, report:

- **knowledge coverage**: the share of blocks, parts and constraints that resolve
  without `UNKNOWN`;
- **highest acceptance level passed** (A1 to A6), with the exact commit and bundle.

A design counts as done only at A6. Lower levels are progress, not completion.

## Reference inputs and G1 acceptance

`g1.brief.json`, `g2.brief.json` and `g3.brief.json` are original synthetic briefs.
`g1.block-graph.json` is the hand-made reference answer, with declared planning
interfaces and requirement links. Its catalog block identifiers now resolve to verified records. Brief acceptance
fields describe the requested gates, not execution receipts. G1 reaches A2 on
`ad7b84352f27cff6a65ec24e43eb474a42506ec2`; three preserved independently authored
graphs and their actual input/review receipts live in `evals/synthesis/g1/`.

G1 places the monitor shunt between the regulator output and logger rail, with
the monitor itself supplied upstream. This is an explicit synthetic design
choice enforced by expansion checks.
Contract tests check shapes, reference closure and requirement coverage. G1
operating and mechanical inputs use D7 engineering defaults. Header allocations are 5 mA SWD, 40 mA I2C expansion and 5 mA UART, totaling
50 mA within the 150 mA logger budget. The component height is explicitly unconstrained.
A1/A2 pass for the recorded G1 receipt; A3-A6 require actual layout, DRC,
fabrication and physical bring-up, not the parked Stage 7 handoff.

## Variant and refusal corpus

The active corpus extends G1 with G1V1 (a sourced I2C temperature sensor replacing
the current monitor and its shunt) and G1V2 (a USB-UART bridge replacing the UART header and a
USB2-capable sink block). These are distinct briefs, not changes to the original G1
reference. N1-N3 intentionally request a 12 V input, an absent Wi-Fi module, and a BGA MCU,
respectively and require typed refusals rather than fabricated catalog facts. Exact
requirements and expected refusal code/function binding live in each brief.
N1 checks the available input block against 12 V; N3 checks the selected MCU
role and BGA package together rather than inventing a BGA-specific category.
D28-D30 preserve the initial corpus decisions from `999c85d`; D31-D33 record
the verified sensor/bridge substitutions and pair defaults used by the integrated briefs.

`v2 coverage --all` reports every brief, ready reference blocks and refusals; its
`--json` form is suitable for tooling. Eligibility or reference replay does not
prove independent synthesis. Fresh evaluation requires exactly three distinct
query-mediated attempts per brief, preserved actual transcripts and exact input
hashes, with no reference-answer access. Raw bundles contain audit/reference inputs
and are retained by the mediator rather than supplied to attempt authors.

An independent reviewer must return a controlled positive verdict (`EQUIVALENT`
or `NOT_EQUIVALENT`) with an explanation. At least two of three positive attempts
must pass A2 and equivalence; all three negative attempts must reproduce the
expected typed refusal. Historical G1 receipts remain unchanged. Corpus completion
is reported only after real attempts and evaluator results are preserved in Git;
this description of the protocol is not itself an execution receipt.

The fifteen preserved Stage 8 attempts used the exact earlier input recorded in
`evals/synthesis/stage8-input.json`. Their original packets, transcripts and hashes
are unchanged by integration with `999c85d`. Replaying their outputs against the
current briefs is a separate check, not a new independent synthesis attempt.

## G2 reference

D38-D54 replace the earlier refused partial graph with source-backed protection,
conversion and actuation blocks. The 7-12 V adapter and 500 mA total budget remain;
three external 100 mA loads leave 200 mA for the regulated logic branch. The
source-guided buck input model requires at most 161.5 mA at its 150 mA logic-load
point. The exact feedback-derived rail feeds GPIO and I2C checks. See `TODO.md`
for the acceptance receipt. Three fresh attempts on published `9b4aa7d` are
preserved in `evals/synthesis/g2/`; the earlier round remains in `g2-round1/`.
D54 subsequently corrects only fuse placement and adds pin proximity. Unchanged
author graphs are independently revalidated against that catalog as a separate
regression, not relabeled as fresh synthesis on different inputs.

## G3 reference

D55-D59 select a 15-35 degC bench acquisition board with an external 3.2-3.4 V
supply, a 10 mA filtered analog budget, and separate external-host I2C and UART
connections. The photodiode input is an imposed 0-50 uA electrical scenario at
940 nm, not a calibrated irradiance specification. The NTC Beta transfer, ADC
loading, TIA error envelope and first-order loop estimate retain their explicit
engineering assumptions. Source test conditions are not broadened into operating
guarantees. Both RS-485 nodes use SN65HVD75 receivers; only one bias pair is fitted.

The hand-authored `g3.block-graph.json` carries common-ground return references
and buffered-bias guard geometry. Their actual copper realization remains an A3
check; the parked handoff does not establish it.
