# PcbKnowledge architecture

PcbKnowledge supplies a Git-native catalog for turning a design brief into a
manufacturable board. [ADR-022](adr/ADR-022-board-generation-knowledge.md) owns the
direction; [the knowledge model](knowledge-model-v2.md) defines consumer queries;
[`TODO.md`](../TODO.md) owns unfinished work.

## Current implementation

One v2 record model lives in `schemas/` and `src/pcbknowledge/v2/`:

| Layer | Implementation |
|---|---|
| Canonical JSON | `serialization.py` |
| Workspace format and schema pin | `workspace.py` |
| Structural evaluation | `v2/schema.py` |
| Registry and quantity semantics | `v2/vocabulary.py` |
| Record loading and cross-record closure | `v2/catalog.py` |
| Catalog reachability and local evidence import | `v2/audit.py`, `v2/evidence.py` |
| Public-source policy and pinned viewer assets | `public_repo.py`, `pdfjs_vendor.py`, `static/` |
| Assembly classification | `v2/assembly.py` |
| ADR-023 handoff validation | `v2/intent.py` |
| Original footprints and calculators | `v2/footprints/`, `v2/calculators.py` |
| Commit-authenticated snapshots | `v2/bundle.py` |
| Expansion, rules and interchange | `v2/expansion.py`, `rules.py`, `netlist.py` |
| Coverage and independent synthesis evaluation | `v2/requirements.py`, `coverage.py`, `synthesis.py` |
| Query CLI, explicit evidence cache commands and change scope | `v2/cli.py` |
| Derived KiCad project, rules and assembly BOM | `v2/handoff.py`, `handoff_rules.py` |
| Exported-board parser and measured checks | `v2/sexpr.py`, `boardview.py`, `layout.py` |
| Isolated native DRC and combined reports | `v2/drc.py` |
| Owned report schemas, input bindings and consistency | `v2/report_contracts.py`, `bringup_report_validation.py`, `drc_report_validation.py` |
| Original isolated vectors and pinned public replay | `configs/pcbknowledge_conformance.py`, `evals/conformance/` |
| Loopback transport, view models, HTML | `v2/server.py`, `application.py`, `views.py` |

