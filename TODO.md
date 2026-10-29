# TODO — PcbKnowledge Roadmap

> Status: `LIGHTWEIGHT_CURATION_ACTIVE_FORMAL_PILOT_OPEN`
> Updated: 2026-10-29
> Goal: expand reviewable knowledge around device-selection and setup-condition questions, preserving evidence limitations and the separate formal PDF/typed-authority pilot.

## Owner acknowledgement recorded without authority promotion

The [2026-10-29 record](docs/owner-acknowledgement-2026-10-29.md) captures the
owner's overall acceptance and continuation instruction against observed main
`c02a34081f2d2003f3ce7839d7d4922fef9a899e`. The owner supplied no itemized audit
inventory; snapshot counts are not per-item human review counts. Prior receipts,
intake fields, warnings, source restrictions and CI verification remain separate.
Future work is not accepted in advance.

## Scoped machine-readable intake handoff

- [x] Add a [read-only scoped bundle](docs/intake-bundle.md) with complete source,
  batch, candidate, warning and handling context and individually resolvable pins
  from one validated load. No lexical/fact-only filter can omit source warnings.
- Synthetic checks cover exact scope, empty sources, batch-local identity, full
  candidate parity, item resolution, byte/context drift, complete fingerprint,
  invalid queue/selector refusal and selected-workspace readonly CLI behavior.
  This is not an atomic snapshot, canonical export, original-byte verification,
  renewed owner approval or formal pilot completion.
- Local receipt (2026-10-29): 13 focused tests; final Build and Test each 474
  tests without skips; English/public/vendor, workspace, Config, Agent validate
  and Package gates pass. All 801 existing aggregate/disposition cases and 49
  source-scope bundle replays with 428 individual item resolutions pass, retaining
  37 batches / 329 facts. Independent Agent review found no blocking issue.
  Exact published-commit CI is checked separately after publication.

## Fixed synthetic INA219 register interpretation

The [register example](docs/worked-examples/ina219-register-scale.md) separates
signed shunt/current interpretation, bus status bits, unsigned power and
calibration-word quantization. It scales independently supplied synthetic codes,
not predicted chip arithmetic. Full existing source facts and warnings stay
pinned; CNVR wording remains unresolved and no fresh/coherent sample, analog
validity or total accuracy is certified. README now links the bounded practical
examples so their reproducible commands and limits are discoverable.
Independent review, full gates and exact-commit CI remain separate receipts.

## Fixed synthetic EEPROM transaction geometry

A [24LC256 page-write example](docs/worked-examples/24lc256-page-write-plan.md)
now evaluates complete fixed synthetic splits, address roles and whole-request
range refusal. It extends the existing short wrap-counter example rather than
claiming that page boundaries were previously untested. All seven existing
facts and three warnings remain pinned and unchanged. Geometry, valid WP-high
assumptions and matching-device ACK readiness never establish data persistence,
supply/WP timing, lifetime or circuit qualification. Independent review, full
gates and exact published-commit CI are separate receipts.

## Source-access prerequisites recorded

A bounded [source-access investigation](docs/source-investigations/source-access-observations-2026-10-29.md)
records why the proposed Vishay LED, Littelfuse fuse and TI application-resource
paths did not proceed. Observed website/use restrictions remain prerequisites,
not permission inferred from public availability or a product disclaimer.
No new facts from those candidates were accepted; historical batches stay intact.
Do not repeat these collection attempts without applicable authorization.

## Reviewed once-only fuse integration

The collection now contains 37 batches / 49 source scopes / 329 annotations.
Six SF-1206S050-2 facts bind the current product-linked Rev. 10/26 document,
not the older search-result PDF. Clearing specifications and reliability test
criteria remain distinct. Typical melting I2t does not establish total clearing
energy or system coordination; thermal and pulse inputs remain unknown.
See the [evaluation scope](docs/intake-evaluation-fuse.md). Independent source
and integration reviews, final gates and exact-commit CI remain separate receipts.

## Fixed synthetic NE555 model regression

The existing nominal astable worked example now has a fixed-input evaluator,
not a general circuit calculator. It binds four unchanged metadata batches and
preserves complete conditions and unresolved warnings. Rational checks separate
480 Hz from the reciprocal rounded period and label high versus low duty;
initial tolerance and typical sensitivities never establish hardware accuracy.
See the [worked example](docs/worked-examples/ne555-astable-model-bound.md).
Independent review, full gates and exact published-commit CI are separate receipts.

## Reviewed ferrite bead integration

At the ferrite stage the collection contained 36 batches / 48 source scopes / 323 annotations.
Five exact MH2029-601T facts preserve frequency, measurement amplitude, DCR,
current temperature-rise basis and graph limitations. Sixteen distinct recipes
extend immutable history, with full-payload semantic mutation tests.
See the [evaluation scope](docs/intake-evaluation-ferrite.md). Independent source
and integration reviews, full gates and exact-commit CI remain separate receipts.

## Reviewed photodiode integration

At the photodiode stage the collection contained 35 batches / 47 source scopes / 318 annotations.
Seven exact BPW34 facts retain illumination, bias, load, frequency, typical/limit
and unknown optical conditions; three warnings preserve application boundaries.
The compact successor inherits 738 retrieval cases and adds 26 justified cases.
Synthetic same-ID mutations protect full conditions, not lexical hits.
See the [evaluation scope](docs/intake-evaluation-photodiode.md). Independent
integration review, full final gates and published-commit CI remain separate.

