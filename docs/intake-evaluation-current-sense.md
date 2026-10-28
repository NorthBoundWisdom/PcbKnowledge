# Current-sense resistor condition evaluation

This increment adds six original WSLP2512R0100FEA annotations, not a qualified
current-sensing circuit. The exact 10-milliohm, 1% part uses the Vishay Dale
30122 electrical source dated 09-Sep-2024; the legal appendix date is distinct.
The [independent source-review receipt](../knowledge/intake/wslp2512-current-sense-constraints-review.md)
records actual PDF bytes, rendered pages and the separately hashed official
identity HTML. Neither ordinary retrieval nor this integration re-audits the PDF.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-current-sense.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_current_sense_replay -v
```

The 9,596-byte delta references the immutable optocoupler manifest by SHA-256,
inheriting all 589 preceding cases and 29 pins. Only one new source pin and 29
recipes are stored: six exact parameters, all facts, all warnings, three kind
selections, twelve negative fact selections and six negative warning selections.
Expected IDs derive from reviewed source scopes, not refreshed CLI output.
The resolved collection is 618 retrieval cases plus six unchanged dispositions.

Negative selections exclude a different source identity/revision, manufacturer,
resistor family, resistance, package or packaging suffix. Missing recommended
operation, qualified continuous/pulse current, system accuracy, complete footprint
and lifetime drift claims remain missing. An empty selection is not a circuit
safety determination. Full candidate payloads, conditions, provenance and all
three warnings must remain intact; lexical/ID matching alone is insufficient.

## Engineering distinctions preserved

- Component TCR includes terminals and is not the alloy element's smaller value.
  Initial tolerance and TCR are not total sensing-system accuracy.
- P70 and an ambient derating plot are conditioned references, not an approved
  board power or current without thermal implementation and operating data.
- Working voltage depends on applicable power/energy conditions; no independent
  pulse or current rating is calculated from the formula.
- Terminal dimensions depend on resistance. A typical sensing-trace sketch is
  not a four-terminal component, complete footprint or guaranteed trace error.
- Load-life change retains the additive resistance term, durations and ambient.
  It is neither initial tolerance nor a lifetime/system-accuracy guarantee;
  unlisted applied test power is not filled in from the power rating.
- An illustrative pulse plot does not establish a numerical pulse envelope.

Synthetic fixtures use invented values, not copied source tables. Forty-nine
same-ID mutations must fail for lost conditions, unsupported numerical upgrades,
wrong kind/device/package, absent warnings and canonical/verification promotion.
Each mutation starts from a fresh deserialization of an immutable genuine CLI
baseline; fixture bytes remain unchanged. A separate successor test pins the
accepted source/review pair and preserves every inherited recipe and source pin.

## Scope and verification

Only small original facts, annotations and review metadata are published. The
original PDF, HTML, complete extracts and rendered pages remain local and are
not packaged. Source review is independent Agent review under owner delegation,
not human, canonical or circuit approval. No old source, warning, disposition,
owner acceptance or historical manifest is rewritten.

Source JSON SHA-256: `91abaf2e01f2cbd092e2e4e33f194a59bacf1eebcb33aeb07ff28b1ef775414b`.
Source review SHA-256: `b634a27fc8cf901ac3c55ecb9d125bc28171d902189f0c8856aec44bc1eaa262`.
PDF SHA-256: `d3dd7b4f590e713c84303e32530e8c8c6fd025617896e11d25599521771e4c13`
(146,445 bytes, five pages; not redistributed).

Final independent integration review, repository gates and exact-commit CI are
separate checks; source acceptance and local focused tests do not establish them.

Final local verification on 2026-10-28: all ten repository gates passed (English,
public boundary, vendor, workspace, config, build, test, authority, aggregate and
package). Build and test each ran 406 tests without skips; aggregate replay passed
all 624 cases including the unchanged six dispositions. Exact remote CI remains
a separate post-publication check. The source pair and inherited history are
unchanged; later local verification does not add a human or canonical approval.

Independent integration reviewer
`agent:/root/resume_compact_evaluation/review_current_sense_integration` accepted
the final scope after independently replaying all 624 cases, running the three
focused tests/49 mutations and checking the complete pair and inherited payloads.
The 76 historical source/evaluation/owner/disposition paths remain unchanged.
The package has 36 JSON members (35 payloads) with verified sizes and SHA-256
entries, no originals or review prose; package SHA-256 is
`070b1cd689c95cc2d574bae553759ca29e48b4ab1d5eed4d70a154324699beff`.
