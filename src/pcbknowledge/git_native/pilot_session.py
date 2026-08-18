"""Local orchestration for a private P0.4a pilot session.

A pilot session is derived/evaluation state. It deliberately lives outside both the
public software checkout and the selected knowledge workspace so evaluation files do
not contaminate canonical authority or Git change-scope decisions.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pcbknowledge.git_native.pilot_eval import (
    PilotEvaluationError,
    example_manifest_payload,
)
from pcbknowledge.git_native.pilot_scenarios import (
    example_scenario_suite_payload,
)
from pcbknowledge.git_native.workspace import (
    initialize_workspace,
    validate_workspace_gitignore,
)


PILOT_SESSION_FORMAT = "pcbknowledge-pilot-session-v1"
PILOT_SESSION_FILE = Path("pilot-session.json")
PILOT_EVALUATION_FILE = Path("pilot-evaluation.json")
PILOT_SCENARIO_FILE = Path("pilot-scenarios.json")
PILOT_SCENARIO_REPORT_FILE = Path("reports/pilot-scenario-report.json")
PILOT_REPORT_FILE = Path("reports/pilot-report.json")
PILOT_RUNBOOK_FILE = Path("RUNBOOK.md")
CREATED_WITH = "PcbKnowledge"
MAX_SESSION_BYTES = 128 * 1024


class PilotSessionError(PilotEvaluationError):
    """Pilot-session state is unsafe, ambiguous, or inconsistent."""


@dataclass(frozen=True, slots=True)
class PilotSessionManifest:
    dataset_name: str
    workspace: str
    evaluation_manifest: str = PILOT_EVALUATION_FILE.as_posix()
    scenario_suite: str = PILOT_SCENARIO_FILE.as_posix()
    scenario_report: str = PILOT_SCENARIO_REPORT_FILE.as_posix()
    pilot_report: str = PILOT_REPORT_FILE.as_posix()
    published_ref: str = "HEAD"
    created_with: str = CREATED_WITH
    format: str = PILOT_SESSION_FORMAT

    def validate(self) -> "PilotSessionManifest":
        if self.format != PILOT_SESSION_FORMAT:
            raise PilotSessionError(
                f"pilot session format must equal {PILOT_SESSION_FORMAT}"
            )
        if self.created_with != CREATED_WITH:
            raise PilotSessionError(
                f"pilot session created_with must equal {CREATED_WITH}"
            )
        dataset = self.dataset_name.strip()
        if not dataset or len(dataset) > 200 or "\x00" in dataset:
            raise PilotSessionError(
                "pilot session dataset_name must be 1..200 non-NUL characters"
            )
        workspace = Path(self.workspace)
        if not workspace.is_absolute():
            raise PilotSessionError("pilot session workspace must be an absolute path")
        if not self.published_ref or self.published_ref.startswith("-"):
            raise PilotSessionError("pilot session published_ref is invalid")
        if any(character in self.published_ref for character in ("\x00", "\n", "\r")):
            raise PilotSessionError("pilot session published_ref is invalid")
        for label, value in (
            ("evaluation_manifest", self.evaluation_manifest),
            ("scenario_suite", self.scenario_suite),
            ("scenario_report", self.scenario_report),
            ("pilot_report", self.pilot_report),
        ):
            _validate_relative_file(value, label)
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "dataset_name": self.dataset_name,
            "workspace": self.workspace,
            "evaluation_manifest": self.evaluation_manifest,
            "scenario_suite": self.scenario_suite,
            "scenario_report": self.scenario_report,
            "pilot_report": self.pilot_report,
            "published_ref": self.published_ref,
            "created_with": self.created_with,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"

    @classmethod
    def from_dict(cls, value: object) -> "PilotSessionManifest":
        if not isinstance(value, dict):
            raise PilotSessionError("pilot session manifest must be an object")
        expected = {
            "format",
            "dataset_name",
            "workspace",
            "evaluation_manifest",
            "scenario_suite",
            "scenario_report",
            "pilot_report",
            "published_ref",
            "created_with",
        }
        if set(value) != expected:
            raise PilotSessionError(
                "pilot session manifest has unsupported or missing fields"
            )
        if not all(isinstance(value[key], str) for key in expected):
            raise PilotSessionError("pilot session manifest fields must be strings")
        return cls(
            format=value["format"],
            dataset_name=value["dataset_name"],
            workspace=value["workspace"],
            evaluation_manifest=value["evaluation_manifest"],
            scenario_suite=value["scenario_suite"],
            scenario_report=value["scenario_report"],
            pilot_report=value["pilot_report"],
            published_ref=value["published_ref"],
            created_with=value["created_with"],
        ).validate()

    @classmethod
    def from_json(cls, payload: str) -> "PilotSessionManifest":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise PilotSessionError(
                f"pilot session manifest is not valid JSON: {error.msg}"
            ) from error
        manifest = cls.from_dict(value)
        if payload != manifest.canonical_json():
            raise PilotSessionError("pilot session manifest is not canonical JSON")
        return manifest


@dataclass(frozen=True, slots=True)
class PilotSession:
    root: Path
    manifest: PilotSessionManifest

    @property
    def manifest_path(self) -> Path:
        return self.root / PILOT_SESSION_FILE

    @property
    def workspace(self) -> Path:
        return Path(self.manifest.workspace)

    def path(self, relative: str) -> Path:
        return _session_path(self.root, relative)


@dataclass(frozen=True, slots=True)
class PilotBootstrapResult:
    session: PilotSession
    workspace_replayed: bool
    session_replayed: bool
    runbook: Path

    def to_dict(self) -> dict[str, object]:
        return {
            "format": PILOT_SESSION_FORMAT,
            "status": "OK",
            "dataset_name": self.session.manifest.dataset_name,
            "workspace": str(self.session.workspace),
            "session_root": str(self.session.root),
            "session_manifest": str(self.session.manifest_path),
            "runbook": str(self.runbook),
            "workspace_replayed": self.workspace_replayed,
            "session_replayed": self.session_replayed,
            "authority": False,
            "git_mutation": "NONE",
        }


def _validate_relative_file(value: str, label: str) -> None:
    if not value or "\x00" in value or "\\" in value:
        raise PilotSessionError(f"pilot session {label} is invalid")
    path = Path(value)
    if path.is_absolute() or path.as_posix() != value:
        raise PilotSessionError(
            f"pilot session {label} must be a normalized relative POSIX path"
        )
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PilotSessionError(f"pilot session {label} contains an unsafe path")


def _session_path(root: Path, relative: str) -> Path:
    _validate_relative_file(relative, "file")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise PilotSessionError("pilot session file escapes its state root") from error
    return candidate


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def require_separate_pilot_roots(*, workspace: Path, state_root: Path, software_root: Path) -> None:
    workspace = workspace.resolve()
    state_root = state_root.resolve()
    software_root = software_root.resolve()
    if _is_within(workspace, software_root):
        raise PilotSessionError(
            "pilot workspace must not be the public software checkout or a child of it"
        )
    if _is_within(state_root, software_root):
        raise PilotSessionError(
            "pilot evaluation state must not live in the public software checkout"
        )
    if _is_within(state_root, workspace) or _is_within(workspace, state_root):
        raise PilotSessionError(
            "pilot evaluation state and knowledge workspace must be separate roots"
        )


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def evaluation_template_payload(dataset_name: str) -> dict[str, object]:
    payload = example_manifest_payload()
    payload["dataset_name"] = dataset_name
    payload["notes"] = (
        "Private P0.4a evaluation metadata. Replace placeholders only after "
        "canonical Source/Entity/Fact IDs exist in the selected workspace."
    )
    return payload


def scenario_template_payload(dataset_name: str) -> dict[str, object]:
    payload = example_scenario_suite_payload()
    payload["dataset_name"] = dataset_name
    payload["notes"] = (
        "Private P0.4a executable scenarios. Replace placeholder canonical IDs "
        "after ingestion; intentionally wrong inputs remain scenario parameters."
    )
    return payload


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def load_pilot_session(path: Path) -> PilotSession:
    manifest_path = path.expanduser().resolve()
    if not manifest_path.is_file():
        raise PilotSessionError(
            f"pilot session manifest is not a regular file: {manifest_path}"
        )
    if manifest_path.name != PILOT_SESSION_FILE.name:
        raise PilotSessionError(
            f"pilot session manifest must be named {PILOT_SESSION_FILE.name}"
        )
    if manifest_path.stat().st_size > MAX_SESSION_BYTES:
        raise PilotSessionError("pilot session manifest exceeds size limit")
    try:
        payload = manifest_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise PilotSessionError("pilot session manifest must be UTF-8") from error
    return PilotSession(
        root=manifest_path.parent.resolve(),
        manifest=PilotSessionManifest.from_json(payload),
    )


def validate_pilot_session_layout(session: PilotSession) -> None:
    for label, relative in (
        ("evaluation manifest", session.manifest.evaluation_manifest),
        ("scenario suite", session.manifest.scenario_suite),
    ):
        path = session.path(relative)
        if not path.is_file():
            raise PilotSessionError(f"pilot session {label} is missing: {path}")
    runbook = session.root / PILOT_RUNBOOK_FILE
    if not runbook.is_file():
        raise PilotSessionError(f"pilot session runbook is missing: {runbook}")


def render_pilot_runbook(session: PilotSession, *, software_root: Path) -> str:
    software = software_root.resolve()
    workspace = session.workspace
    evaluation = session.path(session.manifest.evaluation_manifest)
    scenarios = session.path(session.manifest.scenario_suite)
    scenario_report = session.path(session.manifest.scenario_report)
    pilot_report = session.path(session.manifest.pilot_report)
    status_command = (
        f"python3 {software / 'configs/pcbknowledge_pilot.py'} status "
        f"--session {session.manifest_path}"
    )
    return f"""# P0.4a Private Pilot Runbook

