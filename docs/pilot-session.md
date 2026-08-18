# P0.4a Pilot Session

The P0.4a pilot intentionally spans three different roots:

```text
PcbKnowledge/          public software checkout
PcbKnowledgeData/      private canonical knowledge workspace
PcbKnowledgePilot/     private evaluation/session state
```

They serve different authority roles and must not be collapsed into one Git tree.

- `PcbKnowledge/` contains software, schemas, Agent skills, synthetic tests, and the
  public evaluation harness.
- `PcbKnowledgeData/` contains the self-contained canonical workspace contract,
  Source/Entity/Fact authority, evidence, review history, and publication Git history.
- `PcbKnowledgePilot/` contains local evaluation inputs, executable scenario bindings,
  human visual-acceptance receipts, reports, and the generated runbook. It is derived
  evaluation state, **not** engineering authority.

The separation is operational rather than cosmetic. `KnowledgeRepository` classifies
all workspace paths outside `knowledge/**` and `evidence/**` as non-data for the next
Git commit. Keeping evaluation JSON/report files inside the workspace would therefore
turn a review candidate into `CODE_ONLY` or `MIXED` and correctly block P0.3c review
writes. The session bootstrap refuses that layout instead of weakening change-scope.

## Bootstrap

Create the workspace and private session state in one command:

```bash
python3 configs/pcbknowledge_pilot.py bootstrap \
  --workspace ../PcbKnowledgeData \
  --state-dir ../PcbKnowledgePilot \
  --dataset-name "P0.4a first real IC pilot" \
  --init-git
```

`--init-git` is allowed only when the workspace target is missing or empty. Existing
workspace initialization rules remain unchanged: the command pins the current schema
snapshot and creates the authority/evidence layout but does **not** stage or commit.

Bootstrap also creates:

```text
PcbKnowledgePilot/
├── pilot-session.json
├── pilot-evaluation.json
├── pilot-scenarios.json
├── RUNBOOK.md
└── reports/
```

No file in this directory is canonical PCB engineering authority.

### Bootstrap safety rules

The command fails closed when:

- the knowledge workspace is the public PcbKnowledge checkout or a child of it;
- the evaluation state directory is inside the public checkout;
- the evaluation state directory is inside the knowledge workspace;
- the workspace is inside the evaluation state directory;
- an existing non-empty state directory does not contain the exact session manifest;
- an existing session targets a different dataset, workspace, or published ref;
- the workspace contract/schema snapshot is invalid or incompatible.

Re-running bootstrap for the same valid session is idempotent. It validates the
existing session but never rewrites an edited private evaluation manifest or scenario
suite.

## Session manifest

`pilot-session.json` uses:

```text
pcbknowledge-pilot-session-v1
```

It pins:

```text
dataset_name
absolute workspace path
evaluation manifest path
scenario suite path
scenario report path
final pilot report path
published ref
creator marker
```

Session-owned file paths are normalized relative POSIX paths below the state root.
Absolute paths, `..`, backslash aliases, and path escape are rejected.

The manifest itself uses canonical JSON so accidental/manual format drift is visible.
It is local orchestration state and does not participate in Published Knowledge.

## Machine-readable status

At any point run:

```bash
python3 configs/pcbknowledge_pilot.py status \
  --session ../PcbKnowledgePilot/pilot-session.json
```

The command is read-only. It reports one current phase:

```text
WORKSPACE_CONTRACT
INGESTION
HUMAN_REVIEW
PUBLICATION
SCENARIOS
VISUAL_ACCEPTANCE
FINAL_REPORT
COMPLETE
```

It also returns:

- working workspace metrics;
- committed Published Knowledge metrics when the selected ref exists;
- whether the workspace contract has been committed;
- evaluation-manifest binding state;
- executable-scenario state;
- visual-acceptance state;
- final-report freshness;
- warnings for stale/unbound evaluation receipts;
- machine-readable next actions as `argv[]` plus `human_required`.

The status command never executes those actions.

## Phase semantics

### WORKSPACE_CONTRACT

The workspace exists and validates in the working tree, but the configured published
ref does not yet contain the workspace contract.

