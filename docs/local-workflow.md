# Local workflow

## Prepare the software checkout

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
```

Config and Build are software-checkout operations. They validate the repository's empty development-workspace contract, compile the local editor, run the standard-library test suite, and write local receipts. No account, Docker service, network download, or database is created.

## Create a knowledge workspace

Production knowledge lives in a separate Git repository:

```bash
mkdir ../PcbKnowledgeData
git -C ../PcbKnowledgeData init
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData
```

Or initialize Git only for a missing/empty target:

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData --init-git
```

The initializer copies the three current schemas, writes `pcbknowledge.workspace.json`, and creates empty authority/evidence directories. It never stages, commits, or pushes. Review the generated files and commit the workspace contract with your normal Git workflow before publishing data.

Validate the working contract or a committed ref:

```bash
python3 configs/pcbknowledge_workspace.py validate ../PcbKnowledgeData
python3 configs/pcbknowledge_workspace.py validate-ref ../PcbKnowledgeData --ref HEAD
```

## Open and close the editor

```bash
python3 configs/pcbknowledge_workflow.py run --workspace ../PcbKnowledgeData
```

For first use, `open` prepares the software checkout if necessary and then launches the workspace:

```bash
python3 configs/pcbknowledge_workflow.py open --workspace ../PcbKnowledgeData
```

The browser opens the loopback URL printed by the terminal. Every rendered page displays the exact selected workspace root. Press `Ctrl+C` to stop the editor.

The GUI reads/writes Source authority, PDF evidence, review state, and Git diffs only from the selected workspace. Static application assets continue to come from the PcbKnowledge software checkout. The GUI never stages, commits, or pushes.

## Agent ingestion

Use the same explicit workspace for the entire task:

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData source list
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData fact conflicts
```

The repository-local skills validate `<workspace>` before ingestion and keep `--repo '<workspace>'` on all Agent commands. `INVALID_WORKSPACE` is a stop condition, not a reason to retry against the public source checkout.

## Review a Source batch

The current GUI is still the Source Corpus editor. Its workflow is:

1. Create or open a draft; leave unknown values empty.
2. Select a PDF and save the draft.
3. Submit the record for review when required information is complete.
4. An engineer verifies the source and approves it, or rejects it with a specific reason.
5. Open the repository-change view and inspect the workspace JSON diff plus binary evidence receipt.
6. Use the team's normal Git GUI or command-line workflow to stage, commit, and push accepted data.

P0.3 replaces this Source-only review flow with typed Source/Entity/Fact evidence review.

## Test and package an external workspace

```bash
python3 configs/pcbknowledge_workflow.py test --workspace ../PcbKnowledgeData
python3 configs/pcbknowledge_workflow.py package --workspace ../PcbKnowledgeData
```

`test` runs the full software test suite and additionally validates the selected external workspace. `package` reads the selected workspace manifest, pinned schemas, canonical authority, and referenced evidence. The ZIP and SHA-256 sidecar are written under the software checkout's ignored `build/package/` directory, not into the knowledge authority repository.

## Collaboration guidance

- Keep each knowledge batch in a focused data commit.
- Keep workspace manifest/schema upgrades in separate contract commits.
- Pull before ingestion to reduce concurrent edits to the same authority object.
- Never rename content-addressed evidence manually; its path is derived from the digest.
- Correct a committed approved record by creating a new record and linking the prior ID through `supersedes`.
- Never move production data into the public PcbKnowledge source checkout.

## Local gates

For software changes:

```bash
python3 configs/check_english_repo.py
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

For production data, run the equivalent Agent/workflow validation against the selected private workspace. All applicable commands must exit 0 with no required checks skipped. Unexecuted, interrupted, or truncated checks are not passes.
