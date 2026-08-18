#!/usr/bin/env python3
"""Bootstrap, measure, and close a P0.4a pilot against private workspace state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.git_native.pilot_eval import (  # noqa: E402
    PilotEvaluationError,
    PilotEvaluationManifest,
    build_pilot_report,
    example_manifest_payload,
    measure_snapshot,
    write_example_manifest,
)
from pcbknowledge.git_native.pilot_scenarios import (  # noqa: E402
    PilotScenarioReport,
    PilotScenarioSuite,
    apply_scenario_report,
    example_scenario_suite_payload,
    run_pilot_scenarios,
    write_example_scenario_suite,
)
from pcbknowledge.git_native.pilot_session import (  # noqa: E402
    bootstrap_pilot_session,
    load_pilot_session,
)
from pcbknowledge.git_native.pilot_session_status import (  # noqa: E402
    pilot_session_status,
)
from pcbknowledge.git_native.store import KnowledgeRepository  # noqa: E402
from pcbknowledge.git_native.workspace import (  # noqa: E402
    WorkspaceError,
    validate_workspace,
    validate_workspace_ref,
)


def _write_report(path: Path, payload: str) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(payload, encoding="utf-8")


def _scaffold(path: Path) -> Path:
    """Create the example evaluation manifest, or replay only the exact template."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return write_example_manifest(resolved)
    if not resolved.is_file():
        raise PilotEvaluationError(
            f"refusing to overwrite non-file scaffold path: {resolved}"
        )
    try:
        existing = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PilotEvaluationError(
            f"refusing to overwrite non-template file: {resolved}"
        ) from error
    if existing != example_manifest_payload():
        raise PilotEvaluationError(f"refusing to overwrite existing file: {resolved}")
    return resolved


def _scenario_scaffold(path: Path) -> Path:
    """Create the example executable suite, replaying only identical templates."""

    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return write_example_scenario_suite(resolved)
    if not resolved.is_file():
        raise PilotEvaluationError(
            f"refusing to overwrite non-file scenario scaffold path: {resolved}"
        )
    try:
        existing = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PilotEvaluationError(
            f"refusing to overwrite non-template scenario file: {resolved}"
        ) from error
    if existing != example_scenario_suite_payload():
        raise PilotEvaluationError(
            f"refusing to overwrite existing scenario file: {resolved}"
        )
    return resolved


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Operate a private PcbKnowledge P0.4a pilot without storing negative "
            "evaluation cases as canonical engineering authority"
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    bootstrap = commands.add_parser(
        "bootstrap",
        help="initialize an isolated private pilot workspace and evaluation session",
    )
    bootstrap.add_argument("--workspace", required=True)
    bootstrap.add_argument("--state-dir", required=True)
    bootstrap.add_argument("--dataset-name", required=True)
    bootstrap.add_argument("--ref", default="HEAD")
    bootstrap.add_argument(
        "--init-git",
        action="store_true",
        help="initialize Git only when the workspace target is missing or empty",
    )

    status = commands.add_parser(
        "status",
        help="project the current pilot phase and machine-readable next actions",
    )
    status.add_argument("--session", required=True)

    scaffold = commands.add_parser(
        "scaffold", help="write an editable pilot-evaluation manifest template"
    )
    scaffold.add_argument("--output", required=True)

    scenario_scaffold = commands.add_parser(
        "scenario-scaffold",
        help="write an editable executable-scenario suite template",
    )
    scenario_scaffold.add_argument("--output", required=True)

    metrics = commands.add_parser(
        "metrics", help="show working and published workspace coverage metrics"
    )
    metrics.add_argument("--workspace", required=True)
    metrics.add_argument("--ref", default="HEAD")

    scenarios = commands.add_parser(
        "scenario-run",
        help="execute read-only golden scenarios against the selected workspace",
    )
    scenarios.add_argument("--workspace", required=True)
    scenarios.add_argument("--suite", required=True)
    scenarios.add_argument("--ref", default="HEAD")
    scenarios.add_argument("--output")
    scenarios.add_argument(
        "--require-pass",
        action="store_true",
        help="return exit code 3 when any executable scenario fails",
    )

    report = commands.add_parser(
        "report", help="evaluate structural, scenario, visual, and publication gates"
    )
    report.add_argument("--workspace", required=True)
    report.add_argument("--manifest", required=True)
    report.add_argument("--scenario-report")
    report.add_argument("--ref", default="HEAD")
    report.add_argument("--output")
    report.add_argument(
        "--require-pass",
        action="store_true",
        help="return exit code 3 when any required pilot gate is incomplete or failed",
    )
    return parser.parse_args(argv)


