# PcbKnowledge documentation

The active roadmap is the root [`TODO.md`](../TODO.md). Agent rules are in the root
[`AGENTS.md`](../AGENTS.md).

## Current

| Topic | Document |
| --- | --- |
| Direction and why it changed | [ADR-022](adr/ADR-022-board-generation-knowledge.md) |
| System boundary, current code status, target summary | [`architecture.md`](architecture.md) |
| V2 contracts, consumer queries and implementation boundary | [`knowledge-model-v2.md`](knowledge-model-v2.md) |
| Golden designs, brief format, acceptance levels A1 to A6 | [`golden-designs.md`](golden-designs.md) |
| Public versus private content and source originals | [`open-source-boundary.md`](open-source-boundary.md) |
| Local Config/Build/Open/Test/Package and workspaces | [`local-workflow.md`](local-workflow.md) |
| Architecture decisions | [`adr/README.md`](adr/README.md) |
| Implementer brief for the current round (temporary) | [`implementer-brief.md`](implementer-brief.md) |

## History

[`archive/`](archive/README.md) and Git retain historical receipts. The retired
intake input is available at the `intake-final` tag; current records are v2.

## Maintenance rules

1. One durable authority per topic; other documents link to it.
2. Code, schemas and tests are the authority. When a contract changes, update the
   matching document in the same change.
3. Unfinished work lives only in `TODO.md`. Do not create per-batch, per-stage or
   per-receipt documents; put receipts in commit messages and one-line TODO entries.
4. When moving or deleting a document, fix every link in the same change.
5. Repository documents stay English.
