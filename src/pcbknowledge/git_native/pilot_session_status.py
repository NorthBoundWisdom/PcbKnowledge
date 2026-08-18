"""Progress projection and next-action planning for a private P0.4a pilot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from pcbknowledge.git_native.pilot_eval import (
    PilotCaseStatus,
    PilotEvaluationError,
    PilotEvaluationManifest,
    PilotReport,
    build_pilot_report,
    measure_snapshot,
    validate_manifest_references,
)
from pcbknowledge.git_native.pilot_scenarios import (
    PilotScenarioReport,
    PilotScenarioSuite,
    apply_scenario_report,
)
from pcbknowledge.git_native.pilot_session import (
    PilotSession,
    PilotSessionError,
    evaluation_template_payload,
    require_separate_pilot_roots,
    scenario_template_payload,
    validate_pilot_session_layout,
)
from pcbknowledge.git_native.store import KnowledgeRepository, RepositoryError
from pcbknowledge.git_native.workspace import (
    WorkspaceError,
    validate_workspace,
    validate_workspace_ref,
)


class PilotPhase(StrEnum):
    WORKSPACE_CONTRACT = "WORKSPACE_CONTRACT"
    INGESTION = "INGESTION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    PUBLICATION = "PUBLICATION"
    SCENARIOS = "SCENARIOS"
    VISUAL_ACCEPTANCE = "VISUAL_ACCEPTANCE"
    FINAL_REPORT = "FINAL_REPORT"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class PilotAction:
    code: str
    description: str
    argv: tuple[str, ...] = ()
    human_required: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "description": self.description,
            "argv": list(self.argv),
            "human_required": self.human_required,
        }


@dataclass(frozen=True, slots=True)
class PilotSessionStatus:
    phase: PilotPhase
    session_root: str
    workspace: str
    published_ref: str
    published_commit: str | None
    workspace_contract_committed: bool
    working_metrics: Mapping[str, int]
    published_metrics: Mapping[str, int] | None
    evaluation_state: str
    scenario_state: str
    visual_state: str
    final_report_state: str
    actions: tuple[PilotAction, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "format": "pcbknowledge-pilot-session-status-v1",
            "phase": self.phase.value,
            "session_root": self.session_root,
            "workspace": self.workspace,
            "published_ref": self.published_ref,
            "published_commit": self.published_commit,
            "workspace_contract_committed": self.workspace_contract_committed,
            "working": dict(self.working_metrics),
            "published": (
                None if self.published_metrics is None else dict(self.published_metrics)
            ),
            "evaluation_state": self.evaluation_state,
            "scenario_state": self.scenario_state,
            "visual_state": self.visual_state,
            "final_report_state": self.final_report_state,
            "actions": [action.to_dict() for action in self.actions],
            "warnings": list(self.warnings),
        }


def _structural_ready(metrics: Mapping[str, int]) -> bool:
    return (
        3 <= metrics["component_count"] <= 5
        and 20 <= metrics["fact_count"] <= 40
        and metrics["component_pin_fact_count"] > 0
        and metrics["parameter_limit_fact_count"] > 0
        and metrics["multi_package_component_count"] >= 1
        and metrics["source_supersedes_count"] >= 1
    )


def _fully_reviewed(metrics: Mapping[str, int]) -> bool:
    return (
        metrics["source_count"] == metrics["approved_source_count"]
        and metrics["fact_count"] == metrics["approved_fact_count"]
        and metrics["ready_for_review_count"] == 0
        and metrics["rejected_count"] == 0
        and metrics["draft_count"] == 0
        and metrics["incomplete_source_count"] == 0
        and metrics["incomplete_fact_count"] == 0
        and metrics["conflict_count"] == 0
    )


def _published_matches(
    working: Mapping[str, int], published: Mapping[str, int] | None
) -> bool:
    if published is None:
        return False
    return (
        working["source_count"] == published["source_count"]
        and working["entity_count"] == published["entity_count"]
        and working["fact_count"] == published["fact_count"]
        and published["source_count"] == published["approved_source_count"]
        and published["fact_count"] == published["approved_fact_count"]
    )


def _visual_ready(manifest: PilotEvaluationManifest | None) -> bool:
    if manifest is None:
        return False
    passed = [
        item for item in manifest.visual_acceptance if item.status is PilotCaseStatus.PASS
    ]
    if not passed or any(
        item.status is PilotCaseStatus.FAIL for item in manifest.visual_acceptance
    ):
        return False
    return any(
        characteristic.value == "RESIZE_ZOOM"
        for item in passed
        for characteristic in item.characteristics
    )


def _all_cases_pass(manifest: PilotEvaluationManifest | None) -> bool:
    return bool(manifest and manifest.cases) and all(
        case.status is PilotCaseStatus.PASS for case in manifest.cases
    )


def _action(
    code: str,
    description: str,
    *argv: str,
    human_required: bool = False,
) -> PilotAction:
    return PilotAction(code, description, tuple(argv), human_required)


def _phase_actions(
    phase: PilotPhase, *, session: PilotSession, software_root: Path
) -> tuple[PilotAction, ...]:
    software = software_root.resolve()
    workspace = str(session.workspace)
    evaluation = str(session.path(session.manifest.evaluation_manifest))
    scenarios = str(session.path(session.manifest.scenario_suite))
    scenario_report = str(session.path(session.manifest.scenario_report))
    pilot_report = str(session.path(session.manifest.pilot_report))
    pilot_cli = str(software / "configs/pcbknowledge_pilot.py")
    agent_cli = str(software / "configs/pcbknowledge_agent.py")
    workflow_cli = str(software / "configs/pcbknowledge_workflow.py")
    if phase is PilotPhase.WORKSPACE_CONTRACT:
        return (
            _action(
                "STAGE_WORKSPACE_CONTRACT",
                "Review and stage only the initialized workspace contract.",
                "git", "-C", workspace, "add",
                ".gitignore", "pcbknowledge.workspace.json", "schemas", "knowledge", "evidence",
                human_required=True,
            ),
            _action(
                "COMMIT_WORKSPACE_CONTRACT",
                "Commit the reviewed workspace contract before data ingestion.",
                "git", "-C", workspace, "commit", "-m",
                "initialize PcbKnowledge pilot workspace",
                human_required=True,
            ),
        )
    if phase is PilotPhase.INGESTION:
        return (
            _action(
                "VALIDATE_WORKSPACE",
                "Validate typed authority before continuing ingestion.",
                "python3", agent_cli, "--repo", workspace, "validate",
            ),
            _action(
                "OPEN_WORKBENCH",
                "Open the workbench for the selected private workspace.",
                "python3", workflow_cli, "open", "--workspace", workspace,
                human_required=True,
            ),
        )
    if phase is PilotPhase.HUMAN_REVIEW:
        return (
            _action(
                "OPEN_WORKBENCH",
                "Review every pilot Source and Fact.",
                "python3", workflow_cli, "open", "--workspace", workspace,
                human_required=True,
            ),
        )
    if phase is PilotPhase.PUBLICATION:
        return (
            _action(
                "CHECK_CHANGE_SCOPE",
                "Confirm the next private data commit is DATA_ONLY.",
                "python3", agent_cli, "--repo", workspace, "change-scope",
            ),
            _action(
                "STAGE_REVIEWED_DATA",
                "Stage reviewed knowledge/evidence using the human Git workflow.",
                "git", "-C", workspace, "add", "knowledge", "evidence",
                human_required=True,
            ),
        )
    if phase is PilotPhase.SCENARIOS:
        return (
            _action(
                "EDIT_SCENARIO_SUITE",
                f"Bind executable scenarios to real canonical IDs in {scenarios}.",
                human_required=True,
            ),
            _action(
                "RUN_SCENARIOS",
                "Run read-only executable pilot scenarios.",
                "python3", pilot_cli, "scenario-run",
                "--workspace", workspace, "--suite", scenarios,
                "--ref", session.manifest.published_ref,
                "--output", scenario_report, "--require-pass",
            ),
        )
    if phase is PilotPhase.VISUAL_ACCEPTANCE:
        return (
            _action(
                "OPEN_WORKBENCH",
                "Inspect real PDF anchors, including resize/zoom.",
                "python3", workflow_cli, "open", "--workspace", workspace,
                human_required=True,
            ),
            _action(
                "RECORD_VISUAL_ACCEPTANCE",
                f"Record exact Source/Fact/page acceptance in {evaluation}.",
                human_required=True,
            ),
        )
    if phase is PilotPhase.FINAL_REPORT:
        argv = [
            "python3", pilot_cli, "report",
            "--workspace", workspace, "--manifest", evaluation,
        ]
        if session.path(session.manifest.scenario_report).is_file():
            argv.extend(("--scenario-report", scenario_report))
        argv.extend((
            "--ref", session.manifest.published_ref,
            "--output", pilot_report, "--require-pass",
        ))
        return (
            _action(
                "WRITE_FINAL_REPORT",
                "Generate the current bound P0.4a completion receipt.",
                *argv,
            ),
        )
    return ()


def _load_final_report(session: PilotSession) -> Mapping[str, Any] | None:
    path = session.path(session.manifest.pilot_report)
    if not path.exists():
        return None
    if not path.is_file():
        raise PilotSessionError(f"pilot report path is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PilotSessionError("pilot report is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise PilotSessionError("pilot report must be a JSON object")
    return value


def pilot_session_status(
    session: PilotSession, *, software_root: Path
) -> PilotSessionStatus:
    software = software_root.resolve()
    require_separate_pilot_roots(
        workspace=session.workspace, state_root=session.root, software_root=software
    )
    validate_pilot_session_layout(session)
    validate_workspace(session.workspace)
    repository = KnowledgeRepository(session.workspace)
    working_snapshot = repository.validate_all(require_canonical=True)
    working = measure_snapshot(working_snapshot).to_dict()

    warnings: list[str] = []
    published_commit: str | None = None
    published_metrics: Mapping[str, int] | None = None
    contract_committed = False
    try:
        ref_validation = validate_workspace_ref(
            session.workspace, session.manifest.published_ref
        )
        published_commit = ref_validation.commit
        published_metrics = measure_snapshot(
            repository.read_published_snapshot(ref=session.manifest.published_ref)
        ).to_dict()
        contract_committed = True
    except (WorkspaceError, RepositoryError) as error:
        warnings.append(f"Published ref is not ready: {error}")

    evaluation_path = session.path(session.manifest.evaluation_manifest)
    evaluation: PilotEvaluationManifest | None = None
    evaluation_state = "MISSING"
    try:
        evaluation = PilotEvaluationManifest.from_path(evaluation_path)
        raw_eval = json.loads(evaluation_path.read_text(encoding="utf-8"))
        if raw_eval == evaluation_template_payload(session.manifest.dataset_name):
            evaluation_state = "TEMPLATE"
        else:
            try:
                validate_manifest_references(evaluation, working_snapshot)
                evaluation_state = "BOUND"
            except PilotEvaluationError as error:
                evaluation_state = "UNBOUND"
                warnings.append(str(error))
    except PilotEvaluationError as error:
        evaluation_state = "INVALID"
        warnings.append(str(error))

    scenario_path = session.path(session.manifest.scenario_suite)
    scenario_state = "MISSING"
    try:
        PilotScenarioSuite.from_path(scenario_path)
        raw_suite = json.loads(scenario_path.read_text(encoding="utf-8"))
        scenario_state = (
            "TEMPLATE"
            if raw_suite == scenario_template_payload(session.manifest.dataset_name)
            else "NOT_RUN"
        )
    except PilotEvaluationError as error:
        scenario_state = "INVALID"
        warnings.append(str(error))

    effective_evaluation = evaluation
    scenario_report_path = session.path(session.manifest.scenario_report)
    if scenario_report_path.exists():
        try:
            report = PilotScenarioReport.from_path(scenario_report_path)
            if evaluation is None:
                raise PilotSessionError(
                    "scenario report exists but evaluation manifest is unavailable"
                )
            effective_evaluation = apply_scenario_report(
                evaluation,
                report,
                repository,
                published_ref=session.manifest.published_ref,
            )
            scenario_state = "PASS" if report.passed else "FAIL"
        except PilotEvaluationError as error:
            scenario_state = "STALE_OR_INVALID"
            warnings.append(str(error))

    computed_report: PilotReport | None = None
    if contract_committed and effective_evaluation is not None:
        try:
            computed_report = build_pilot_report(
                repository,
                effective_evaluation,
                published_ref=session.manifest.published_ref,
            )
        except PilotEvaluationError as error:
            warnings.append(str(error))

    visual_state = (
        "PASS"
        if _visual_ready(effective_evaluation)
        else (
            "FAIL"
            if effective_evaluation is not None
            and any(
                item.status is PilotCaseStatus.FAIL
                for item in effective_evaluation.visual_acceptance
            )
            else "PENDING"
        )
    )

    final_report_state = "MISSING"
    try:
        final_payload = _load_final_report(session)
        if final_payload is not None:
            if computed_report is None:
                final_report_state = "STALE_OR_INVALID"
            elif final_payload == computed_report.to_dict():
                final_report_state = "PASS" if computed_report.passed else "INCOMPLETE"
            else:
                final_report_state = "STALE"
    except PilotSessionError as error:
        final_report_state = "INVALID"
        warnings.append(str(error))

    if not contract_committed:
        phase = PilotPhase.WORKSPACE_CONTRACT
    elif not _structural_ready(working):
        phase = PilotPhase.INGESTION
    elif not _fully_reviewed(working):
        phase = PilotPhase.HUMAN_REVIEW
    elif not _published_matches(working, published_metrics):
        phase = PilotPhase.PUBLICATION
    elif not _all_cases_pass(effective_evaluation):
        phase = PilotPhase.SCENARIOS
    elif visual_state != "PASS":
        phase = PilotPhase.VISUAL_ACCEPTANCE
    elif computed_report is None or not computed_report.passed:
        phase = PilotPhase.FINAL_REPORT
    elif final_report_state != "PASS":
        phase = PilotPhase.FINAL_REPORT
    else:
        phase = PilotPhase.COMPLETE

    return PilotSessionStatus(
        phase=phase,
        session_root=str(session.root),
        workspace=str(session.workspace),
        published_ref=session.manifest.published_ref,
        published_commit=published_commit,
        workspace_contract_committed=contract_committed,
        working_metrics=working,
        published_metrics=published_metrics,
        evaluation_state=evaluation_state,
        scenario_state=scenario_state,
        visual_state=visual_state,
        final_report_state=final_report_state,
        actions=_phase_actions(phase, session=session, software_root=software),
        warnings=tuple(dict.fromkeys(warnings)),
    )