def _workspace(arguments: argparse.Namespace) -> KnowledgeRepository:
    root = Path(arguments.workspace)
    validate_workspace(root)
    validate_workspace_ref(root, arguments.ref)
    return KnowledgeRepository(root)


def _print_json(value: object) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.command == "bootstrap":
            result = bootstrap_pilot_session(
                workspace=Path(arguments.workspace),
                state_root=Path(arguments.state_dir),
                schema_source_root=REPO_ROOT,
                software_root=REPO_ROOT,
                dataset_name=arguments.dataset_name,
                init_git=arguments.init_git,
                published_ref=arguments.ref,
            )
            _print_json(result.to_dict())
            return 0

        if arguments.command == "status":
            session = load_pilot_session(Path(arguments.session))
            _print_json(
                pilot_session_status(
                    session,
                    software_root=REPO_ROOT,
                ).to_dict()
            )
            return 0

        if arguments.command == "scaffold":
            output = _scaffold(Path(arguments.output))
            _print_json(
                {
                    "status": "OK",
                    "format": "pcbknowledge-pilot-eval-v1",
                    "output": str(output),
                    "authority": False,
                }
            )
            return 0

        if arguments.command == "scenario-scaffold":
            output = _scenario_scaffold(Path(arguments.output))
            _print_json(
                {
                    "status": "OK",
                    "format": "pcbknowledge-pilot-scenarios-v1",
                    "output": str(output),
                    "authority": False,
                    "read_only_runner": True,
                }
            )
            return 0

        repository = _workspace(arguments)
        working = repository.validate_all(require_canonical=True)
        published = repository.read_published_snapshot(ref=arguments.ref)

        if arguments.command == "metrics":
            _print_json(
                {
                    "format": "pcbknowledge-pilot-metrics-v1",
                    "status": "OK",
                    "workspace": str(repository.root),
                    "published_ref": arguments.ref,
                    "published_commit": published.commit,
                    "working": measure_snapshot(working).to_dict(),
                    "published": measure_snapshot(published).to_dict(),
                }
            )
            return 0

        if arguments.command == "scenario-run":
            suite = PilotScenarioSuite.from_path(Path(arguments.suite))
            scenario_report = run_pilot_scenarios(
                repository,
                suite,
                published_ref=arguments.ref,
            )
            payload = scenario_report.canonical_json()
            if arguments.output:
                _write_report(Path(arguments.output), payload)
            print(payload, end="")
            if arguments.require_pass and not scenario_report.passed:
                return 3
            return 0

        manifest = PilotEvaluationManifest.from_path(Path(arguments.manifest))
        if arguments.scenario_report:
            executable = PilotScenarioReport.from_path(Path(arguments.scenario_report))
            manifest = apply_scenario_report(
                manifest,
                executable,
                repository,
                published_ref=arguments.ref,
            )
        report = build_pilot_report(
            repository,
            manifest,
            published_ref=arguments.ref,
        )
        payload = report.canonical_json()
        if arguments.output:
            _write_report(Path(arguments.output), payload)
        print(payload, end="")
        if arguments.require_pass and not report.passed:
            return 3
        return 0
    except WorkspaceError as error:
        print(
            "pcbknowledge: "
            + json.dumps(
                {
                    "status": "ERROR",
                    "error_code": "INVALID_WORKSPACE",
                    "message": str(error),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError, PilotEvaluationError) as error:
        print(
            "pcbknowledge: "
            + json.dumps(
                {
                    "status": "ERROR",
                    "error_code": "INVALID_PILOT_EVALUATION",
                    "message": str(error),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
