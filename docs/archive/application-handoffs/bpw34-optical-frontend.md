# BPW34 optical-front-end application inputs

This handoff is a checklist, not a component selection, TIA design, calibrated
lux conversion or qualification. A complete input card still requires justified
analysis and validation; it does not resolve any existing warning.

## Evidence and access boundary

Technical baseline: `98d7ca5eba5865967afca2a1fd379307acdd0d41`.
Separate current-head replay base: `f3200aa2e4822c80208b3a7e591976477c86b3ae`.
Existing source annotations (`git show intake-final:knowledge/intake/bpw34-photodiode-constraints.json`)
and historical review (`git show intake-final:knowledge/intake/bpw34-photodiode-constraints-review.md`)
are the only engineering evidence used. Source ID is
`bpw34-vishay-81521-r2p1-bulk`; source JSON SHA-256 is
`f495129cc4068f6519883de8b3c81d962ee6e727e5476d30efc7efc463dbe6bb`.

Exact identity: Vishay Semiconductors BPW34, bulk, non-automotive, package
`Leaded top-view clear plastic`; BPW34S tube is excluded. Document 81521,
electrical Rev. 2.1, 23-Aug-11 is distinct from the 2026 legal notice and carries
no current-revision guarantee. Historical PDF SHA-256
`848a480a7dabad95338765a9d6646ca25223db77c4f426aa5218eb7778687c65`
is recorded provenance, not fresh byte evidence.

Follow the [source-access observations](../source-investigations/source-access-observations-2026-10-29.md).
No manufacturer URL, PDF, HTML or local original was visited/read for this card;
no new manufacturer fact or source-access reassessment is made. Historical URLs,
visual flags and review statements in the unchanged metadata describe earlier
work only. Retrieval remains `canonical: false`, `human_reviewed: false`,
`NOT_LOCALLY_VERIFIED`; earlier Agent acceptance is not new human acceptance.

## Blank input card

For every supplied answer record supplier/owner, date, evidence reference,
units, tolerance/range, measurement method and whether measured or assumed.
Use **unknown** rather than an inferred nominal value. Separate manufacturer
facts below from application data and proposed analysis.

| Input group | Questions to answer | Supplied answer / evidence |
| --- | --- | --- |
| Identity and mounting | Exact orderable/packing, package and polarity? Mechanical/optical mounting and connection evidence? | Unknown |
| Optical signal | Spectrum or wavelength distribution? Irradiance, illuminance or optical power definition, range and calibration? Spatial/angular distribution at the diode? | Unknown |
| Optical path | Lens, aperture, window transmission, alignment and coupling? Ambient/background/stray light, saturation exposure and modulation waveform/duty? | Unknown |
| Performance | Required bandwidth, settling deadline, signal-to-noise ratio and error definition over signal range and temperature? | Unknown |
| Bias and topology | Proposed diode bias range including transients, zero/reverse-bias topology, leakage paths and operating temperature? | Unknown |
| Analog front end | Exact amplifier, noise spectra, input leakage/offset/drift, feedback impedance and parasitics, total capacitance and stability analysis? | Unknown |
| Conversion | ADC/reference/range, acquisition time, resolution, sampling/alias filtering and settling requirements? | Unknown |
| Supplies and headroom | Rails and tolerance/transients, amplifier input/output headroom and overload/recovery behavior? | Unknown |
| Environment | Diode/junction/ambient temperatures, copper/wire mounting, heat sources and environmental variation? | Unknown |
| Validation | Optical/electrical calibration method, reference uncertainty, error allocation, temperature/time drift and validation coverage? | Unknown |

Remaining analysis: establish the actual optical transfer and uncertainty, then
justify front-end bias/headroom/noise/stability/settling and ADC acquisition
against those inputs. These are questions for modeling and measurement, not
results supplied by retrieval or this card.

## Existing conditioned manufacturer evidence

The selected IDs are `bpw34-photodiode-01` through `bpw34-photodiode-07`.
Their full objects, source metadata, evidence/provenance and attached warnings
are reproduced by the pinned search recipe below, not replaced by this summary.

- **01, identity:** 7.5 mm2 sensitive area has no recorded tolerance. It is not a
  calibrated installed collecting area, complete footprint, automotive grade or
  current compliance certificate. Exact BPW34 bulk is not BPW34S tube.
