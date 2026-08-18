# Local workflow

## First-time preparation

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
```

The repository has no submodule initialization requirement. Config creates no account or secret. Build performs no network download and does not run Docker; it normally completes quickly on a local development machine.

## Open and close the editor

```bash
python3 configs/pcbknowledge_workflow.py run
```

The default browser opens <http://127.0.0.1:18080>. If the operating system blocks automatic browser launch, copy the URL printed by the terminal. Press `Ctrl+C` to stop the editor. The terminal does not emit periodic health-poll noise.

P0.2.5 will make the selected knowledge workspace explicit:

```bash
python3 configs/pcbknowledge_workflow.py run --workspace ../PcbKnowledgeData
```

Until that implementation is complete, use the Agent CLI's existing `--repo` option for external private knowledge work and do not place production records in the public source checkout.

## Review a small source batch

The current GUI is the Source Corpus editor. Its workflow is:

1. Create or open a draft; leave unknown values empty.
2. Select a PDF and save the draft.
3. Submit the record for review when required information is complete.
4. An engineer verifies the source and approves it, or rejects it with a specific reason.
5. Open the repository-change view and inspect the JSON diff plus binary evidence receipt.
6. Use the team's normal Git GUI or command-line workflow to stage, commit, and push the accepted data.

The application never performs step 6 itself.

## Collaboration guidance

- Keep each knowledge batch in a focused commit and include the source or task identifier in the commit message.
- Pull before ingestion to reduce concurrent edits to the same authority object.
- Never rename content-addressed evidence manually; its path is derived from the digest.
- Correct a committed approved record by creating a new record and linking the prior ID through `supersedes`.
- Keep code/schema/policy commits separate from knowledge/evidence commits.
- Keep production knowledge in a private workspace repository rather than the public software checkout.

## Local gates

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
```

All applicable commands must exit 0 with no skipped tests. Unexecuted, interrupted, or truncated checks are not passes.
