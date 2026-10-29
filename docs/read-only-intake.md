# Read-only intake commands

The intake CLI reads the selected working-tree metadata without initializing a
canonical workspace layout or writing cache, index, evidence or receipt files:

```bash
python3 configs/pcbknowledge_agent.py --repo <workspace> intake list
python3 configs/pcbknowledge_agent.py --repo <workspace> intake search --device SYNTH-A
python3 configs/pcbknowledge_agent.py --repo <workspace> intake issues --device SYNTH-A
python3 configs/pcbknowledge_agent.py --repo <workspace> intake coverage
python3 configs/pcbknowledge_agent.py --repo <workspace> intake report --device SYNTH-A
python3 configs/pcbknowledge_agent.py --repo <workspace> intake bundle --device SYNTH-A
```

`SYNTH-A` is an invented filter example, not component knowledge. `list` returns
intake metadata batches; `search` returns noncanonical fact candidates; `issues`
returns source warnings and any validated handling receipts. `report` renders
a [scoped Markdown inspection aid](intake-report.md) with full recorded conditions
and warnings; at least an exact source ID or device is required. `bundle` captures
a [machine-readable scoped handoff](intake-bundle.md) with complete source context
and per-record metadata pins, also requiring an exact source ID or device. See the
[coverage inventory](intake-coverage.md) for the aggregate view and the
[lightweight contract](lightweight-knowledge.md) for authority boundaries.

The intake handlers leave the selected repository's files, directory layout, Git
index and existing local cache unchanged. Missing intake returns an empty result, unless an invalid
or orphan handling receipt makes the read fail. Read-only filesystem permissions
do not prevent these commands when the required metadata remains readable. No
canonical Source/Entity/Fact records or source-original bytes are loaded by the
intake readers. Recorded evidence remains `NOT_LOCALLY_VERIFIED`; this behavior
does not establish electrical correctness or canonical approval.

Python may separately create ordinary `__pycache__` files in the software checkout
when importing modules. Use `python3 -B` if those interpreter caches must also be
suppressed, especially when software and workspace share the same directory.

The public wrapper still validates the explicit workspace contract and pinned
schemas before dispatch. An empty Git repository without that contract is not a
valid public workspace. The internal Python CLI still requires a Git repository;
it can inspect an empty queue without creating the missing layout. Neither entry
point falls back to another repository. Other CLI command families retain their
existing initialization behavior; this is not a claim that every CLI command is
read-only.

Validation remains fail-closed. Invalid intake bytes or links, stale/orphan
dispositions and invalid filters return status 2 without partial JSON output or
filesystem changes. Unknown subcommands and unsupported options remain parser
errors and do not initialize a layout.

## Regression checks

`tests/git_native/test_intake_read_only.py` exercises all three existing read
commands through the internal CLI and public wrapper. It compares complete
before/after trees, including empty directories, file bytes, modes, modification
times and an existing Git index, and also runs against chmod-read-only temporary
repositories. It covers successful empty/populated reads, malformed input,
disposition errors, invalid filters, parser errors and workspace rejection. The
separate coverage and report tests cover their projections and read-only contracts. Read-access timestamps are outside the snapshot assertion.

Local verification on 2026-10-28: all 10 new tests and all 67 focused intake tests
passed. Build and Test each passed 218 tests with no skips; the 70 pinned CLI
cases, Config, workspace/Agent validation, English/public/PDF.js guards and
metadata-only Package exited 0. Independent review found no blocking issue and
also checked six unsafe-symlink cases across both entrypoints. These are software
regression results, not source evidence or owner acceptance. Remote CI is verified
separately for the published commit.
