#!/usr/bin/env python3
"""Measure and close the P0.4a pilot against an explicit private workspace."""

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
    """Create the example manifest, or replay only the exact same template."""

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
        raise PilotEvaluationError(
            f"refusing to overwrite existing file: {resolved}"
        )
    return resolved


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a private PcbKnowledge pilot without storing negative cases "
            "as canonical engineering authority"
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    scaffold = commands.add_parser(
        "scaffold", help="write an editable pilot-evaluation manifest template"
    )
    scaffold.add_argument("--output", required=True)

    metrics = commands.add_parser(
        "metrics", help="show working and published workspace coverage metrics"
    )
    metrics.add_argument("--workspace", required=True)
    metrics.add_argument("--ref", default="HEAD")

    report = commands.add_parser(
        "report", help="evaluate structural, scenario, visual, and publication gates"
    )
    report.add_argument("--workspace", required=True)
    report.add_argument("--manifest", required=True)
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


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.command == "scaffold":
            output = _scaffold(Path(arguments.output))
            print(
                json.dumps(
                    {
                        "status": "OK",
                        "format": "pcbknowledge-pilot-eval-v1",
                        "output": str(output),
                        "authority": False,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        repository = _workspace(arguments)
        working = repository.validate_all(require_canonical=True)
        published = repository.read_published_snapshot(ref=arguments.ref)

        if arguments.command == "metrics":
            payload = {
                "format": "pcbknowledge-pilot-metrics-v1",
                "status": "OK",
                "workspace": str(repository.root),
                "published_ref": arguments.ref,
                "published_commit": published.commit,
                "working": measure_snapshot(working).to_dict(),
                "published": measure_snapshot(published).to_dict(),
            }
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        manifest = PilotEvaluationManifest.from_path(Path(arguments.manifest))
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