The suggested Git commands are explicitly marked `human_required`. PcbKnowledge does
not stage or commit them automatically.

### INGESTION

The initial workspace contract is committed, but the structural pilot target is not
yet present.

The session uses the same P0.4a structural thresholds as the evaluator:

```text
3..5 Components
20..40 Facts
ComponentPinFactV1 > 0
ParameterLimitFactV1 > 0
>= 1 multi-package Component
>= 1 Source supersedes relation
```

The session does not create fake records to satisfy these counts.

### HUMAN_REVIEW

The structural target exists, but Source/Fact review closure is incomplete.

A working pilot remains in this phase while any Source/Fact is DRAFT,
READY_FOR_REVIEW, REJECTED, incomplete, conflicting, or otherwise not approved.
The suggested action is to open the existing typed workbench.

### PUBLICATION

Working Source/Fact authority is fully reviewed, but the configured immutable Git ref
does not contain the same Source/Entity/Fact closure.

The session exposes `change-scope` before suggesting a human data publication. It
never runs `git add`, `git commit`, or `git push` itself.

### SCENARIOS

The reviewed/published structural dataset exists, but declared pilot cases are not all
PASS yet.

Executable scenarios are recommended because they provide deterministic observations
and stale-result binding, but they remain an optional mechanism in the broader
`pcbknowledge-pilot-eval-v1` contract. A manually recorded case remains valid when it
follows the same expected/observed rules.

When a scenario report exists, status validates it against current:

```text
working authority fingerprint
Git state fingerprint
published commit
pilot case bindings
```

A stale report is reported as stale; it is never silently accepted.

### VISUAL_ACCEPTANCE

All declared pilot cases pass, but the private evaluation manifest still lacks the
required human browser/PDF acceptance.

At least one PASS visual receipt must include `RESIZE_ZOOM`. The receipt remains bound
to a real Source, Fact, page, and complete EvidenceAnchor through the existing pilot
evaluator.

### FINAL_REPORT

All underlying required gates currently pass, but the stored `reports/pilot-report.json`
is missing, stale, invalid, or reflects an earlier workspace state.

The suggested report command is assembled from the current session. If a current
scenario report exists it is included; otherwise the normal manual evaluation path is
used.

### COMPLETE

The current computed P0.4a report passes and the stored final report exactly matches
that current report.

This means the private pilot has a current evaluation receipt. It does not turn the
receipt into engineering authority and does not change the Git publication boundary.

## Generated runbook

Bootstrap writes `RUNBOOK.md` into the private state directory. The runbook contains
concrete paths for the selected machine and walks through:

1. initial workspace contract commit;
2. ingestion target;
3. human review;
4. explicit data publication;
5. executable scenario binding/run;
6. final pilot report;
7. status re-check.

The file is derived convenience state. Regenerate/re-bootstrap only when creating a
new session; do not treat it as a project-wide architecture document.

## Evaluation state and privacy

The public repository contains only example manifests and synthetic tests. Real pilot
state may contain:

- selected internal Source/Fact IDs;
- evaluation notes;
- deliberate wrong-input procedures;
- human browser observations;
- report snapshots;
- local filesystem paths.

Keep that state private when any of those values disclose non-public engineering
work. Nothing in `bootstrap` uploads the state directory or creates a remote Git
repository.

## Git responsibilities

The session layer preserves the existing role split:

```text
Agent
  create/edit/validate/submit drafts
  run read-only evaluation scenarios

Human reviewer
  inspect visual evidence
  approve/reject Source/Fact
  own visual-acceptance receipt

Human Git workflow
  stage
  commit
  push/publish

Pilot session
  inspect current state
  report phase
  suggest argv
  never execute human/Git decisions
```

## Relationship to the other P0.4a tools

The session is orchestration around existing contracts rather than a replacement.

Use the lower-level commands directly when preferred:

```bash
python3 configs/pcbknowledge_pilot.py metrics ...
python3 configs/pcbknowledge_pilot.py scenario-run ...
python3 configs/pcbknowledge_pilot.py report ...
```

`bootstrap` and `status` simply make the three-root workflow explicit and prevent a
common unsafe layout before real data starts accumulating.
