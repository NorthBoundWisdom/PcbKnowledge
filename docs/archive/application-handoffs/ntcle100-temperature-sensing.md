# NTCLE100 temperature-sensing application inputs

This is a blank input handoff and one invented example, not a selected sensor
circuit or temperature calculator. An input-complete card does not establish
accuracy, response, lifetime or circuit safety.

## Evidence boundary

Exact identity: **Vishay BCcomponents NTCLE100E3103JB0**, 10 kohm at 25 C,
J 5% R25 tolerance, B0 bulk, **no A suffix**, radial bead with 2.54-mm lead spacing.
The source JSON (`git show intake-final:knowledge/intake/ntcle100-thermistor-constraints.json`)
and historical review (`git show intake-final:knowledge/intake/ntcle100-thermistor-constraints-review.md`)
are pinned at `67e02cef0edc6c67a8e2445c567afff8febe0ddd`.
Source ID: `ntcle100-vishay-29049-20250507-10k5pct`.
JSON SHA-256: `085793b239cb1a67f455f327c7214fa87b5ffbb3df0161eaee72e34d8d514a5a`.
Document 29049 electrical revision **07-May-2025** is distinct from the
01-Jan-2026 legal appendix. Recorded PDF SHA-256:
`f9d6153738198dc705ed681c3b55e70a6571f8fee13a4ed7b2b41e49973cb9c9`.
These hashes identify existing metadata/provenance, not a new PDF-byte or visual
audit. Prior Agent review is not new human acceptance. Retrieval remains
`canonical: false`, `human_reviewed: false`, `NOT_LOCALLY_VERIFIED`.

## Blank application-input card

Use `unknown` until supplied with an identified source or measured bound.
Keep manufacturer evidence, board inputs, assumptions and subsequent analysis
in separate fields; record who supplied each input and when.

| Input group | Questions to complete | Supplied value / evidence |
|---|---|---|
| Identity | Exact MPN, suffix, tolerance, package and lot? Is no-A JB0 actually intended, with no implicit JB0A substitution? | unknown |
| Measurand | Target object, sensor element and ambient temperature ranges separately? What gradients and transients connect them? | unknown |
| Installation | Thermal contact material/pressure, mounting, airflow, enclosure, leads, PCB heat sources and nearby dissipation? Is potting proposed despite source limitation? | unknown |
| Excitation | Supply interval, source impedance, waveform, startup/fault levels, on/off duty and duration? Bound instantaneous and average thermistor power versus temperature. | unknown |
| Divider | Exact resistor, tolerance, drift, self-heating, connections and supply/reference relationship? | unknown |
| Acquisition | ADC/reference identity, gain/offset/noise/drift, input leakage/capacitance, filtering, acquisition and settling time, sample schedule and loading? | unknown |
| Conversion | Selected R-T data/model and valid range, interpolation/error evidence, calibration points/procedure and traceable reference? | unknown |
| Performance | Required temperature-error definition and confidence, range, response metric/deadline, aging/lifetime and recalibration interval? | unknown |
| Validation | Which evidence supports installed thermal coupling, self-heating, response, conversion and full error budget? What measurements remain? | unknown |

Analysis still required: propagate excitation, divider, ADC/reference and sensor
uncertainties through a justified conversion; distinguish R25 and Beta variation,
calibration residuals and aging; establish installed thermal gradients, heating
and dynamic response. Do not assign a source guarantee where only a model or
measurement assumption exists.

## Manufacturer facts and interpretation limits

The complete payloads, provenance and conditions are retained by the pinned
source and reproducible commands below, not replaced by a count or lexical hit.

- `ntcle100-sense-01`: R25 **10000 ohm +/-5%**, B25/85 **3977 K +/-0.75%**,
  B0 bulk. Separate specifications, not total temperature accuracy or resistance
  bounds at arbitrary temperature. Do not apply initial tolerance uniformly over
  temperature or certify a Beta conversion; G/H and A variants are excluded.
