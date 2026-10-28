# Legacy polymer PTC condition evaluation

This batch documents the exact Bourns MF-MSMF050-2 legacy polymer PTC; it is not
a new-design recommendation, a one-shot fuse replacement or protection-system
certification. The electrical source revision BE, 09/26 is separate from its
08/26R legal appendix. The page-1 graphical warning marks the base model as not
recommended for new designs; text-only extraction did not preserve that symbol.
See the [source review](../knowledge/intake/bourns-mf-msmf050-ptc-constraints-review.md)
for actual-byte identity, rendered-page inspection and independent review.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-ptc.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_ptc_replay -v
```

The small successor delta stores only one new source pin and 30 recipes; it
references the immutable current-sense manifest by exact SHA-256. All preceding
618 recipes and 30 source pins remain inherited, not copied or rewritten. The
resolved aggregate is 648 retrieval cases plus the unchanged six dispositions.
Thirty additions include seven exact parameters, all facts, all warnings, three
kind selections, twelve negative fact selections and six negative warnings.
Expected IDs come from the reviewed records, not blindly refreshed CLI output.

## Boundaries that must survive retrieval

- The 23 C hold and trip currents have different meanings. The timed-trip test
  uses a much higher stated current; its maximum delay is not the delay at Itrip.
- Hold-current temperature points are specific tabulated conditions. They do not
  establish an unknown board temperature or arbitrary interpolation guarantee.
- Vmax and Imax retain their source labels. The cited table does not identify
  AC versus DC; a fuse-style interruption rating or continuous-current allowance
  must not be invented.
- Typical tripped dissipation is not maximum dissipation or zero residual current.
  Reset time, recovered resistance and application residual current remain unknown.
- Temporary-fault scope and mechanical expansion warnings do not establish repeated
  fault endurance, a potting material or a numerical enclosure-clearance approval.
- The no-new-design warning and exact -2 packaging scope remain visible. A slash
  voltage option, current variant, package or replacement part is not substituted.

Negative queries test wrong source identity, vendor, voltage option, current,
package and packaging. Missing timed behavior at the trip threshold, zero-current
isolation, recovery time, AC voltage and new-design replacement remain missing.
No-match is unavailable scoped evidence, not an electrical safety verdict. Full
candidate payloads must preserve conditions, provenance and all three warnings;
lexical matching or ID counts alone do not validate an engineering answer.

Synthetic tests use invented PTC identities and values, not copied datasheet
ratings. Each semantic mutation starts from a fresh copy of genuine CLI output,
with immutable baselines and unchanged fixture bytes. Successor tests preserve
all inherited pins/cases and check exact accepted pair identity. Source acceptance,
local replay, final repository gates and exact-commit CI are separate checks.

Original PDF, extracts and renders stay local; no source table, artwork or raw
original is committed or packaged. This is independent Agent review under owner
delegation, not human review, canonical approval or mains/battery safety approval.


Final local verification on 2026-10-28: English/public/vendor/workspace guards,
config/build/test/authority, aggregate replay and package all passed. Build and
test each ran 409 tests without skips; 654 aggregate cases passed (648 retrieval
and six unchanged dispositions). Fifty synthetic same-ID mutations are included
in the three focused tests. This verifies preservation, not protection adequacy.
Remote exact-commit CI is checked after publication and is not inferred here.

Accepted JSON SHA-256: `e9f8629bc2504c1999be2512248a51ffabeeb37ec2c4d99b8ec62c405ce48835`.
Source-review receipt SHA-256: `5dda5a7f2a4cf1c32b8553df32297780e14a7401bbd44a46e55a16097742c726`.
Original PDF SHA-256: `50d80228581842471d563e28ba0f1b67ab095ee95dfac4079f4a49f7f7bbf3c8`
(1,327,051 bytes, 16 pages, not redistributed).

Independent integration reviewer
`agent:/root/resume_compact_evaluation/review_ptc_integration` accepted the exact
source pair, all inherited cases/pins, the 30 new recipes and full conditions.
The reviewer independently ran 654 CLI cases and three focused tests, inspected
78 unchanged historical paths and checked every final package payload and hash.
Package SHA-256 is `e3e8543d86245a8b2a032e11541319525f8a3d8f4f489b25441e63b4503795c2`;
all 37 members are JSON (36 payloads), with no original source or review prose.
