# Exact-bin optocoupler condition evaluation

This successor is scoped to the eight original VO617A-3 standard DIP-4
annotations. It is not a safety certification, circuit design, complete component
model or canonical/human approval. The selected electrical source is Vishay
Semiconductors document 83430, Rev. 2.8, 22-Jan-2025; the separate legal appendix
date is not an electrical revision. The exact accepted pair and source-review receipt (`git show intake-final:knowledge/intake/vo617a-3-optocoupler-logic-constraints-review.md`)
are pinned following distinct independent review, not inferred from retrieval.

## Reproduce

```bash
python3 configs/pcbknowledge_intake_eval.py --repo . \
  --cases evals/intake-retrieval-optocoupler.json \
  --dispositions evals/intake-dispositions-2026-10-28.json
PYTHONPATH=src:. python3 -m unittest tests.git_native.test_optocoupler_replay -v
```

The compact successor references the exact immutable low-voltage MOSFET manifest
by relative filename and SHA-256, inheriting all 559 preceding recipes and 28
dataset pins. It stores only one new pin and 30 new cases; the evaluator resolves
the complete 589-case manifest before normal validation and execution. Thirty
new recipes select each of the eight exact parameters, all eight facts, all
three warnings, the stress-only kind and six electrical-characteristic records.
Eighteen negative selections reject a different source revision identity,
manufacturer, CTR bin, missing bin, option suffix or package; recommended drive,
guaranteed logic-low sink, hot leakage, qualified saturated delay, chosen LED
resistor and continuous working-voltage approval are not synthesized.
Expected IDs are selected from raw reviewed records, not CLI output. Exact
revision-encoded source identity is not a claim to test the separate CLI revision
filter, which the aggregate manifest does not support.

Complete-payload comparison is essential: lexical or ID retrieval alone cannot
show whether the answer retained the manufacturer test conditions or unknowns.
The following decision boundaries are explicitly preserved:

- Bin 3 CTR at 5 mA LED current and 5 V collector-emitter voltage is not a
  guaranteed saturated logic-low sink, lifetime minimum or another bin's rating.
- LED forward-voltage limits at 60 mA cannot supply a missing 5 mA design bound.
  Supply, driver, current, temperature and resistor tolerances remain inputs.
- Saturation voltage at 1 mA collector current is separate from the CTR test;
  it does not establish the same voltage limit at 5 mA collector current.
- Bin-specific leakage retains its voltage and ambient conditions; hot leakage
  and receiver high-state margin remain unknown.
- Non-saturated switching is typical only. Circuit load, scope impedance,
  generator impedance, pulse width and duty are distinct conditions, not an
  approved logic rate or worst-case delay for a different circuit.
- The saturated table's 5 mA and Figure 3's 10 mA LED-current labels conflict.
  Both locations remain recorded; neither is silently selected as correct.
  Reconciled current and qualified saturated delay remain null, pending
  manufacturer clarification or independent characterization of the intended
  circuit. A conservative use restriction is not a repaired manufacturer source.
- Family isolation claims and option-specific approvals do not establish the
  standard part's application safety or continuous working-voltage approval.

Synthetic tests use invented identities and numbers, not source rating fixtures.
Fifty-three same-ID semantic mutations must fail, including CTR-bin substitutions,
active-region/saturation confusion, typical/maximum conflation, current or load
condition loss, scope/circuit-load substitution, invented hot/lifetime guarantees,
choosing either side of the source conflict, invented qualified delay, warning
removal and canonical/local-verification promotion.

## Verification scope

The first, copied-full-manifest candidate passed 595/595 aggregate cases and
392 tests in each build/test gate, with independent integration and package
review. Publication of its redundant 187 KB manifest was blocked by auto-review;
no commit or remote update resulted. Those results describe that prior candidate,
not the revised runtime or compact manifest.

The replacement is genuine immutable-base composition, not file splitting: only
30 new cases and one new source pin are stored, with the existing manifest
referenced by exact hash. Independent runtime/integration review, full 595-case
replay and repository gates must be rerun for this changed design. Earlier
11-file scope and 392-test counts are not current verification receipts.
Remote CI is checked only for the exact published commit; local results cannot
establish a terminal CI result. Source-pair bytes, historical manifests, owner
acceptance and the MCP23017 disposition remain unchanged. No original PDF, table
or artwork is included in Git or the package.

| Item | SHA-256 |
| --- | --- |
| Reviewed JSON | `adc2ce86339add3ad91ee96225abdc2bc4343dd6e994afc0e4e50f35ae60e64c` |
| Distinct source review | `60d562758d2dea912416a199fe6fe9fe4b37fb5d36c4fc5452b502d26fd72da3` |
| Original PDF (237,004 bytes; 11 pages; not redistributed) | `145893b5422f68cc3f2016e2dddfc33f6ee26f0d2444fe8889d0dc0388f805a1` |
| Successor manifest | `a6191cadb9eb2ce6ba4704e3aaa8e013e9ad5a39dce67bf79b582ccb61ecf2c3` |
| Intake dataset | `78cfe976278cb5e8a14ba75342fd92674fd45014bc799e83027a7dc835b1085f` |

The earlier integration review and metadata-only package inspection applied to
the prior copied-manifest candidate. They do not substitute for independent
review of composition, resolved payload equality, inherited pins or the current
publication scope. Revised verification results will be recorded after execution.

The revised compact candidate was independently reviewed by
`agent:/root/continue_pcbknowledge_iteration/review_revision_filter`:
its 10,191-byte delta resolves to exactly the archived candidate's 589 cases and
29 pins, and the real CLI replay passes all 595 cases including six dispositions.
The old/new reports are identical except the root-manifest hash and explicit
base-dependency receipt. Fourteen focused composition/optocoupler tests pass,
including 53 same-ID semantic mutations. The unchanged accepted source pair
retains its separate source reviewer. This verifies compact composition and
retrieval parity, not yet the full revised repository gates or remote CI.

A prior compact-package attempt correctly refused publication after a concurrent
Windows-path correction made its validation receipt stale. It was not a passing
package result; a fresh full-gate run is required for the final unchanged tree.

Final compact-candidate verification on 2026-10-28: all ten gates passed on the
unchanged runtime (English, public boundary, vendor, workspace, config, build,
test, authority, 595-case aggregate and package). Build and test each ran 403
tests without skips. The data-only package remains
`PcbKnowledge_8d20adf46d0c02cc.zip`, SHA-256
`376401c32b5561f79534ab16b4a72f3eba6d3b2281b9ffddd18fa55a1b3fd303`;
the evaluation representation did not change its 35 JSON members or 34 payloads.
No originals, images, runtime code or review prose are packaged. Exact published
commit CI remains a separate post-publication check, not inferred here.

Final independent integration reviewer
`agent:/root/continue_pcbknowledge_iteration/review_mosfet_integration`
rechecked source-pair, delta, base and dataset hashes, unchanged historical
136 paths, final thirteen-file scope and every package payload/hash entry after
the fresh gate run. Runtime/path safety review is the separate actor recorded
above; neither review claims human or canonical approval.
