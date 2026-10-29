# ADR-024: Terminal numbering, package geometry authority and selection matching

- Status: Accepted
- Date: 2026-10-29
- Accepted: 2026-10-29 by the agent under explicit owner delegation (AGENTS.md section 3).
- Refines: ADR-022 and the v2 model.

## Context

The Stage 2 review (`4a79bf2`) found three issues that would block G1:

1. Five G1 parts (TVS, Schottky, PTC, 0603 capacitor, 0603 resistor) were removed
   from migration because their datasheets print no numbered terminal table.
   Two-terminal datasheets never do. Without a rule, every resistor, capacitor,
   LED and diode in G1 is blocked.
2. Package records store explicit pad arrays as authority. The three current
   records are 172 to 372 lines of `UNKNOWN` placeholders, and the SOT-223 record
   lacks its tab pad. If a generator writes pads into records, generated output
   becomes authority and every generator fix rewrites data.
3. Part selection compares a requested `value` against a part's `min`. Once a part
   records a real min/typ/max range, an exact request such as "3.3 V output"
   matches nothing.

## Decision

### Terminal numbering

- Parts with exactly two electrical terminals use `basis: STANDARD_CONVENTION`
  numbering. Unpolarized parts (resistors, ceramic capacitors, inductors, ferrite
  beads, fuses, PTCs, bidirectional TVS) use `1` and `2`. Diodes, LEDs and
  unidirectional TVS use `1` = cathode, `2` = anode. Polarized capacitors use
  `1` = positive, `2` = negative.
- The polarity itself is `DATASHEET` evidence: the cathode band, marking drawing
  or polarity symbol on a cited page. A polarized part without such a page stays
  blocked.
- Parts with more than two electrical terminals (ICs, transistors, crystals with
  four pads, switches, connectors) still need a numbered terminal map from a cited
  source. A generic package convention is never enough for them.

### Package geometry authority

- A standard-family package (chip, SOD, SMA/SMB, SOT, SOIC, TSSOP/VSSOP, LQFP,
  QFN, pin headers) records the **drawing dimensions** from a cited page (body,
  lead span, lead width, lead length, pitch, exposed or tab pads, pin count), a
  **generator** name and a **density level**. Pads are derived by the generator
  and appear only in derived outputs (bundle, KiCad export, read-only views).
- An irregular part (USB-C receptacle, tactile switch, some connectors) records
  explicit pads copied from the manufacturer's recommended land pattern, with
  `basis: DATASHEET` and a page.
- Exactly one of the two forms is present in a package record. The validator
  derives pads for both forms before checking pin and pad coverage.

### Selection matching

- A requested `value` matches a part whose nominal equals it: the part's `value`,
  or its `typ` when it records a range. A part with only `min`/`max` does not match
  a nominal request.
- A requested `min` is satisfied when the part's guaranteed lower bound (`min`, or
  `value` when no range exists) is at least the request. A requested `max` is
  satisfied when the part's guaranteed upper bound (`max`, or `value`) is at most
  the request.
- An `UNKNOWN` on either side never matches.

## Consequences

- The five removed G1 parts can return in Stage 4 with convention numbering and
  cited polarity.
- Package records shrink to the dimensions a drawing actually shows, and
  generator fixes need no data rewrite. The package schema changes in a
  contract-only commit with a re-pinned digest (Stage 3).
- `catalog.py` selection logic changes with tests for nominal, range and unknown
  cases (Stage 4).
