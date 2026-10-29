#!/usr/bin/env python3
"""Fail if versioned knowledge includes originals, binary data, or large files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.public_repo import (  # noqa: E402
    check_public_distribution,
)


def main() -> int:
    try:
        violations = check_public_distribution(REPO_ROOT)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"pcbknowledge: cannot inspect tracked public-source paths: {error}", file=sys.stderr)
        return 2

    if violations:
        print("pcbknowledge: metadata-only boundary violation", file=sys.stderr)
        for path in violations:
            print(f"  - {path}", file=sys.stderr)
        print(
            "Track small UTF-8 text only (exact pinned PDF.js runtime excepted); "
            "keep originals in the ignored .pcbknowledge/evidence cache.",
            file=sys.stderr,
        )
        return 2

    print(
        "[pcbknowledge] metadata-only boundary: ok (index and worktree)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
