# Exact-orderable low-voltage MOSFET drive evaluation

This successor adds six original annotations for Vishay Siliconix
Si2342DS-T1-GE3, SOT-23 (TO-236), electrical revision S11-1388-Rev. A
(11-Jul-2011). The separate legal appendix date is not an electrical revision.
The distinct [source reviewer](../knowledge/intake/si2342ds-low-voltage-drive-constraints-review.md)
verified the unchanged original hash and independently rendered cited pages 1/2.
Acceptance is Agent review under owner delegation, not human review, canonical
approval, electrical qualification or assurance of the latest revision.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-low-voltage-mosfet.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_low_voltage_mosfet_replay -v
```

All 533 preceding retrieval cases and 27 pins remain unchanged. The 26 new
source-informed recipes consist of six exact parameter selections, the complete
six-fact selection, the complete three-warning selection, two distinct kind
selections and 16 negative selections. Wrong vendor, device, orderable suffix,
package and revision-encoded source identity return no candidate; recommended
operating envelope, guaranteed hot resistance, qualified PWM frequency and
complete CAD footprint are not fabricated. The manifest has no revision filter;
revision-encoded source selection is not a test of the separate CLI revision flag.
Expected IDs are selected from reviewed raw records, not copied from CLI output.
Complete-payload equality checks conditions, provenance, unknowns, warnings and
nonverification rather than treating lexical or identity hits as correct answers.
An empty candidate set is neither engineering permission nor absence of risk.

## Engineering distinctions exercised

- Threshold voltage is measured at a small drain current, not proof of useful
  load enhancement. The two low-voltage resistance rows retain gate-source
  voltage, drain test current, temperature, pulse length and duty limitations.
- Typical and maximum resistance/charge remain separate. The resistance test
  currents are not approved continuous assembled-board currents; hot resistance
  is unknown, not interpolated from room-temperature guarantees.
- The drain stress maximum is not a recommended rail. This 8 V part does not
  become suitable for a 12 V exposure or interchangeable with AO3400A.
- Short-duration and steady-state junction-to-ambient values differ from the
  drain-foot reference; board setup is part of their applicability.
- Charge at a 2.5 V gate drive is not a 1.8 V charge/switching-time guarantee or
  a PWM frequency qualification. Design guarantee is not production testing.
- Actual driver waveform, source bounce, overvoltage, switching loss, thermal
  environment and continuous-current qualification remain missing inputs.
- Poppler recovered a missing xref object in memory. Legible reviewed pages do
  not imply a clean original container or complete page/bounding-box review.

The synthetic replay uses invented identities and numbers, never manufacturer
rating fixtures. Thirty-nine same-ID semantic mutations must fail, including
conflated typical/maximum values, omitted test conditions, upgraded unknowns,
changed thermal reference, production-test claims, removed warnings, canonical
promotion and invented local evidence verification. Exact source-pair hash tests
also preserve the accepted handoff and historical recipes.

## Verification scope

The focused three-test suite passes without skips. On 2026-10-28, all ten local
gates passed: English, public-source boundary, pinned vendor, workspace, config,
build, test, authority, aggregate replay and package. Build and test each ran
389 tests without skips. The first build exposed two stale active-CI manifest
assertions; only their successor selector was updated, with historical and
disposition assertions retained. The full gates were then rerun successfully.
Exact-commit remote CI remains a separate post-publication check, not a claim
inferred from these local results. The actual aggregate replay passes 565/565 cases: 559
retrieval cases plus six unchanged disposition cases, covering 28 batches,
40 batch-local source scopes and 270 annotations.
Historical receipts, owner acceptance, all earlier intake bytes and the separate
MCP23017 disposition remain unchanged. Original PDFs remain local and untracked;
no source document, table or artwork is included in Git or the package.

| Item | SHA-256 |
| --- | --- |
| Reviewed JSON | `7dee5cb9349c408a9dc01b39edd6b65bfe6f93f5429b17f13146dd0ae3b1664a` |
| Independent source review | `fa098769edd9833674a2cb8f4b76fc2c3c2331c2638079726c7cc10a8a1dbc60` |
| Original PDF (208,998 bytes; 9 pages; not redistributed) | `eba3913f3b9856077dd8ba9b1e81d691fbe958c759075b89ff7fcb605f0e0a03` |
| Successor manifest | `1417b54784e5aa739c71b9d5272d45b0ddebd48fbc36706f1b0b7696e57209f4` |
| Intake dataset | `91405840bb93e02ac7a1f092c08072b7719d946313520c65cfa08384eeb2134d` |

Independent integration reviewer
`agent:/root/continue_pcbknowledge_iteration/review_mosfet_integration`
verified the 565-case replay, the three mutation tests, 72 unchanged protected
historical paths and the final eleven-file scope. This review is separate from
the source reviewer named in the paired receipt; neither claims human approval.
The data-only package `PcbKnowledge_de8b5d3be3478272.zip` has SHA-256
`e2a310568a000b38e6887b18cdc5bfceab2c016f7c835cf1911a18d279bd074f`:
34 JSON members (28 intake batches, one disposition, workspace, three schemas
and manifest). All 33 payloads match the worktree and manifest size/hash entries;
no originals, images, code or review prose are packaged.
