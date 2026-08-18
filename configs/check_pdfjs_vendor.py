#!/usr/bin/env python3
"""Validate the pinned local PDF.js evidence-review distribution."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from pcbknowledge.git_native.pdfjs_vendor import PdfJsVendorError, validate_pdfjs_vendor  # noqa: E402


def main() -> int:
    try:
        receipt = validate_pdfjs_vendor()
    except PdfJsVendorError as error:
        print(f"pcbknowledge: {error}", file=sys.stderr)
        return 2
    print(
        "[pcbknowledge] PDF.js vendor: "
        f"{receipt.version} {receipt.build}; {receipt.file_count} pinned files; SHA-256 OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
