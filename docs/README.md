# PcbKnowledge documentation

The active roadmap is the root [`TODO.md`](../TODO.md). Agent rules are in the root
[`AGENTS.md`](../AGENTS.md).

## Current

| Topic | Document |
| --- | --- |
| Direction and why it changed | [ADR-022](adr/ADR-022-board-generation-knowledge.md) |
| System boundary, current code status, target summary | [`architecture.md`](architecture.md) |
| Target data model, consumer queries, API | [`knowledge-model-v2.md`](knowledge-model-v2.md) |
| Golden designs, brief format, acceptance levels A1 to A6 | [`golden-designs.md`](golden-designs.md) |
| Public versus private content and source originals | [`open-source-boundary.md`](open-source-boundary.md) |
| Local Config/Build/Open/Test/Package and workspaces | [`local-workflow.md`](local-workflow.md) |
| Architecture decisions | [`adr/README.md`](adr/README.md) |
| Course-correction brief for implementers (temporary) | [`course-correction-prompt.md`](course-correction-prompt.md) |

## Legacy and archive

- [`legacy/`](legacy/README.md): accurate descriptions of subsystems that still
  run but are scheduled for removal (intake queue, pilot harness, worked-example
  evaluators, v1 typed ingestion). Delete each document with its code.
- [`archive/`](archive/README.md): frozen historical receipts (batch evaluations,
  owner acknowledgements, application handoffs, source investigations). Not
  maintained; useful only as source material during migration.

## Maintenance rules

1. One durable authority per topic; other documents link to it.
2. Code, schemas and tests are the authority. When a contract changes, update the
   matching document in the same change.
3. Unfinished work lives only in `TODO.md`. Do not create per-batch, per-stage or
   per-receipt documents; put receipts in commit messages and one-line TODO entries.
4. When moving or deleting a document, fix every link in the same change.
5. Repository documents stay English.
