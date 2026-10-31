# Local workflow

Git and Python 3.11+ are required. Config and Build operate on the software checkout:

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
```

Create an explicitly selected external workspace with:

```bash
python3 configs/pcbknowledge_workspace.py init <workspace> --init-git
python3 configs/pcbknowledge_workspace.py validate <workspace>
```

Initialization copies pinned v2 schemas and initial registries and creates empty
collections. It never stages, commits or pushes. Existing v1 manifests are rejected;
re-extract selected records into a new v2 workspace. `pin-contract` is an explicit
software-authoring operation for the checkout's schema contract.

## Query and inspect

```bash
python3 configs/pcbknowledge_agent.py --repo <workspace> v2 validate
python3 configs/pcbknowledge_agent.py --repo <workspace> part search --role monitor.current
python3 configs/pcbknowledge_agent.py --repo <workspace> part show part:ti-ina219aidcnr
python3 configs/pcbknowledge_agent.py --repo <workspace> source authorize-read source:ti-ina219
python3 configs/pcbknowledge_workflow.py open --workspace <workspace>
```

The browser displays parts and blocks read-only. Select a citation beside a value
or pin to render the exact PDF page with pinned PDF.js. Evidence is read only
from the selected workspace; missing local cache files are reported explicitly.
The default URL is `http://127.0.0.1:18080/`. Keep the terminal open; Ctrl+C stops it.
`run` requires a current Build; `open` prepares software if necessary.

Author canonical JSON records with the repository's v2 skills and shared
serializer, then validate the complete workspace. No approval state or GUI write
path exists. A correction is a new Git commit, preserving actual verification
provenance. Before an authorized data commit run:

```bash
python3 configs/pcbknowledge_agent.py --repo <workspace> change-scope
```

`MIXED` is invalid. Never mix knowledge data with schema, workspace-contract or
policy changes. Source originals remain ignored and cannot enter packages.

