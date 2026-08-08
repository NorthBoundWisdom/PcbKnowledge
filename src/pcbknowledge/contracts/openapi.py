"""Deterministic OpenAPI export and drift check."""

import argparse
import difflib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import FastAPI

DEFAULT_OUTPUT = Path("packages/contracts/openapi/pcbknowledge.openapi.json")


def render_openapi(application: FastAPI) -> str:
    """Render OpenAPI with stable key ordering and exactly one trailing newline."""

    document: dict[str, Any] = application.openapi()
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def export_openapi(output: Path, *, check: bool) -> bool:
    """Write or compare the canonical artifact; return whether it was up to date."""

    from pcbknowledge.api import app

    rendered = render_openapi(app)
    if not check:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        return True

    try:
        committed = output.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"OpenAPI artifact is missing: {output}", file=sys.stderr)
        return False
    if committed == rendered:
        return True

    diff = difflib.unified_diff(
        committed.splitlines(),
        rendered.splitlines(),
        fromfile=str(output),
        tofile="generated OpenAPI",
        lineterm="",
    )
    print("\n".join(diff), file=sys.stderr)
    return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pcbknowledge-openapi")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare with the committed artifact instead of writing it",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """OpenAPI export CLI."""

    arguments = _build_parser().parse_args(argv)
    return 0 if export_openapi(arguments.output, check=arguments.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())
