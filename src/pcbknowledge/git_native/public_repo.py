"""Deterministic metadata-only boundary for versioned knowledge and local caches.

This gate checks every Git index path (the prospective commit) and existing
worktree bytes. It does not inspect ignored/untracked local originals. The only
size/binary exception is exact SHA-256-pinned PDF.js runtime bytes. Schema and review validation remain
separate: passing this gate does not approve a knowledge record.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from .pdfjs_vendor import PDFJS_RUNTIME_FILES, PDFJS_STATIC_RELATIVE


MAX_METADATA_BYTES = 1_000_000
ALLOWED_AUTHORITY_PLACEHOLDERS = frozenset(
    {
        "knowledge/sources/.gitkeep",
        "knowledge/entities/.gitkeep",
        "knowledge/facts/.gitkeep",
        *{f"knowledge/{name}/.gitkeep" for name in ("parts","packages","blocks","rules","fab-profiles","registry")},
        "knowledge/intake/.gitkeep",
        "evidence/sha256/.gitkeep",
    }
)
ALLOWED_REGISTRY_PATHS = frozenset(
    f"knowledge/registry/{name}.json" for name in (
        "quantities", "parameters", "pin-types", "layout-constraints", "package-families", "roles"
    )
)
PROTECTED_AUTHORITY_PREFIXES = ("knowledge/", "evidence/", ".pcbknowledge/")
RAW_DOCUMENT_SUFFIXES = frozenset({
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar", ".doc", ".docx", ".ppt",
    ".pptx", ".xls", ".xlsx", ".rtf", ".ps", ".eps", ".png", ".jpg", ".jpeg",
    ".gif", ".tif", ".tiff", ".webp", ".mp3", ".mp4", ".wav", ".exe", ".dll",
    ".so", ".bin", ".sqlite", ".db", ".wasm", ".pyc",
})
PINNED_SOFTWARE_LINKS = {".grok/skills": b"../.codex/skills"}
PINNED_RUNTIME_FILES = {
    (Path("src/pcbknowledge/git_native/static") / PDFJS_STATIC_RELATIVE / name).as_posix(): identity
    for name, identity in PDFJS_RUNTIME_FILES.items()
}


def _normalize_git_path(raw: str) -> str:
    path = raw.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _allowed_metadata_path(path: str) -> bool:
    if path in ALLOWED_AUTHORITY_PLACEHOLDERS:
        return True
    if PurePosixPath(path).suffix.lower() in RAW_DOCUMENT_SUFFIXES:
        return False
    if not path.startswith(PROTECTED_AUTHORITY_PREFIXES):
        return path not in {"knowledge", "evidence", ".pcbknowledge"}
    parts = PurePosixPath(path).parts
    if ".." in parts or len(parts) < 3 or parts[0] != "knowledge":
        return False
    if parts[1] == "registry":
        return path in ALLOWED_REGISTRY_PATHS
    if parts[1] in {"sources", "entities", "facts", "parts", "packages", "blocks", "rules", "fab-profiles"}:
        return len(parts) == 3 and path.endswith(".json")
    return parts[1] in {"intake", "intake-dispositions"} and PurePosixPath(path).suffix in {".json", ".md"}


def public_distribution_violations(tracked_paths: Iterable[str]) -> tuple[str, ...]:
    """Return forbidden paths; callers must additionally inspect their bytes."""

    return tuple(sorted({
        path
        for raw in tracked_paths
        if not _allowed_metadata_path(path := _normalize_git_path(raw))
    }))


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def tracked_authority_paths(repo_root: Path) -> tuple[str, ...]:
    """Read indexed paths, including force-added ignored cache files."""

    return tuple(path for path in _git(
        repo_root, "ls-files", "-z", "--", "knowledge", "evidence", ".pcbknowledge"
    ).decode("utf-8").split("\0") if path)


def _text_metadata(payload: bytes, *, placeholder: bool = False) -> bool:
    if len(payload) > MAX_METADATA_BYTES or (placeholder and payload.strip()):
        return False
    # PDF can be ASCII; do not mistake a renamed original for metadata.
    if (re.search(rb"(?:^|[\r\n])[ \t]*%PDF-[0-9]+\.[0-9]+", payload[:1024])
            or payload.lstrip().startswith((b"%PDF-", b"{\\rtf", b"%!PS"))):
        return False
    try:
        text = payload.decode("utf-8")
    except UnicodeError:
        return False
    return not any(
        (ord(character) < 32 and character not in "\t\n\r") or ord(character) == 127
        for character in text
    )


def _valid_payload(payload: bytes, *, pin: tuple[int, str] | None, placeholder: bool) -> bool:
    if pin is not None:
        return len(payload) == pin[0] and hashlib.sha256(payload).hexdigest() == pin[1]
    return _text_metadata(payload, placeholder=placeholder)


def _native_link_target_bytes(target: str) -> bytes:
    """Normalize only the host-native separator, not arbitrary target paths."""

    return os.fsencode(target.replace(os.sep, "/"))


def check_public_distribution(repo_root: Path) -> tuple[str, ...]:
    """Reject original/binary/oversized files anywhere in the index or worktree.

    Unmerged entries and symlinks fail closed. Blob size is checked before blob
    content is read; worktree files are similarly bounded. Results are sorted
    paths, independent of filesystem traversal order.
    """

    entries = _git(repo_root, "ls-files", "--stage", "-z")
    violations: set[str] = set()
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if path in PINNED_SOFTWARE_LINKS:
            expected = PINNED_SOFTWARE_LINKS[path]
            local = repo_root / path
            # Git on Windows may materialize a symlink as its small target text.
            if local.is_symlink():
                local_matches = _native_link_target_bytes(os.readlink(local)) == expected
            else:
                local_matches = (local.is_file() and local.stat().st_size == len(expected)
                                 and local.read_bytes() == expected)
            if (mode != "120000" or stage != "0"
                    or int(_git(repo_root, "cat-file", "-s", object_id)) != len(expected)
                    or _git(repo_root, "cat-file", "blob", object_id) != expected
                    or not local_matches):
                violations.add(path)
            continue
        allowed_modes = {"100644"} if path.startswith(PROTECTED_AUTHORITY_PREFIXES) else {"100644", "100755"}
        if not _allowed_metadata_path(path) or mode not in allowed_modes or stage != "0":
            violations.add(path)
            continue
        size = int(_git(repo_root, "cat-file", "-s", object_id))
        placeholder = path in ALLOWED_AUTHORITY_PLACEHOLDERS
        pin = PINNED_RUNTIME_FILES.get(path)
        maximum = pin[0] if pin else MAX_METADATA_BYTES
        if size > maximum:
            violations.add(path)
        else:
            payload = _git(repo_root, "cat-file", "blob", object_id)
            if not _valid_payload(payload, pin=pin, placeholder=placeholder):
                violations.add(path)
        local = repo_root / path
        if any((repo_root / parent).is_symlink() for parent in Path(path).parents
               if parent != Path(".")) or local.is_symlink():
            violations.add(path)
        elif local.exists():
            if not local.is_file() or local.stat().st_size > maximum:
                violations.add(path)
            else:
                with local.open("rb") as stream:
                    payload = stream.read(maximum + 1)
                if not _valid_payload(payload, pin=pin, placeholder=placeholder):
                    violations.add(path)
    return tuple(sorted(violations))