## Gates and packages

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/check_pdfjs_vendor.py
python3 configs/pcbknowledge_workspace.py validate .
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py --repo . v2 validate
python3 configs/pcbknowledge_workflow.py package
```

Test and Package also accept `--workspace <workspace>`. Packages contain the
validated manifest, schema snapshot, registries and records, with output under
the software checkout's ignored `build/package/`. They are owner-facing metadata
snapshots; use `bundle build` for commit-pinned consumer bundles.

Manual acceptance: open a part, inspect an identity, a pin and a parameter citation,
and compare their numbered pages to the PDF. Open a block page;
check nets and constraints. Repeat with an external workspace and confirm its path
is displayed. Mutation requests must receive HTTP 405 and write no records.

## Original footprint generation and visual acceptance

Export derived geometry, never commit generated land patterns as authority:

```bash
python3 configs/pcbknowledge_agent.py --repo . footprint export --output build/footprints/pcbknowledge.pretty
kicad-cli fp export svg --output build/footprints/svg --layers F.Cu,F.SilkS,F.CrtYd build/footprints/pcbknowledge.pretty
```

Open `pcbknowledge.pretty` in KiCad's Footprint Editor. Compare SOIC-8 SN,
SOT-23-8 DCN and SOT-223 LD1117 against their cited package drawings. Check
pin 1 at upper left, counterclockwise electrical numbering, lead pitch, opposite
row span, and courtyard enclosure. The SOT-223 tab is a second physical pad
numbered 2 (VOUT), not electrical pin 4: the datasheet connection note controls
its electrical identity. Check source dimensions against the hand-calculated
coordinate tables in `test_v2_footprints.py`; do not compare only to another
copy of the generator. A native KiCad SVG export is an additional parser smoke
test, not a substitute for source-value and solderability review.

Coordinates are millimetres, top view, x right and y down; body width is along x
and body length along y. Standard packages store drawing dimensions, generator
and density only. Irregular connectors instead store explicit pads. Both forms
cannot coexist. Explicit plated slots use `drill_width` and `drill_height`, not
a scalar round drill; pad rotation also rotates the slot. Physically separate
pads may share one electrical number, but physical copper may not overlap.

These are original engineering rules, not IPC implementations. Gullwing and
molded-diode toe/heel/side extensions are 0.15/0.05/0.025 (COMPACT),
0.30/0.10/0.05 (NOMINAL), and 0.45/0.15/0.075 (ROBUST). Chip extensions
are 0.10/0/0.025, 0.20/0.05/0.05 and 0.30/0.10/0.075 respectively.
Outer lead bounds use maximum span; inner bounds use minimum span and maximum
lead length. Where SOT-223 has no lead-length dimension, the projected contact
extends from half the minimum body width to half the maximum lead span; this
is a derived engineering assumption, not an invented datasheet dimension.
Crystal pitch and row pitch are terminal-centre spacing, with cited terminal
metal width/height expanded by the selected extensions. Headers use a 0.30 mm
annular ring and, absent a cited drill, square-pin diagonal plus 0.20 mm clearance.
Courtyards enclose both maximum body and derived pads plus the recorded margin.
Manufacturing suitability still requires review against the actual assembly
process; density labels are not certification or guaranteed solderability.

## Coverage, commit-pinned bundles and design expansion

Inspect the selected workspace before committing its completed data:

```bash
python3 configs/pcbknowledge_agent.py --repo . v2 coverage evals/golden-designs/g1.block-graph.json
```

Use the actual reference-graph filename in the selected checkout. Coverage reports
remaining selections and inputs per block; it does not invent missing records.
`selections` lists all matching candidates; `selected_parts` identifies the part
expansion chooses by verification level, then stable ID. Only that chosen part
and its dependency closure determine readiness; an unselected DRAFT candidate
does not block a verified selection. A selected DRAFT dependency still blocks.
`INCOMPLETE` returns exit code 2.

After committing all authority changes, build a snapshot from the clean workspace:

```bash
python3 configs/pcbknowledge_agent.py --repo . bundle build
BUNDLE="build/bundle/$(git rev-parse HEAD).json"
python3 configs/pcbknowledge_agent.py --repo . part search --role regulator.linear.fixed --bundle "$BUNDLE"
python3 configs/pcbknowledge_agent.py --repo . block search --bundle "$BUNDLE"
python3 configs/pcbknowledge_agent.py --repo . registry show registry:roles --bundle "$BUNDLE"
```

Bundle queries use the validated snapshot, not uncommitted catalog edits. A bundle
contains commit-authenticated records and schemas, not cached source originals.
`source authorize-read` remains a workspace-only operation. A dirty workspace
cannot produce a bundle.

Expand an agent-authored graph and export only after successful expansion. This
`export` command produces a netlist and footprint library, not a board project.
For a parked project and judged board reports, follow the
[consumer guide](consumer-guide.md) and the derived KiCad handoff section below:

```bash
GRAPH=build/g1/graph.json
python3 configs/pcbknowledge_agent.py --repo . expand "$GRAPH" --bundle "$BUNDLE" --output build/g1/design-intent.json
python3 configs/pcbknowledge_agent.py --repo . export --bundle "$BUNDLE" --graph "$GRAPH" --intent build/g1/design-intent.json --output build/g1/export
```

Expansion prints the complete intent, including typed `REFUSED` reasons, and
returns exit code 2 for a refusal. When `--output` is supplied, the refused intent
is also saved for diagnosis; it is not an exportable design. Export independently
replays the graph against the pinned bundle and rejects changed or forged intents
before writing a netlist or footprint library. The export directory contains
`design-intent.json`, `graph.json`, `design.net` and `pcbknowledge.pretty`.
All output paths are resolved against `--repo` and must remain below its `build/`
directory, including after symlink resolution. Input graph, intent and bundle
paths are ordinary explicit input paths relative to the calling directory.

### Independent AI synthesis evaluation

For new corpus attempts, freeze content identity before giving the author its
input packet. The broker runs the following commands and retains the raw bundle;
query-mediated authors receive only standalone input and requested catalog packets,
never repository files, reference graphs or the bundle. A single skill smoke
attempt is not the three-author corpus acceptance evaluation:

```bash
python3 configs/pcbknowledge_agent.py --repo . bundle identity --bundle "$BUNDLE"
python3 configs/pcbknowledge_agent.py --repo . bundle snapshot --bundle "$BUNDLE" --brief G2 --skill .codex/skills/synthesize-block-graph/SKILL.md --output build/synthesis/g2-input.json
```

Preserve the snapshot with the attempts. Each new receipt has
`format: pcbknowledge.synthesis-receipt.v2` and copies its `input_identity`
(`catalog_tree`, `audit_sha256`, `engine_sha256`), alongside actual original
`bundle_commit`/`bundle_sha256`, actor, reviewer, orchestrator, mode, brief, skill,
transcript and output hashes. Positive reviews require a controlled
`EQUIVALENT`/`NOT_EQUIVALENT` verdict. Use `eval-synthesis --brief <ID>` with
`--orchestrator`, `--skill`, and the reference or expected refusal.

After a rebase, build a candidate bundle from the published clean checkout.
Recover the input identity without fetching the unpublished original commit:

```python
from pathlib import Path
from pcbknowledge.serialization import read_json
from pcbknowledge.v2.bundle import Bundle
from pcbknowledge.v2.synthesis_inputs import resolve_inputs

