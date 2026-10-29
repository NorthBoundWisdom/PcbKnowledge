# Legacy subsystem documentation

These pages describe code that still runs at the time of writing but is scheduled
for removal or replacement by [ADR-022](../adr/ADR-022-board-generation-knowledge.md).
They stay accurate while the code exists. Delete each page in the same change that
deletes its code; see [`TODO.md`](../../TODO.md) for the order.

| Folder / page | Subsystem | Planned outcome |
| --- | --- | --- |
| [`intake/`](intake/lightweight-knowledge.md) | Noncanonical intake queue, its CLI, workbench page, bundle, report, audit and preflight tools | Frozen; golden-design parts migrate to v2, then deleted |
| [`pilot/`](pilot/pilot-evaluation.md) | P0.4a pilot harness | Deleted in Stage 0 |
| [`worked-examples/`](worked-examples/resistor-dc-bound.md) | Fixed per-device evaluators in `configs/pcbknowledge_*_eval.py` | Deleted in Stage 0 |
| [`agent-workflow-v1.md`](agent-workflow-v1.md) | v1 typed Source/Entity/Fact ingestion and repository skills | Replaced by the v2 workflow |
