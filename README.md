# PcbKnowledge

[![CI](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml/badge.svg)](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml)

PcbKnowledge is the knowledge side of a pipeline that turns a design package (for
example a simple hardware-competition brief) into a manufacturable PCB. It keeps a
closed-world, evidence-backed catalog of parts, footprints, reusable circuit blocks,
layout rules, fab profiles and calculators in Git, and expands a block graph into a
design intent (netlist, BOM and layout constraints) for
[PcbAtlas](docs/architecture.md#1-product-role) to place, route, check and fabricate.

Unknown is a result: missing evidence makes generation refuse rather than guess.

## Status

The project is in **Stage 0, course correction**. The direction changed on
2026-10-29 ([ADR-022](docs/adr/ADR-022-board-generation-knowledge.md)):

- The earlier review-centric design is implemented and tested, but its canonical
  store is empty and its 329 curated intake annotations are prose-heavy and not
  machine-queryable. The intake queue is now frozen.
- The target is the [v2 knowledge model](docs/knowledge-model-v2.md), driven by
  [golden designs](docs/golden-designs.md). The first target, G1, is a small
  USB-powered sensor-logger board that must go all the way to a working fabricated board.

See [`TODO.md`](TODO.md) for the stage plan and [`docs/`](docs/README.md) for
documentation.

## Requirements

- Git
- Python 3.11+

No Docker, database, account system, hosted service or Node runtime is required.

## Quick start

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
```

Browse the frozen intake collection in this checkout (read-only, noncanonical):

```bash
python3 configs/pcbknowledge_agent.py --repo . intake list
python3 configs/pcbknowledge_agent.py --repo . intake search LD1117
python3 configs/pcbknowledge_workflow.py open --workspace .
```

`open` serves a loopback-only workbench at `http://127.0.0.1:18080/` by default;
keep the terminal running and use Ctrl+C to stop it. Details of the legacy
commands are in [`docs/legacy/`](docs/legacy/README.md).

## Workspaces

A knowledge workspace is a Git repository with a pinned manifest and schemas. This
checkout holds public curated data; private knowledge goes in a separate workspace:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData --init-git
python3 configs/pcbknowledge_workspace.py validate ../PcbKnowledgeData
```

Selection is always explicit (`--workspace` or `--repo`). Initialization never
stages, commits or pushes. See [local workflow](docs/local-workflow.md).

## Evidence and public-source boundary

Source documents are identified by the SHA-256 of their bytes. Originals live only
in the ignored local cache `.pcbknowledge/evidence/sha256/` and are never committed
or packaged. The public repository accepts small original summaries and metadata
only. See [open-source boundary](docs/open-source-boundary.md).

```bash
python3 configs/check_public_repo.py
python3 configs/check_english_repo.py
```

## Verification

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/check_pdfjs_vendor.py
python3 configs/pcbknowledge_workspace.py validate .
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

A skipped, interrupted or truncated run is not a pass.

## Contributing

Read [`AGENTS.md`](AGENTS.md), [`CONTRIBUTING.md`](CONTRIBUTING.md),
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and
[`docs/open-source-boundary.md`](docs/open-source-boundary.md). Report security
issues privately according to [`SECURITY.md`](SECURITY.md).

## License

Software and repository documentation are licensed under the
[Apache License 2.0](LICENSE) unless a file states otherwise. Vendored third-party
assets keep their upstream licenses. Third-party engineering documents keep their
own rights.
