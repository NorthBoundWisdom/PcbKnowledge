#!/usr/bin/env python3
"""Initialize and validate self-contained PcbKnowledge Git workspaces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.git_native.workspace import (  # noqa: E402
    WorkspaceError,
    initialize_workspace,
    validate_workspace,
    validate_workspace_ref,
)


def _payload(validation, *, replayed: bool | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "status": "OK",
        "workspace": str(validation.root),
        "format": validation.manifest.format,
        "schema_contract": validation.manifest.schema_contract,
        "schema_digest": validation.manifest.schema_digest,
    }
    if validation.ref is not None:
        value["ref"] = validation.ref
        value["commit"] = validation.commit
    if replayed is not None:
        value["replayed"] = replayed
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage a PcbKnowledge knowledge workspace")
    actions = parser.add_subparsers(dest="command", required=True)

    initialize = actions.add_parser("init", help="initialize a knowledge workspace")
    initialize.add_argument("target")
    initialize.add_argument(
        "--init-git",
        action="store_true",
        help="create a Git repository only when the target is missing or empty",
    )

    validate = actions.add_parser("validate", help="validate the working workspace contract")
    validate.add_argument("target")

    validate_ref = actions.add_parser(
        "validate-ref", help="validate the workspace contract from one Git ref"
    )
    validate_ref.add_argument("target")
    validate_ref.add_argument("--ref", default="HEAD")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        if arguments.command == "init":
            result = initialize_workspace(
                Path(arguments.target),
                schema_source_root=REPO_ROOT,
                init_git=arguments.init_git,
            )
            print(
                json.dumps(
                    _payload(result.validation, replayed=result.replayed),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if arguments.command == "validate-ref":
            validation = validate_workspace_ref(Path(arguments.target), arguments.ref)
        else:
            validation = validate_workspace(Path(arguments.target))
        print(json.dumps(_payload(validation), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, WorkspaceError) as error:
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


if __name__ == "__main__":
    raise SystemExit(main())
