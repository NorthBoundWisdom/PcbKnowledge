"""Atomic repository and content-addressed evidence operations."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

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
        """Read committed APPROVED records from a Git ref, never from workspace drafts."""
        if not self._git_ref_exists(ref):
            return []
        paths = self._git(
            "ls-tree", "-r", "--name-only", ref, "--", "knowledge/records"
        )
        records: list[KnowledgeRecord] = []
        for relative in paths.splitlines():
            name = Path(relative).name
            if _RECORD_FILENAME.fullmatch(name) is None:
                continue
            result = subprocess.run(
                ["git", "show", f"{ref}:{relative}"],
                cwd=self.root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != 0:
                raise RecordValidationError(f"cannot read published record: {relative}")
            record = KnowledgeRecord.from_json(result.stdout)
            if record.status is RecordStatus.APPROVED:
                records.append(record)
        return self._sorted_records(records)

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
        self.ensure_layout()
        record.validate()
        self._write_new(self.record_path(record.id), record.canonical_json())

    def save(self, previous: KnowledgeRecord, updated: KnowledgeRecord, expected_revision: str) -> None:
        self.ensure_layout()
        current = self.load(previous.id)
        if current.revision_token != expected_revision or current != previous:
            raise RecordConflictError("record changed since it was loaded")
        if updated.id != previous.id:
            raise RecordConflictError("record id cannot change")
        if previous.status is RecordStatus.APPROVED and updated != previous:
            raise RecordTransitionError("approved records are immutable; create a superseding record")
        if (
            len(updated.review_history) < len(previous.review_history)
            or updated.review_history[: len(previous.review_history)] != previous.review_history
        ):
            raise RecordTransitionError("review_history is append-only")
        updated.validate()
        self._atomic_replace(self.record_path(updated.id), updated.canonical_json())
        self._prune_replaced_evidence(previous.evidence, updated.evidence)

    def import_pdf_bytes(self, payload: bytes) -> Evidence:
        evidence = self.inspect_pdf_bytes(payload)
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
        """Classify current workspace changes so data and executable policy are not committed together."""
        status = self._git("status", "--short", "--untracked-files=all")
        data = False
        code = False
        for line in status.splitlines():
            if not line:
                continue
            relative = line[3:]
            if " -> " in relative:
                relative = relative.split(" -> ", 1)[1]
            if relative.startswith(_DATA_ROOTS):
                data = True
            else:
                code = True
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

    def _git_ref_exists(self, ref: str) -> bool:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=self.root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0

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
        if not self._git_ref_exists("HEAD"):
            return
        paths = self._git(
            "ls-tree", "-r", "--name-only", "HEAD", "--", "knowledge/records"
        )
        for relative in paths.splitlines():
            name = Path(relative).name
            if _RECORD_FILENAME.fullmatch(name) is None:
                continue
            result = subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=self.root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != 0:
                raise RecordValidationError(f"cannot read committed record: {relative}")
            committed = KnowledgeRecord.from_json(result.stdout)
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
