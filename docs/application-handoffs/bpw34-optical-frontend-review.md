# BPW34 optical-front-end card: independent metadata review

- Author: Agent `/root/document_photodiode_application_inputs`.
- Reviewer: Agent `/root/document_photodiode_application_inputs/review_bpw34_application_card`.
- Review completed: 2026-10-29T02:28:25Z.
- Result: PASS for the bounded application-input handoff; no technical corrections required.
- Final [card](bpw34-optical-frontend.md) SHA-256:
  `37102c612c458d8a2555cabcfbb51b165caba7d827ee548417f1baecf9f3fbad`.

## Independent replay and payload comparison

I executed all five literal recipes in the card in a clean detached checkout of
`98d7ca5eba5865967afca2a1fd379307acdd0d41`, and separately against current base
`f3200aa2e4822c80208b3a7e591976477c86b3ae`. All ten executions exited 0.
Every command UTF-8 hash (no newline) and complete stdout hash (including newline)
matched the card. The current and pinned source JSON bytes both hash to
`f495129cc4068f6519883de8b3c81d962ee6e727e5476d30efc7efc463dbe6bb`.

I compared all seven complete fact objects (`bpw34-photodiode-01` through `07`),
the complete source object, and all three complete warning objects against the
pinned JSON, including values, conditions, evidence, provenance, status and
unknowns. CLI warnings are sorted differently from the source array; comparison
by exact ID preserves complete object equality rather than mistaking order for
content. The card's three JSON warning blocks exactly match the original array.
Consumer results retain `canonical: false` and `NOT_LOCALLY_VERIFIED`; historical
source/fact human-review flags remain false.

The three negatives are justified by the exact structured identity, independently
of their empty outputs: BPW34 differs from BPW34S, Vishay Semiconductors differs
from Bourns, and leaded top-view clear plastic differs from SOT-23. All yield `[]`
plus newline, only scoped evidence absence, never compatibility or safety.

## Full-card interpretation review

The card separates the radiometric and photometric tests and their missing
maximums/spectrum; preserves dark-current bias/temperature, distinct capacitance
bias rows, typical response setup and unknown pulse/threshold details; and keeps
typical spectral/angular values separate from installed optical acceptance.
Absolute voltage, conditioned power and copper-wire thermal data are not promoted
to recommended bias or assembled performance. Exact bulk non-automotive identity,
area tolerance, footprint and certificate limitations remain visible.

The blank card covers optical, analog, ADC, supply/headroom, environment and
calibration inputs. Its single explicitly synthetic 3.3 V / 25 C / 1 kHz case
leaves the unprovided spectrum, intensity, topology, bias, feedback, ADC and error
requirements unknown. It computes no photocurrent, lux conversion, feedback
resistor, bandwidth, stability or accuracy and does not resolve any warning.

## Limits

I read existing repository annotations, historical review and the source-access
observations only. No manufacturer site, PDF, HTML, local original, extracted
source or image was accessed. Historical PDF hash/visual/source-review claims
remain attributed provenance, not a fresh byte audit or renewed access clearance.
This is distinct Agent review, not human, canonical, calibrated-sensor or circuit
acceptance. Repository gates, remote publication/readback, exact-commit CI and
independent maintainer acceptance remain separate receipts on issue #36.
