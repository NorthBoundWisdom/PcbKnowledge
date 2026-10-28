"""Bounded, explicit local-byte checks; never canonical or content review.

Only caller-listed candidates are opened. Intake paths are association hints,
not filesystem instructions. No discovery, network, PDF parsing or writes occur.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Sequence

from .intake import IntakeError, _filters, _matches, load_intake


MAX_CANDIDATES = 128
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
MAX_PATH_PARTS = 16
SECURE_PATHS_SUPPORTED = (os.name == "posix" and hasattr(os, "O_NOFOLLOW")
                          and hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NONBLOCK") and os.open in os.supports_dir_fd
                          and os.stat in os.supports_dir_fd and os.stat in os.supports_follow_symlinks)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _relative_path(value: Any) -> str:
    # Use one portable spelling; reject Windows drives, ADS and separators even
    # on POSIX. Never normalize away traversal or consult an intake locator.
    if (not isinstance(value, str) or not value or len(value) > 1024
            or "\\" in value or ":" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise IntakeError("cache-file must be a bounded portable relative path")
    parts = value.split("/")
    if len(parts) > MAX_PATH_PARTS or any(part in {"", ".", ".."} for part in parts):
        raise IntakeError("cache-file must not be absolute or contain traversal/empty components")
    return value


def _safe_hint(value: Any) -> str | None:
    try:
        return _relative_path(value)
    except IntakeError:
        # Historical or absolute recorded paths never become read instructions.
        return None


def _identity(info: os.stat_result) -> tuple:
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _stable_file(info: os.stat_result) -> tuple:
    return (*_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _check_kind(info: os.stat_result, *, directory: bool) -> None:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & reparse:
        raise IntakeError("cache paths must not contain symlinks or reparse points")
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid:
        raise IntakeError("cache paths must use directories and regular files only")


def _unchanged_directories(chain: list[tuple]) -> None:
    for parent_fd, name, descriptor, before in chain:
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        _check_kind(after, directory=True)
        _check_kind(current, directory=True)
        if _identity(before) != _identity(after) or _identity(before) != _identity(current):
            raise IntakeError("cache directory identity changed during audit")


def _open_directory(stack: ExitStack, chain: list, parent_fd: int | None, name: str) -> int:
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    _check_kind(before, directory=True)
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=parent_fd)
    stack.callback(os.close, descriptor)
    opened = os.fstat(descriptor)
    _check_kind(opened, directory=True)
    if _identity(before) != _identity(opened):
        raise IntakeError("cache directory identity changed before opening")
    chain.append((parent_fd, name, descriptor, before))
    return descriptor


@contextmanager
def _root_chain(root: Path):
    # Anchor every lookup in a held parent descriptor, from filesystem root down.
    # O_NOFOLLOW on a leaf alone cannot prevent an ancestor symlink-swap race.
    with ExitStack() as stack:
        chain = []
        descriptor = _open_directory(stack, chain, None, root.anchor)
        for part in root.parts[1:]:
            descriptor = _open_directory(stack, chain, descriptor, part)
        yield descriptor, chain


def _read_candidate(root_fd: int, relative: str, root_chain: list, remaining: int) -> dict:
    chain = list(root_chain)
    parts = relative.split("/")
    with ExitStack() as stack:
        parent_fd = root_fd
        try:
            for part in parts[:-1]:
                parent_fd = _open_directory(stack, chain, parent_fd, part)
            before = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            _unchanged_directories(chain)
            return {"read_status": "MISSING", "actual_sha256": None, "actual_byte_size": None}
        _check_kind(before, directory=False)
        if before.st_size > MAX_FILE_BYTES or before.st_size > remaining:
            raise IntakeError("cache candidate exceeds file or total byte limit")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(parts[-1], flags, dir_fd=parent_fd)
        stack.callback(os.close, descriptor)
        opened = os.fstat(descriptor)
        _check_kind(opened, directory=False)
        if _stable_file(before) != _stable_file(opened):
            raise IntakeError("cache file identity changed before reading")
        _unchanged_directories(chain)
        digest = hashlib.sha256()
        size = 0
        limit = min(MAX_FILE_BYTES, remaining)
        while chunk := os.read(descriptor, min(CHUNK_BYTES, limit - size + 1)):
            size += len(chunk)
            if size > limit:
                raise IntakeError("cache candidate grew beyond file or total byte limit")
            digest.update(chunk)
        after = os.fstat(descriptor)
        _unchanged_directories(chain)
        final = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        _check_kind(final, directory=False)
        if (size != before.st_size or _stable_file(before) != _stable_file(after)
                or _stable_file(before) != _stable_file(final)):
            raise IntakeError("cache file changed during audit")
        return {"read_status": "READ", "actual_sha256": digest.hexdigest(), "actual_byte_size": size}


def _pin(source: dict) -> tuple[str | None, int | None]:
    digest, size = source.get("pdf_sha256"), source.get("pdf_byte_size")
    if digest is not None and (not isinstance(digest, str) or _SHA256.fullmatch(digest) is None):
        raise IntakeError("intake pdf_sha256 must be null or a lowercase SHA-256 digest")
    if size is not None and (type(size) is not int or size <= 0):
        raise IntakeError("intake pdf_byte_size must be null or a positive integer")
    return digest, size


def _source_check(source: dict, candidates: list[dict]) -> dict:
    digest, size = _pin(source)
    result = {"source_id": source["id"], "recorded_sha256": digest,
              "recorded_byte_size": size, "local_byte_check": "UNPINNED",
              "matching_copy_count": 0, "associated_candidates": []}
    if digest is None or size is None:
        return result
    hints = {_safe_hint(source.get(key)) for key in ("pdf_local_path", "evidence_cache_path")}
    associated = [item for item in candidates
                  if item["actual_sha256"] == digest or item["relative_path"] in hints
                  or item["relative_path"].split("/")[-1] == digest + ".pdf"]
    result["associated_candidates"] = [item["candidate"] for item in associated]
    present = [item for item in associated if item["read_status"] == "READ"]
    identities = {(item["actual_sha256"], item["actual_byte_size"]) for item in present}
    result["matching_copy_count"] = sum(
        (item["actual_sha256"], item["actual_byte_size"]) == (digest, size) for item in present)
    if len(identities) > 1:
        result["local_byte_check"] = "AMBIGUOUS"
    elif identities == {(digest, size)}:
        result["local_byte_check"] = "FOUND_MATCH"
    elif identities:
        result["local_byte_check"] = "HASH_MISMATCH"
    else:
        result["local_byte_check"] = "MISSING"
    return result


def intake_evidence_audit(
    root: Path, *, cache_root: Path, cache_files: Sequence[str], include_paths: bool = False,
    source_id: str | None = None, manufacturer: str | None = None,
    device: str | None = None, package: str | None = None,
) -> dict:
    """Compare full recorded pins with only explicit local candidates.

    Missing bytes are scoped to this candidate list, never the whole filesystem.
    A match checks hash and size only, not document contents or source authority.
    """
    if not SECURE_PATHS_SUPPORTED:
        raise IntakeError("local byte audit unsupported: requires POSIX descriptor-relative no-follow filesystem operations")
    filters = _filters(id=source_id, manufacturer=manufacturer, device=device, package=package)
    if (isinstance(cache_files, (str, bytes)) or not isinstance(cache_files, (list, tuple))
            or not 1 <= len(cache_files) <= MAX_CANDIDATES):
        raise IntakeError(f"supply 1 to {MAX_CANDIDATES} explicit cache-file candidates")
    paths = [_relative_path(value) for value in cache_files]
    if len(paths) != len(set(paths)):
        raise IntakeError("duplicate cache-file candidates are not allowed")
    # Validate the complete intake before any payload reads, even for no matches.
    batches = load_intake(root)
    for batch in batches:
        for source in batch["data"]["sources"]:
            _pin(source)
    root_text = os.fspath(cache_root)
    if (not isinstance(root_text, str) or root_text.startswith(("\\", "//"))
            or "://" in root_text):
        raise IntakeError("cache-root must be local, not UNC, device namespace or URL")
    selected_root = Path(root_text).absolute()
    if (selected_root == selected_root.parent or ".." in selected_root.parts
            or len(selected_root.parts) > 128 or len(str(selected_root)) > 4096):
        raise IntakeError("cache-root must be a bounded explicit non-root directory without traversal")
    candidates = []
    total = 0
    try:
        with _root_chain(selected_root) as (root_fd, chain):
            for number, relative in enumerate(paths, 1):
                item = _read_candidate(root_fd, relative, chain, MAX_TOTAL_BYTES - total)
                total += item["actual_byte_size"] or 0
                candidates.append({"candidate": number, "relative_path": relative, **item})
            _unchanged_directories(chain)
    except OSError as error:
        # Do not leak absolute cache paths through normal CLI diagnostics.
        raise IntakeError(f"cache audit cannot safely read candidates ({type(error).__name__})") from error
    rows = []
    for batch in batches:
        for source in sorted(batch["data"]["sources"], key=lambda item: item["id"]):
            if _matches(source, filters):
                rows.append({"batch_path": batch["path"], "batch_sha256": batch["sha256"],
                             **_source_check(source, candidates)})
    public_candidates = [{key: value for key, value in item.items()
                          if include_paths or key != "relative_path"} for item in candidates]
    return {
        "format": "pcbknowledge-intake-evidence-audit-v1", "canonical": False,
        "scope": "EXPLICIT_LOCAL_CANDIDATES_ONLY", "metadata_modified": False,
        "limitations": [
            "Local byte checks compare SHA-256 and byte count only; no PDF parsing or content review occurs.",
            "FOUND_MATCH does not verify manufacturer, revision, visual anchors, license or electrical claims.",
            "Recorded review/evidence statuses, owner acceptance and canonical authority are unchanged.",
            "MISSING means no match among these candidates, not absence elsewhere; UNPINNED is not a byte match.",
            "HASH_MISMATCH includes a byte-count conflict; AMBIGUOUS preserves conflicting claimed locators.",
            "This is an ephemeral observation, not a durable receipt, source fetch or current-revision check.",
        ],
        "summary": {"source_scope_count": len(rows), "candidate_count": len(candidates),
                    "read_candidate_count": sum(item["read_status"] == "READ" for item in candidates),
                    "total_bytes_read": total,
                    "local_byte_checks": {status: sum(row["local_byte_check"] == status for row in rows)
                                          for status in ("FOUND_MATCH", "MISSING", "HASH_MISMATCH", "UNPINNED", "AMBIGUOUS")}},
        "candidates": public_candidates, "sources": rows,
    }
