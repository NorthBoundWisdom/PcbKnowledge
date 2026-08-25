# PcbKnowledge Grok project config

Grok does not scan Codex `.codex/skills`. `.grok/skills` is a relative symlink
to `../.codex/skills`, so both harnesses share one skill tree.

Edit SOP, scripts, and assets only under `.codex/skills/`. Command examples in
those files keep the `.codex/skills/...` paths.

## Invoke

- Slash: `/<skill-name>`
- Menu: `/skills`
- Inspect: `grok inspect`

## Catalog

| Skill | Use |
| --- | --- |
| `extract-component-facts` | Prepare typed ComponentPin and ParameterLimit FactRecord drafts in one explicitly selected PcbKnowledge workspace, wi... |
| `ingest-engineering-source` | Register one exact engineering-document revision in an explicitly selected PcbKnowledge workspace, including provenan... |
| `prepare-knowledge-review` | Validate selected Source, Entity, and Fact drafts in one explicit PcbKnowledge workspace, resolve machine-reported bl... |
| `resolve-component-identity` | Resolve and create exact Manufacturer, Component, and Package identities inside one explicitly selected PcbKnowledge... |
