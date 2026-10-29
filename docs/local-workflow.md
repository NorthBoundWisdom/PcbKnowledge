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
snapshots; Stage 5 implements commit-pinned consumer bundles.

Manual acceptance: open a part, inspect an identity, a pin and a parameter citation,
and compare their numbered pages to the PDF. Open a block page when blocks exist;
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

Expand an agent-authored graph and export only after successful expansion:

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

KiCad 9's official `kicad_netlist_reader` accepts the exported XML, including
complete component/library links. `kicad-cli pcb` offers no netlist-import
subcommand: full PCB import remains a manual KiCad step, not a claimed CLI pass.
Import `design.net` in PCB Editor after adding the generated `pcbknowledge.pretty`
footprint library, inspect all associations and unrouted nets, and perform the
Stage 7 layout/DRC/hardware checks separately.

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
