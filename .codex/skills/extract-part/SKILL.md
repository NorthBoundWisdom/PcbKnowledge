---
name: extract-part
description: Extract an exact v2 orderable part, numbered pin map and parameters from eligible registered source pages.
---

# Extract Part

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

Use `source authorize-read <source-id>` before reading each registered source.
Resolve manufacturer, exact orderable MPN and package from the cited pages; do not
infer a variant from a related device or suffix. Follow
[the part schema](../../../schemas/part.schema.json) and parameter/pin/role registries.

Cite `identity_evidence` and `pin_evidence` separately. Every datasheet quantity
carries its source and 1-based PDF page, canonical unit and structured conditions.
Do not manufacture terminal numbers from package conventions. If a complete
numbered map is unavailable, report that blocker instead of creating a guessed part.
Quantity facts may be typed `UNKNOWN` with reason and affected queries. Design
choices use `ENGINEERING_DEFAULT`, not missing-evidence status.

Create as `DRAFT` with the actual creator. Package references must close; unresolved
geometry remains explicit for the footprint stage. Request independent verification
before upgrading to `AGENT_VERIFIED`.