- **02, illumination:** at 25 C, 1 mW/cm2 at 950 nm and 5 V reverse bias gives
  40 uA minimum / 50 uA typical, with maximum unknown. Separately, 1 klx at 5 V
  gives 75 uA typical with minimum/maximum and test illuminant spectrum unknown.
  These are not universal radiometric/photometric conversions or installed-current
  guarantees; 50 uA is not a maximum.
- **03, darkness:** 2 nA typical / 30 nA maximum is at 10 V, darkness and 25 C.
  It is not a full-temperature or lower-bias guarantee, nor a complete front-end
  offset/noise allowance. No temperature plot is digitized.
- **04, capacitance:** darkness, 1 MHz and 25 C apply to both rows: 70 pF typical
  at 0 V (maximum unknown), versus 25 pF typical / 40 pF maximum at 3 V.
  The 40 pF maximum does not apply at zero bias. Diode values are not total
  input capacitance, constant over bias or evidence of TIA stability.
- **05, response:** 100 ns typical rise and fall times belong to 10 V, 1 kohm,
  820 nm and 25 C. Maximums, optical pulse amplitude and edge thresholds are
  unknown. They do not establish TIA bandwidth, ADC settling or a system deadline.
- **06, spectrum/angle:** at 25 C, 900 nm typical peak, 430–1100 nm typical
  lambda_0.1 relative-response band and +/-65 degree typical half-sensitivity
  angle do not imply a flat response, calibrated lux sensitivity or complete
  optical acceptance of an assembly.
- **07, absolute boundaries:** 60 V reverse absolute maximum is not recommended
  bias or avalanche permission. 215 mW requires ambient <=25 C; junction maximum
  is 100 C and operating ambient range -40 to 100 C. The 350 K/W junction-to-ambient
  entry uses Cu wire of 0.14 mm2, not arbitrary PCB mounting. These entries do not
  qualify assembled power, thermal performance or full-temperature optical limits.

Missing guarantees remain separate from missing application inputs: no universal
illumination conversion, full-temperature dark-current bound, response-time maximum,
complete footprint or installed thermal/optical model is established here.

## One synthetic receiver case

Every number in this paragraph is an **invented synthetic application input**,
not user-board data, a source test or manufacturer recommendation: nominal
3.3 V supply, nominal 25 C ambient, and desired 1 kHz modulated-light reception.
The example names exact BPW34 bulk only; it does not select it as suitable.

| Filled field | Synthetic case state |
| --- | --- |
| Identity | BPW34 bulk, non-automotive, leaded top-view clear plastic; actual procurement and assembly evidence unknown |
| Supply / ambient / requested modulation | Synthetic values stated above; tolerances, transients, thermal variation and waveform/duty unknown |
| Spectrum, intensity and optical path | Unknown spectrum, intensity definition/range, spatial/angular distribution, optics/window and background light |
| Performance criteria | Unknown required bandwidth, settling, error and SNR; modulation request alone is not a bandwidth specification |
| Diode bias / front end | Unknown topology, operating bias, amplifier, feedback, leakage/noise and total capacitance |
| ADC / headroom | Unknown ADC, reference/range/acquisition, rail tolerance and analog headroom/recovery |
| Calibration / validation | Unknown reference method, uncertainty, temperature/time coverage and acceptance criteria |
| Input provenance | Scenario invented by the author for this card on 2026-10-29; no measured board evidence |

No photocurrent, lux conversion, feedback resistor, bandwidth, stability or
accuracy is computed. Neither the conditioned optical-current rows nor typical
response times fill these gaps. Optical calibration and front-end performance
remain unknown; the example is not circuit suitability or safety approval.

## Complete unresolved warnings

The following existing warning payloads retain status and provenance unchanged.
Neither filling the card nor a successful command closes them.

```json
{
  "id": "bpw34-optical-calibration-unknown",
  "source_id": "bpw34-vishay-81521-r2p1-bulk",
  "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
  "description": "Actual spectrum, irradiance or illuminance distribution, optical window/geometry, angle and calibration are missing. Radiometric and photometric rows cannot supply a universal conversion or guaranteed installed photocurrent.",
  "provenance": {
    "actor": "agent:/root/continue_ntc_collection/curate_zener_conditions",
    "recorded_at": "2026-10-28T23:49:33.908194+00:00"
  }
}
```

