# MH2029-601T rail-filter application inputs

This handoff is an input checklist, not a selected filter or a qualified circuit.
The blank card and single synthetic case separate conditioned manufacturer
metadata, application inputs, assumptions and engineering work still required.

## Identity and evidence boundary

Pinned technical snapshot: `8d9e5b211e565067234e642d8f52309ac9bd07fb`.
Separately replayed drafting base: `cfc4737c8a5be6a1a83903807adbd80d9286146f`.
Use the [source JSON](../../knowledge/intake/mh2029-ferrite-constraints.json)
and [historical review](../../knowledge/intake/mh2029-ferrite-constraints-review.md).
Exact identity is Bourns MH2029-601T, not MH2029-601Y; SMD chip,
2.00 x 1.25 x 0.85 mm nominal. Each body dimension has +/-0.2 mm tolerance;
these are not a complete footprint or assembly acceptance. Extra suffix and
lifecycle status are unknown; no substitution or certification is asserted.
Electrical Rev. 09/23 is distinct from legal appendix K2540 05/26R.

- Source ID: `mh2029-601t-bourns-r0923`.
- Source JSON SHA-256: `775888fa8e72583c65aa350d63ded06002a7142246db64ff92d976f7c936137b`.
- Recorded PDF SHA-256: `359f5ab799d0f9d03b15a0b886e6b29818ee134304c104cebd79db1aeb5041c9`.
- [Official reference](https://www.bourns.com/docs/Product-Datasheets/MH2029-T.pdf).

This task replays accepted metadata only, with `canonical: false`,
`human_reviewed: false` and consumer `NOT_LOCALLY_VERIFIED` semantics.
Recorded source hashes, historical visual checks and Agent acceptance do not
constitute a fresh PDF-byte/visual audit, human approval or circuit acceptance.

## Conditioned manufacturer evidence

All five complete records, including provenance and conditions, remain in the
pinned source; the replay below retrieves their complete payloads.

- `mh2029-ferrite-01`: exact identity and dimensions above; stock, lifecycle,
  manufacturing acceptance and a complete footprint are not established.
- `mh2029-ferrite-02`: impedance magnitude 600 ohm +/-25% at 100 MHz,
  60 mV and 25 C. RMS/peak amplitude convention and DC bias are unspecified.
  This is not 600 ohm DC resistance, a fixed broad-band value or an attenuation.
- `mh2029-ferrite-03`: maximum DCR 0.06 ohm at 25 C; measurement current
  and full-temperature maximum are unknown. It is not an installed drop or
  heating guarantee. RF impedance must not replace DCR in DC calculations.
- `mh2029-ferrite-04`: 2300 mA maximum rating under the 25 C table uses
  maximum 40 C temperature rise. The -55 to +125 C operating range does not
  permit that current at every ambient. Mounting, current derating, permitted
  hot-ambient current and treatment of self-heating at the upper limit are unknown.
- `mh2029-ferrite-05`: separate Z, R and X frequency traces (MHz axis)
  have no stated min/typ/max class or DC-bias condition. No points are digitized;
  R(f) is not DCR. Neither biased impedance nor system insertion loss,
  resonance or rail stability is guaranteed by the isolated plot.

## Blank application-input card

For each answer, attach supplier/owner, source or measurement method, date,
revision and uncertainty; leave unavailable answers **unknown**, not assumed.
Manufacturer values above are evidence, not answers about the installed board.

| Input group | Questions to resolve | Supplied value and provenance |
|---|---|---|
| Exact identity | Manufacturer, full suffix/orderable, package and received-part evidence? | unknown |
| Rail limits | Supply minimum/nominal/maximum and tolerance; allowed DC drop and rail limits at the load? | unknown |
| Current waveforms | DC, ripple, inrush, load-step and fault currents, shape, frequency/duty, duration, recovery/protection? | unknown |
| Noise objective | Noise spectrum/amplitude, operating modes, target insertion loss versus frequency and measurement setup (probe, bandwidth, reference plane, loading)? | unknown |
| Network | Source and load impedances versus frequency, regulator identity/control/compensation and load-transient behavior? | unknown |
| Capacitors | Exact decoupling, effective capacitance versus bias/temperature/tolerance, ESR/ESL, placement and interconnect? | unknown |
| Physical path | Mounting, pads/copper/stackup, ambient range, airflow, coupled heating, layout and return paths? | unknown |
| Acceptance | Acceptable rail transient response, resonance/stability margins, thermal limits and validation procedure/uncertainty? | unknown |

Engineering still required: justify a frequency- and operating-point-dependent
network model, assess regulator interaction and parasitics, obtain applicable
bias/temperature evidence and validate with representative noise, transient and
thermal measurements. Identify which assumptions each measurement can test.
Completing fields does not itself close any warning or qualify the circuit.

## One synthetic filled case

Every numeric application value in this paragraph is **synthetic**, not a
user-board fact, manufacturer recommendation or approved operating point:
a proposed nominal **3.3 V** rail carries nominal **1.0 A DC**, at proposed
ambient **40 C**, with a hypothetical noise concern near **100 MHz**.
The proposed exact component is Bourns MH2029-601T in the package above.
These invented inputs merely exercise the checklist; there is no measured board.

- Supply range/tolerance, allowed DC drop and load rail limits: **unknown**.
- Actual DC extrema, ripple/inrush/fault waveforms, protection and recovery: **unknown**.
- Noise amplitude/full spectrum, target insertion loss and measurement setup: **unknown**.
- Frequency-dependent source/load impedances, regulator/control and load steps: **unknown**.
- Capacitor identity/effective capacitance/ESR/ESL and placement: **unknown**.
- Mounting/copper/stackup, airflow, coupled heat, layout and returns: **unknown**.
- Allowed self-heating, transient/stability limits and validation evidence: **unknown**.
- Provenance: invented for this handoff; no supplier/user measurement or date is available.

The synthetic current and ambient cannot be approved by comparing them with
2300 mA or the operating range. The one-frequency impedance does not establish
noise reduction. No insertion loss, approved current, dissipation or permitted
voltage drop is calculated from these incomplete inputs. Obtain the missing
inputs and applicable evidence, then perform and validate the analysis; this
card does not choose a bead, regulator, capacitor or board design.

## Complete retained warnings

### `mh2029-filter-network-unknown`

Status: `UNRESOLVED_APPLICATION_INPUTS`.

Noise spectrum, source/load impedances, capacitor ESR/ESL, layout and acceptable insertion loss/rail transient response are missing. Impedance at one test frequency is not filter attenuation or supply stability.

Recorded by `agent:/root/finish_bpw34_stage/curate_ferrite_conditions` at `2026-10-29T00:11:14.519475+00:00`.

### `mh2029-bias-and-thermal-unknown`

Status: `UNRESOLVED_APPLICATION_INPUTS`.

Actual DC and ripple current, ambient, mounting/copper, DC-bias-dependent impedance and allowed self-heating are missing. Rated current and operating range do not establish a permitted hot-ambient operating point.

Recorded by `agent:/root/finish_bpw34_stage/curate_ferrite_conditions` at `2026-10-29T00:11:14.519475+00:00`.

### `mh2029-source-scope-limits`

Status: `SOURCE_SCOPE_LIMITATION`.

Exact -601T only, not -601Y. Electrical revision 09/23 differs from legal appendix K2540 05/26R. Signal amplitude convention, bias, plot min/typ/max class, full-temperature DCR bound and hot-current derating remain unknown; no certification or lifecycle status inferred.

Recorded by `agent:/root/finish_bpw34_stage/curate_ferrite_conditions` at `2026-10-29T00:11:14.519475+00:00`.

## Reproducible retrieval and exact negatives

Run from a clean detached checkout of the pinned technical commit above.
Commands are literal supported CLI recipes; command hashes use their UTF-8
bytes without a newline, stdout hashes include the complete trailing newline.
The separately labeled drafting-base replay produced byte-identical outputs.
These are retrieval checks, not evaluation of the synthetic circuit.

### Recipe 1

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id mh2029-601t-bourns-r0923
```

- Command SHA-256: `78a1030b7cb7086d932d301cbf8882c58c8fcf94f4234325e2d0bad5bd5d5d6c`.
- Full stdout SHA-256: `fc2d2282f811d6ee07954d6488e0b294732e9d4ed1f8fadcc1a8270f6a660bbb`.

### Recipe 2

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id mh2029-601t-bourns-r0923
```

- Command SHA-256: `87f5cf7a860bd70c1ab8124321c68705f4889bc181509124c174573f341b9c17`.
- Full stdout SHA-256: `5aa7ad2a041df2a4a3e56dbf243c447552e3d6abf0bb0d8fa5595f7bdbf20946`.

### Recipe 3

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id mh2029-601t-bourns-r0923 --device MH2029-601Y
```

- Command SHA-256: `b7941b88118390a16b437484936a90c04ea870f0d9b88cde24f7747665cf7eb9`.
- Full stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

### Recipe 4

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id mh2029-601t-bourns-r0923 --manufacturer Vishay
```

- Command SHA-256: `7d924555faca0f277c82fd2cb94193f454ffc4250b69d463456b8bbb68f764ef`.
- Full stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

### Recipe 5

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id mh2029-601t-bourns-r0923 --package 0603
```

- Command SHA-256: `a42ddb0835d3a54c1ee4a09941b257564f9e3762f77313af03252d247a94ea0e`.
- Full stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

Recipe 1 selects exactly `mh2029-ferrite-01` through `mh2029-ferrite-05`;
review compares all full values, conditions, evidence/source metadata, provenance
and attached warnings, not IDs or counts alone. Recipe 2 returns the three full
warnings above. Both retain noncanonical/nonhuman and local-verification limits.

Recipes 3-5 independently exclude the scoped source because structured device
MH2029-601T is not MH2029-601Y, manufacturer Bourns is not Vishay, and the exact
nominal SMD package string is not 0603. These conjunctions produce empty results;
lexical mention of -601Y in a warning cannot make it the selected device.
Empty selection means no scoped candidates, not global absence, compatibility,
incompatibility or safety. Successful exit, lexical hits or counts are not
attenuation, temperature-rise or rail-stability verification.
