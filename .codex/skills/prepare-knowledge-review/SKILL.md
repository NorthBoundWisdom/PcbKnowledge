---
name: prepare-knowledge-review
description: Validate selected Git-native Source, Entity, and Fact drafts, resolve machine-reported blockers, submit complete Source and Fact records, and produce a DATA_ONLY review receipt and diff. Use after ingestion when an Agent must hand a bounded knowledge change to a human without approving, staging, committing, or pushing it.
---

# Prepare Knowledge Review

End with a validated `DATA_ONLY` working-tree diff and `WAIT_FOR_HUMAN_REVIEW`.

## Check the selected task

Validate the entire authority first:

```bash
python3 configs/pcbknowledge_agent.py validate
```

Then inspect the selected closure. Repeat ID flags as needed:

```bash
python3 configs/pcbknowledge_agent.py review-status \
  --source-id '<source-id>' \
  --entity-id '<entity-id>' \
  --fact-id '<fact-id>'
```

Treat exit code 2 as a normal blocked/not-ready report. Resolve every machine-reported category:

- `unknown`: confirm required Source fields; preserve valid optional unknowns.
- `missing_anchors`: use `$extract-component-facts`; never fabricate evidence.
- `license_blocked`: stop without reading or exposing raw or derived content.
- `conflicts`: stop and retain all candidates until explicitly resolved or superseded.
- `not_ready`: submit only after the record content is complete.
- `MIXED`: stop and report that code/policy and data cannot share a commit candidate. Do not manipulate the Git index.

## Submit complete drafts

Use the latest revision tokens from `source show` and `fact show`:

```bash
python3 configs/pcbknowledge_agent.py source submit '<source-id>' \
  --expected-revision '<source-revision-token>'

python3 configs/pcbknowledge_agent.py fact submit '<fact-id>' \
  --expected-revision '<fact-revision-token>'
```

Submitting is not approving or publishing. If a record is rejected later, preserve its review history, edit it with the new token, and resubmit.

## Produce the handoff

Run the gates again:

```bash
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py review-status \
  --source-id '<source-id>' \
  --entity-id '<entity-id>' \
  --fact-id '<fact-id>'
python3 configs/pcbknowledge_agent.py change-scope
python3 configs/pcbknowledge_agent.py diff
```

Hand off only when `review_ready` is true, `change_scope` is `DATA_ONLY`, conflicts and missing anchors are empty, and `next_action` is `WAIT_FOR_HUMAN_REVIEW`. Report the IDs, commands, exit codes, and remaining valid optional unknowns.

Stop there. Never approve, reject, stage, commit, push, or modify a PCB board.
