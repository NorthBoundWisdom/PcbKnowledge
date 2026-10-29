# Golden designs

> Status: target accepted by [ADR-022](adr/ADR-022-board-generation-knowledge.md).
> Machine-readable briefs will live in `evals/golden-designs/`; until then this page
> is the authority for their scope.

Golden designs are original, synthetic design packages in the style of a simple
hardware-competition task. They decide what knowledge to collect next and how to
measure progress. Knowledge that no golden design needs waits.

## Design brief format

A brief is JSON with these sections (the first schema version may simplify):

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

Existing intake devices that G1 can migrate: LD1117/LM1117, SMBJ5.0A, SS14,
MF-MSMF050-2 or SF-1206S050-2, C0603C104K5RACTU, CRCW060310K0FKEA, INA219,
24LC256, Wurth 2.54 mm header. New knowledge needed: the MCU, crystal, USB-C
receptacle, tactile switch, LEDs and their footprints.

## G2: motor and actuator controller

Adds switching power and high current.

- Power: 7 V to 12 V input on a terminal block, fuse, reverse protection, bulk
  electrolytic capacitor, TPS62160 buck to 3.3 V with SRP4020TA inductor.
- Actuation: ULN2003A for a unipolar stepper or relays; AO3400A or Si2342DS
  low-side switch with flyback diode; WSLP2512 shunt with INA219 current monitor.
- Layout: buck hot loop, Kelvin sense, high-current net widths, thermal copper.
- Reuses the G1 MCU block.

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
