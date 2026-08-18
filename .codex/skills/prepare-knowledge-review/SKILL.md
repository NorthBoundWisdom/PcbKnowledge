---
name: prepare-knowledge-review
description: Validate selected Source, Entity, and Fact drafts in one explicit PcbKnowledge workspace, resolve machine-reported blockers, submit complete records, and produce a DATA_ONLY human-review handoff without approving or publishing it.
---

# Prepare Knowledge Review

End with a validated `DATA_ONLY` working-tree diff and `WAIT_FOR_HUMAN_REVIEW` in the workspace selected by the task.

## Validate the workspace and selected task

```bash
python3 configs/pcbknowledge_workspace.py validate '<workspace>'
python3 configs/pcbknowledge_agent.py --repo '<workspace>' validate
```

Then inspect the selected closure:

```bash
python3 configs/pcbknowledge_agent.py --repo '<workspace>' review-status \
  --source-id '<source-id>' \
  --entity-id '<entity-id>' \
  --fact-id '<fact-id>'
```

Treat exit code 2 as a normal blocked/not-ready report. Resolve every machine-reported category:

- `unknown`: confirm required Source fields; preserve valid optional unknowns;
- `missing_anchors`: use `$extract-component-facts`; never fabricate evidence;
- `license_blocked`: stop without reading or exposing raw or derived content;
- `conflicts`: stop and retain all candidates until explicitly resolved or superseded;
- `not_ready`: submit only after record content is complete;
- `MIXED`: stop and report that contract/policy and data cannot share one commit candidate;
- `INVALID_WORKSPACE`: stop and ask for an explicit valid workspace rather than falling back to `.`.

## Submit complete drafts

Use the latest revision tokens:

```bash
python3 configs/pcbknowledge_agent.py --repo '<workspace>' source submit '<source-id>' \
  --expected-revision '<source-revision-token>'

python3 configs/pcbknowledge_agent.py --repo '<workspace>' fact submit '<fact-id>' \
  --expected-revision '<fact-revision-token>'
```

Submitting is not approving or publishing. If a record is rejected later, preserve its review history, edit it with the new token, and resubmit.

## Produce the handoff

Run the gates again against the same workspace:

```bash
python3 configs/pcbknowledge_agent.py --repo '<workspace>' validate
python3 configs/pcbknowledge_agent.py --repo '<workspace>' review-status \
  --source-id '<source-id>' \
  --entity-id '<entity-id>' \
  --fact-id '<fact-id>'
python3 configs/pcbknowledge_agent.py --repo '<workspace>' change-scope
python3 configs/pcbknowledge_agent.py --repo '<workspace>' diff
```

Hand off only when `review_ready` is true, `change_scope` is `DATA_ONLY`, conflicts and missing anchors are empty, and `next_action` is `WAIT_FOR_HUMAN_REVIEW`. Report the workspace path, selected IDs, commands, exit codes, and remaining valid optional unknowns.

Stop there. Never approve, reject, stage, commit, push, switch workspaces silently, or modify a PCB board.