snapshot = read_json(Path("evals/synthesis/g2-input.json").read_bytes())
candidate = Path("build/bundle/<published-commit>.json")
with Bundle.from_document(resolve_inputs(snapshot, candidate)) as inputs:
    assert inputs.catalog_tree == snapshot["input_identity"]["catalog_tree"]
```

A changed catalog, audit input, brief, skill or engine is not a rebase. Keep the
matching input data commit reachable and use its bundle; a missing candidate
fails explicitly. Never rewrite the author's original commit or file hash to the
candidate's values. For preserved Stage 8 commit-only receipts only, add
`--historical`; evaluation still validates their exact original inputs.
For prior v2 receipts after an engine change, use `resolve_replay_inputs` and
`eval-synthesis --replay`. The result separately identifies original and current
engines; all content, skill, transcript and review checks still apply. Retain the
original receipt and result rather than relabeling the new replay as its execution.

The following legacy G1 procedure remains for its already preserved receipts:


Run three genuinely separate agents with only the brief, skill and pinned query
CLI. Do not expose the reference graph or other attempts. Preserve each original
graph and a receipt containing `agent`, independent `reviewer`, `bundle_commit`,
`brief_sha256`, `graph_sha256` and `reference_accessed: false`. Hashes use the
repository canonical JSON encoding. Put each graph and receipt together under
`graph` and `receipt` in an attempt JSON. Receipts attest the actual orchestration;
JSON alone cannot prove model independence. A non-identical but electrically
equivalent topology requires a substantive independent `equivalence_review`.

```bash
python3 configs/pcbknowledge_agent.py --repo . eval-synthesis --bundle build/bundle/<commit>.json --reference evals/golden-designs/g1.block-graph.json --attempt build/synthesis/one.json --attempt build/synthesis/two.json --attempt build/synthesis/three.json --output build/synthesis/result.json
```

The command re-expands every attempt and the reference from the same immutable
bundle; a refusal is never A2. At least two of three must pass. Board oscillator
startup, assembly and bring-up remain Stage 7 physical verification, not software
claims of manufactured performance.

Graph requirement labels are the IDs from the brief's functions, interfaces,
constraints and mechanical mounting items, never prose descriptions. Their
union across the graph and instances must match that complete set. A function
ID appears on exactly its requested number of implementing instances.

The preserved G1 attempts in `evals/synthesis/g1/` target catalog commit
`ad7b84352f27cff6a65ec24e43eb474a42506ec2`. Rebuild its bundle from a clean detached
worktree at that commit to reproduce their original input, and run that
checkout's evaluation command against the preserved attempt files. Current
contracts additionally require package scopes, assembly metadata and audited
graph inputs; historical bundles are not silently migrated by the current loader. Their author receipts
retain the actual input hashes and iterative public-contract clarification.
All three graphs were authored in distinct fresh contexts without reference
access and independently reviewed; moving `monitor_scope` to the graph level
is documented as electrically equivalent.

For the netlist-only `export` workflow, KiCad 9's official `kicad_netlist_reader`
accepts the exported XML, including complete component/library links.
`kicad-cli pcb` offers no netlist-import subcommand: import `design.net` manually
in PCB Editor after adding the generated `pcbknowledge.pretty` library, then
inspect associations and unrouted nets. Alternatively, `layout export` below
already produces a parked native project and needs no netlist-import step.
Placement, routing and physical acceptance remain separate.

## Fetch or add local evidence

```bash
python3 configs/pcbknowledge_agent.py --repo . evidence fetch
python3 configs/pcbknowledge_agent.py --repo . evidence fetch --source source:st-ldl1117
python3 configs/pcbknowledge_agent.py --repo . evidence add /path/to/manually-downloaded.pdf
```

Fetching requests only missing, processing-eligible sources at their recorded
HTTPS URLs. An already verified original returns `MATCH` with `cached: true`.
A new matching download enters the local SHA-256 cache; `DIFFERENT_BYTES` keeps
the actual bytes separately under `.pcbknowledge/evidence/different/` and never
changes a source record or overwrites the expected original. `FAILED` includes
the HTTP status when the server supplies one. Requests have size/time limits,
validate public redirect destinations and never retry or switch hosts after an
access failure. No credentials, cookies or source bytes enter public Git.

ST and Wurth blocked some scripted requests with HTTP 403 on 2026-10-29. Stop
at access controls or bot checks. If the publisher permits an ordinary manual
download, use its normal download process and then `evidence add`; the import
accepts only bytes whose SHA-256 matches an eligible recorded source. An unknown
or blocked source is not made eligible by importing it.

Some generated spec sheets stamp the download date into their bytes. The same
URL can therefore produce `DIFFERENT_BYTES` later. Review that document as a new
source revision rather than editing the stored digest to suppress a mismatch.
The evidence cache is local and ignored; fetch/import does not alter knowledge.

HTML citations in the local catalog open the recorded publisher HTTPS URL in a
separate tab, with the recorded SHA-256 and access date displayed beside the link.
The live page can differ from the cached snapshot. Saved HTML is never served as
active content from the local application's origin, and its `/content` endpoint
is rejected rather than passed to PDF.js. Engineering-default mechanical records
without source/page citations display an explicit no-citation label.

## Derived KiCad handoff and read-only board checks

The [consumer guide](consumer-guide.md) describes the complete input/output
contract. [Owned consumer reports](knowledge-model-v2.md#owned-consumer-reports)
defines report versions, validation and `identity` fields: bundle commit, graph
digest, canonical intent digest and board-byte digest where applicable. Preserve
the exact input files with each report. Digests are not signatures or proof that
a saved measurement was performed on those inputs.

Build a clean commit-pinned bundle and expand the original graph first. Keep the
bundle, graph and intent together; neither a saved `PASS` label nor an edited
intent replaces revalidation against those inputs.

```bash
python3 configs/pcbknowledge_agent.py --repo . layout export \
  --bundle build/bundle/<commit>.json --graph evals/golden-designs/g1.block-graph.json \
  --intent build/g1-intent.json --output build/g1-handoff
