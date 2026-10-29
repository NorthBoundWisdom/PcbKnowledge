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