```json
{
  "id": "bpw34-frontend-performance-unknown",
  "source_id": "bpw34-vishay-81521-r2p1-bulk",
  "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
  "description": "Amplifier topology and bias, feedback impedance, total input capacitance, leakage, noise spectrum, bandwidth, settling target, ADC range/resolution and temperature are missing. Conditioned typical diode data do not establish TIA stability, signal-to-noise ratio or ADC accuracy.",
  "provenance": {
    "actor": "agent:/root/continue_ntc_collection/curate_zener_conditions",
    "recorded_at": "2026-10-28T23:49:33.908194+00:00"
  }
}
```

```json
{
  "id": "bpw34-source-and-qualification-scope",
  "source_id": "bpw34-vishay-81521-r2p1-bulk",
  "issue_status": "SOURCE_SCOPE_LIMITATION",
  "description": "Exact BPW34 bulk non-automotive scope only. Electrical revision 2011 and legal notice 2026 are different. No full CAD footprint, current compliance certificate, calibrated sensor model or system safety qualification is supplied. Unstated maximums, optical pulse amplitude and edge thresholds remain unknown.",
  "provenance": {
    "actor": "agent:/root/continue_ntc_collection/curate_zener_conditions",
    "recorded_at": "2026-10-28T23:49:33.908194+00:00"
  }
}
```

## Reproducible metadata-only recipes

Run from a clean detached checkout of the technical baseline above. Commands are
supported exact structured filters, not lexical evaluation of the scenario.
Command hashes use UTF-8 without a trailing newline; stdout hashes cover complete
UTF-8 output including the final newline. The separately labeled current-head
replay produced identical complete bytes for all five commands.

### Recipe 1

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id bpw34-vishay-81521-r2p1-bulk
```

- Command SHA-256: `3f14a502b225a4894acbe87c4d5694ca1c0fb98c8a35ab9a32512efd35b4ba13`.
- Complete stdout SHA-256: `bf88ca5727ca7ba2b7a728814247bd6957bc2b6866d3a6d2e8cdd8b7da0b0ed4`.

### Recipe 2

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake issues --source-id bpw34-vishay-81521-r2p1-bulk
```

- Command SHA-256: `1aac294dc25f1787449e93e7128aa4399b533be51ca7f543b1ce1717a8dd0b34`.
- Complete stdout SHA-256: `00256244dd6b16d7187d237a6b9dd97eb01ca45bc89fb26868424e156b414245`.

### Recipe 3

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id bpw34-vishay-81521-r2p1-bulk --device BPW34S
```

- Command SHA-256: `834b627474fc003d60f5b74e84542011f4720cf835ef17232c76b3e61610cd0d`.
- Complete stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

### Recipe 4

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id bpw34-vishay-81521-r2p1-bulk --manufacturer Bourns
```

- Command SHA-256: `ebcd8e466592e1460b04c09700175ba1c771843c31385988cb313d2c66f74a13`.
- Complete stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

### Recipe 5

```bash
python3 -B configs/pcbknowledge_agent.py --repo . intake search --source-id bpw34-vishay-81521-r2p1-bulk --package SOT-23
```

- Command SHA-256: `980bc7cac6cf27faf7cf153612d475e355fae3b0c18e1a8cdc8b0f49d4cf7e23`.
- Complete stdout SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

Search selects exactly the seven IDs above, including all complete source/fact/
evidence/condition/warning objects. Issues selects the three complete warnings
listed above. Reviewer compares the full objects to the pinned JSON, not only
IDs/counts, lexical hits or exit-zero results.

The three negative conjunctions are independently justified by structured identity:
BPW34 is not BPW34S, Vishay Semiconductors is not Bourns, and the exact leaded
package is not SOT-23. Each returns `[]` plus newline. This means no candidates
in that scope only, not compatibility, incompatibility, safety or global absence.

Author: Agent `/root/document_photodiode_application_inputs`, 2026-10-29.
See the [distinct review receipt](bpw34-optical-frontend-review.md) for actual
reviewer identity, time, final document hash and limits. Full repository gates,
remote readback and exact-commit CI are separate publication receipts on issue #36.