python3 configs/pcbknowledge_agent.py --repo . layout check \
  build/g1-handoff/design-intent.json build/g1-handoff/design.kicad_pcb \
  --bundle build/bundle/<commit>.json --graph evals/golden-designs/g1.block-graph.json \
  --output build/g1-layout-report.json
python3 configs/pcbknowledge_agent.py --repo . drc build/g1-handoff/design.kicad_pcb \
  --intent build/g1-handoff/design-intent.json --bundle build/bundle/<commit>.json \
  --graph evals/golden-designs/g1.block-graph.json --output build/g1-drc-report.json
```

Open `design.kicad_pro` in KiCad 9, retaining the adjacent `.kicad_dru`, local
footprint library and `fp-lib-table`. Mounting holes follow the intent, while
all electrical footprints are parked outside the outline. The owner or PcbAtlas
must place and route them. Do not fabricate this skeleton. `assembly.csv` lists
orderable identities, references and mount/assembly classification; it is not a
placement/CPL file.

Save an exported board after editing, then rerun both checks against the same
pinned authority. The checker reads files only; the DRC wrapper uses temporary
copies and isolated settings. Reports are derived JSON below `build/`, never
edits to the board. A DRC-only invocation without intent/bundle/graph reports the
native result but cannot claim complete layout conformance.

Results distinguish `FAIL`, `NOT_CHECKABLE` and `NOT_RUN`. Missing KiCad is not a
pass. Unrouted or out-of-outline findings are expected for a parked skeleton,
not acceptable waivers for a finished board. Unsupported outline/courtyard/fill
geometry and ambiguous Kelvin sense branches remain explicit. Loop-area checks
are pad-center bounding-polygon estimates, not proof of a routed return path;
keepout checks are conservative courtyard-envelope comparisons. See
[ADR-025](adr/ADR-025-derived-board-handoff.md) for measurement scope. PcbKnowledge acceptance ends at A2. A3-A5 belong to PcbAtlas or a manual layout;
ordering and physical bring-up remain owner-only activities.

### Explicit Kelvin branch checks

KELVIN declarations may carry two ordered `branches`, each naming the exact sense
pin, corresponding shunt pin and source/page anchor. Expansion binds each pair to
its declared sense net; editing a saved intent cannot substitute another pair.
Unmapped legacy declarations remain `NOT_CHECKABLE`.

The checker measures supported straight finite-width copper and solid rectangular
or circular SMD pads on a closed rectangular board. A direct sense branch may join
load-current copper only within its specified shunt pad. A proven connection to a
supply/load terminal outside that pad fails. Unresolved input filters, crossing
contacts, relevant vias, zones, drilled pads and unsupported shapes remain
`NOT_CHECKABLE`; remote unsupported objects are ignored only when their separation
is proved. Optional INA219 input filters are not prohibited by the datasheet.
Copper drawings/text that the reader cannot project also remain explicitly unknown.
These measurements neither route the board nor replace external DRC.

### Connected filled-copper area

`layout check` applies D79 to `COPPER_AREA` using exact rational area and
positive-area contact with a cardinal rectangular, solid SMD target pad. It
subtracts recognized keyhole-contour holes and can sum disjoint filled regions
joined directly by that physical pad. A disconnected island does not increase the
measured area. A supported direct region below the declared bound fails.

Overlapping or touching regions requiring a union, ambiguous repeated pads,
unresolved drill voids and unsupported target shapes remain `NOT_CHECKABLE`.
If tracks, vias or another pad might connect additional material needed to reach
the bound, that indirect connection is also `NOT_CHECKABLE`. This checker reads
exported fills; it neither generates copper nor changes the area requirement.

## Optional manual external-tool checks (D78)

PcbKnowledge accepts designs through A2. Placement, routing, zone fill, native DRC
and fabrication belong to PcbAtlas or a manual layout, not this repository.
The retired `layout tools` and `layout run` commands are unavailable.

A developer may open the parked handoff in an independently installed KiCad or use
Freerouting manually to investigate a catalog constraint or footprint. Keep the
original pinned bundle, graph, intent, adjacent project/rules and footprint library;
record the exact external command and tool version with any resulting finding.
Keep boards, receipts and rendered comparisons locally under `build/`; do not commit
them. A finding must be corrected at its knowledge source and covered by a tool-free
regression, not bypassed by changing a constraint or accepting a DRC waiver.

The retained `layout check` and optional thin `drc` commands above inspect supplied
files. External tools are not prerequisites for CI, expansion or A2 acceptance.
Bring-up report generation remains tool-free and supports an absent placed board;
physical measurements and ordering remain owner-only activities.

### Conditional waveform bring-up

Regenerate the JSON plan and human checklist from one clean committed bundle:

```sh
python3 configs/pcbknowledge_agent.py --repo . bringup \
  --bundle build/bundle/<commit>.json --graph evals/golden-designs/g2.block-graph.json \
  --intent build/g2-intent.json --output build/g2-bringup.json --markdown build/g2-bringup.md