- `ntcle100-sense-02`: continuous **-40 to 125 C** and short-period **150 C**
  are zero-dissipation scope; short-period duration is unknown. Measuring power
  no greater than 1% of maximum power is a convention, not zero self-heating or
  a universal 5-mW allowance at every ambient temperature.
- `ntcle100-sense-03`: **500 mW at 55 C**, recorded plot plateau **0 to 55 C**
  at 100%, and zero-power ambient points **-40 and 85 C**. These are only retained
  labeled points, not digitized/interpolated operating allowances or a flat
  rating. Voltage must remain **below 50 VDC**, strictly, not an excitation
  recommendation or insulation/isolation rating.
- `ntcle100-sense-04`: approximately **1.2 s in oil** response is distinct from
  informational **15 s** thermal time constant with **unspecified medium**.
  Guaranteed maximum response is unknown; neither establishes installed response.
- `ntcle100-sense-05`: informational **7 mW/K** applies to this 10-kohm scope;
  **8.5 mW/K** belongs only to R25 <=680 ohm and is excluded. Mounting,
  environment and excitation duty are needed; no guaranteed installed heating
  error follows from dividing power by an informational value.
- `ntcle100-sense-06`: no specified coating insulation; potted applications
  are not intended. This part uses the **330-ohm to 470-kohm** dimension row,
  not the 3.3-to-220-ohm row: lead spacing **2.54 mm**, body thickness maximum
  **3.0 mm**, lead diameter **0.6 +/-0.06 mm**. Preserve **BMAX** header and
  **3.3 +/-0.5 mm** entry together without resolving their dimensional meaning
  or creating a footprint guarantee. Soldering in any position refers separate
  handling instructions not audited here; no installed thermal coupling follows.
- `ntcle100-sense-07`: selected **JB0** is in the source's RoHS-compliant-with-
  exemption column; **JB0A** is the distinct preferred-new-design column.
  This is not a current regulatory assessment, discontinued/NRND statement or
  qualified substitution. Discontinuation and replacement qualification remain
  unknown.

## One explicitly synthetic filled case

Every number in this paragraph is an invented scenario input, not user-board
information, a selected component value or an approved operating point. Assume
for discussion only a **nominal 3.3-V DC** supply, a **nominal 10-kohm** upper
resistor, the exact NTC from the divider node to return, an object target of
**25 C**, nominal ambient **25 C**, desired indicated accuracy **+/-1 C**, and
an acquisition request of **one sample per second**. These invented nominal
values do not establish actual element temperature or electrical bounds.

| Category | Filled synthetic entry and remaining unknowns |
|---|---|
| Manufacturer evidence | Exact no-A NTC identity and the conditioned facts above; no alternate suffix assumed. |
| Assumed inputs | Only the explicitly synthetic topology and nominal values in the paragraph above. |
| Excitation/electrical unknowns | Supply limits, resistor tolerance/drift, actual excitation and fault waveform, reference correlation, ADC/loading/leakage and settling are unknown. |
| Thermal unknowns | Object-to-sensor contact, element temperature, gradients, airflow/enclosure/PCB heating, self-heating and installed time response are unknown. Nominal ambient does not set element temperature. |
| Conversion/error unknowns | R-T conversion and its validation, calibration, aging, required error coverage and allocation are unknown. A 1-Hz sampling request is not a sensor response guarantee. |
| Analysis still required | Bound operating power without promoting plot points to a new allowance; justify installed thermal behavior and full conversion/acquisition/calibration error budget before testing any accuracy or response requirement. |

No computed temperature, operating power allowance, error bound, response pass,
resistor recommendation or circuit qualification is delivered. The 5% R25 and
0.75% B25/85 entries do not prove the synthetic +/-1-C goal. Keep all warnings
below even if the input fields are later completed.

## Complete unresolved warnings

