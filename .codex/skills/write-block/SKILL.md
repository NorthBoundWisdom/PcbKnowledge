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
ports, component selections, nets, checks and layout constraints that serve G1.
Every reference and component pin must resolve; a role selector must have a
satisfying catalog part. Checks are structured data, never executable expressions.

Use only supported calculator implementations and registered constraint kinds.
Until Stage 4 calculators exist, calculator checks and `CALCULATED` quantities
are refused.
Record evidence beside source-backed values and actual creator/verifier identities.
Validation establishes record closure; Stage 5 expansion establishes A1/A2 for a
pinned design. Do not mark a golden acceptance level from a shape-only check.