```

The CLI replays the supplied graph and intent against the bundle before writing
under `build/`. It does not modify the graph, bundle or intent.

A bring-up rail declares either `expected_voltage` or `waveform`, never both.
D91 binds G2 BUCK_SW to TPS5430 PH pin 8, ground pin 6 and synchronous VIN pin 7.
The report exposes `expected_waveform` with the complete typed acquisition protocol,
source limits from the selected part and explicit probe locations. Its checklist
prints every level, edge, excursion, uncertainty and acquisition setting.
`range_coverage: COMPLETE` means all rails have measurement plans; hardware results
and conditions remain `NOT_RUN`. Removing the waveform declaration leaves BUCK_SW
`UNKNOWN`; a DMM reading cannot replace it.

D105's high plateau is relative to measured VIN, its low plateau to ground.
The high-drop budget uses D50's modeled hot resistance at the declared peak current;
the low-drop budget uses the cited SS14 value as context, with an engineering margin.
Neither extends the datasheet's RDS(on) or diode test conditions. The operator must
establish the D103 thermal/current prerequisites and fit full measurement uncertainty
inside each acceptance envelope. Source absolute ratings bound the protocol, not
nominal behavior. No waveform acquisition or measured-pass evaluator is implemented.

### Return-copper measurement

`layout check` applies D100 to `RETURN_PATH`: every observed straight signal
segment must have its full width covered by simple filled return copper on the
opposite layer of a closed rectangular two-layer board. Possible intersecting
drill apertures and board slots remain `NOT_CHECKABLE`. The covering polygon must directly contact
a solid SMT pad on that return net. Reports include the reference layer, squared
boundary distance and failed segment indices. Interior slots and wrong-net copper
fail; unsupported geometry, signal vias and via-only return contact remain
`NOT_CHECKABLE`. Pad-edge-only contact that is possible but unmeasured is also
`NOT_CHECKABLE`, rather than a false failure. This is a read-only measurement of exported copper, not a router.

D107 additionally checks observed arcs by an exact circumcircle and an outward
1 nm rounded full-circle bounding box. One simple opposite-layer return polygon
must contain the entire box and track width; its physical pad contact must survive
possible drill intersections. The expanded box must stay inside the board outline
and contain no possible physical holes. Reports identify the enclosure method and
bounds. Failure to prove this conservative enclosure is `NOT_CHECKABLE`, even if
the actual arc might fit. Signal vias and layer transitions remain unresolved.

### Guard enclosure measurement

`layout check` applies D101 to `GUARD_RING`. The protected `net` identifies all
its pads and routed tracks, not a selected subset. Every exposed F/B copper
surface is checked independently, including both faces of through-hole pads.
Each surface requires a simple closed straight-track cycle on `guard_net`.
All surfaces must pass; a missing lower-face ring fails even with a valid top ring.
The report retains per-surface width, clearance, enclosure and contact results.

Guard contact is proved by explicit same-layer track endpoints, positive-area
contact with solid SMT copper, and plated through-vias whose center-ended tracks
cross the annulus beyond the drill radius. Via evidence identifies participating
tracks; annular width participates in the ring minimum where the drill intersects
ring tracks. A remote SMT source can therefore supply both surface rings.

Exact rectangle, circle and cardinal oval pad extents and all straight sensitive
tracks participate in clearance checks, including guard pads, vias and feed branches.
Arcs, sensitive-net vias, filled guard/signal zones, ambiguous intersections,
non-center via contacts, possible drill interruptions and pad-mediated ring closure
remain `NOT_CHECKABLE`. An open, narrow, floating, misplaced or insufficient-clearance
supported ring fails. This read-only check generates no copper.

### Copper-edge placement distance

`PLACE_NEAR.datum` defaults to `ORIGIN_PAD_CENTER`. D90 selects `COPPER_EDGE` for
all ten G2 buck rules without changing their numbers. This is the owner's distance
decision, not a datum explicitly stated by TI. The read-only check compares the
subject component's same-net pads with the named target pin's physical pads on a
common copper layer. Exact supported outlines retain selected pin identities,
layer, distance and limit. Unsupported outlines or absent eligible pairs return a
typed reason; there is no center or different-net fallback. The C4-to-L1 rule has
no same-net pair across its series ESR resistors and remains an open owner question.

### Necessary distance audit

`v2 validate` and bundle compilation apply D106 to expanded design graphs. An
explicit `KEEPOUT` already excludes every other projected authoritative courtyard,
regardless of copper surface. For a center-based `PLACE_NEAR` pair, the audit uses
a disk inside each courtyard centered on the actual measurement point, including
physical pin centers. The sum of radii and exclusion margin is a necessary distance
lower bound under any rotation. Multiple eligible pads use the smallest radius.

A bound strictly greater than the unchanged limit rejects validation with both
references and the bound. Equality is not rejected. `near_bounds_checked` counts
expanded graph/rule occurrences, not unique rules or feasible layouts. No exclusion
premise, unsupported endpoints and `COPPER_EDGE` produce no proof; they retain their
normal runtime checks. The audit neither places parts nor establishes joint layout
feasibility, and does not impose a universal courtyard exclusion where none exists.

### Native exported-board regression corpus

Nine small original fixtures in `tests/fixtures/layout/native/` were saved and
reloaded by KiCad 9.0.2; boards with zones were filled by that external tool.
They exercise straight tracks, arcs, plated vias, real fill polygons and two-face
guard connectivity. Reproduce the tool-free measurements and per-kind rates with:

```sh
PYTHONPATH=src python3 -B -m tests.git_native.test_layout_native_boards
```

The report distinguishes a full identity-checked simple board from isolated
constraint probes on the other boards. Negative cases remain failures, and
`NOT_CHECKABLE` remains part of each kind's denominator. Reserved, unimplemented
registry kinds are included rather than silently excluded. These results do not
establish complete routing or replace the owner's DRC and hardware checks.
