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
| Workspace format and schema pin | `git_native/workspace.py` |
| Structural evaluation | `v2/schema.py` |
| Registry and quantity semantics | `v2/vocabulary.py` |
| Record loading and cross-record closure | `v2/catalog.py` |
| ADR-023 handoff validation | `v2/intent.py` |
| Read-only JSON CLI and change scope | `v2/cli.py` |
| Loopback transport, view models, HTML | `v2/server.py`, `application.py`, `views.py` |

The catalog contains verified source/part records for LD1117S33TR,
INA219AIDCNR and 24LC256-I/SN. Package identities have explicit missing geometry
for Stage 3. G1's brief and reference graph use concrete D7 engineering defaults.
No golden acceptance level has passed yet.

The retired record families, intake toolchain and approval UI are removed. Frozen
migration input is available with `git show intake-final:knowledge/intake/<file>`.
Historical design receipts remain in Git and [`archive/`](archive/README.md).

## Authority and evidence

A workspace is one Git repository, a `pcbknowledge-workspace-v2` manifest, its exact
pinned schema snapshot, registries and canonical UTF-8 JSON records:

```text
knowledge/registry/      controlled names, quantities and conditions
knowledge/sources/       exact document revisions and processing policy
knowledge/packages/      pad identities and land-pattern geometry
knowledge/parts/         exact orderable parts, pin maps and parameters
knowledge/blocks/        reusable circuit definitions
knowledge/rules/         class-level layout defaults
knowledge/fab-profiles/  manufacturing limits
```

Agents and humans author these files through the same canonical serializer and
validator. The CLI and browser are read-only. Git commits version knowledge;
data changes remain separate from schema and policy changes. Source originals
live only in ignored `.pcbknowledge/evidence/sha256/` cache files. Missing bytes
produce `NOT_LOCALLY_VERIFIED`; wrong hashes, sizes or unsafe paths fail closed.
The evidence endpoint checks rights and byte identity before serving a PDF.

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

Stage 3 generates and checks footprints. Stage 4 completes G1 parts, blocks,
rules, calculators and fab limits. Stage 5 builds commit-pinned consumer bundles
and pure deterministic expansion:

```text
brief -> block graph -> expand(pinned bundle, graph) -> design intent -> PcbAtlas
```

PcbAtlas owns synthesis orchestration, board state, placement, routing, DRC and
fabrication output. PcbKnowledge never reads or mutates live board state and has
no PcbCore runtime dependency. [ADR-023](adr/ADR-023-design-intent-handoff.md) owns
the JSON handoff and derived KiCad interchange contract.