## Reviewed Zener integration

At the Zener stage the collection contained 34 batches / 46 source scopes / 311 annotations.
Six exact BZX84C5V1-E3-08 facts preserve pulse/test-current voltage, conditioned
dynamic resistance, unpromoted leakage classification, temperature coefficient
and distinct absolute-power boundaries. Precision-reference and clamp suitability
remain unknown. A compact pinned successor adds 30 recipes without copying history.
See the [evaluation receipt](docs/intake-evaluation-zener.md).
Final local gates and exact published-commit CI are checked separately.

## Reviewed thermistor integration

At the preceding thermistor stage, the collection contained 33 batches / 45 source scopes / 305 annotations.
Seven exact NTCLE100E3103JB0 facts preserve R25/B tolerances, zero-power and
derating conditions, informational response and self-heating, coating limits
and exact-suffix design scope. Application accuracy remains unknown. A compact
hash-pinned successor adds 30 recipes without copying accepted history.
See the [evaluation receipt](docs/intake-evaluation-thermistor.md).
Final local gates and exact published-commit CI are checked separately.

## Reviewed aluminum electrolytic integration

At the preceding electrolytic stage, the collection contained 32 batches / 44 source scopes / 298 annotations.
Seven exact MAL214636471E3 facts preserve conditioned RMS ripple, impedance
versus ESR, initial versus post-test limits and case-specific life-test scope.
Unknown installed-board heating and field lifetime remain explicit. A compact
hash-pinned successor adds 30 recipes without copying accepted history.
See the [evaluation receipt](docs/intake-evaluation-electrolytic.md).
Final local gates and exact published-commit CI are checked separately.

## Reviewed legacy polymer PTC integration

At the preceding PTC stage, the collection contained 31 batches / 43 source scopes / 291 annotations.
Seven exact MF-MSMF050-2 facts retain its source no-new-design warning, conditioned
hold/trip/time-to-trip limits, temperature derating and unknown residual/reset
behavior. The source is not a fuse or safety-system qualification. A compact
hash-pinned successor adds 30 recipes without copying inherited history.
See the [evaluation receipt](docs/intake-evaluation-ptc.md). Final local gates
passed: Build/Test each 409 tests without skips and aggregate 654 cases.
Exact published-commit CI is checked separately after publication.

## Reviewed current-sense resistor integration

At the preceding current-sense stage, the collection contained 30 batches / 42 source scopes / 284 annotations.
Six exact WSLP2512R0100FEA annotations and three warnings retain component versus
element TCR, conditioned power, resistance-specific geometry, additive test drift
and unknown pulse/system accuracy. A compact hash-pinned successor adds 29 cases
without copying historical manifests. Prior 278 annotations and owner receipts
remain unchanged. See the [evaluation receipt](docs/intake-evaluation-current-sense.md).
Final local gates passed: Build/Test each 406 tests without skips, and all 624
aggregate cases. Exact-commit CI is checked separately after publication.

## Reviewed exact-bin optocoupler integration

At the preceding optocoupler stage, the collection was 29 batches / 41 source scopes / 278 annotations.
Eight exact VO617A-3 standard DIP-4 annotations are independently Agent-reviewed
under owner delegation. All 270 prior annotations and historical manifests and
receipts remain unchanged. CTR-bin and test-condition boundaries remain explicit;
5 mA versus 10 mA saturated-test source wording is not silently reconciled and
qualified saturated delay remains unknown. Both CI jobs selected the optocoupler
successor with the unchanged separate MCP23017 disposition.
See the [evaluation receipt](docs/intake-evaluation-optocoupler.md).
Exact-commit publication and terminal CI are reported separately after verification.

## Reviewed low-voltage MOSFET integration

At the preceding MOSFET integration, the collection was 28 batches / 40 source scopes / 270 annotations.
Six exact-orderable Vishay Si2342DS-T1-GE3 annotations are independently
Agent-reviewed under owner delegation. All 264 prior annotations and historical
manifests/receipts remain unchanged. Low-gate-voltage resistance conditions,
stress versus operating limits, thermal references and unknown PWM/board
qualification remain explicit. Both CI jobs select the successor aggregate and
the unchanged separate MCP23017 disposition; neither issue #31 nor its files
are claimed by this independent collection task.
See the [evaluation receipt](docs/intake-evaluation-low-voltage-mosfet.md).
Exact-commit CI and publication are reported separately after verification.

## Reviewed inductor handoff integration

At the preceding inductor integration, the collection was 27 batches / 39 source scopes / 264 annotations.
The exact six-annotation Bourns SRP4020TA-4R7M pair is reused from immutable
`ce0f002a481fc4b9888079f4ed3204fa56dc0cf4`, without recollection or altered review.
All 258 earlier annotations and historical manifests/receipts remain unchanged.
The successor `evals/intake-retrieval-inductor.json` and separate MCP23017
disposition are required in both CI jobs. Saturation and heating criteria remain
distinct; unknown matched sample, mounting and curve-test conditions do not prove
manufacturer error or permit a higher curve-derived rating.
See the [evaluation receipt](docs/intake-evaluation-inductor.md).
Exact-commit CI and publication are reported in the issue handoff.

## Practical task coverage receipt

The [2026-10-28 bounded evaluation](docs/practical-task-evaluation-2026-10-28.md)
records eight evidence-supported narrow decisions at pinned `0373a341`, with
22 replayable CLI commands and explicit remaining facts, inputs and analysis gaps.
It is not a circuit qualification, new human acceptance, or formal pilot pass.

