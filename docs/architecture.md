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
| Loopback transport, view models, HTML | `v2/server.py`, `application.py`, `views.py` |

The catalog covers all 15 G1 block instances with independently verified parts,
packages, rules and manufacturing evidence. Standard footprints derive from cited
drawing dimensions; irregular connectors retain explicit manufacturer patterns.
The G1 reference and three independent AI-produced graphs reach A2 on a pinned
bundle. Electrical screening is not a physical fabrication or bring-up claim.

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

PcbAtlas owns synthesis orchestration, board state, placement, routing and
fabrication output. Under D16-D17, PcbKnowledge additionally derives a parked
KiCad 9 handoff and checks exported files without mutating them. Native DRC is
optional and runs on isolated copies; unsupported geometry and absent tools are
not passes. [ADR-025](adr/ADR-025-derived-board-handoff.md) defines this boundary. PcbKnowledge never reads or mutates live board state and has
no PcbCore runtime dependency. [ADR-023](adr/ADR-023-design-intent-handoff.md) owns
the JSON handoff and derived KiCad interchange contract.

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
and graph replay. No screening result creates a new acceptance receipt.

Corpus attempts use query-mediated access to a pinned bundle. Because bundles
include reference/audit inputs, fresh authors must not receive raw bundles or
reference graphs: the coordinator mediates catalog queries and preserves the
actual requests and responses. Filesystem access is limited to exact broker-supplied input/response packets
outside the repository and the author's designated output directory. The initial
packet contains only the skill, target brief, schema, decisions and hashes;
response packets contain only requested catalog projections. Other reads, path
listing and direct repository/network access are forbidden. Exactly three distinct fresh authors and a reviewer
independent of every author and the coordinator are required. Receipts bind the
actual bundle file, brief, skill, output and transcript hashes. This is an auditable
workflow attestation, not an operating-system isolation or identity guarantee.
Positive reviews use `EQUIVALENT` or `NOT_EQUIVALENT`, never prose truthiness;
negative refusals are reproduced against the pinned catalog and expected code/path.
Historical G1 evaluation remains a separate mode and is not rewritten.

USB differential constraints derive KiCad width, gap, skew and netclass rules.
Matching P/N or +/- net suffixes are required. These engineering constraints are
not controlled-impedance or USB compliance certification and do not route a board.

### Replaying preserved synthesis inputs

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
