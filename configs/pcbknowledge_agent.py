#!/usr/bin/env python3
"""Repository-local entry point for the bounded Git-native Agent CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.git_native.cli import main as cli_main  # noqa: E402
from pcbknowledge.git_native.workspace import (  # noqa: E402
    WorkspaceError,
    validate_workspace,
    validate_workspace_ref,
)


def _selected_repository(arguments: list[str]) -> Path:
    for index, value in enumerate(arguments):
        if value == "--repo":
            if index + 1 >= len(arguments):
                return Path(".")
            return Path(arguments[index + 1])
        if value.startswith("--repo="):
            return Path(value.split("=", 1)[1])
    return Path(".")


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    root = _selected_repository(arguments)
    try:
        validate_workspace(root)
        if "--published" in arguments:
            validate_workspace_ref(root, "HEAD")
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
    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
