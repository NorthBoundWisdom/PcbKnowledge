# PcbKnowledge documentation

`docs/` contains the durable product, architecture, open-source-boundary, workflow, and evaluation documentation. The repository root keeps the active execution roadmap in [`TODO.md`](../TODO.md).

## Start here

| Topic | Authoritative document |
| --- | --- |
| Product role, Git-native authority, runtime boundary, and evolution | [`architecture.md`](architecture.md) |
| Separation between open-source software and private knowledge/evidence | [`open-source-boundary.md`](open-source-boundary.md) |
| Local workflow for product managers and engineers | [`local-workflow.md`](local-workflow.md) |
| Agent typed ingestion and human handoff | [`agent-workflow.md`](agent-workflow.md) |
| P0.4a private pilot evaluation contract and closure gates | [`pilot-evaluation.md`](pilot-evaluation.md) |
| P0.4a three-root bootstrap/session/status workflow | [`pilot-session.md`](pilot-session.md) |
| Executable read-only pilot scenario contract | [`pilot-scenarios.md`](pilot-scenarios.md) |
| Architecture decisions and current status | [`adr/README.md`](adr/README.md) |
| Current phase, unfinished work, and completion gates | [`../TODO.md`](../TODO.md) |

## Maintenance rules

1. Keep one durable authority per topic. Adjacent documents link to it instead of copying status, boundaries, or schema contracts.
2. Architecture documents describe stable current behavior and explicit evolution boundaries. Unfinished execution work belongs in the root TODO.
3. The public upstream is never the production knowledge/evidence authority. Real data lives in a separately controlled private Git workspace.
4. Evaluation metadata for deliberately wrong/ambiguous scenarios is not canonical engineering authority; keep sensitive real pilot observations private.
5. Pilot session/evaluation state stays outside the selected knowledge workspace so it cannot contaminate `DATA_ONLY` publication scope or P0.3c review decisions.
6. When moving, renaming, or merging documents, update repository links in README files, ADRs, scripts, tests, and skills in the same change.
7. A mismatch among implementation, schema, validator, workflow, and documentation is contract drift and must be converged in the same change.
8. Historical decisions remain in ADRs and Git history. Superseded designs must not continue to describe the current runtime.
9. Repository-facing documentation remains English so that the public project has one contributor language.
