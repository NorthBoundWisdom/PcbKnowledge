"""Atomic repository and content-addressed evidence operations."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator

import fcntl

from pcbknowledge.git_native.model import (
    Evidence,
    KnowledgeRecord,
    PreparedBy,
    RecordStatus,
    RecordTransitionError,
    RecordValidationError,
    deterministic_record_id,
)


MAX_RECORD_BYTES = 1_000_000
MAX_PDF_BYTES = 64 * 1024 * 1024
_RECORD_FILENAME = re.compile(r"pk_[0-9a-f]{24,32}\.json\Z")
_EVIDENCE_PATH = re.compile(
    r"evidence/sha256/(?P<prefix>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})\.pdf\Z"
)
_DATA_ROOTS = ("knowledge/", "evidence/")


class RepositoryError(RuntimeError):
    """Base error for repository operations."""


class RecordNotFoundError(RepositoryError):
    """A requested record does not exist."""


class RecordConflictError(RepositoryError):
    """An optimistic write or idempotent create conflicts."""


class EvidenceError(RepositoryError):
    """A PDF is malformed or conflicts with existing evidence."""


class ChangeScope(StrEnum):
    CLEAN = "CLEAN"
    DATA_ONLY = "DATA_ONLY"
    CODE_ONLY = "CODE_ONLY"
    MIXED = "MIXED"


@dataclass(frozen=True, slots=True)
class GitChanges:
    status_lines: tuple[str, ...]
    tracked_diff: str
    untracked_preview: str

    @property
    def count(self) -> int:
        return len(self.status_lines)


class KnowledgeRepository:
    def __init__(self, root: Path) -> None:
        resolved = root.resolve()
        if not (resolved / ".git").exists():
            raise RepositoryError(f"not a Git repository: {resolved}")
        self.root = resolved
        self.records_dir = resolved / "knowledge" / "records"
        self.evidence_dir = resolved / "evidence" / "sha256"
        self.state_dir = resolved / ".pcbknowledge"
        self._thread_write_lock = threading.RLock()
        self._write_lock_depth = 0
        self._write_lock_stream: BinaryIO | None = None

    def ensure_layout(self) -> None:
        for directory in (self.records_dir, self.evidence_dir):
            directory.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise RepositoryError(f"repository layout directory is unsafe: {directory}")

    def record_path(self, record_id: str) -> Path:
        candidate = KnowledgeRecord.new(record_id, prepared_by=PreparedBy.HUMAN)
        return self.records_dir / f"{candidate.id}.json"

    def load(self, record_id: str) -> KnowledgeRecord:
        self.ensure_layout()
        path = self.record_path(record_id)
        try:
            stat = path.lstat()
        except FileNotFoundError as error:
            raise RecordNotFoundError("record not found") from error
        if path.is_symlink() or not path.is_file():
            raise RecordValidationError(f"record path is not a regular file: {path}")
        if stat.st_size > MAX_RECORD_BYTES:
            raise RecordValidationError(f"record exceeds {MAX_RECORD_BYTES} bytes: {path}")
        try:
            payload = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise RecordValidationError(f"record is not UTF-8: {path}") from error
        record = KnowledgeRecord.from_json(payload)
        if record.id != record_id:
            raise RecordValidationError(f"record id does not match filename: {path}")
        return record

    def list(self, *, status: RecordStatus | None = None) -> list[KnowledgeRecord]:
        if not self.records_dir.exists():
            return []
        records: list[KnowledgeRecord] = []
        for path in sorted(self.records_dir.glob("pk_*.json")):
            record = self.load(path.stem)
            if status is None or record.status is status:
                records.append(record)
        return self._sorted_records(records)

    def list_published(self, *, ref: str = "HEAD") -> list[KnowledgeRecord]:
        """Read a fully validated committed snapshot, then expose only APPROVED records."""
        records = self._validated_ref_records(ref)
        return self._sorted_records(
            record for record in records if record.status is RecordStatus.APPROVED
        )

    def validate_all(self, *, require_canonical: bool = True) -> list[KnowledgeRecord]:
        self.ensure_layout()
        self._validate_record_layout()
        records = self.list()
        ids = {record.id for record in records}
        referenced_evidence: set[str] = set()
        for record in records:
            path = self.record_path(record.id)
            if require_canonical and path.read_text(encoding="utf-8") != record.canonical_json():
                raise RecordValidationError(f"record is not canonical JSON: {path}")
            if record.supersedes is not None and record.supersedes not in ids:
                raise RecordValidationError(
                    f"record {record.id} supersedes missing record {record.supersedes}"
                )
            if record.evidence.present:
                self.verify_evidence(record.evidence)
                assert record.evidence.path is not None
                referenced_evidence.add(record.evidence.path)
        self._validate_committed_approved_records()
        self._validate_evidence_layout(referenced_evidence)
        return records

    def create(
        self,
        *,
        prepared_by: PreparedBy,
        idempotency_key: str | None = None,
    ) -> KnowledgeRecord:
        with self._write_lock():
            self.ensure_layout()
            record_id = (
                deterministic_record_id(idempotency_key)
                if idempotency_key is not None
                else f"pk_{secrets.token_hex(12)}"
            )
            record = KnowledgeRecord.new(record_id, prepared_by=prepared_by)
            path = self.record_path(record.id)
            if path.exists():
                existing = self.load(record.id)
                if existing.prepared_by is not prepared_by:
                    raise RecordConflictError("idempotency key belongs to a different origin")
                return existing
            self._write_new(path, record.canonical_json())
            return record

    def insert(self, record: KnowledgeRecord) -> None:
        """Insert a fully constructed new record without staging or committing it."""
        with self._write_lock():
            self.ensure_layout()
            record.validate()
            self._validate_record_references_for_write(record)
            self._write_new(self.record_path(record.id), record.canonical_json())

    def save(self, previous: KnowledgeRecord, updated: KnowledgeRecord, expected_revision: str) -> None:
        with self._write_lock():
            self.ensure_layout()
            current = self.load(previous.id)
            if current.revision_token != expected_revision or current != previous:
                raise RecordConflictError("record changed since it was loaded")
            if updated.id != previous.id:
                raise RecordConflictError("record id cannot change")
            if previous.status is RecordStatus.APPROVED and updated != previous:
                raise RecordTransitionError(
                    "approved records are immutable; create a superseding record"
                )
            if (
                len(updated.review_history) < len(previous.review_history)
                or updated.review_history[: len(previous.review_history)]
                != previous.review_history
            ):
                raise RecordTransitionError("review_history is append-only")
            updated.validate()
            self._validate_record_references_for_write(updated)
            self._atomic_replace(self.record_path(updated.id), updated.canonical_json())
            self._prune_replaced_evidence(previous.evidence, updated.evidence)

    def import_pdf_bytes(self, payload: bytes) -> Evidence:
        evidence = self.inspect_pdf_bytes(payload)
        with self._write_lock():
            self.ensure_layout()
            assert evidence.path is not None
            destination = self.root / evidence.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.parent.is_symlink() or not destination.parent.is_dir():
                raise EvidenceError("evidence digest directory is unsafe")
            if destination.exists():
                self.verify_evidence(evidence)
                return evidence

            assert evidence.sha256 is not None
            digest = evidence.sha256
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{digest}.", suffix=".tmp", dir=destination.parent
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temporary, destination)
                except FileExistsError:
                    pass
            finally:
                temporary.unlink(missing_ok=True)
            self.verify_evidence(evidence)
            return evidence

    def inspect_pdf_bytes(self, payload: bytes) -> Evidence:
        """Validate and describe PDF bytes without mutating the repository."""
        if not payload.startswith(b"%PDF-"):
            raise EvidenceError("the selected file is not a PDF")
        if not payload or len(payload) > MAX_PDF_BYTES:
            raise EvidenceError(f"PDF must be between 1 and {MAX_PDF_BYTES} bytes")
        digest = hashlib.sha256(payload).hexdigest()
        relative = Path("evidence") / "sha256" / digest[:2] / f"{digest}.pdf"
        return Evidence(
            path=relative.as_posix(),
            sha256=digest,
            byte_size=len(payload),
            media_type="application/pdf",
        )

    def import_pdf_path(self, source: Path) -> Evidence:
        resolved = source.expanduser().resolve()
        if not resolved.is_file():
            raise EvidenceError("PDF source is not a regular file")
        if resolved.stat().st_size > MAX_PDF_BYTES:
            raise EvidenceError(f"PDF exceeds {MAX_PDF_BYTES} bytes")
        return self.import_pdf_bytes(resolved.read_bytes())

    def inspect_pdf_path(self, source: Path) -> Evidence:
        resolved = source.expanduser().resolve()
        if not resolved.is_file():
            raise EvidenceError("PDF source is not a regular file")
        if resolved.stat().st_size > MAX_PDF_BYTES:
            raise EvidenceError(f"PDF exceeds {MAX_PDF_BYTES} bytes")
        return self.inspect_pdf_bytes(resolved.read_bytes())

    def verify_evidence(self, evidence: Evidence) -> None:
        if not evidence.present:
            return
        assert evidence.path is not None
        assert evidence.sha256 is not None
        assert evidence.byte_size is not None
        path = self.root / evidence.path
        try:
            stat = path.lstat()
        except FileNotFoundError as error:
            raise EvidenceError(f"evidence file is missing: {evidence.path}") from error
        if path.is_symlink() or not path.is_file():
            raise EvidenceError(f"evidence path is not a regular file: {evidence.path}")
        if stat.st_size != evidence.byte_size:
            raise EvidenceError(f"evidence size does not match record: {evidence.path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != evidence.sha256:
            raise EvidenceError(f"evidence hash does not match record: {evidence.path}")
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise EvidenceError(f"evidence is not a PDF: {evidence.path}")

    def git_changes(self) -> GitChanges:
        status = self._git(
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "knowledge",
            "evidence",
        )
        tracked = self._git("diff", "--no-ext-diff", "--", "knowledge", "evidence")
        status_lines = tuple(line for line in status.splitlines() if line)
        previews: list[str] = []
        for line in status_lines:
            if not line.startswith("?? "):
                continue
            relative = line[3:]
            candidate = (self.root / relative).resolve()
            try:
                candidate.relative_to(self.root)
            except ValueError:
                continue
            if candidate.suffix == ".json" and candidate.is_file():
                previews.append(f"--- /dev/null\n+++ b/{relative}\n")
                previews.extend(f"+{item}\n" for item in candidate.read_text("utf-8").splitlines())
            elif candidate.suffix == ".pdf" and candidate.is_file():
                previews.append(f"new binary evidence: {relative} ({candidate.stat().st_size} bytes)\n")
        return GitChanges(
            status_lines=status_lines,
            tracked_diff=tracked,
            untracked_preview="".join(previews),
        )

    def git_change_scope(self) -> ChangeScope:
        """Classify the next commit: staged paths first, otherwise all workspace paths."""
        paths = self._candidate_change_paths()
        data = any(path.startswith(_DATA_ROOTS) for path in paths)
        code = any(not path.startswith(_DATA_ROOTS) for path in paths)
        if data and code:
            return ChangeScope.MIXED
        if data:
            return ChangeScope.DATA_ONLY
        if code:
            return ChangeScope.CODE_ONLY
        return ChangeScope.CLEAN

    def validate_change_scope(self) -> ChangeScope:
        scope = self.git_change_scope()
        if scope is ChangeScope.MIXED:
            raise RepositoryError(
                "mixed knowledge/evidence and software changes are not allowed in one commit"
            )
        return scope

    def _candidate_change_paths(self) -> tuple[str, ...]:
        staged = self._parse_name_status(
            self._git_bytes(
                "diff",
                "--cached",
                "--name-status",
                "--find-renames",
                "--no-ext-diff",
                "-z",
                "--",
            )
        )
        if staged:
            return staged

        unstaged = self._parse_name_status(
            self._git_bytes(
                "diff",
                "--name-status",
                "--find-renames",
                "--no-ext-diff",
                "-z",
                "--",
            )
        )
        untracked = self._decode_nul_paths(
            self._git_bytes("ls-files", "--others", "--exclude-standard", "-z")
        )
        return tuple(dict.fromkeys((*unstaged, *untracked)))

    @staticmethod
    def _parse_name_status(payload: bytes) -> tuple[str, ...]:
        tokens = payload.split(b"\0")
        if tokens and tokens[-1] == b"":
            tokens.pop()
        paths: list[str] = []
        index = 0
        while index < len(tokens):
            try:
                status = tokens[index].decode("ascii")
            except UnicodeDecodeError as error:
                raise RepositoryError("Git returned an invalid change status") from error
            index += 1
            path_count = 2 if status[:1] in {"R", "C"} else 1
            if not status or index + path_count > len(tokens):
                raise RepositoryError("Git returned a malformed change list")
            paths.extend(
                KnowledgeRepository._decode_path(token)
                for token in tokens[index : index + path_count]
            )
            index += path_count
        return tuple(paths)

    @staticmethod
    def _decode_nul_paths(payload: bytes) -> tuple[str, ...]:
        tokens = payload.split(b"\0")
        if tokens and tokens[-1] == b"":
            tokens.pop()
        return tuple(KnowledgeRepository._decode_path(token) for token in tokens)

    @staticmethod
    def _decode_path(payload: bytes) -> str:
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RepositoryError("Git path is not UTF-8") from error

    def _git(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RepositoryError(result.stderr.strip() or "git command failed")
        return result.stdout

    def _git_bytes(self, *arguments: str) -> bytes:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise RepositoryError(message or "git command failed")
        return result.stdout

    def _resolve_git_ref(self, ref: str) -> str | None:
        if not ref or ref.startswith("-") or "\x00" in ref or "\n" in ref:
            raise RepositoryError("Git ref is invalid")
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--verify",
                "--quiet",
                "--end-of-options",
                f"{ref}^{{commit}}",
            ],
            cwd=self.root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="ascii",
        )
        if result.returncode != 0:
            return None
        commit = result.stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40,64}", commit) is None:
            raise RepositoryError("Git resolved an invalid commit id")
        return commit

    def _validated_ref_records(self, ref: str) -> list[KnowledgeRecord]:
        commit = self._resolve_git_ref(ref)
        if commit is None:
            return []
        entries = self._parse_tree_entries(
            self._git_bytes(
                "ls-tree",
                "-r",
                "-z",
                commit,
                "--",
                "knowledge/records",
                "evidence/sha256",
            )
        )
        record_paths: list[str] = []
        evidence_paths: list[str] = []
        for mode, object_type, relative in entries:
            if mode != "100644" or object_type != "blob":
                raise RepositoryError(
                    f"published snapshot path is not a regular non-executable file: {relative}"
                )
            if relative == "knowledge/records/.gitkeep":
                continue
            if relative.startswith("knowledge/records/"):
                path = Path(relative)
                if (
                    path.parent.as_posix() != "knowledge/records"
                    or _RECORD_FILENAME.fullmatch(path.name) is None
                ):
                    raise RecordValidationError(
                        f"unexpected published record path: {relative}"
                    )
                record_paths.append(relative)
                continue
            if relative == "evidence/sha256/.gitkeep":
                continue
            if relative.startswith("evidence/sha256/"):
                match = _EVIDENCE_PATH.fullmatch(relative)
                if match is None or match["prefix"] != match["digest"][:2]:
                    raise EvidenceError(f"unexpected published evidence path: {relative}")
                evidence_paths.append(relative)
                continue
            raise RepositoryError(f"unexpected published snapshot path: {relative}")

        records: list[KnowledgeRecord] = []
        ids: set[str] = set()
        for relative in record_paths:
            payload = self._read_ref_blob(
                commit, relative, maximum_bytes=MAX_RECORD_BYTES
            )
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError as error:
                raise RecordValidationError(
                    f"published record is not UTF-8: {relative}"
                ) from error
            record = KnowledgeRecord.from_json(text)
            if record.id != Path(relative).stem:
                raise RecordValidationError(
                    f"published record id does not match filename: {relative}"
                )
            if payload != record.canonical_json().encode("utf-8"):
                raise RecordValidationError(
                    f"published record is not canonical JSON: {relative}"
                )
            if record.id in ids:
                raise RecordValidationError(f"duplicate published record id: {record.id}")
            ids.add(record.id)
            records.append(record)

        for record in records:
            if record.supersedes is not None and record.supersedes not in ids:
                raise RecordValidationError(
                    f"published record {record.id} supersedes missing record "
                    f"{record.supersedes}"
                )

        evidence_metadata: dict[str, tuple[int, str]] = {}
        for relative in evidence_paths:
            payload = self._read_ref_blob(
                commit, relative, maximum_bytes=MAX_PDF_BYTES
            )
            if not payload.startswith(b"%PDF-"):
                raise EvidenceError(f"published evidence is not a PDF: {relative}")
            digest = hashlib.sha256(payload).hexdigest()
            match = _EVIDENCE_PATH.fullmatch(relative)
            assert match is not None
            if digest != match["digest"]:
                raise EvidenceError(
                    f"published evidence hash does not match path: {relative}"
                )
            evidence_metadata[relative] = (len(payload), digest)

        referenced: set[str] = set()
        for record in records:
            if not record.evidence.present:
                continue
            assert record.evidence.path is not None
            assert record.evidence.byte_size is not None
            assert record.evidence.sha256 is not None
            metadata = evidence_metadata.get(record.evidence.path)
            if metadata is None:
                raise EvidenceError(
                    f"published evidence is missing from {ref}: {record.evidence.path}"
                )
            byte_size, digest = metadata
            if byte_size != record.evidence.byte_size or digest != record.evidence.sha256:
                raise EvidenceError(
                    f"published evidence does not match record: {record.evidence.path}"
                )
            referenced.add(record.evidence.path)

        orphaned = sorted(set(evidence_metadata) - referenced)
        if orphaned:
            raise EvidenceError(f"unreferenced published evidence file: {orphaned[0]}")
        return records

    @staticmethod
    def _parse_tree_entries(payload: bytes) -> tuple[tuple[str, str, str], ...]:
        raw_entries = payload.split(b"\0")
        if raw_entries and raw_entries[-1] == b"":
            raw_entries.pop()
        entries: list[tuple[str, str, str]] = []
        for raw_entry in raw_entries:
            try:
                header, raw_path = raw_entry.split(b"\t", 1)
                raw_mode, raw_type, _raw_object = header.split(b" ", 2)
                mode = raw_mode.decode("ascii")
                object_type = raw_type.decode("ascii")
            except (ValueError, UnicodeDecodeError) as error:
                raise RepositoryError("Git returned a malformed tree entry") from error
            entries.append(
                (mode, object_type, KnowledgeRepository._decode_path(raw_path))
            )
        return tuple(entries)

    def _read_ref_blob(
        self, commit: str, relative: str, *, maximum_bytes: int
    ) -> bytes:
        specification = f"{commit}:{relative}"
        raw_size = self._git("cat-file", "-s", specification).strip()
        try:
            byte_size = int(raw_size)
        except ValueError as error:
            raise RepositoryError(f"Git returned an invalid blob size: {relative}") from error
        if byte_size < 0 or byte_size > maximum_bytes:
            raise RepositoryError(
                f"published blob exceeds {maximum_bytes} bytes: {relative}"
            )
        payload = self._git_bytes("cat-file", "blob", specification)
        if len(payload) != byte_size:
            raise RepositoryError(f"published blob size changed while reading: {relative}")
        return payload

    def _validate_record_references_for_write(self, record: KnowledgeRecord) -> None:
        if record.evidence.present:
            self.verify_evidence(record.evidence)

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        with self._thread_write_lock:
            if self._write_lock_depth == 0:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                if self.state_dir.is_symlink() or not self.state_dir.is_dir():
                    raise RepositoryError(
                        f"repository state directory is unsafe: {self.state_dir}"
                    )
                lock_path = self.state_dir / "write.lock"
                flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
                flags |= getattr(os, "O_NOFOLLOW", 0)
                try:
                    descriptor = os.open(lock_path, flags, 0o600)
                except OSError as error:
                    raise RepositoryError("cannot open repository write lock") from error
                stream = os.fdopen(descriptor, "r+b", buffering=0)
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                except BaseException:
                    stream.close()
                    raise
                self._write_lock_stream = stream
            self._write_lock_depth += 1
            try:
                yield
            finally:
                self._write_lock_depth -= 1
                if self._write_lock_depth == 0:
                    stream = self._write_lock_stream
                    self._write_lock_stream = None
                    assert stream is not None
                    try:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                    finally:
                        stream.close()

    def _prune_replaced_evidence(self, previous: Evidence, updated: Evidence) -> None:
        if not previous.present or previous.path == updated.path:
            return
        assert previous.path is not None

        # Current records are the first authority. Shared evidence must never be removed.
        for record in self.list():
            if record.evidence.path == previous.path:
                return

        # A committed APPROVED record may still need the bytes even if the workspace is already
        # inconsistent for another reason. Preserve that evidence and let validation report the
        # immutable-record violation rather than deleting authoritative bytes.
        for record in self.list_published():
            if record.evidence.path == previous.path:
                return

        candidate = self.root / previous.path
        if candidate.exists():
            if candidate.is_symlink() or not candidate.is_file():
                raise EvidenceError(f"replaced evidence path is unsafe: {previous.path}")
            candidate.unlink()
            try:
                candidate.parent.rmdir()
            except OSError:
                pass

    def _validate_record_layout(self) -> None:
        for path in sorted(self.records_dir.iterdir()):
            if path.is_symlink():
                raise RecordValidationError(f"record layout contains a symlink: {path}")
            if path.name == ".gitkeep" and path.is_file():
                continue
            if not path.is_file() or _RECORD_FILENAME.fullmatch(path.name) is None:
                raise RecordValidationError(f"unexpected record layout entry: {path}")

    def _validate_evidence_layout(self, referenced: set[str]) -> None:
        discovered: set[str] = set()
        for path in sorted(self.evidence_dir.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
            if path.is_symlink():
                raise EvidenceError(f"evidence layout contains a symlink: {relative}")
            if path.is_dir():
                if path.parent != self.evidence_dir or re.fullmatch(r"[0-9a-f]{2}", path.name) is None:
                    raise EvidenceError(f"unexpected evidence directory: {relative}")
                continue
            if path.name == ".gitkeep" and path.parent == self.evidence_dir:
                continue
            match = _EVIDENCE_PATH.fullmatch(relative)
            if not path.is_file() or match is None or match["prefix"] != match["digest"][:2]:
                raise EvidenceError(f"unexpected evidence file: {relative}")
            evidence = Evidence(
                path=relative,
                sha256=match["digest"],
                byte_size=path.stat().st_size,
                media_type="application/pdf",
            )
            self.verify_evidence(evidence)
            discovered.add(relative)
        orphaned = sorted(discovered - referenced)
        if orphaned:
            raise EvidenceError("unreferenced evidence file: " + orphaned[0])

    def _validate_committed_approved_records(self) -> None:
        for committed in self._validated_ref_records("HEAD"):
            relative = f"knowledge/records/{committed.id}.json"
            current_path = self.root / relative
            if committed.status is RecordStatus.APPROVED:
                if not current_path.is_file() or current_path.is_symlink():
                    raise RecordValidationError(
                        f"committed approved record cannot be deleted: {relative}"
                    )
                current = self.load(Path(relative).stem)
                if current != committed:
                    raise RecordValidationError(
                        f"committed approved record is immutable: {relative}"
                    )
                continue

            if not current_path.is_file() or current_path.is_symlink():
                continue
            current = self.load(Path(relative).stem)
            if (
                len(current.review_history) < len(committed.review_history)
                or current.review_history[: len(committed.review_history)]
                != committed.review_history
            ):
                raise RecordValidationError(
                    f"committed review_history is append-only: {relative}"
                )

    @staticmethod
    def _sorted_records(records: Iterable[KnowledgeRecord]) -> list[KnowledgeRecord]:
        return sorted(records, key=lambda item: ((item.title or "").casefold(), item.id))

    @staticmethod
    def _write_new(path: Path, payload: str) -> None:
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise RecordConflictError("record already exists") from error

    @staticmethod
    def _atomic_replace(path: Path, payload: str) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def summarize_records(records: Iterable[KnowledgeRecord]) -> dict[str, int]:
    summary = {status.value: 0 for status in RecordStatus}
    for record in records:
        summary[record.status.value] += 1
    return summary