## 0. Permanent boundaries

- The public repository also accepts small original curated summaries and metadata; never source originals or private material.
- Private records stay in controlled workspaces. Original PDFs live only in ignored local caches; packages contain metadata, not originals.
- A workspace pins metadata authority and schemas. Git publication does not imply locally verified original bytes.
- The GUI and Agent share one typed authority model, validator, and repository write path.
- Agents may review intake under owner delegation and publish authorized main-branch changes. Canonical human review is not impersonated.
- Working-tree `APPROVED` is distinct from publication. Formal reads use a fully validated committed Git snapshot.
- Unknown values, conflicts, wrong revisions, wrong packages, missing anchors, and license blocks stay explicit.
- Deliberately wrong/ambiguous evaluation inputs are evaluation metadata, not false canonical authority.
- PcbKnowledge does not read or mutate live PCB board state and is not a PcbCore runtime dependency.
- SQLite/FTS/page-text/vector indexes are disposable derived state, never authority.
- Vector retrieval is not a P0/P1 prerequisite and enters the roadmap only after evaluation demonstrates value.

---

## Active lightweight curation slice

- [x] Integrate the initial 3 TI sources / 20 Agent-reviewed annotations, actual source hashes, and 7 rendered-page review receipts.
- [x] Expand the curated collection to 5 batches / 15 device scopes / 100 unique reviewed annotations. Ninety-four have byte-identity and visual-page receipts; 6 Nexperia observations remain explicitly text-only. Preserve the MCP23017 source-wording discrepancy without synthesizing a supply envelope. Precise bbox and full component coverage remain unresolved.
- [x] Verify `typed-v2-local-cache`, metadata-only packages, and repository-wide index/working-tree guards.
- [x] Add read-only `intake list` / `intake search` retrieval without mixing curation into canonical published Facts.
- [x] Add a [scoped Markdown intake report](docs/intake-report.md) for human inspection of complete recorded conditions, warnings and handling policy without synthesizing electrical answers or new approval.
- [x] Add a separate [explicit local evidence-byte audit](docs/intake-evidence-audit.md) for bounded caller-listed cache files, without fetches, PDF parsing, metadata writes or authority upgrades. Secure byte I/O currently requires POSIX no-follow descriptor operations; unsupported platforms fail closed.
- [x] Independently verify exact identity, pinned-snapshot parity and structured intake filters; [#10](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/10), [#11](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/11) and [#12](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/12) accepted and closed on 2026-10-28.
- [x] Record [human owner batch-level content acceptance](docs/owner-acceptance-2026-10-28.md) dated 2026-10-28 for the immutable 100-annotation snapshot at `9530c0d`; preserve all original Agent provenance, unresolved issues and noncanonical status.
- [x] Handle the sole recorded original-source conflict with a [separate conservative MCP23017 disposition](docs/mcp23017-source-disposition-2026-10-28.md): recheck official Revision E, preserve unresolved manufacturer wording, expose the bounded preliminary supply/ambient screen and unknown outside it; keep the accepted 100 bytes immutable.
- [ ] Complete byte identity, visual anchors, revision drift, and negative-case coverage in the formal pilot.

Local receipt (2026-10-27): 141 tests pass; config/build/test, workspace/authority validation, repository-wide staged/worktree text-size gate, English guard, pinned PDF.js hashes, and metadata-only package pass. Read-only independent code audit cleared after cache-retention and alternate-folder original guards were repaired. Intake retrieval returns 1 batch / 20 annotations (LM358 search: 7); canonical counts remain zero. Remote CI is checked separately after the authorized main push, not inferred from these local results.

Cross-platform correction receipt: commit `8515bf5` passed all four jobs in [CI run 40552649329](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/runs/40552649329), including 143 Windows tests. This fixed native symlink separators without relaxing the pinned-target boundary. The following data-only expansion retains the same executable contract and is verified separately; see the [collection index](knowledge/intake/README.md) and [23-query evaluation receipt](docs/intake-evaluation-100.md).

Issue implementation receipt (2026-10-27; independently verified 2026-10-28):

- [#10](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/10): exact component identity uses manufacturer ID and outer-trimmed raw MPN, preserving case, Unicode, punctuation, suffixes and internal whitespace. Existing serialized records, IDs, Fact references and approved bytes are unchanged.
- [#11](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/11): the publication equality gate and scenario receipts share one canonical-content fingerprint; local evidence availability is excluded and existing approval/stale-receipt protections remain.
- [#12](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/12): exact structured intake filters precede lexical candidate retrieval; missing structured fields fail closed. Full batch-local source warnings remain distinct and retrievable through `intake issues`.
- Combined local verification: 169 tests passed with no skips; English/public-source/PDF.js guards, workspace validation, Config, Build, Test, Agent validate and Package passed. Independent focused review passed 25 tests without blocking findings. No live intake data, schema or cache policy changed. Remote CI is verified separately after publication.

Historical 100-record retrieval evaluation: [18 pinned real-data CLI cases](docs/intake-evaluation-100.md)
exercise the original 100 annotations without adding records. Those cases are now
retained inside the current aggregate selected by CI; synthetic mutation tests detect lost conditions,
warnings/provenance and incorrect selections even with unchanged counts.
Local receipt (2026-10-28): 178 tests passed with no skips in both Build and Test;
all 18 pinned CLI cases passed. English/public-source/PDF.js guards, workspace and
Agent validation, Config and metadata-only Package also exited 0. The archive
contains only five intake batches, the workspace manifest, three schemas and its
derived manifest. Remote CI for this stage must be verified after publication.

Owner-acceptance documentation receipt (2026-10-28): independent scope/provenance
review passed. The five batch files and retrieval manifest are byte-identical to
`9530c0d`; all 100 unique annotation IDs and 15 scopes were rechecked. Local gates
exited 0: 31 focused intake tests, 178 tests in both Build and Test (no skips), all
18 pinned CLI cases, Config, workspace/Agent validation, English/public/PDF.js
guards, local Markdown link-target checks, and metadata-only Package. No new source
evidence or canonical authority was added. Exact-commit remote CI is checked after
publication, independently of this local receipt.

#MCP23017 handling receipt (2026-10-28): independent source/code review passed;
44 focused tests and 191 full tests passed with no skips, and all 24 explicitly
pinned CLI cases passed. Config/Build/Test, workspace/Agent validation,
English/public/PDF.js guards and metadata-only Package exited 0. The original
100-record fingerprint is unchanged; the separately pinned receipt is attached to
normal queries and packaged without originals. See the [dated disposition](docs/mcp23017-source-disposition-2026-10-28.md).
Remote CI is checked separately for the published commit.

## Network, memory and power application stage

Issues #16 (CAN), #17 (EEPROM), and #18 (buck) add 23 reviewed conditional
annotations and nine explicit application unknowns. One integrator owns the
successor aggregate, tests and CI wiring; collectors own only their new pairs.
The maintainer's coverage/read-only CLI lane remained disjoint; the later MCP6002
integration is recorded below.

The historical `evals/intake-retrieval-network-memory-power.json` pins eleven batches /
148 annotations while retaining immutable historical 100/125 receipts and full
MCP23017 disposition metadata. Semantic mutation tests detect lost conditions,
stress/typical/example promotion, ACK-to-persistence inference, page-wrap changes,
unchecked LC acceptance and unknown-to-safety claims. This is not a circuit-answer
engine or completion of the formal pilot. Final reconciled gates and exact-commit
CI are recorded with the issue delivery receipts.
Local integrated receipt: Build and Test each passed 222 tests without skips;
all 114 full CLI cases passed. Config, workspace/Agent validation,
English/public/PDF.js guards and Package exited 0. The package has 17 metadata
members, including all eleven batches and the exact disposition, with no originals.
Independent source and integration review found no blocker. Remote CI remains
a separate exact-commit publication check.

## Signal-chain and logic application stage

- [x] Integrate the independently reviewed MCP6002-I/SN and SN74HC00/D pairs without
  modifying the original 100 annotations, historical manifests, owner receipt or
  MCP23017 disposition. These add fourteen annotations and six source warnings;
  acceptance is Agent review under owner delegation, not new human approval.
- [x] Add the [signal/logic aggregate](docs/intake-evaluation-signal-logic.md): thirteen
  batches / 162 annotations, 159 base cases plus six unchanged disposition cases.
  All 108 prior case definitions and selections remain intact; 27 MCP6002 and 24
  SN74HC00 recipes preserve complete payloads and exact-identity negatives.
- [x] Retain the SN74HC00 RKS/20-pin figure exclusion, unresolved full orderable and
  missing interface/load inputs; retain op-amp typical, load, temperature and
  signal-envelope limits. Neither circuit suitability nor source correction is
  inferred. Synthetic mutations cover these distinctions without source originals.

Integrated local receipt (2026-10-28): independent aggregate review accepted all
prior and new selections. All 12 focused replay tests passed; Build and Test each
passed 276 tests, zero skips. All 165 full-payload CLI cases passed. English/public/PDF.js
guards, workspace/Agent validation, Config, Package and staged diff checks exited 0.
The package contains exactly 19 metadata members: thirteen batches, the unchanged
disposition, workspace manifest, three schemas and derived manifest; every packaged
input is byte-identical and no original/render/text is included. All nineteen
protected baseline files and both immutable reviewed pairs were rechecked unchanged.
Exact-commit remote CI remains a separate publication check.

## Measurement, reference and timing application stage

Issues #19 (INA219), #20 (TL431) and #21 (NE555) add 22 independently reviewed
conditional annotations and ten explicit source/application warnings. The single
integrator preserves the already landed MCP6002/SN74HC00 stage, exact historical
100/125/148/162 snapshots, owner acceptance and MCP23017 disposition. The source
CNVR-clear wording and reference-current equation signs remain unresolved; this
stage does not guess corrections or promote unknowns into circuit permission.

The [successor replay](docs/intake-evaluation-measurement-timing.md) has 230 base
cases plus six unchanged disposition cases. All earlier 159 base recipes retain
their definitions and selections. New full-payload/identity negatives and synthetic
semantic corruptions preserve calibration, grade, timing/topology, test conditions,
warning association and noncanonical/nonverification status. Maintainer report and
evidence-audit tools are left unchanged. Publication gates are recorded in the
final issue receipts, separately from source review. A bounded operational successor
retains the initial measurement/timing manifest and updates only the re-reviewed
INA219 clarification pin; named source-conflict mutations protect blocked sequences
and scoped divider conditions.

## Next application-question milestones

The accepted 100 annotations are a baseline, not a target to inflate. Prioritize
knowledge that helps answer a concrete engineering question and identifies what
is still missing. Candidate retrieval alone is never a recommendation or design
sign-off. New material is not covered by the owner's snapshot-specific acceptance.

- [ ] **Device selection with sufficient conditions:** choose bounded questions
  about the existing device scopes, state required supply, temperature, package,
  signal/load and performance constraints, and identify evidence-supported
  candidates versus explicit unknowns. Keep absolute maximum separate from
  recommended operation; do not infer cross-vendor replacements from family names.
- [ ] **Setup and application conditions:** curate focused original annotations
  for necessary connections, startup/reset, decoupling or external-component
  constraints only where an authorized public source supports the exact device,
  revision and conditions. Record omitted design/thermal assumptions; do not
  elevate a typical circuit into a guaranteed universal design.
- [ ] **Question-level evidence and negative cases:** pair each bounded slice with
  concrete user questions, pinned source/fact selections, preserved conditions and
  warnings, and unsupported/wrong-device/wrong-package negatives. Require an
  independently reviewed, replayable receipt; report unanswered questions rather
  than judging completion by annotation count alone.
- [ ] **Resolve gaps only with new evidence:** keep the six Nexperia text-only
  observations and MCP23017 source-wording ambiguity open until authorized evidence
  actually supports a narrower resolution. No repeated blocked-source bypass, no
  invented supply envelope, and no retroactive evidence upgrade.

Application-knowledge assignments (independently reviewed; coordinated integration):

| Issue | Application question | Exclusive new intake batch and review stem |
| --- | --- | --- |
| [#13](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/13) | What capacitor/ESR, dropout/load and thermal constraints govern the selected TI LM1117 / ST LD1117 scopes? | `knowledge/intake/ldo-application-constraints` |
| [#14](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/14) | What input/PGA, loading/settling and controller-interface conditions govern ADS1115 use? | `knowledge/intake/ads1115-input-interface-constraints` |
| [#15](https://github.com/NorthBoundWisdom/PcbKnowledge/issues/15) | What clamp, input-drive and concurrent-channel thermal conditions govern ULN2003A inductive-load use? | `knowledge/intake/uln2003a-load-protection-constraints` |

Each stem owns only its new `.json` batch and `-review.md` receipt. Existing 100
annotations, the owner acceptance receipt, shared documentation and retrieval
manifest stay coordinator-owned; agree any integration change explicitly. The
issues require conditional evidence, independent Agent review and bounded questions
plus negative cases, not a new owner certification or a quantity-only target.

The coordinated integration uses a separate `evals/intake-retrieval-125.json`
manifest for eight batches / 125 annotations, with the existing separately pinned
disposition manifest retained. The original five JSONs, 100-record manifest and
owner-acceptance receipt are unchanged. The evaluator still rejects unexpected
bytes/batch sets; no gate was weakened. See the [aggregate receipt](docs/intake-evaluation-125.md).

The three new pairs contain 25 annotations and 11 explicit application unknowns,
independently reviewed against four actual source hashes and 32 rendered pages.
The reviewer corrected ADS rate-tolerance conditions and ULN ambient/junction and
GPIO-option wording before acceptance. These are Agent-reviewed noncanonical
candidates, not new human acceptance, engineering sign-off or a formal pilot pass.
Integrated local receipt (2026-10-28): independent aggregate review found no
blocking issue. Build and Test each passed 195 tests without skips; all 70 CLI
cases passed with complete disposition metadata. English/public/PDF.js guards,
workspace/Agent validation, Config and Package exited 0. Package inspection found
only eight intake JSONs, the unchanged disposition, workspace/schema metadata and
derived manifest (14 members), with no originals. Exact-commit remote CI is
verified separately after the authorized coherent main publication.

External-team work should use non-overlapping issues with explicit file ownership,
source-access/evidence boundaries, acceptance criteria and verification receipts.
Review delivered commits against those criteria before integration or issue closure;
fetch latest main and never force-push. Continue small source/topic batches without
committing originals. The formal canonical pilot below remains a separate gate,
not a side effect of owner content acceptance or additional intake quantity.

See [ADR-021](docs/adr/ADR-021-lightweight-curation-local-evidence.md). Historic receipts below describe their original stage, not a claim that the new pilot is complete.

## 1. Completed foundation

### P0.0 — Git-native Core Hardening — COMPLETE

Implemented deterministic Git-native JSON/PDF authority, canonical serialization, content-addressed PDF evidence, append-only review history, optimistic revision tokens, committed-approved immutability, explicit `supersedes`, evidence lifecycle protection, repository write locking, `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change scope, validated published readers, and deterministic package snapshots.

### P0.1 — Typed Authority Model — COMPLETE

```text
SourceRecordV1
EntityRecordV1
  - ManufacturerV1
  - ComponentV1
  - PackageV1
FactRecordV1
  - ComponentPinFactV1
  - ParameterLimitFactV1
EvidenceAnchorV1
```

The model keeps exact identity, Source licensing, typed conditions/applicability, page/bbox/quote anchors, reference closure, semantic conflicts, review history, and explicit unknowns.

### P0.2 — Agent-native Ingestion — COMPLETE

Repository-local skills:

```text
ingest-engineering-source
resolve-component-identity
extract-component-facts
prepare-knowledge-review
```

Agents have typed Source/Entity/Fact commands, stable idempotency, exact identity resolution, `source authorize-read`, explicit unknown/conflict/missing-anchor reporting, selected-closure review status, and `WAIT_FOR_HUMAN_REVIEW` handoff. Agents have no approval or Git-publication operation.

### Open-source + P0.2.5 Workspace Foundation — COMPLETE

Stage commit:

```text
cdf71606610d49504eb6d9ce0783832e6ba58100
[feat]: establish open-source workspace foundation
```

Implemented Apache-2.0 licensing, English-only source policy, public-source data/evidence guard, GitHub Actions, CodeQL, Dependabot, contribution/security/AGENTS contracts, public/private workspace separation, canonical workspace manifest, pinned workspace schemas, explicit `--workspace` / `--repo` selection, external-workspace GUI/package support, and cross-platform repository locking.

---

## 2. P0.3 — Local Review Workbench — COMPLETE

### P0.3a — Typed Workbench Foundation — COMPLETE

Stage commit:

```text
4cb0318b457be19fb9e1c1337d98f2259148fbf3
[feat]: build typed review workbench foundation P0.3a
```

Active routes:

```text
/review
/sources
/sources/<id>
/entities
/entities/<id>
/facts
/facts/<id>
/diff
```

The old `/records/**` Source-only route family was hard-cut. HTTP/security transport, application/view-model construction, repository/domain logic, and HTML rendering are separated. Source/Entity/Fact/supersedes/conflict navigation is derived from canonical authority, not a sidecar graph.

Verified stage tree: 83 tests, 0 failures/errors/skips on Ubuntu 3.11/3.14, macOS 3.11, and Windows 3.11, plus Config/Build/Agent validate/Package gates.

### P0.3b — Visual Evidence Review — COMPLETE

Stage commit:

```text
8b357ff0b28c9ad08fa6976df2677ee6b18e5410
[feat]: complete visual evidence review P0.3b
```

Completed:

- pinned local `pdfjs-dist` 6.2.108 display-layer/worker assets and upstream license;
- package integrity plus per-file SHA-256/byte-size gate;
- exact Source revision/page rendering;
- `PDF_NORMALIZED_V1` bbox overlay;
- quote and `quote_sha256` display;
- multiple-anchor navigation;
- component/package/conditions/applicability context beside evidence;
- backend Source-license enforcement before PDF bytes are served;
- same-origin viewer, worker, CSS, and PDF fetches under explicit CSP;
- explicit crop/rotation/origin/axis semantics in ADR-013.

Verified stage tree: 88 tests, 0 failures/errors/skips across the public matrix, including the pinned PDF.js vendor integrity gate.

### P0.3c — Review Closure — COMPLETE

Stage commit:

```text
44b8338c0217a1cf5f5d837cd0b2a0d0278f2050
[feat]: complete typed human review workbench P0.3c
```

Completed:

- Source and Fact approve/reject from typed review views;
- immediate revalidation of status, typed closure, and next-commit scope before every decision write;
- append-only rejection/edit/resubmission/approval history;
- fail-closed missing/incomplete anchor gate;
- fail-closed semantic conflict gate;
- fail-closed Source license gate for Fact approval;
- `CLEAN` / `DATA_ONLY` decision requirement and `CODE_ONLY` / `MIXED` blocking;
- exact selected closure paths, Git status, and diff before decision;
- visual evidence before Fact decision controls;
- immutable approved-Fact UX;
- preserved loopback Host/Origin, CSRF, optimistic revision, workspace isolation, and GUI no-stage/no-commit/no-push boundaries.

Verified stage tree: 96 tests, 0 failures/errors/skips across Ubuntu 3.11/3.14, macOS 3.11, and Windows 3.11, plus English/public/PDF.js/workspace/Agent/package gates.

P0.3 does not claim human pixel-level acceptance against a real vendor PDF. That belongs to P0.4a.

---

## 3. P0.4 — First Real Dataset + Evals

### P0.4a — Private Pilot — HARNESS READY / REAL PILOT NEXT

The public software repository now contains the pilot evaluation contract and synthetic vertical coverage. Private evaluation notes stay private. Public curated annotations are allowed under ADR-021; original PDFs stay outside Git. Intake counts do not complete this formal pilot.

Public harness:

```bash
python3 configs/pcbknowledge_pilot.py scaffold --output <private-eval.json>
python3 configs/pcbknowledge_pilot.py metrics --workspace <private-workspace>
python3 configs/pcbknowledge_pilot.py report \
  --workspace <private-workspace> \
  --manifest <private-eval.json>
python3 configs/pcbknowledge_pilot.py report \
  --workspace <private-workspace> \
  --manifest <private-eval.json> \
  --require-pass
```

Harness capabilities:

- [x] measure working authority separately from committed Published Knowledge;
- [x] count Source/Entity/Fact/fact-family/review/conflict/anchor coverage;
- [x] enforce 3–5 Component and 20–40 Fact pilot bounds;
- [x] require both initial Fact families;
- [x] detect at least one multi-package Component from canonical pin Facts;
- [x] require an explicit Source revision/supersedes chain;
- [x] keep deliberately wrong/ambiguous scenarios outside canonical authority;
- [x] require 5–10 negative/ambiguous scenario receipts;
- [x] require explicit `UNKNOWN`, table-pin, and footnote-limit receipts;
- [x] record expected vs observed symbolic outcomes with `PASS / FAIL / NOT_RUN` semantics;
- [x] bind visual acceptance receipts to an exact Source, Fact, page, and complete anchor;
- [x] require at least one visual PASS and browser resize/zoom receipt;
- [x] report rotated/cropped or complex-font coverage when available;
- [x] require fully reviewed working Source/Fact authority;
- [x] require committed published counts to match reviewed working authority;
- [x] provide a deterministic synthetic 3-Component / 20-Fact vertical test.

Real private pilot still required:

- [ ] initialize and commit one private `pcbknowledge-workspace-v1` workspace;
- [ ] perform the first desktop-browser visual acceptance on a real vendor PDF;
- [ ] include at least one rotated/cropped or otherwise non-trivial PDF page where available;
- [ ] ingest 3–5 common ICs;
- [ ] create 20–40 total Facts;
- [ ] include at least one multi-package component;
- [ ] include at least one datasheet revision + explicit `supersedes` case;
- [ ] run 5–10 deliberately wrong or ambiguous negative cases without creating false authority;
- [ ] include table-based pin Facts;
- [ ] include parameter limits with footnotes/conditions;
- [ ] preserve at least one unresolved unknown outcome rather than guessing a Fact;
- [ ] review every pilot Source/Fact through the workbench;
- [ ] commit only reviewed data and confirm Published Knowledge matches the working closure;
- [ ] make `pcbknowledge_pilot.py report --require-pass` succeed;
- [ ] record real failures before changing schemas or adding new Fact families.

Evaluate specifically:

- table-cell and multi-line anchors;
- multiple anchors per Fact;
- package-specific applicability;
- footnote-linked constraints;
- absolute maximum vs recommended operating conditions;
- revision drift and supersedes behavior;
- visual bbox accuracy under browser resize/zoom;
- intrinsic page crop/rotation;
- complex-font PDF rendering;
- wrong MPN/package/revision negatives;
- license-block and conflict decision gates.

See [`docs/pilot-evaluation.md`](docs/pilot-evaluation.md).

### P0.4b — First production-scale dataset

After the pilot stabilizes:

- [ ] 20–30 common ICs;
- [ ] at least 100 pin Facts;
- [ ] at least 100 parameter-limit Facts;
- [ ] at least two datasheet revision-update cases;
- [ ] at least 20 deliberately wrong/ambiguous negative cases;
- [ ] golden evals for wrong MPN, wrong package, wrong revision, absolute-max vs recommended, unknown, supersede, conflict, license block, anchor drift, review history, uncommitted approval, mixed commit, and wrong-workspace targeting.

---

## 4. P1 — Local Retrieval

Build retrieval only after a real published dataset exists.

- [ ] `.pcbknowledge/index.sqlite` rebuildable derived index;
- [ ] exact manufacturer / MPN / package / Fact-type index;
- [ ] SQLite FTS5;
- [ ] derived PDF page-text cache;
- [ ] published snapshot as the default index source;
- [ ] explicit opt-in for working-tree preview;
- [ ] results retain Fact/evidence/conflict/unknown structure.

Query order:

```text
exact entity
-> exact package / revision / fact type
-> published filters
-> FTS
-> fact / evidence / conflict / unknown
```

---

## 5. P1.5 — PCB Knowledge Expansion

Candidate typed families after P0.4 stabilizes:

- [ ] PackageDimension;
- [ ] PowerSequence;
- [ ] Decoupling;
- [ ] ClockReset;
- [ ] LayoutGuideline.

Every new Fact family requires executable model, schema, validator, Agent projection, review UI, synthetic coverage, and at least one real-data evaluation case.

---

## 6. P2 — Product Integration

Candidate knowledge: FabCapability, InternalRule, DesignReview, Waiver, Lifecycle, Replacement, HistoricalCase.

- [ ] immutable `KnowledgeSnapshot` contract;
- [ ] task-level query/read API;
- [ ] read-only PCBAtlas/PcbCore adapter;
- [ ] optional iOS/read-only snapshot format;
- [ ] Agent harness combines PcbCore live board facts with one pinned KnowledgeSnapshot;
- [ ] PcbCore remains fully usable when PcbKnowledge is unavailable.

---

## 7. P3 — Advanced Retrieval

Vector/embedding/reranking starts only after golden evaluation shows stable benefit over Exact + FTS for open-ended guideline or historical-case retrieval.

Before implementation:

- [ ] define retrieval metrics and a fixed golden set;
- [ ] measure Exact + FTS baseline;
- [ ] demonstrate repeatable quality gain worth added complexity;
- [ ] write a new ADR selecting local vector technology and lifecycle;
- [ ] keep vectors disposable and rebuildable from published authority.

---

## 8. Verification contract

Use the narrowest relevant tests during editing, then the applicable repository checkpoint. GUI work requires focused HTTP/view-model coverage and a real loopback smoke. Workspace work requires a temporary external Git repository and tamper tests. Pilot/evaluation work additionally requires deterministic synthetic structural/negative/visual/publication closure. Public intake must obey the lightweight contract; private pilot data and original PDFs are never added. Interrupted, truncated, skipped, or unexecuted checks are not passes.

## Offline intake handoff preflight

- [x] Add the bounded, pinned Git-object [handoff preflight](docs/intake-handoff-preflight.md)
  without changing intake content, schemas, evaluators or CI. Batch-local IDs remain
  batch-local; shared source/device metadata across distinct batches is legal.
- Verification: synthetic real-object tests cover immutable additive scope,
  forged object identities, hostile Git configuration/environment, bounded payloads,
  parsing/reference failures and path safety. Four original local delivery commits
  match separately recorded pair pins against the historical pre-integration target;
  already integrated pairs correctly collide against the newer target. These are
  compatibility observations, not new source review or aggregate acceptance.
- Local receipt (2026-10-28): 24 focused tests and 314 tests each in Build/Test,
  zero skips; English/public/vendor guards, workspace validation, Config,
  authority validation, unchanged 228-annotation aggregate/disposition replay and
  Package all exit zero. Independent security review cleared the implementation.
  Exact published-commit cross-platform CI is checked separately after publication.

## Bounded synthetic resistor worked example

- [x] Document a [DC resistor bound](docs/worked-examples/resistor-dc-bound.md)
  with independently supplied synthetic operating resistance and exact arithmetic.
  The embedded standard-library check and independent arithmetic/source-linkage
  review pass; this is not an added annotation or application qualification.
  The frozen practical evaluation and all source records remain unchanged.

## Nominal steady-state timer worked example

- [x] Document the [NE555 astable nominal model](docs/worked-examples/ne555-astable-model-bound.md),
  separating high/low duty conventions, rounded coefficients and physical uncertainty.
  Fixed-input arithmetic and independent source-bound review pass; no operating
  timing interval, new annotation, selected timing capacitor or circuit approval.

## Executable ADS1115 pin-rail example

- [x] Add a [fixed synthetic boundary evaluation](docs/worked-examples/ads1115-pin-boundary-eval.md)
  which calculates each pin's interval against the reviewed rail, rather than
  treating successful retrieval as a correct engineering conclusion.
- Fourteen fixed cases preserve explicit unknowns, full pinned evidence and all
  application warnings; no-violation never implies circuit qualification.
  No source records, historical reports, existing evaluators or CI gates change.
- Local verification (2026-10-28): 16 focused tests; Build and Test each 339 tests
  without skips; all 539 existing aggregate/disposition cases; English/public/vendor,
  workspace/Agent, Config and Package gates pass. Independent Agent review checked
  35 additional exact-arithmetic pin pairs and complete evidence preservation.
  Exact-commit remote CI is verified separately after publication.

## Executable conditional resistor DC example

- [x] Turn the existing [resistor DC bound](docs/worked-examples/resistor-dc-bound.md)
  into a fixed synthetic regression with complete pinned evidence and exact
  arithmetic; no general calculator, new source records or circuit approval.
- Fourteen cases preserve missing operating inputs and reject nominal-tolerance,
  AC/pulse and wrong-identity substitutions. Fourteen focused tests pass, including
  441 exact grid points and false-qualification mutations. Full gates and exact
  published-commit CI remain separate publication checks.

## Read-only intake workbench

- [x] Expose curated fact candidates and source issues through the existing local
  workbench's [read-only intake page](docs/intake-workbench.md), bound exclusively
  to the selected workspace with exact filters, explicit pagination and complete
  escaped candidate payloads. No canonical approval or original-file access.
- Focused synthetic tests include actual loopback HTTP, external-workspace isolation,
  malformed/duplicate filters, escaping, warning/disposition preservation and POST
  rejection. Full gates and exact-commit CI are separate publication checks.

## Exact local intake references

- [x] Add read-only per-record intake links bound to batch-local identity, exact
  batch JSON bytes and complete candidate/disposition context. Single-load browse
  projections prevent attaching new hashes to an older displayed candidate.
- Missing records return 404; malformed links 400; changed batch/context 409.
  This is not a canonical immutable publication or source-original byte audit.
- Focused checks cover duplicate IDs across batches/types, stale bytes and
  disposition-only changes, traversal/malformed selectors, full escaped payload,
  one-load consistency and actual workspace-server HTTP behavior. Existing CLI
  candidate payloads remain unchanged; complete gates and CI are separate checks.

## Included-collection onboarding

- [x] Link the read-only intake guide from README and give the explicit public
  checkout workspace launch command. Distinguish an empty private workspace from
  missing public data; list both intake routes and explain local pinned links.
- Existing loopback launch and HTTP checks verify the documented workspace path.
  Browser visual acceptance remains unverified; cloud-browser loopback navigation
  was blocked by its client policy, without a bypass or source-original access.

## Agent-native exact intake references

- [x] Reuse one pure batch-local reference resolver for GUI and readonly CLI.
  `intake pin` explicitly captures current metadata; `intake item` requires both
  exact byte/context pins and never refreshes stale evidence automatically.
- Synthetic tests cover full candidate parity, same IDs across batches and types,
  one-load capture, changed bytes/dispositions, duplicate/missing selectors and
  actual selected-workspace CLI reads with unchanged filesystem bytes. Existing
  search/list/issues payloads and source records remain unchanged. Independent
  review, full repository gates and exact-commit CI remain publication checks.

## Exact source-revision selection

- [x] Extend the shared exact source filters with revision across fact/issue
  retrieval, scoped reports, explicit byte-audit metadata selection and workbench.
  Revision means the structured source field, not evidence/prose or a latest-version
  inference. Missing or non-string revisions never match; existing unfiltered
  candidate payloads and evidence pins stay unchanged.
- Synthetic checks cover same IDs across batch revisions, misleading fact evidence,
  missing/null/non-string revisions, exact Unicode/whitespace, conjunction, CLI
  dispatch and actual workspace HTTP pagination. Publication gates remain separate.
