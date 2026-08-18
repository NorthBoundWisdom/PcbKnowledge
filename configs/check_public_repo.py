#!/usr/bin/env python3
"""Fail if the open-source checkout tracks production knowledge or evidence."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.git_native.public_repo import (  # noqa: E402
    ALLOWED_AUTHORITY_PLACEHOLDERS,
    check_public_distribution,
)


def main() -> int:
    try:
        violations = check_public_distribution(REPO_ROOT)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"pcbknowledge: cannot inspect tracked public-source paths: {error}", file=sys.stderr)
        return 2

    if violations:
        print("pcbknowledge: public-source boundary violation", file=sys.stderr)
        for path in violations:
            print(f"  - {path}", file=sys.stderr)
        print(
            "Move production knowledge/evidence to a private Git workspace; "
            "the public upstream may track only approved placeholders.",
            file=sys.stderr,
        )
        return 2

    print(
        "[pcbknowledge] public-source boundary: ok; allowed authority placeholders: "
        f"{len(ALLOWED_AUTHORITY_PLACEHOLDERS)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