The catalog covers all 15 G1 block instances with independently verified parts,
packages, rules and manufacturing evidence. Standard footprints derive from cited
drawing dimensions; irregular connectors retain explicit manufacturer patterns.
See the [current acceptance table](golden-designs.md#current-acceptance) for
reference and synthesis progress.

The retired record families, intake toolchain and approval UI are removed. Frozen
migration input is available with `git show intake-final:knowledge/intake/<file>`.
Historical design receipts remain in Git and [`archive/`](archive/README.md).

## Authority and evidence

A workspace is one Git repository, a `pcbknowledge-workspace-v2` manifest, its exact
pinned schema snapshot, registries and canonical UTF-8 JSON records:

```text
knowledge/registry/      controlled names, quantities and conditions
knowledge/sources/       exact document revisions and processing policy
knowledge/packages/      drawing dimensions or explicit manufacturer pads
knowledge/parts/         exact orderable parts, pin maps and parameters
knowledge/blocks/        reusable circuit definitions
knowledge/rules/         class-level layout defaults
knowledge/fab-profiles/  manufacturing limits
```

Agents and humans author these files through the same canonical serializer and
validator. Query commands and the browser are read-only; explicit evidence fetch/add
commands write ignored cache files, not knowledge or Git. Git commits version knowledge;
data changes remain separate from schema and policy changes. Source originals
live only in ignored `.pcbknowledge/evidence/sha256/` cache files. Missing bytes
produce `NOT_LOCALLY_VERIFIED`; wrong hashes, sizes or unsafe paths fail closed.
The evidence endpoint checks rights and byte identity before serving evidence.
PDF and HTML source identities include exact hashes, sizes and media signatures.
Fetch uses eligible recorded HTTPS URLs, bounded downloads and public-address
checks. Changed bytes are stored separately; manual add requires a recorded hash.

Package scope ties a drawing to supported exact MPNs and the part identity source.
Mount types and fab assembly services produce explicit assembly metadata; THT
items outside the selected service become hand-solder work, not automatic refusals.
Brief function categories and explicit power-function bindings drive checks, never
prose descriptions. Catalog audit follows graph selections and dependency closure
to reject unreachable parts, packages and sources.

Verification records actual creator and independent verifier identities. A person
must actually inspect values before being named as a human verifier. Generated
intent reports the weakest level across its dependencies.

## Runtime and workspace selection

The standard-library Python process listens only on `127.0.0.1`. Host/Origin
checks prevent cross-origin requests, and all mutation methods are refused.
Request flow is `HTTP -> application/view model -> catalog`; HTML only renders
view models. PDF.js and static assets come from the software checkout. Knowledge
and evidence come only from the explicitly selected workspace, rebuilt on each
request rather than cached as authority.

Config/Build prepare software receipts. Run stays terminal-owned and performs no
build, installation or migration. Test can additionally validate an external
workspace. Package writes a deterministic metadata-only ZIP under software
`build/`, containing the selected validated workspace and excluding originals.

## Next stages and PcbAtlas boundary

Stages 3-5 provide footprints, G1 catalog closure, engineering calculators,
commit-pinned consumer bundles and pure deterministic expansion:

```text
brief -> block graph -> expand(pinned bundle, graph) -> design intent -> PcbAtlas
```

PcbAtlas owns layout algorithms, product synthesis orchestration and live board state.
PcbKnowledge accepts designs through A2 and exports knowledge-backed handoff files;
it does not place, route, fill zones, implement DRC or generate fabrication outputs.
The parked KiCad handoff and read-only checks follow
[ADR-025](adr/ADR-025-derived-board-handoff.md). D78 retires the reference pipeline
formerly authorized by [ADR-026](adr/ADR-026-reference-layout-pipeline.md).
The thin optional `drc` wrapper invokes an external KiCad executable; it is not a
DRC implementation or an acceptance dependency. `layout check` evaluates supplied
board files against catalog constraints without changing them. Unsupported checks
remain `NOT_CHECKABLE`, never a pass.

Developers may use external KiCad or Freerouting manually to discover knowledge
errors. Such findings must become catalog corrections with tool-free regressions;
local boards and tool outputs stay uncommitted under `build/`. CI and A2 acceptance
need neither tool. PcbKnowledge never reads or mutates live board state and has no
PcbCore runtime dependency.
[ADR-023](adr/ADR-023-design-intent-handoff.md) owns the JSON handoff contract.

Expansion rejects mutually incompatible directional edge intervals across the
shared maximum outline envelope. An envelope is not a fixed board size. The
derived KiCad handoff additionally checks feasibility against its actual chosen
rectangle before export; LEFT/RIGHT use width and TOP/BOTTOM use length.
Rules may conjunctively select an exact part, role and pin type. The G2 fuse
proximity rule resolves one directly connected non-ground physical fuse/header
pin pair and refuses missing or ambiguous pairs. Its distance limits placement,
not routed trace length.

## Reproducing historical receipts

Strict contract and audit upgrades are not compatibility shims. Reproduce an older
published bundle or receipt with its recorded software checkout and pinned input
commit, rather than rewriting the historical artifact to satisfy current schemas.
Current bundles include their committed design audit inputs. Stage 7 layout and
board checks remain separate from these Stage 6 infrastructure changes.

## Corpus screening and independent synthesis

Brief screening matches explicit function categories, fixed operating parameters,
and role-qualified package requirements. Expansion rechecks the actual selected
part; an unrelated passive in the requested family cannot satisfy an IC package
requirement. `coverage --all` separates eligibility from reference block readiness
and graph replay for every preserved graph; it never selects only a successful
attempt. Audit validates all briefs and rejects graphs without a matching brief.
No screening result creates a new acceptance receipt.

Corpus attempts use query-mediated access to a pinned bundle. Because bundles
include reference/audit inputs, fresh authors must not receive raw bundles or
reference graphs: the coordinator mediates catalog queries and preserves the
actual requests and responses. Filesystem access is limited to exact broker-supplied input/response packets
outside the repository and the author's designated output directory. The initial
packet contains only the skill, target brief, schema, decisions and hashes;
response packets contain only requested catalog projections. Other reads, path
listing and direct repository/network access are forbidden. Exactly three distinct fresh authors and a reviewer
independent of every author and the coordinator are required. Receipts bind the
actual bundle file provenance, brief, skill, output and transcript hashes, plus
the catalog/audit/engine content identity described below. This is an auditable
workflow attestation, not an operating-system isolation or identity guarantee.
Positive reviews use `EQUIVALENT` or `NOT_EQUIVALENT`, never prose truthiness;
negative refusals are reproduced against the pinned catalog and expected code/path.
Historical G1 evaluation remains a separate mode and is not rewritten.

USB differential constraints derive KiCad width, gap, skew and netclass rules.
Matching P/N or +/- net suffixes are required. These engineering constraints are
not controlled-impedance or USB compliance certification and do not route a board.

### Replaying preserved synthesis inputs

Current receipts use `pcbknowledge.synthesis-receipt.v2`. Their `input_identity`
has three fields computed by the runtime:

- `catalog_tree`: a Git tree reconstructed from the authenticated `knowledge/`,
  `schemas/` and workspace-manifest entries, preserving their paths and modes;
- `audit_sha256`: canonical JSON digest of the same brief and graph projections
  consumed by `design_inputs`, including preserved attempt graphs;
- `engine_sha256`: digest of the installed `pcbknowledge` Python source files.

Brief, skill, transcript and submitted-output hashes remain mandatory. Original
bundle commit and file hashes are provenance; a published bundle can have another
commit or unrelated file while supplying identical inputs. Missing catalog/schema
files, changed audit graphs, changed executable sources and altered blob/tree
proofs fail default evaluation. A result identifies both the candidate bundle used for
replay and each author's original bundle. Its evaluator source digest is explicit.

`bundle snapshot` creates a small `pcbknowledge.synthesis-input.v2` metadata
record with these identities, the target brief hash and exact skill text. To
recover, build a bundle from a published commit with matching inputs and call
`resolve_inputs(snapshot, candidate_bundle_path)`. This validates the candidate
through the normal `Bundle` loader and compares the complete input identity;
it does not consult mutable worktree files or require the original commit object.
The return value is the candidate document, not reconstructed original bytes.
Keep the original snapshot and receipts unchanged. If no matching published
catalog is available, recovery fails; publish the input data commit before later
catalog changes. No provenance merge is needed merely to retain commit metadata.

Historical commit-only receipts use the explicit `--historical` corpus mode
(or `evaluate_historical_corpus`), which reports the current evaluator identity.
It rejects v2 receipts rather than bypassing their content checks. New receipts
must use current evaluation. For prior v2 receipts after an engine update,
`--replay` / `replay_corpus` permits only engine drift and labels the result
`CATALOG_CONTENT_REPLAY`. `input_identity` preserves the original source version;
`evaluation_input_identity` and `evaluation_engine_sha256` record the actual new
engine. All three authors must retain one original identity. Catalog, audit,
brief, skill, transcript, output and independent-review checks remain enforced.
`resolve_replay_inputs` is the corresponding explicit snapshot resolver.
Replaying an old receipt with current code is a new replay result, not a
replacement of its recorded original execution.


`evals/synthesis/stage8-input.json` preserves the original input commit object,
Git tree identity, bundle SHA-256 and exact skill text. A connector publication
may create a different commit identity for the same tree because author or
committer metadata differs. Its publication mapping records that relationship;
it never relabels an author's actual input commit, hashes or initial packet.

To reconstruct the original bundle without checkout, network access or Git writes:

```python
from pcbknowledge.serialization import read_json
from pcbknowledge.v2.bundle import Bundle
from pcbknowledge.v2.synthesis_inputs import reconstruct_bundle

snapshot = read_json((root / "evals/synthesis/stage8-input.json").read_bytes())
with Bundle.from_document(reconstruct_bundle(root, snapshot)) as original:
    original_briefs = original.briefs
```

The local Git object database must contain the pinned tree and selected blobs;
CI fetches full history. Reconstruction authenticates the preserved commit bytes,
tree, blobs and exact canonical bundle hash before validating the snapshot.
`tests/git_native/test_v2_preserved_corpus.py` replays all five benchmarks against
that original catalog and its original expectations, and checks raw submissions,
initial packets and fifteen distinct author identities. Later brief corrections
or catalog additions must not retroactively rewrite historical refusal outcomes.

The Stage 8 reconciliation retains the original input tree through provenance
ancestry. Current brief decisions and embedded refusal expectations are separate
from the fifteen historical attempts: current-reference expansion and screening
are regression replays, not newly authored synthesis attempts.

## G2 power modeling

G2 connects protected adapter power through the INA219 shunt to the buck and
three external loads. TPS5430 uses a source-guided nonideal CCM model at the
150 mA design point, with separate feedback, filter, ripple and input-budget
checks. Its documented DCM operation covers lower loads; the CCM calculation
rejects nonpositive valley current. Application thermal and passive-component
models are explicit engineering inputs alongside source test conditions.

Typed GPIO requirements bind the three control pins to their supported physical
functions. Source-backed unconnected input states cover TPS5430 enable. Typed
external-load declarations pair real connector supply/return terminals with a
catalog supply provider; POWER_SINK checks reject shorts and missing load returns.
The generic ideal buck, MOSFET conduction-loss and RC calculators retain their
original domains. RC time remains a passive time constant rather than ADC settling.

Manufacturer-land generators repeat cited pad size, pitch and row spacing for
two- or four-sided packages without adding gull-wing fillets. A distinct exposed
pad is derived from its cited land dimensions; collision checks remain unchanged.
Board-level thermal vias are not silently synthesized from a package illustration.

## G3 analog models and functional wiring

G3 keeps source-condition facts separate from the selected bench envelopes.
Original calculators cover reference bias, thermistor transfer and RC filtering,
TIA DC and first-order loop estimates, ferrite DC loss, RS-485 bias/loading and
single-ended microstrip planning. The loop model uses an ideal integrator op-amp;
the electrical operating assumptions are inputs, not inferred device guarantees.

A brief can declare functional electrical binding groups. Expansion resolves
function/port endpoints through selected instances to merged physical nets. All
endpoints in a group must share a net, and different groups must remain distinct.
This binds G3 supply providers, reference distribution, ADC channels and common
return without matching graph labels or a stored reference answer. It is not a
general power-flow solver. Guard and return-path copper checks are described in
[the v2 model](knowledge-model-v2.md#guard-and-reference-copper-requirements).

## Synthesis evidence storage

Committed attempts contain the graph or typed refusal, unchanged receipt and
independent review, plus SHA-256 identities for the initial packet, transcript,
and each original submission. Full packets, submissions and query transcripts
live in `.pcbknowledge/evals/sha256/<prefix>/<digest>.json`, ignored local state.
`load_attempt` verifies the cache and every retained submission hash before replay;
missing evidence reports `NOT_LOCALLY_VERIFIED`, never acceptance.

Historical migrated attempts also name their original Git blob. For an explicit
read-only historical replay, `load_attempt(root, path, recover_history=True)`
recovers that blob from full local Git history and verifies its original receipt,
graph and evidence digest. It performs no fetch or repository/cache writes. CI
uses this route so all original replay and provenance assertions still run on a
fresh clone. New attempts require their local cache; do not commit full evidence.
The committed `evals/` budget is 1.5 MB and is tested alongside hash preservation.