Dataset: `{session.manifest.dataset_name}`

Knowledge workspace: `{workspace}`

Evaluation state: `{session.root}`

This directory is **not canonical engineering authority**. Keep it outside both the
public PcbKnowledge checkout and the knowledge workspace. The evaluator never
approves records, stages Git, commits, or pushes.

## 1. Commit the workspace contract

```text
git -C {workspace} add .gitignore pcbknowledge.workspace.json schemas knowledge evidence
git -C {workspace} commit -m "initialize PcbKnowledge pilot workspace"
```

The workspace `.gitignore` keeps `/.pcbknowledge/` derived runtime state out of data
change-scope decisions. It is part of the initial human-reviewed workspace contract.

Then inspect machine state:

```text
{status_command}
```

## 2. Ingest 3-5 real components

```text
python3 {software / 'configs/pcbknowledge_agent.py'} --repo {workspace} validate
python3 {software / 'configs/pcbknowledge_workflow.py'} open --workspace {workspace}
```

Target 3-5 Components, 20-40 Facts, both initial Fact families, at least one
multi-package Component, and one Source revision/supersedes chain.

## 3. Human review

Review every pilot Source and Fact in the workbench. Keep evaluation receipts outside
canonical authority. Edit:

```text
{evaluation}
```

## 4. Publish reviewed data

