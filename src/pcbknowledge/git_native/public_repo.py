"""Guards for keeping the open-source repository free of production knowledge data."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path


ALLOWED_AUTHORITY_PLACEHOLDERS = frozenset(
    {
        "knowledge/sources/.gitkeep",
        "knowledge/entities/.gitkeep",
        "knowledge/facts/.gitkeep",
        "evidence/sha256/.gitkeep",
    }
)
PROTECTED_AUTHORITY_PREFIXES = ("knowledge/", "evidence/")


def _normalize_git_path(raw: str) -> str:
    path = raw.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def public_distribution_violations(tracked_paths: Iterable[str]) -> tuple[str, ...]:
    """Return tracked authority/evidence paths that cannot ship in the public source repo."""

    violations: set[str] = set()
    for raw in tracked_paths:
        path = _normalize_git_path(raw)
        if path.startswith(PROTECTED_AUTHORITY_PREFIXES) and path not in ALLOWED_AUTHORITY_PLACEHOLDERS:
            violations.add(path)
    return tuple(sorted(violations))


def tracked_authority_paths(repo_root: Path) -> tuple[str, ...]:
    """Read tracked authority paths from Git without inspecting untracked private workspace data."""

    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", "knowledge", "evidence"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    decoded = result.stdout.decode("utf-8")
    return tuple(path for path in decoded.split("\0") if path)


def check_public_distribution(repo_root: Path) -> tuple[str, ...]:
    """Validate the tracked public-source boundary for one Git checkout."""

    return public_distribution_violations(tracked_authority_paths(repo_root))