- `ntcle100-excitation-thermal-inputs-unknown` — `UNRESOLVED_APPLICATION_INPUTS`: Actual excitation waveform/duty, dissipated power, ambient/contact medium, PCB heat sources and airflow are missing. Informational dissipation factor and response do not guarantee self-heating or response time; derating and zero-power conditions remain applicable.
  Historical provenance: `agent:/root/continue_ntc_collection/curate_ntc_source`, `2026-10-28T22:59:57.951496+00:00`.
- `ntcle100-conversion-accuracy-inputs-unknown` — `UNRESOLVED_APPLICATION_INPUTS`: Resistance tolerance and B25/85 tolerance do not complete a temperature-error budget. Calibration, selected resistance-temperature conversion, reference/ADC/divider errors, operating range, aging and mounting remain unspecified; no computed temperature accuracy is certified.
  Historical provenance: `agent:/root/continue_ntc_collection/curate_ntc_source`, `2026-10-28T22:59:57.951496+00:00`.
- `ntcle100-mounting-suffix-scope` — `SOURCE_SCOPE_LIMITATION`: No specified coating insulation or potted-use suitability; separate handling instruction is referenced but not audited. Exact no-A orderable is not the preferred A-column version, but discontinuation and qualified substitution remain unknown. No lifetime, safety or regulatory approval follows from this intake.
  Historical provenance: `agent:/root/continue_ntc_collection/curate_ntc_source`, `2026-10-28T22:59:57.951496+00:00`.

## Reproducible retrieval, not circuit evaluation

Run from a clean detached checkout of the pinned technical commit above.
Author separately replayed the same commands on current drafting base
`0a2de5daf023de3f770299cca8d3ab3fe5a0973a`;
source JSON and all full stdout bytes are identical. Latest-head replay does
not rewrite the pinned receipt. Literal command hashes use UTF-8 without a
trailing newline; stdout hashes include the final newline.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ntcle100-vishay-29049-20250507-10k5pct
```
Command SHA-256: `2ec908ef9bfffb3a6596212728bb05731eb4ce4e51624fe007e93c39093715b1`.
Full stdout SHA-256: `2ba3d15e628c7d4e5c2b59fcf8f7d67b51667fb49904de8197342f61314dbab1`.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id ntcle100-vishay-29049-20250507-10k5pct
```
Command SHA-256: `a4cd30f7397477574a6f9e6def061458eb60e25cba4d5cfec8641f7a33d2b37d`.
Full stdout SHA-256: `a94b9955d85c13a55e6b577b5660241f23173598048c5ae3f6e61b241d8fdd24`.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ntcle100-vishay-29049-20250507-10k5pct --device NTCLE100E3103JB0A
```
Command SHA-256: `5624aa4cb7f4b4a84edcc354987350b2dea6f5b1ecc7cb32b196dbc6efe52b71`.
Full stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ntcle100-vishay-29049-20250507-10k5pct --device NTCLE100E3103GB0
```
Command SHA-256: `ac926a658639b3e52329d14f212670b6fa5859b0ab24909cb3642262c955e74a`.
Full stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id ntcle100-vishay-29049-20250507-10k5pct --package 0603
```
Command SHA-256: `1001ca2b4cf2d658a841856afda6bfdb0cb6bb2b83762b7b23139550a729ef9f`.
Full stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

The first command selects all seven complete `ntcle100-sense-01` through `07`
facts and source metadata/attached warnings; the second selects the three full
warnings named above. The final three conjunctions select no candidates:
JB0A has the excluded A suffix, GB0 has G rather than J tolerance, and 0603
is not the exact radial bead package. Exclusions follow exact structured identity,
not substring matching. Empty retrieval means absent scoped evidence, not
compatibility, safety, incompatibility or global absence. Exit zero, selected
IDs/counts and matching bytes do not evaluate the invented circuit.

The [distinct review receipt](ntcle100-temperature-sensing-review.md) records
independent complete-payload checks and final card hash. Publication gates and
exact-commit CI are recorded in [issue #34](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/34).
