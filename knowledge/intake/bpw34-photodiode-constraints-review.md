# BPW34 photodiode conditions

Seven small original annotations cover exact Vishay BPW34 bulk, leaded top-view
clear plastic, non-automotive. This is noncanonical source-bound knowledge,
not a calibrated sensor, transimpedance-amplifier design or ADC guarantee.

## Actual source and rights boundary

- Official PDF: https://www.vishay.com/docs/81521/bpw34.pdf
- Electrical document 81521, Rev. 2.1, 23-Aug-11, pages 1-4.
- Downloaded PDF: 113,384 bytes, five pages; SHA-256
  `848a480a7dabad95338765a9d6646ca25223db77c4f426aa5218eb7778687c65`.
- Page 5 legal notice 91000, 01-Jan-2026, is not a new electrical revision.
- Official identity HTML: https://www.vishay.com/en/product/81521/tab/quality/,
  763,187 bytes; SHA-256
  `6144b7f61582f54fb07d23dfb764d7b7e7659a2f2c24c36791fc8ed4473c93dd`.
  Exact MAT_NO BPW34 equality and Non-Automotive classification verified;
  this does not establish stock, future supply or current certification.
- Collector `agent:/root/continue_ntc_collection/curate_zener_conditions`
  inspected actual rendered pages 1 and 2 including MIN/TYP/MAX alignment.

Legal page 5 was read before factual processing. Rights are reserved and no
intellectual-property license is granted; application validation is required.
No explicit prohibition of limited original factual annotations was identified.
No open license or redistribution permission is asserted. Original PDF/HTML,
text and rendered pages remain local untracked evidence, never Git or packages.
No whole table, source prose or artwork is copied. Bounding boxes are unknown.

## Engineering boundaries

- Irradiance at 950 nm and illuminance in klx are different conditioned rows;
  the photometric row does not name its test spectrum. Do not convert them
  into a universal lux/current/ADC calibration.
- Dark current retains typical and maximum values only at darkness, 10 V
  reverse bias and 25 C, not over the whole operating temperature range.
- Capacitance retains darkness, 1 MHz and separate 0 V/3 V bias conditions;
  the 40 pF maximum belongs to the 3 V row only.
- Response times are typical at 10 V, 1 kohm and 820 nm. Missing pulse amplitude
  and edge thresholds remain unknown; no TIA bandwidth or ADC settling claim.
- Spectral lambda_0.1 range, peak and angle are typical, not a flat passband.
- Absolute 60 V and conditioned power/thermal entries are not recommended bias
  or qualification of an installed optical/analog system.

All three full warnings preserve optical calibration, analog front-end inputs
and source/qualification limits. Ordinary retrieval stays NOT_LOCALLY_VERIFIED.

## Independent source review accepted

Draft JSON SHA-256: `8d5d073c32298164fb86e9ec4b5711336e7db5254e47020695cd75e95ecffe50`.

Final accepted JSON SHA-256: `f495129cc4068f6519883de8b3c81d962ee6e727e5476d30efc7efc463dbe6bb`.

Reviewer `agent:/root/continue_ntc_collection/curate_zener_conditions/review_bpw34_source` independently accepted at `2026-10-28T23:50:15.705713+00:00` after checking actual PDF/HTML hashes, exact BPW34 identity, rendered pages 1 and 2, and legal page 5. All seven complete facts and all three warnings were reviewed without technical corrections. The acceptance transition changes review/status metadata only; canonical and human flags remain false.

This is Agent review under owner delegation, not canonical approval, human review or circuit certification. Downstream integration, full gates, packaging and exact published-commit CI remain separate.
