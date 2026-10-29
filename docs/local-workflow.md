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
