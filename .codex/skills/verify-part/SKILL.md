---
name: verify-part
description: Independently recheck every cited value and numbered pin in a v2 part against its exact local sources.
---

# Verify Part

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

The verifier must be independent of the creator. Use `source authorize-read` and
recompute source hashes/sizes before inspecting exact cited pages. Recheck exact
orderable identity, package, every pin number/name/type, parameter value, unit,
condition and evidence anchor. Inspect drawings visually where text loses layout.

Correct source-grounded errors and recheck the final exact JSON. Only then set
`AGENT_VERIFIED` and record the actual verifier in `provenance.verified_by`.
A human verification requires a person who actually performed it; delegation is
not a human observation. Leave unresolved geometry and other drafts at their real
level. Validate the whole selected workspace after the update and report the
actual reviewed fields, corrections and command results.