```text
python3 {software / 'configs/pcbknowledge_agent.py'} --repo {workspace} change-scope
```

Only a DATA_ONLY knowledge/evidence publication candidate is expected. Staging and
commit remain explicit human Git actions.

## 5. Bind executable scenarios

Edit:

```text
{scenarios}
```

Then run:

```text
python3 {software / 'configs/pcbknowledge_pilot.py'} scenario-run --workspace {workspace} --suite {scenarios} --ref {session.manifest.published_ref} --output {scenario_report} --require-pass
```

## 6. Final pilot gate

```text
python3 {software / 'configs/pcbknowledge_pilot.py'} report --workspace {workspace} --manifest {evaluation} --scenario-report {scenario_report} --ref {session.manifest.published_ref} --output {pilot_report} --require-pass
```

## 7. Re-check current phase

```text
{status_command}
```
"""


def bootstrap_pilot_session(
    *,
    workspace: Path,
    state_root: Path,
    schema_source_root: Path,
    software_root: Path,
    dataset_name: str,
    init_git: bool = False,
    published_ref: str = "HEAD",
) -> PilotBootstrapResult:
    workspace_candidate = workspace.expanduser().resolve()
    state_candidate = state_root.expanduser().resolve()
    software = software_root.expanduser().resolve()
    require_separate_pilot_roots(
        workspace=workspace_candidate,
        state_root=state_candidate,
        software_root=software,
    )
    initialization = initialize_workspace(
        workspace,
        schema_source_root=schema_source_root,
        init_git=init_git,
    )
    resolved_workspace = initialization.validation.root
    validate_workspace_gitignore(resolved_workspace)
    desired = PilotSessionManifest(
        dataset_name=dataset_name.strip(),
        workspace=str(resolved_workspace),
        published_ref=published_ref,
    ).validate()
    manifest_path = state_candidate / PILOT_SESSION_FILE
    if manifest_path.exists():
        session = load_pilot_session(manifest_path)
        if session.manifest != desired:
            raise PilotSessionError(
                "existing pilot session targets a different dataset/workspace/ref"
            )
        validate_pilot_session_layout(session)
        return PilotBootstrapResult(
            session=session,
            workspace_replayed=initialization.replayed,
            session_replayed=True,
            runbook=session.root / PILOT_RUNBOOK_FILE,
        )
    if state_candidate.exists():
        if not state_candidate.is_dir() or any(state_candidate.iterdir()):
            raise PilotSessionError(
                "pilot bootstrap requires a missing/empty state root or an existing session"
            )
    else:
        state_candidate.mkdir(parents=True)
    session = PilotSession(root=state_candidate, manifest=desired)
    created: list[Path] = []
    try:
        reports_dir = state_candidate / "reports"
        reports_dir.mkdir()
        created.append(reports_dir)
        evaluation_path = session.path(desired.evaluation_manifest)
        _atomic_write_text(
            evaluation_path,
            _json_text(evaluation_template_payload(desired.dataset_name)),
        )
        created.append(evaluation_path)
        scenario_path = session.path(desired.scenario_suite)
        _atomic_write_text(
            scenario_path,
            _json_text(scenario_template_payload(desired.dataset_name)),
        )
        created.append(scenario_path)
        _atomic_write_text(manifest_path, desired.canonical_json())
        created.append(manifest_path)
        runbook_path = state_candidate / PILOT_RUNBOOK_FILE
        _atomic_write_text(
            runbook_path,
            render_pilot_runbook(session, software_root=software),
        )
        created.append(runbook_path)
    except BaseException:
        for path in reversed(created):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
            else:
                path.unlink(missing_ok=True)
        try:
            state_candidate.rmdir()
        except OSError:
            pass
        raise
    validate_pilot_session_layout(session)
    return PilotBootstrapResult(
        session=session,
        workspace_replayed=initialization.replayed,
        session_replayed=False,
        runbook=state_candidate / PILOT_RUNBOOK_FILE,
    )
