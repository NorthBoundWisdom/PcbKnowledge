# Consuming PcbKnowledge design intent

This guide describes the implemented repository-side contract. PcbAtlas does not
currently integrate it. Use the selected bundle's schemas and catalog together;
The [v2 model](knowledge-model-v2.md#owned-consumer-reports) defines report binding (D108).

## 1. Pin and query a bundle

From a clean, committed PcbKnowledge checkout:

```sh
pk() { python3 configs/pcbknowledge_agent.py --repo . "$@"; }
pk bundle build --output build/bundle
BUNDLE="build/bundle/$(git rev-parse HEAD).json"
pk bundle identity --bundle "$BUNDLE"
pk block search --text buck --bundle "$BUNDLE"
pk block show block:g2-buck --bundle "$BUNDLE"
pk part show part:ti-tps5430dda --bundle "$BUNDLE"
```

Keep the returned bundle path and commit. A bundle contains commit/tree-bound
catalog records, briefs and schema bytes. Querying it does not select dirty
working-tree records. Source/page references identify evidence; source originals
are not included. Digests identify inputs and detect changed bytes, not signatures.

## 2. Expand and export

Choose a graph against that bundle. The committed G2 graph is one example:

```sh
GRAPH=evals/golden-designs/g2.block-graph.json
INTENT=build/g2-intent.json
pk expand "$GRAPH" --bundle "$BUNDLE" --output "$INTENT"
pk layout export --bundle "$BUNDLE" --graph "$GRAPH" --intent "$INTENT" \
  --output build/g2-handoff
```

Expansion returns `EXPANDED` or `REFUSED`. Export and subsequent consumers replay
expansion against the supplied bundle and graph: changing an intent field or
using another graph/commit fails instead of accepting a saved status claim.

`design-intent.json` remains authority. `layout export` writes copies of intent
and `graph.json`, `design.net`, `pcbknowledge.pretty/`, `fp-lib-table`,
`design.kicad_pcb`, `design.kicad_pro`, `design.kicad_dru`, and `assembly.csv`.
For netlist/library interchange without a board project, use `pk export` with the
same `--bundle`, `--graph`, `--intent` and `--output` arguments.

The generated board uses the rectangular envelope and deterministic mounting
positions derived from edge constraints. Other footprints have parked origins
outside the board. Those origins are transport coordinates, not placement or
routing results. A layout consumer places/routes the design and saves a board
for checking; it must preserve the selected footprint identities, physical pin
numbers and nets, and retain the intent constraints.

## 3. Judge a saved board

Set `BOARD` to the actual saved board, not the parked handoff unless deliberately
checking that unfinished state. Save its corresponding project and rules beside
it for DRC.

```sh
BOARD=build/g2-reviewed/design.kicad_pcb
pk layout check "$INTENT" "$BOARD" --bundle "$BUNDLE" --graph "$GRAPH" \
  --output build/g2-layout-report.json
pk drc "$BOARD" --bundle "$BUNDLE" --graph "$GRAPH" --intent "$INTENT" \
  --output build/g2-drc-report.json
```

`layout check` is tool-free. It verifies board identity before measuring layout
rules and board requirements. Unsupported or insufficient geometry produces
`NOT_CHECKABLE`, not a skipped pass. Results remain scoped to the reported checks;
`routing_certified` is false.

`drc` needs the board's `.kicad_pro` and `.kicad_dru`, and `kicad-cli` for an actual
run. It checks isolated copies and retains input digests. With all three context
arguments it recomputes and embeds the complete layout report. Supplying only
some of `--bundle`, `--graph`, `--intent` is rejected. Missing KiCad gives
`NOT_RUN`. Native DRC success without layout context cannot give overall `PASS`;
its context and identity are null and overall status is `NOT_CHECKABLE`.

## 4. Generate the hardware measurement plan

```sh
pk bringup --bundle "$BUNDLE" --graph "$GRAPH" --intent "$INTENT" \
  --output build/g2-bringup-report.json --markdown build/g2-bringup-checklist.md
```

Each POWER net has either a DC expectation or a typed waveform protocol.
`range_coverage=COMPLETE` means no rail plan is `UNKNOWN`; it says nothing about
measurements. Rail, programming, functional, prerequisite and A6 observations
remain `NOT_RUN`. G2 `BUCK_SW` uses PH pin 8, GND pin 6 and synchronous VIN pin 7;
the checklist includes acquisition thresholds and source limits, not a DMM test.
This CLI takes no board input, so its report has `board_sha256: null` and terminal
identities without placed coordinates.

## Report contracts and identity

Validate with the selected bundle's `schemas/envelope.schema.json` definitions:

| Output | `schema` value | Definition |
| --- | --- | --- |
| Layout | `pcbknowledge.layout-check.v2` | `#/$defs/layoutReport` |
| Bring-up | `pcbknowledge.bringup.v2` | `#/$defs/bringupReport` |
| DRC wrapper | `pcbknowledge.drc.v2` | `#/$defs/drcReport` |

The [owned report contract](knowledge-model-v2.md#owned-consumer-reports) defines
input hashes, null identities, snapshot schema selection and validation limits.
Keep the full report, including layout constraints and DRC context, rather than
reducing it to a success flag. Reject a bundle that lacks the requested report
definition; do not substitute the current checkout's schema.

## 5. Run consumer conformance

```sh
python3 configs/pcbknowledge_conformance.py --repo . --bundle "$BUNDLE" \
  --output build/conformance/report.json
```

The default manifest is `evals/conformance/manifest.json`; `--manifest` selects
another manifest. The result has `schema: pcbknowledge.conformance-result.v1` and
`status: MATCH` or `MISMATCH`. Exit 0 means expectations agree, including intentional
`FAIL` and `NOT_CHECKABLE` cases; it does not mean every board passed.

`measurements.scope: ISOLATED_MEASUREMENT` labels handler probes and reports
per-kind results. `consumer_replay.scope: BUNDLE_REPLAY` separately records the
selected-bundle intent/board check and its identity. Keep these scopes distinct:
conformance covers the declared cases, not a PcbAtlas integration.

## Refusals and errors

- Expansion `REFUSED` includes `refusals` with `code`, `path`, `reason` and query
  guidance. Correct the selected inputs and expand again; do not edit a refusal
  into `EXPANDED`.
- Layout `FAIL` means a measured requirement or identity check failed;
  `NOT_CHECKABLE` means the requested proof was unavailable. Preserve its reason.
- DRC `drc_status`/`a4` describe native execution; overall `status` also includes
  layout context. Bring-up coverage and hardware observation states are separate.
- Agent CLI (`pk`) errors return JSON `status: ERROR` and a message. Refusal/failure,
  `NOT_CHECKABLE`, and `NOT_RUN` use exit code 2. A successful bring-up command can
  exit 0 while hardware remains unobserved; always inspect report fields.
- The conformance runner reports invalid inputs on stderr and exits 2. A completed
  evaluation reports MATCH or MISMATCH separately from board measurement states.

Derived outputs must stay below the selected workspace's `build/` directory;
unsafe paths and symlink traversal are rejected. Keep the bundle, graph, intent,
saved board/project/rules and reports together for reproducible checking.
