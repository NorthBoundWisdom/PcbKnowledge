---
name: write-block
description: Author a v2 reusable circuit block from verified catalog parts and registered constraints.
---

# Write Block

Operate only in the workspace explicitly selected for this task. Run
`python3 <software>/configs/pcbknowledge_workspace.py validate <workspace>` first.
Use `--repo <workspace>` on every query. A workspace failure never permits fallback.

Records are canonical sorted UTF-8 JSON files in `knowledge/`, checked by the
workspace's pinned schemas and runtime validator. Use
`pcbknowledge.serialization.canonical_json` when authoring them. Edit these files
as the one authority path; the browser and query CLI are read-only. Validate the
whole catalog with `python3 <software>/configs/pcbknowledge_agent.py --repo <workspace> v2 validate`.
Keep data separate from schemas and policy; run `change-scope` before an authorized
commit. Respect the task's existing commit/push authorization.

Query `part search`, `part show` and `registry show` in the selected workspace.
Use [the block schema](../../../schemas/block.schema.json). Declare typed parameters,
ports, component selections, nets, checks and layout constraints that serve the
selected brief or an identified consumer query.
Every reference and component pin must resolve; a role selector must have a
satisfying catalog part. Checks are structured data, never executable expressions.

Use only supported calculator implementations, their required typed inputs and
registered constraint kinds. Validate calculated quantities with their declared
calculator and inputs; do not substitute a guessed result.
Record evidence beside source-backed values and actual creator/verifier identities.
Validation establishes record closure; actual expansion checks A1/A2 for a pinned
design. Follow the [consumer guide](../../../docs/consumer-guide.md) for expansion
and derived handoff checks. A shape-only check does not establish acceptance;
parked handoff files are not placed or routed boards.
