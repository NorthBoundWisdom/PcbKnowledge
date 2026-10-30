# PcbKnowledge

[![CI](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml/badge.svg)](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml)

PcbKnowledge supplies Git-native engineering knowledge for a pipeline from a
design brief to a manufacturable PCB. PcbAtlas owns synthesis orchestration,
placement, routing, DRC and fabrication output. The product direction is
[ADR-022](docs/adr/ADR-022-board-generation-knowledge.md).

The runtime uses one v2 model and shared structural/semantic validation, a
read-only catalog, original footprint generators and commit-pinned deterministic
design expansion. G1 has 100% catalog coverage and reaches A2 with its reference
graph and all three independently authored AI graphs. G2 reaches A2 with its
reference, three fresh graphs and separately recorded current-catalog regression;
switching-power and external-load models retain explicit source conditions. G3
adds a reference analog acquisition design with declared bench models and
functional wiring checks; its independent synthesis evaluation is pending. Hardware
fabrication and bring-up are not claimed. Derived KiCad 9 handoff, read-only exported-board
checks and an optional isolated DRC wrapper support the owner's layout work;
parked skeletons and incomplete geometry checks are not A3/A4 acceptance.
[`TODO.md`](TODO.md) records the acceptance receipts and remaining work.

## Use

Git and Python 3.11+ are required; runtime code uses the standard library.

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_agent.py --repo . v2 validate
python3 configs/pcbknowledge_agent.py --repo . part search --role monitor.current
python3 configs/pcbknowledge_agent.py --repo . v2 coverage evals/golden-designs/g1.block-graph.json
python3 configs/pcbknowledge_agent.py --repo . v2 coverage --all
python3 configs/pcbknowledge_agent.py --repo . v2 coverage --all --json
python3 configs/pcbknowledge_agent.py --repo . bundle build
python3 configs/pcbknowledge_workflow.py open --workspace .
```

The viewer runs at `http://127.0.0.1:18080/`; keep the terminal open and use Ctrl+C
to stop. Select a citation to inspect its source evidence. The GUI and query CLI are
read-only. Missing facts stay explicit; generation refuses rather than guesses.

`coverage --all` prints one JSON line per brief, retaining every preserved graph,
block readiness, eligibility and typed refusals. Missing graphs are `NOT_RUN` and
incomplete coverage exits 2. Use `--json` for one aggregate report or `--human` for
a readable summary. The single-graph command remains JSON. Coverage is not a fresh synthesis receipt.
The [golden-design corpus](docs/golden-designs.md) defines positive variants and
negative refusal cases, with query-mediated independent evaluation.

## Workspaces and evidence

```bash
python3 configs/pcbknowledge_workspace.py init <workspace> --init-git
python3 configs/pcbknowledge_workspace.py validate <workspace>
```

A workspace is one Git repository with pinned schemas, registries and canonical
JSON records. Select it with `--workspace` or `--repo`; explicit selection never
falls back. Initialization never stages, commits or pushes.

Source originals stay in ignored `.pcbknowledge/evidence/sha256/` caches. Public
Git and packages contain small original metadata and citations. Cache absence is
`NOT_LOCALLY_VERIFIED`. Explicit cache imports are separate from read-only queries:

```bash
python3 configs/pcbknowledge_agent.py --repo . evidence fetch --source source:example
python3 configs/pcbknowledge_agent.py --repo . evidence add /path/to/original.pdf
python3 configs/pcbknowledge_agent.py --repo . v2 audit
```

Use an existing eligible source ID. Fetch/add never edit knowledge or Git; changed
bytes remain separate and failed fetches do not bypass access restrictions.
`v2 validate` rejects unreachable parts, packages and sources. See [local workflow](docs/local-workflow.md),
[architecture](docs/architecture.md), [knowledge model](docs/knowledge-model-v2.md)
and [public-source boundary](docs/open-source-boundary.md).

## Verify

```bash
python3 configs/check_commits.py origin/main..HEAD
python3 configs/check_code_style.py
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

Read [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Report vulnerabilities through
[`SECURITY.md`](SECURITY.md).

Software and repository documentation use [Apache-2.0](LICENSE) unless stated
otherwise. Vendor assets and cited engineering documents retain their own rights.
