#!/usr/bin/env python3
# Usage: python3 configs/validate_freecm_repo_commands.py

"""Rebuild and run the repository-pinned FreeCM command-manifest validator."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def validate_repo_commands(repo_root: Path = REPO_ROOT) -> int:
    extension_root = repo_root / "FreeCM" / "vscode-extension"
    package_json = extension_root / "package.json"
    node_modules = extension_root / "node_modules"
    if not package_json.is_file():
        print(
            "FreeCM is not initialized; run `git submodule update --init --recursive FreeCM`",
            file=sys.stderr,
        )
        return 1
    if not node_modules.is_dir():
        print(
            "FreeCM validator dependencies are missing; run "
            "`npm ci --no-audit --prefix FreeCM/vscode-extension`",
            file=sys.stderr,
        )
        return 1

    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        missing = "npm" if npm is None else "node"
        print(f"{missing} is required to validate FreeCM commands", file=sys.stderr)
        return 1

    compile_result = subprocess.run(
        [npm, "run", "compile", "--", "--pretty", "false"],
        cwd=extension_root,
        check=False,
    )
    if compile_result.returncode != 0:
        print("FreeCM command validator rebuild failed", file=sys.stderr)
        return compile_result.returncode or 1

    validator = extension_root / "out" / "validateRepoCommands.js"
    if not validator.is_file():
        print(f"FreeCM validator output is missing: {validator}", file=sys.stderr)
        return 1
    validate_result = subprocess.run(
        [node, str(validator), "--preview", str(repo_root)],
        cwd=repo_root,
        check=False,
    )
    if validate_result.returncode != 0:
        print("FreeCM command manifest validation failed", file=sys.stderr)
    return validate_result.returncode


def main() -> int:
    return validate_repo_commands()


if __name__ == "__main__":
    raise SystemExit(main())
