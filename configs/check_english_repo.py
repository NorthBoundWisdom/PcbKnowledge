#!/usr/bin/env python3
"""Fail if tracked public-repository text contains CJK, Kana, or Hangul."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class LanguageViolation:
    path: str
    line: int
    column: int
    codepoint: int


# The public software repository uses English as its contributor/UI language.
# Private knowledge workspaces are not subject to this source-repository policy.
def _is_disallowed_character(character: str) -> bool:
    value = ord(character)
    return any(
        lower <= value <= upper
        for lower, upper in (
            (0x3040, 0x30FF),      # Hiragana + Katakana
            (0x31F0, 0x31FF),      # Katakana phonetic extensions
            (0x3400, 0x4DBF),      # CJK Unified Ideographs Extension A
            (0x4E00, 0x9FFF),      # CJK Unified Ideographs
            (0xAC00, 0xD7AF),      # Hangul syllables
            (0xF900, 0xFAFF),      # CJK compatibility ideographs
            (0xFF66, 0xFF9F),      # Halfwidth Katakana
            (0x20000, 0x2FA1F),    # CJK extensions B through compatibility supplement
        )
    )


def tracked_paths(root: Path = REPO_ROOT) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return tuple(
        Path(raw.decode("utf-8"))
        for raw in result.stdout.split(b"\0")
        if raw
    )


def check_english_repository(root: Path = REPO_ROOT) -> tuple[LanguageViolation, ...]:
    violations: list[LanguageViolation] = []
    for relative in tracked_paths(root):
        relative_text = relative.as_posix()
        for column, character in enumerate(relative_text, start=1):
            if _is_disallowed_character(character):
                violations.append(
                    LanguageViolation(relative_text, 0, column, ord(character))
                )

        path = root / relative
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        if b"\0" in payload:
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for column, character in enumerate(line, start=1):
                if _is_disallowed_character(character):
                    violations.append(
                        LanguageViolation(
                            relative_text,
                            line_number,
                            column,
                            ord(character),
                        )
                    )
    return tuple(violations)


def main() -> int:
    try:
        violations = check_english_repository(REPO_ROOT)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        print(f"pcbknowledge: cannot inspect repository language: {error}", file=sys.stderr)
        return 2

    if violations:
        print("pcbknowledge: repository language boundary violation", file=sys.stderr)
        for violation in violations[:50]:
            location = (
                f"{violation.path}:{violation.line}:{violation.column}"
                if violation.line
                else f"{violation.path}:path:{violation.column}"
            )
            print(
                f"  - {location}: U+{violation.codepoint:04X}",
                file=sys.stderr,
            )
        if len(violations) > 50:
            print(f"  ... and {len(violations) - 50} more", file=sys.stderr)
        print(
            "Keep public repository documentation, UI text, comments, and fixtures in English.",
            file=sys.stderr,
        )
        return 2

    print("[pcbknowledge] repository language: English-only source tree OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
