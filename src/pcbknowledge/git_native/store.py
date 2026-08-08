"""Atomic repository operations for the Git-native typed authority."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import tempfile
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Mapping, Sequence

import fcntl

from pcbknowledge.git_native.model import (
    ENTITY_SCHEMA_VERSION,
    FACT_SCHEMA_VERSION,
    SOURCE_SCHEMA_VERSION,
    ComponentPinPayload,
    EntityKind,
    EntityRecord,
    Evidence,
    FactPayload,
    FactRecord,
    FactType,
    LicenseClass,
    ParameterLimitKind,
    ParameterLimitPayload,
    PreparedBy,
    RecordStatus,
    RecordTransitionError,
    RecordValidationError,
    ReviewEvent,
    SourceRecord,
    SourceType,
    deterministic_entity_id,
    deterministic_fact_id,
    deterministic_source_id,
    normalize_lookup,
)


MAX_RECORD_BYTES = 1_000_000
MAX_SCHEMA_BYTES = 1_000_000
MAX_PDF_BYTES = 64 * 1024 * 1024

_SOURCE_FILENAME = re.compile(r"pk_[0-9a-f]{24,32}\.json\Z")
_ENTITY_FILENAME = re.compile(r"ent_[0-9a-f]{24,32}\.json\Z")
_FACT_FILENAME = re.compile(r"fact_[0-9a-f]{24,32}\.json\Z")
_EVIDENCE_PATH = re.compile(
    r"evidence/sha256/(?P<prefix>[0-9a-f]{2})/"
    r"(?P<digest>[0-9a-f]{64})\.pdf\Z"
)
_DATA_ROOTS = ("knowledge/", "evidence/")

SCHEMA_PATHS = (
    Path("schemas/source-record.schema.json"),
    Path("schemas/entity-record.schema.json"),
    Path("schemas/fact-record.schema.json"),
)


class RepositoryError(RuntimeError):
    """Base error for repository operations."""


class RecordNotFoundError(RepositoryError):
    """A requested authority object does not exist."""


class RecordConflictError(RepositoryError):
    """An optimistic or idempotent write conflicts with current authority."""


class EvidenceError(RepositoryError):
    """Evidence bytes are malformed or inconsistent."""


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


@dataclass(frozen=True, slots=True)
class FactConflict:
    semantic_key: tuple[object, ...]
    fact_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuthoritySnapshot:
    sources: tuple[SourceRecord, ...]
    entities: tuple[EntityRecord, ...]
    facts: tuple[FactRecord, ...]
    conflicts: tuple[FactConflict, ...] = ()
    ref: str | None = None
    commit: str | None = None

    @property
    def published_sources(self) -> tuple[SourceRecord, ...]:
        return tuple(
            source for source in self.sources if source.status is RecordStatus.APPROVED
        )

    @property
    def published_facts(self) -> tuple[FactRecord, ...]:
        return tuple(
            fact for fact in self.facts if fact.status is RecordStatus.APPROVED
        )

    @property
    def active_published_facts(self) -> tuple[FactRecord, ...]:
        approved = self.published_facts
        superseded = {
            fact.supersedes for fact in approved if fact.supersedes is not None
        }
        return tuple(fact for fact in approved if fact.id not in superseded)

    def __len__(self) -> int:
        return len(self.sources) + len(self.entities) + len(self.facts)


class KnowledgeRepository:
    """Single facade used by the GUI, Agent CLI, validator and packager."""

    def __init__(self, root: Path) -> None:
        resolved = root.resolve()
        if not (resolved / ".git").exists():
            raise RepositoryError(f"not a Git repository: {resolved}")
        self.root = resolved
        self.sources_dir = resolved / "knowledge" / "sources"
        self.entities_dir = resolved / "knowledge" / "entities"
        self.facts_dir = resolved / "knowledge" / "facts"
        self.legacy_records_dir = resolved / "knowledge" / "records"
        self.evidence_dir = resolved / "evidence" / "sha256"
        self.schemas_dir = resolved / "schemas"
        self.state_dir = resolved / ".pcbknowledge"

        # Source-only GUI callers historically used these neutral names.  They map
        # to the one typed Source authority and do not create a second write path.
        self.records_dir = self.sources_dir

        self._thread_write_lock = threading.RLock()
        self._write_lock_depth = 0
        self._write_lock_stream: BinaryIO | None = None

    def ensure_layout(self) -> None:
        for directory in (
            self.sources_dir,
            self.entities_dir,
            self.facts_dir,
            self.evidence_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise RepositoryError(
                    f"repository layout directory is unsafe: {directory}"
                )
        self._reject_legacy_authority()

    def _reject_legacy_authority(self) -> None:
        if not self.legacy_records_dir.exists():
            return
        if self.legacy_records_dir.is_symlink() or not self.legacy_records_dir.is_dir():
            raise RecordValidationError(
                f"legacy authority path is unsafe: {self.legacy_records_dir}"
            )
        for entry in self.legacy_records_dir.iterdir():
            if entry.name == ".gitkeep" and entry.is_file() and not entry.is_symlink():
                continue
            raise RecordValidationError(
                "legacy knowledge/records authority is retired; migrate to "
                "knowledge/sources"
            )

    def source_path(self, source_id: str) -> Path:
        filename = f"{source_id}.json"
        if _SOURCE_FILENAME.fullmatch(filename) is None:
            raise RecordValidationError("invalid source id")
        return self.sources_dir / filename

    def record_path(self, record_id: str) -> Path:
        return self.source_path(record_id)

    def entity_path(self, entity_id: str) -> Path:
        filename = f"{entity_id}.json"
        if _ENTITY_FILENAME.fullmatch(filename) is None:
            raise RecordValidationError("invalid entity id")
        return self.entities_dir / filename

    def fact_path(self, fact_id: str) -> Path:
        filename = f"{fact_id}.json"
        if _FACT_FILENAME.fullmatch(filename) is None:
            raise RecordValidationError("invalid fact id")
        return self.facts_dir / filename

    @staticmethod
    def _read_text(path: Path, *, label: str, maximum_bytes: int) -> str:
        try:
            stat = path.lstat()
        except FileNotFoundError as error:
            raise RecordNotFoundError(f"{label} not found") from error
        if path.is_symlink() or not path.is_file():
            raise RecordValidationError(
                f"{label} path is not a regular file: {path}"
            )
        if stat.st_size > maximum_bytes:
            raise RecordValidationError(
                f"{label} exceeds {maximum_bytes} bytes: {path}"
            )
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise RecordValidationError(f"{label} is not UTF-8: {path}") from error

    # Source operations -------------------------------------------------

    def load_source(self, source_id: str) -> SourceRecord:
        self.ensure_layout()
        source = SourceRecord.from_json(
            self._read_text(
                self.source_path(source_id),
                label="source",
                maximum_bytes=MAX_RECORD_BYTES,
            )
        )
        if source.id != source_id:
            raise RecordValidationError("source id does not match filename")
        return source

    def load(self, record_id: str) -> SourceRecord:
        return self.load_source(record_id)

    def list_sources(
        self, *, status: RecordStatus | None = None
    ) -> list[SourceRecord]:
        self.ensure_layout()
        result = [
            self.load_source(path.stem)
            for path in sorted(self.sources_dir.glob("pk_*.json"))
        ]
        if status is not None:
            result = [source for source in result if source.status is status]
        return self._sorted_sources(result)

    def list(self, *, status: RecordStatus | None = None) -> list[SourceRecord]:
        return self.list_sources(status=status)

    def create_source(
        self,
        *,
        prepared_by: PreparedBy,
        idempotency_key: str | None = None,
        source_type: SourceType = SourceType.DATASHEET,
    ) -> SourceRecord:
        with self._write_lock():
            self.ensure_layout()
            source_id = (
                deterministic_source_id(idempotency_key)
                if idempotency_key is not None
                else f"pk_{secrets.token_hex(12)}"
            )
            source = SourceRecord.new(
                source_id, prepared_by=prepared_by, source_type=source_type
            )
            path = self.source_path(source.id)
            if path.exists():
                existing = self.load_source(source.id)
                if (
                    existing.prepared_by is not prepared_by
                    or existing.source_type is not source_type
                ):
                    raise RecordConflictError(
                        "idempotency key belongs to a different source"
                    )
                return existing
            self._write_new(path, source.canonical_json())
            return source

    def create(
        self,
        *,
        prepared_by: PreparedBy,
        idempotency_key: str | None = None,
    ) -> SourceRecord:
        return self.create_source(
            prepared_by=prepared_by, idempotency_key=idempotency_key
        )

    def insert_source(self, source: SourceRecord) -> None:
        with self._write_lock():
            self.ensure_layout()
            source.validate()
            self._validate_source_for_write(source)
            self._write_new(self.source_path(source.id), source.canonical_json())

    def insert(self, record: SourceRecord) -> None:
        self.insert_source(record)

    def save_source(
        self,
        previous: SourceRecord,
        updated: SourceRecord,
        expected_revision: str,
    ) -> None:
        with self._write_lock():
            current = self.load_source(previous.id)
            self._validate_optimistic(
                previous, current, updated.id, expected_revision
            )
            self._validate_append_only_review(
                previous.review_history, updated.review_history
            )
            if previous.status is RecordStatus.APPROVED and updated != previous:
                raise RecordTransitionError(
                    "approved sources are immutable; create a superseding source"
                )
            updated.validate()
            self._validate_source_for_write(updated)
            self._atomic_replace(
                self.source_path(updated.id), updated.canonical_json()
            )
            self._prune_replaced_evidence(previous.evidence, updated.evidence)

    def save(
        self,
        previous: SourceRecord,
        updated: SourceRecord,
        expected_revision: str,
    ) -> None:
        self.save_source(previous, updated, expected_revision)

    def submit_source(
        self, source_id: str, *, expected_revision: str
    ) -> SourceRecord:
        current = self.load_source(source_id)
        updated = current.submit()
        self.save_source(current, updated, expected_revision)
        return updated

    def approve_source(
        self,
        source_id: str,
        *,
        expected_revision: str,
        comment: str | None,
    ) -> SourceRecord:
        current = self.load_source(source_id)
        updated = current.approve(comment)
        self.save_source(current, updated, expected_revision)
        return updated

    def reject_source(
        self,
        source_id: str,
        *,
        expected_revision: str,
        comment: str,
    ) -> SourceRecord:
        current = self.load_source(source_id)
        updated = current.reject(comment)
        self.save_source(current, updated, expected_revision)
        return updated

    # Entity operations -------------------------------------------------

    def load_entity(self, entity_id: str) -> EntityRecord:
        self.ensure_layout()
        entity = EntityRecord.from_json(
            self._read_text(
                self.entity_path(entity_id),
                label="entity",
                maximum_bytes=MAX_RECORD_BYTES,
            )
        )
        if entity.id != entity_id:
            raise RecordValidationError("entity id does not match filename")
        return entity

    def list_entities(
        self, *, kind: EntityKind | None = None
    ) -> list[EntityRecord]:
        self.ensure_layout()
        result = [
            self.load_entity(path.stem)
            for path in sorted(self.entities_dir.glob("ent_*.json"))
        ]
        if kind is not None:
            result = [entity for entity in result if entity.kind is kind]
        return self._sorted_entities(result)

    def insert_entity(self, entity: EntityRecord) -> None:
        with self._write_lock():
            self.ensure_layout()
            entity.validate()
            existing = self.list_entities()
            self._validate_entity_for_write(entity, existing)
            self._write_new(self.entity_path(entity.id), entity.canonical_json())

    def create_manufacturer(
        self,
        raw_name: str,
        *,
        prepared_by: PreparedBy,
        idempotency_key: str,
    ) -> EntityRecord:
        entity = EntityRecord.manufacturer(
            deterministic_entity_id(EntityKind.MANUFACTURER, idempotency_key),
            raw_name,
            prepared_by=prepared_by,
        )
        return self._insert_or_replay_entity(entity)

    def create_component(
        self,
        manufacturer_id: str,
        raw_mpn: str,
        *,
        family: str | None,
        prepared_by: PreparedBy,
        idempotency_key: str,
    ) -> EntityRecord:
        entity = EntityRecord.component(
            deterministic_entity_id(EntityKind.COMPONENT, idempotency_key),
            manufacturer_id,
            raw_mpn,
            family=family,
            prepared_by=prepared_by,
        )
        return self._insert_or_replay_entity(entity)

    def create_package(
        self,
        raw_name: str,
        *,
        prepared_by: PreparedBy,
        idempotency_key: str,
    ) -> EntityRecord:
        entity = EntityRecord.package(
            deterministic_entity_id(EntityKind.PACKAGE, idempotency_key),
            raw_name,
            prepared_by=prepared_by,
        )
        return self._insert_or_replay_entity(entity)

    def find_manufacturers_exact(self, raw_name: str) -> list[EntityRecord]:
        """Return exact normalized manufacturer matches without fuzzy inference."""

        key = normalize_lookup(raw_name)
        return self._sorted_entities(
            entity
            for entity in self.list_entities(kind=EntityKind.MANUFACTURER)
            if entity.normalized_key == key
        )

    def find_components_exact(
        self, manufacturer_id: str, raw_mpn: str
    ) -> list[EntityRecord]:
        """Return exact manufacturer/MPN matches without suffix inference."""

        key = normalize_lookup(raw_mpn)
        return self._sorted_entities(
            entity
            for entity in self.list_entities(kind=EntityKind.COMPONENT)
            if entity.manufacturer_id == manufacturer_id
            and entity.normalized_mpn == key
        )

    def find_packages_exact(self, raw_name: str) -> list[EntityRecord]:
        """Return exact normalized package matches without MPN inference."""

        key = normalize_lookup(raw_name)
        return self._sorted_entities(
            entity
            for entity in self.list_entities(kind=EntityKind.PACKAGE)
            if entity.normalized_key == key
        )

    def _insert_or_replay_entity(self, entity: EntityRecord) -> EntityRecord:
        with self._write_lock():
            self.ensure_layout()
            path = self.entity_path(entity.id)
            if path.exists():
                current = self.load_entity(entity.id)
                if current != entity:
                    raise RecordConflictError(
                        "entity idempotency key exists with different content"
                    )
                return current
            self.insert_entity(entity)
            return entity

    # Fact operations ---------------------------------------------------

    def load_fact(self, fact_id: str) -> FactRecord:
        self.ensure_layout()
        fact = FactRecord.from_json(
            self._read_text(
                self.fact_path(fact_id),
                label="fact",
                maximum_bytes=MAX_RECORD_BYTES,
            )
        )
        if fact.id != fact_id:
            raise RecordValidationError("fact id does not match filename")
        return fact

    def list_facts(
        self, *, status: RecordStatus | None = None
    ) -> list[FactRecord]:
        self.ensure_layout()
        result = [
            self.load_fact(path.stem)
            for path in sorted(self.facts_dir.glob("fact_*.json"))
        ]
        if status is not None:
            result = [fact for fact in result if fact.status is status]
        return self._sorted_facts(result)

    def create_fact(
        self,
        *,
        idempotency_key: str,
        fact_type: FactType,
        payload: ComponentPinPayload | ParameterLimitPayload,
        prepared_by: PreparedBy,
        conditions: tuple[str, ...] = (),
        applicability: tuple[str, ...] = (),
        evidence_anchors: Sequence[object] = (),
        supersedes: str | None = None,
    ) -> FactRecord:
        fact = FactRecord.new(
            deterministic_fact_id(idempotency_key),
            fact_type=fact_type,
            payload=payload,
            prepared_by=prepared_by,
            conditions=conditions,
            applicability=applicability,
            evidence_anchors=tuple(evidence_anchors),  # type: ignore[arg-type]
            supersedes=supersedes,
        )
        with self._write_lock():
            self.ensure_layout()
            path = self.fact_path(fact.id)
            if path.exists():
                current = self.load_fact(fact.id)
                if current != fact:
                    raise RecordConflictError(
                        "fact idempotency key exists with different content"
                    )
                return current
            self._validate_fact_for_write(fact)
            self._write_new(path, fact.canonical_json())
            return fact

    def insert_fact(self, fact: FactRecord) -> None:
        with self._write_lock():
            self.ensure_layout()
            fact.validate()
            self._validate_fact_for_write(fact)
            self._write_new(self.fact_path(fact.id), fact.canonical_json())

    def save_fact(
        self,
        previous: FactRecord,
        updated: FactRecord,
        expected_revision: str,
    ) -> None:
        with self._write_lock():
            current = self.load_fact(previous.id)
            self._validate_optimistic(
                previous, current, updated.id, expected_revision
            )
            self._validate_append_only_review(
                previous.review_history, updated.review_history
            )
            if previous.status is RecordStatus.APPROVED and updated != previous:
                raise RecordTransitionError(
                    "approved facts are immutable; create a superseding fact"
                )
            updated.validate()
            self._validate_fact_for_write(updated, replacing=previous.id)
            self._atomic_replace(self.fact_path(updated.id), updated.canonical_json())

    def submit_fact(
        self, fact_id: str, *, expected_revision: str
    ) -> FactRecord:
        current = self.load_fact(fact_id)
        updated = current.submit()
        self.save_fact(current, updated, expected_revision)
        return updated

    def approve_fact(
        self,
        fact_id: str,
        *,
        expected_revision: str,
        comment: str | None,
    ) -> FactRecord:
        current = self.load_fact(fact_id)
        updated = current.approve(comment)
        self.save_fact(current, updated, expected_revision)
        return updated

    def reject_fact(
        self,
        fact_id: str,
        *,
        expected_revision: str,
        comment: str,
    ) -> FactRecord:
        current = self.load_fact(fact_id)
        updated = current.reject(comment)
        self.save_fact(current, updated, expected_revision)
        return updated

    # Evidence ----------------------------------------------------------

    def inspect_pdf_bytes(self, payload: bytes) -> Evidence:
        """Validate and describe PDF bytes without mutating the repository."""

        if not payload.startswith(b"%PDF-"):
            raise EvidenceError("the selected file is not a PDF")
        if len(payload) > MAX_PDF_BYTES:
            raise EvidenceError(f"PDF must be at most {MAX_PDF_BYTES} bytes")
        digest = hashlib.sha256(payload).hexdigest()
        relative = Path("evidence") / "sha256" / digest[:2] / f"{digest}.pdf"
        return Evidence(
            path=relative.as_posix(),
            sha256=digest,
            byte_size=len(payload),
            media_type="application/pdf",
        ).validate()

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
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{evidence.sha256}.",
                suffix=".tmp",
                dir=destination.parent,
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
        evidence.validate()
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
            raise EvidenceError(
                f"evidence path is not a regular file: {evidence.path}"
            )
        if stat.st_size != evidence.byte_size:
            raise EvidenceError(
                f"evidence size does not match source: {evidence.path}"
            )
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != evidence.sha256:
            raise EvidenceError(
                f"evidence hash does not match source: {evidence.path}"
            )
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise EvidenceError(f"evidence is not a PDF: {evidence.path}")

    # Unified validation ------------------------------------------------

    def validate_all(self, *, require_canonical: bool = True) -> AuthoritySnapshot:
        self.ensure_layout()
        self._validate_schema_files()
        self._validate_authority_layout()

        sources = tuple(self.list_sources())
        entities = tuple(self.list_entities())
        facts = tuple(self.list_facts())

        if require_canonical:
            for source in sources:
                self._require_canonical(
                    self.source_path(source.id), source.canonical_json(), "source"
                )
            for entity in entities:
                self._require_canonical(
                    self.entity_path(entity.id), entity.canonical_json(), "entity"
                )
            for fact in facts:
                self._require_canonical(
                    self.fact_path(fact.id), fact.canonical_json(), "fact"
                )

        conflicts = self._validate_records(sources, entities, facts)

        referenced_evidence: set[str] = set()
        for source in sources:
            if source.evidence.present:
                self.verify_evidence(source.evidence)
                assert source.evidence.path is not None
                referenced_evidence.add(source.evidence.path)
        self._validate_evidence_layout(referenced_evidence)
        self._validate_committed_authority(sources, entities, facts)

        return AuthoritySnapshot(
            sources=sources,
            entities=entities,
            facts=facts,
            conflicts=conflicts,
        )

    def _validate_records(
        self,
        sources: Sequence[SourceRecord],
        entities: Sequence[EntityRecord],
        facts: Sequence[FactRecord],
    ) -> tuple[FactConflict, ...]:
        source_map = self._unique_map(sources, "source")
        entity_map = self._unique_map(entities, "entity")
        fact_map = self._unique_map(facts, "fact")

        for source in sources:
            source.validate()
        self._validate_supersedes(source_map, "source")
        for source in sources:
            if source.supersedes is not None:
                target = source_map[source.supersedes]
                if source.source_type is not target.source_type:
                    raise RecordValidationError(
                        f"source {source.id} supersedes a different source_type"
                    )

        identity_ids: dict[tuple[str, ...], str] = {}
        for entity in entities:
            entity.validate()
            previous_id = identity_ids.get(entity.identity_key)
            if previous_id is not None:
                raise RecordValidationError(
                    f"duplicate entity identity: {previous_id} and {entity.id}"
                )
            identity_ids[entity.identity_key] = entity.id
            if entity.kind is EntityKind.COMPONENT:
                manufacturer = entity_map.get(entity.manufacturer_id or "")
                if manufacturer is None:
                    raise RecordValidationError(
                        f"component {entity.id} references missing manufacturer "
                        f"{entity.manufacturer_id}"
                    )
                if manufacturer.kind is not EntityKind.MANUFACTURER:
                    raise RecordValidationError(
                        f"component {entity.id} manufacturer_id must reference "
                        "MANUFACTURER"
                    )

        for fact in facts:
            fact.validate()
        self._validate_supersedes(fact_map, "fact")
        for fact in facts:
            self._validate_fact_references(
                fact, source_map=source_map, entity_map=entity_map, fact_map=fact_map
            )

        conflicts = self._fact_conflicts(facts)
        approved_conflicts = self._fact_conflicts(facts, approved_only=True)
        if approved_conflicts:
            conflict = approved_conflicts[0]
            raise RecordValidationError(
                "multiple active APPROVED facts conflict for semantic key "
                f"{conflict.semantic_key!r}: {', '.join(conflict.fact_ids)}"
            )
        return conflicts

    @staticmethod
    def _unique_map(
        records: Sequence[SourceRecord | EntityRecord | FactRecord], label: str
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for record in records:
            if record.id in result:
                raise RecordValidationError(f"duplicate {label} id: {record.id}")
            result[record.id] = record
        return result

    @staticmethod
    def _validate_supersedes(
        records: Mapping[str, object], label: str
    ) -> None:
        for record_id, raw_record in records.items():
            supersedes = getattr(raw_record, "supersedes", None)
            if supersedes is not None and supersedes not in records:
                raise RecordValidationError(
                    f"{label} {record_id} supersedes missing {label} {supersedes}"
                )

        state: dict[str, int] = {}

        def visit(record_id: str) -> None:
            marker = state.get(record_id, 0)
            if marker == 1:
                raise RecordValidationError(f"{label} supersedes cycle detected")
            if marker == 2:
                return
            state[record_id] = 1
            supersedes = getattr(records[record_id], "supersedes", None)
            if supersedes is not None:
                visit(supersedes)
            state[record_id] = 2

        for record_id in records:
            visit(record_id)

    def _validate_fact_references(
        self,
        fact: FactRecord,
        *,
        source_map: Mapping[str, SourceRecord],
        entity_map: Mapping[str, EntityRecord],
        fact_map: Mapping[str, FactRecord],
    ) -> None:
        if isinstance(fact.payload, ComponentPinPayload):
            component = entity_map.get(fact.payload.component_id)
            package = entity_map.get(fact.payload.package_id)
            if component is None or component.kind is not EntityKind.COMPONENT:
                raise RecordValidationError(
                    f"fact {fact.id} component_id must reference COMPONENT"
                )
            if package is None or package.kind is not EntityKind.PACKAGE:
                raise RecordValidationError(
                    f"fact {fact.id} package_id must reference PACKAGE"
                )
        elif isinstance(fact.payload, ParameterLimitPayload):
            component = entity_map.get(fact.payload.component_id)
            if component is None or component.kind is not EntityKind.COMPONENT:
                raise RecordValidationError(
                    f"fact {fact.id} component_id must reference COMPONENT"
                )
        else:
            raise RecordValidationError(f"fact {fact.id} has unsupported payload")

        for anchor in fact.evidence_anchors:
            source = source_map.get(anchor.source_id)
            if source is None:
                raise RecordValidationError(
                    f"fact {fact.id} anchor references missing source "
                    f"{anchor.source_id}"
                )
            if fact.status is RecordStatus.APPROVED:
                if source.status is not RecordStatus.APPROVED:
                    raise RecordValidationError(
                        f"approved fact {fact.id} references non-approved source "
                        f"{source.id}"
                    )
                if not source.evidence.present:
                    raise RecordValidationError(
                        f"approved fact {fact.id} source has no evidence: {source.id}"
                    )

        if fact.supersedes is not None:
            target = fact_map[fact.supersedes]
            if target.fact_type is not fact.fact_type:
                raise RecordValidationError(
                    f"fact {fact.id} supersedes a different fact_type"
                )
            if target.semantic_key != fact.semantic_key:
                raise RecordValidationError(
                    f"fact {fact.id} supersedes a different semantic fact"
                )

    @staticmethod
    def _fact_conflicts(
        facts: Sequence[FactRecord], *, approved_only: bool = False
    ) -> tuple[FactConflict, ...]:
        candidates = [
            fact
            for fact in facts
            if not approved_only or fact.status is RecordStatus.APPROVED
        ]
        superseded = {
            fact.supersedes for fact in candidates if fact.supersedes is not None
        }
        active = [fact for fact in candidates if fact.id not in superseded]
        grouped: dict[tuple[object, ...], list[str]] = defaultdict(list)
        for fact in active:
            grouped[fact.semantic_key].append(fact.id)
        return tuple(
            FactConflict(key, tuple(sorted(ids)))
            for key, ids in sorted(grouped.items(), key=lambda item: repr(item[0]))
            if len(ids) > 1
        )

    # Published Git snapshots ------------------------------------------

    def read_published_snapshot(self, *, ref: str = "HEAD") -> AuthoritySnapshot:
        """Return only publishable authority from one fully validated Git snapshot."""

        complete = self._validated_ref_snapshot(ref)
        approved_sources = complete.published_sources
        approved_facts = complete.published_facts
        return AuthoritySnapshot(
            sources=approved_sources,
            entities=complete.entities,
            facts=approved_facts,
            conflicts=self._fact_conflicts(approved_facts),
            ref=ref,
            commit=complete.commit,
        )

    def list_published(self, *, ref: str = "HEAD") -> list[SourceRecord]:
        return self._sorted_sources(self.read_published_snapshot(ref=ref).sources)

    def list_published_facts(self, *, ref: str = "HEAD") -> list[FactRecord]:
        return self._sorted_facts(self.read_published_snapshot(ref=ref).facts)

    def fact_conflicts(self, *, approved_only: bool = False) -> tuple[FactConflict, ...]:
        """Expose unresolved semantic conflicts without choosing a winner."""

        return self._fact_conflicts(self.list_facts(), approved_only=approved_only)

    def _validated_ref_snapshot(self, ref: str) -> AuthoritySnapshot:
        commit = self._resolve_git_ref(ref)
        if commit is None:
            return AuthoritySnapshot((), (), (), ref=ref, commit=None)

        entries = self._parse_tree_entries(
            self._git_bytes(
                "ls-tree",
                "-r",
                "-z",
                commit,
                "--",
                "knowledge/sources",
                "knowledge/entities",
                "knowledge/facts",
                "knowledge/records",
                "evidence/sha256",
                *(path.as_posix() for path in SCHEMA_PATHS),
            )
        )

        source_paths: list[str] = []
        entity_paths: list[str] = []
        fact_paths: list[str] = []
        evidence_paths: list[str] = []
        schema_paths: list[str] = []
        typed_content_present = False

        for mode, object_type, relative in entries:
            if mode != "100644" or object_type != "blob":
                raise RepositoryError(
                    "published snapshot path is not a regular non-executable file: "
                    f"{relative}"
                )
            if relative in {
                "knowledge/sources/.gitkeep",
                "knowledge/entities/.gitkeep",
                "knowledge/facts/.gitkeep",
                "knowledge/records/.gitkeep",
                "evidence/sha256/.gitkeep",
            }:
                continue
            if relative.startswith("knowledge/records/"):
                raise RecordValidationError(
                    "published snapshot contains retired knowledge/records authority: "
                    f"{relative}"
                )
            if relative.startswith("knowledge/sources/"):
                self._validate_ref_authority_path(
                    relative, "knowledge/sources", _SOURCE_FILENAME
                )
                source_paths.append(relative)
                typed_content_present = True
                continue
            if relative.startswith("knowledge/entities/"):
                self._validate_ref_authority_path(
                    relative, "knowledge/entities", _ENTITY_FILENAME
                )
                entity_paths.append(relative)
                typed_content_present = True
                continue
            if relative.startswith("knowledge/facts/"):
                self._validate_ref_authority_path(
                    relative, "knowledge/facts", _FACT_FILENAME
                )
                fact_paths.append(relative)
                typed_content_present = True
                continue
            if relative.startswith("evidence/sha256/"):
                match = _EVIDENCE_PATH.fullmatch(relative)
                if match is None or match["prefix"] != match["digest"][:2]:
                    raise EvidenceError(
                        f"unexpected published evidence path: {relative}"
                    )
                evidence_paths.append(relative)
                typed_content_present = True
                continue
            if Path(relative) in SCHEMA_PATHS:
                schema_paths.append(relative)
                typed_content_present = True
                continue
            raise RepositoryError(f"unexpected published snapshot path: {relative}")

        # This permits a checkout whose HEAD predates P0.1 and contains no typed
        # authority.  The moment any typed schema/data appears, all three schemas
        # and the full closure are mandatory in that same commit.
        if not typed_content_present:
            return AuthoritySnapshot((), (), (), ref=ref, commit=commit)

        expected_schema_paths = {path.as_posix() for path in SCHEMA_PATHS}
        if set(schema_paths) != expected_schema_paths:
            missing = sorted(expected_schema_paths - set(schema_paths))
            raise RecordValidationError(
                "published snapshot is missing typed schema: " + missing[0]
            )
        documents: dict[str, Mapping[str, object]] = {}
        for relative in sorted(schema_paths):
            payload = self._read_ref_blob(
                commit, relative, maximum_bytes=MAX_SCHEMA_BYTES
            )
            documents[relative] = self._decode_schema(payload, relative)
        self._validate_schema_documents(documents)

        sources = tuple(
            self._read_ref_record(commit, relative, SourceRecord.from_json, "source")
            for relative in sorted(source_paths)
        )
        entities = tuple(
            self._read_ref_record(commit, relative, EntityRecord.from_json, "entity")
            for relative in sorted(entity_paths)
        )
        facts = tuple(
            self._read_ref_record(commit, relative, FactRecord.from_json, "fact")
            for relative in sorted(fact_paths)
        )

        conflicts = self._validate_records(sources, entities, facts)
        evidence_metadata: dict[str, tuple[int, str]] = {}
        for relative in sorted(evidence_paths):
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
        for source in sources:
            if not source.evidence.present:
                continue
            assert source.evidence.path is not None
            assert source.evidence.byte_size is not None
            assert source.evidence.sha256 is not None
            metadata = evidence_metadata.get(source.evidence.path)
            if metadata is None:
                raise EvidenceError(
                    f"published evidence is missing from {ref}: "
                    f"{source.evidence.path}"
                )
            byte_size, digest = metadata
            if (
                byte_size != source.evidence.byte_size
                or digest != source.evidence.sha256
            ):
                raise EvidenceError(
                    f"published evidence does not match source: "
                    f"{source.evidence.path}"
                )
            referenced.add(source.evidence.path)
        orphaned = sorted(set(evidence_metadata) - referenced)
        if orphaned:
            raise EvidenceError(
                f"unreferenced published evidence file: {orphaned[0]}"
            )

        return AuthoritySnapshot(
            sources=self._sorted_sources(sources),
            entities=self._sorted_entities(entities),
            facts=self._sorted_facts(facts),
            conflicts=conflicts,
            ref=ref,
            commit=commit,
        )

    @staticmethod
    def _validate_ref_authority_path(
        relative: str, root: str, filename_pattern: re.Pattern[str]
    ) -> None:
        path = Path(relative)
        if path.parent.as_posix() != root or filename_pattern.fullmatch(path.name) is None:
            raise RecordValidationError(
                f"unexpected published authority path: {relative}"
            )

    def _read_ref_record(self, commit, relative, parser, label):
        payload = self._read_ref_blob(
            commit, relative, maximum_bytes=MAX_RECORD_BYTES
        )
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RecordValidationError(
                f"published {label} is not UTF-8: {relative}"
            ) from error
        record = parser(text)
        if record.id != Path(relative).stem:
            raise RecordValidationError(
                f"published {label} id does not match filename: {relative}"
            )
        if payload != record.canonical_json().encode("utf-8"):
            raise RecordValidationError(
                f"published {label} is not canonical JSON: {relative}"
            )
        return record

    def _validate_committed_authority(
        self,
        sources: Sequence[SourceRecord],
        entities: Sequence[EntityRecord],
        facts: Sequence[FactRecord],
    ) -> None:
        committed = self._validated_ref_snapshot("HEAD")
        current_sources = {source.id: source for source in sources}
        current_entities = {entity.id: entity for entity in entities}
        current_facts = {fact.id: fact for fact in facts}

        for source in committed.sources:
            current = current_sources.get(source.id)
            relative = f"knowledge/sources/{source.id}.json"
            if source.status is RecordStatus.APPROVED:
                if current is None:
                    raise RecordValidationError(
                        f"committed approved source cannot be deleted: {relative}"
                    )
                if current != source:
                    raise RecordValidationError(
                        f"committed approved source is immutable: {relative}"
                    )
            elif current is not None:
                self._require_review_prefix(
                    source.review_history, current.review_history, relative
                )

        for fact in committed.facts:
            current = current_facts.get(fact.id)
            relative = f"knowledge/facts/{fact.id}.json"
            if fact.status is RecordStatus.APPROVED:
                if current is None:
                    raise RecordValidationError(
                        f"committed approved fact cannot be deleted: {relative}"
                    )
                if current != fact:
                    raise RecordValidationError(
                        f"committed approved fact is immutable: {relative}"
                    )
            elif current is not None:
                self._require_review_prefix(
                    fact.review_history, current.review_history, relative
                )

        committed_referenced_entities = {
            entity_id
            for fact in committed.facts
            for entity_id in fact.subject_entity_ids
        }
        for entity_id in committed_referenced_entities:
            committed_entity = next(
                entity for entity in committed.entities if entity.id == entity_id
            )
            current = current_entities.get(entity_id)
            relative = f"knowledge/entities/{entity_id}.json"
            if current is None:
                raise RecordValidationError(
                    f"entity referenced by a committed fact cannot be deleted: {relative}"
                )
            if current != committed_entity:
                raise RecordValidationError(
                    f"entity referenced by a committed fact is immutable: {relative}"
                )

    # Schema synchronization -------------------------------------------

    def _validate_schema_files(self) -> None:
        documents: dict[str, Mapping[str, object]] = {}
        for relative in SCHEMA_PATHS:
            path = self.root / relative
            text = self._read_text(
                path, label="schema", maximum_bytes=MAX_SCHEMA_BYTES
            )
            documents[relative.as_posix()] = self._decode_schema(
                text.encode("utf-8"), relative.as_posix()
            )
        self._validate_schema_documents(documents)

    @staticmethod
    def _decode_schema(payload: bytes, label: str) -> Mapping[str, object]:
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RecordValidationError(f"schema is invalid: {label}") from error
        if not isinstance(value, dict):
            raise RecordValidationError(f"schema must be an object: {label}")
        return value

    @staticmethod
    def _validate_schema_documents(
        documents: Mapping[str, Mapping[str, object]]
    ) -> None:
        specs = {
            "schemas/source-record.schema.json": (
                "https://pcbknowledge.local/schemas/source-record.schema.json",
                SOURCE_SCHEMA_VERSION,
                set(SourceRecord.new(
                    "pk_0123456789abcdef01234567",
                    prepared_by=PreparedBy.HUMAN,
                ).to_dict()),
            ),
            "schemas/entity-record.schema.json": (
                "https://pcbknowledge.local/schemas/entity-record.schema.json",
                ENTITY_SCHEMA_VERSION,
                set(EntityRecord.manufacturer(
                    "ent_0123456789abcdef01234567",
                    "Example",
                    prepared_by=PreparedBy.HUMAN,
                ).to_dict()),
            ),
            "schemas/fact-record.schema.json": (
                "https://pcbknowledge.local/schemas/fact-record.schema.json",
                FACT_SCHEMA_VERSION,
                {
                    "schema_version",
                    "id",
                    "fact_type",
                    "status",
                    "prepared_by",
                    "payload",
                    "conditions",
                    "applicability",
                    "evidence_anchors",
                    "review_history",
                    "review",
                    "supersedes",
                },
            ),
        }
        if set(documents) != set(specs):
            raise RecordValidationError("typed schema set is incomplete")
        for relative, (schema_id, version, required) in specs.items():
            document = documents[relative]
            if document.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                raise RecordValidationError(f"schema draft is invalid: {relative}")
            if document.get("$id") != schema_id:
                raise RecordValidationError(f"schema id is invalid: {relative}")
            if document.get("type") != "object" or document.get("additionalProperties") is not False:
                raise RecordValidationError(
                    f"schema root must fail closed: {relative}"
                )
            raw_required = document.get("required")
            properties = document.get("properties")
            if not isinstance(raw_required, list) or set(raw_required) != required:
                raise RecordValidationError(
                    f"schema required keys do not match model: {relative}"
                )
            if not isinstance(properties, dict) or set(properties) != required:
                raise RecordValidationError(
                    f"schema properties do not match model: {relative}"
                )
            schema_version = properties.get("schema_version")
            if not isinstance(schema_version, dict) or schema_version.get("const") != version:
                raise RecordValidationError(
                    f"schema version does not match model: {relative}"
                )

        source_document = documents["schemas/source-record.schema.json"]
        source_properties = source_document.get("properties")
        if not isinstance(source_properties, dict):
            raise RecordValidationError("source schema properties are invalid")
        source_types = source_properties["source_type"]
        statuses = source_properties["status"]
        if not isinstance(source_types, dict) or not isinstance(statuses, dict):
            raise RecordValidationError("source schema enums are invalid")
        if set(source_types.get("enum", [])) != {item.value for item in SourceType}:
            raise RecordValidationError("source schema source_type enum is out of sync")
        if set(statuses.get("enum", [])) != {item.value for item in RecordStatus}:
            raise RecordValidationError("source schema status enum is out of sync")
        source_defs = source_document.get("$defs")
        if not isinstance(source_defs, dict):
            raise RecordValidationError("source schema definitions are invalid")
        license_schema = source_defs.get("license")
        if not isinstance(license_schema, dict):
            raise RecordValidationError("source schema license definition is invalid")
        license_properties = license_schema.get("properties")
        if not isinstance(license_properties, dict):
            raise RecordValidationError("source schema license properties are invalid")
        license_class = license_properties.get("class")
        if not isinstance(license_class, dict):
            raise RecordValidationError("source schema license enum is invalid")
        if set(license_class.get("enum", [])) != {item.value for item in LicenseClass}:
            raise RecordValidationError("source schema license enum is out of sync")

        entity_document = documents["schemas/entity-record.schema.json"]
        entity_properties = entity_document.get("properties")
        if not isinstance(entity_properties, dict):
            raise RecordValidationError("entity schema properties are invalid")
        entity_kind = entity_properties.get("kind")
        if not isinstance(entity_kind, dict) or set(entity_kind.get("enum", [])) != {
            item.value for item in EntityKind
        }:
            raise RecordValidationError("entity schema kind enum is out of sync")

        fact_document = documents["schemas/fact-record.schema.json"]
        fact_properties = fact_document.get("properties")
        if not isinstance(fact_properties, dict):
            raise RecordValidationError("fact schema properties are invalid")
        fact_type = fact_properties.get("fact_type")
        if not isinstance(fact_type, dict) or set(fact_type.get("enum", [])) != {
            item.value for item in FactType
        }:
            raise RecordValidationError("fact schema fact_type enum is out of sync")
        fact_defs = fact_document.get("$defs")
        if not isinstance(fact_defs, dict):
            raise RecordValidationError("fact schema definitions are invalid")
        parameter_payload = fact_defs.get("parameterLimitPayload")
        if not isinstance(parameter_payload, dict):
            raise RecordValidationError(
                "fact schema parameter payload definition is invalid"
            )
        parameter_properties = parameter_payload.get("properties")
        if not isinstance(parameter_properties, dict):
            raise RecordValidationError(
                "fact schema parameter payload properties are invalid"
            )
        limit_kind = parameter_properties.get("limit_kind")
        if not isinstance(limit_kind, dict) or set(limit_kind.get("enum", [])) != {
            item.value for item in ParameterLimitKind
        }:
            raise RecordValidationError(
                "fact schema limit_kind enum is out of sync"
            )

        for relative, document in documents.items():
            properties = document.get("properties")
            if not isinstance(properties, dict):
                raise RecordValidationError(f"schema properties are invalid: {relative}")
            prepared_by = properties.get("prepared_by")
            if not isinstance(prepared_by, dict) or set(
                prepared_by.get("enum", [])
            ) != {item.value for item in PreparedBy}:
                raise RecordValidationError(
                    f"schema prepared_by enum is out of sync: {relative}"
                )

    # Layout and write validation --------------------------------------

    def _validate_authority_layout(self) -> None:
        self._validate_flat_layout(
            self.sources_dir, _SOURCE_FILENAME, "source"
        )
        self._validate_flat_layout(
            self.entities_dir, _ENTITY_FILENAME, "entity"
        )
        self._validate_flat_layout(self.facts_dir, _FACT_FILENAME, "fact")
        self._reject_legacy_authority()

    @staticmethod
    def _validate_flat_layout(
        directory: Path, filename_pattern: re.Pattern[str], label: str
    ) -> None:
        for path in sorted(directory.iterdir()):
            if path.is_symlink():
                raise RecordValidationError(
                    f"{label} layout contains a symlink: {path}"
                )
            if path.name == ".gitkeep" and path.is_file():
                continue
            if not path.is_file() or filename_pattern.fullmatch(path.name) is None:
                raise RecordValidationError(
                    f"unexpected {label} layout entry: {path}"
                )

    def _validate_evidence_layout(self, referenced: set[str]) -> None:
        discovered: set[str] = set()
        for path in sorted(self.evidence_dir.rglob("*")):
            relative = path.relative_to(self.root).as_posix()
            if path.is_symlink():
                raise EvidenceError(
                    f"evidence layout contains a symlink: {relative}"
                )
            if path.is_dir():
                if (
                    path.parent != self.evidence_dir
                    or re.fullmatch(r"[0-9a-f]{2}", path.name) is None
                ):
                    raise EvidenceError(
                        f"unexpected evidence directory: {relative}"
                    )
                continue
            if path.name == ".gitkeep" and path.parent == self.evidence_dir:
                continue
            match = _EVIDENCE_PATH.fullmatch(relative)
            if (
                not path.is_file()
                or match is None
                or match["prefix"] != match["digest"][:2]
            ):
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

    def _validate_source_for_write(self, source: SourceRecord) -> None:
        if source.status is RecordStatus.APPROVED:
            self._validate_schema_files()
        if source.evidence.present:
            self.verify_evidence(source.evidence)
        if source.supersedes is not None:
            target = self.load_source(source.supersedes)
            if target.source_type is not source.source_type:
                raise RecordValidationError(
                    "source supersedes must reference the same source_type"
                )

    def _validate_entity_for_write(
        self, entity: EntityRecord, existing: Sequence[EntityRecord]
    ) -> None:
        if any(current.identity_key == entity.identity_key for current in existing):
            raise RecordConflictError("entity identity already exists")
        if entity.kind is EntityKind.COMPONENT:
            try:
                manufacturer = self.load_entity(entity.manufacturer_id or "")
            except RecordNotFoundError as error:
                raise RecordValidationError(
                    "component manufacturer_id references a missing entity"
                ) from error
            if manufacturer.kind is not EntityKind.MANUFACTURER:
                raise RecordValidationError(
                    "component manufacturer_id must reference MANUFACTURER"
                )

    def _validate_fact_for_write(
        self, fact: FactRecord, *, replacing: str | None = None
    ) -> None:
        if fact.status is RecordStatus.APPROVED:
            self._validate_schema_files()
        sources = {source.id: source for source in self.list_sources()}
        entities = {entity.id: entity for entity in self.list_entities()}
        existing_facts = [
            current for current in self.list_facts() if current.id != replacing
        ]
        fact_map = {current.id: current for current in existing_facts}
        fact_map[fact.id] = fact
        self._validate_supersedes(fact_map, "fact")
        self._validate_fact_references(
            fact,
            source_map=sources,
            entity_map=entities,
            fact_map=fact_map,
        )
        prospective = (*existing_facts, fact)
        conflicts = self._fact_conflicts(prospective, approved_only=True)
        if conflicts:
            raise RecordValidationError(
                "cannot write a second active APPROVED fact for semantic key "
                f"{conflicts[0].semantic_key!r}"
            )

    @staticmethod
    def _validate_optimistic(
        previous: object,
        current: object,
        updated_id: str,
        expected_revision: str,
    ) -> None:
        if (
            getattr(current, "revision_token") != expected_revision
            or current != previous
        ):
            raise RecordConflictError("record changed since it was loaded")
        if updated_id != getattr(previous, "id"):
            raise RecordConflictError("record id cannot change")

    @staticmethod
    def _validate_append_only_review(
        previous: tuple[ReviewEvent, ...], updated: tuple[ReviewEvent, ...]
    ) -> None:
        if len(updated) < len(previous) or updated[: len(previous)] != previous:
            raise RecordTransitionError("review_history is append-only")

    @staticmethod
    def _require_review_prefix(
        committed: tuple[ReviewEvent, ...],
        current: tuple[ReviewEvent, ...],
        relative: str,
    ) -> None:
        if len(current) < len(committed) or current[: len(committed)] != committed:
            raise RecordValidationError(
                f"committed review_history is append-only: {relative}"
            )

    @staticmethod
    def _require_canonical(path: Path, canonical: str, label: str) -> None:
        if path.read_text(encoding="utf-8") != canonical:
            raise RecordValidationError(f"{label} is not canonical JSON: {path}")

    # Evidence cleanup --------------------------------------------------

    def _prune_replaced_evidence(
        self, previous: Evidence, updated: Evidence
    ) -> None:
        if not previous.present or previous.path == updated.path:
            return
        assert previous.path is not None

        # All current Source refs own evidence. Facts only anchor a Source and
        # therefore never participate in PDF cleanup.
        for source in self.list_sources():
            if source.evidence.path == previous.path:
                return

        # Preserve bytes still used by a committed Source, even if another
        # inconsistency means the published snapshot will subsequently fail.
        for source in self.list_published():
            if source.evidence.path == previous.path:
                return

        candidate = self.root / previous.path
        if candidate.exists():
            if candidate.is_symlink() or not candidate.is_file():
                raise EvidenceError(
                    f"replaced evidence path is unsafe: {previous.path}"
                )
            candidate.unlink()
            try:
                candidate.parent.rmdir()
            except OSError:
                pass

    # Git change inspection --------------------------------------------

    def git_changes(self) -> GitChanges:
        status = self._git(
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "knowledge",
            "evidence",
        )
        tracked = self._git(
            "diff", "--no-ext-diff", "--", "knowledge", "evidence"
        )
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
                previews.extend(
                    f"+{item}\n"
                    for item in candidate.read_text("utf-8").splitlines()
                )
            elif candidate.suffix == ".pdf" and candidate.is_file():
                previews.append(
                    f"new binary evidence: {relative} "
                    f"({candidate.stat().st_size} bytes)\n"
                )
        return GitChanges(
            status_lines=status_lines,
            tracked_diff=tracked,
            untracked_preview="".join(previews),
        )

    def git_change_scope(self) -> ChangeScope:
        """Classify the next commit: staged paths first, otherwise workspace."""

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

    def git_candidate_paths(self) -> tuple[str, ...]:
        """Return the paths considered by change-scope using the same index rule."""

        return self._candidate_change_paths()

    def validate_change_scope(self) -> ChangeScope:
        scope = self.git_change_scope()
        if scope is ChangeScope.MIXED:
            raise RepositoryError(
                "mixed knowledge/evidence and software changes are not allowed "
                "in one commit"
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

    # Git plumbing ------------------------------------------------------

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
            raise RepositoryError(
                f"Git returned an invalid blob size: {relative}"
            ) from error
        if byte_size < 0 or byte_size > maximum_bytes:
            raise RepositoryError(
                f"published blob exceeds {maximum_bytes} bytes: {relative}"
            )
        payload = self._git_bytes("cat-file", "blob", specification)
        if len(payload) != byte_size:
            raise RepositoryError(
                f"published blob size changed while reading: {relative}"
            )
        return payload

    # Atomic writes and process lock -----------------------------------

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
                    raise RepositoryError(
                        "cannot open repository write lock"
                    ) from error
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
            with os.fdopen(
                descriptor, "w", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    # Deterministic presentation ---------------------------------------

    @staticmethod
    def _sorted_sources(records: Iterable[SourceRecord]) -> list[SourceRecord]:
        return sorted(records, key=lambda item: ((item.title or "").casefold(), item.id))

    @staticmethod
    def _sorted_entities(records: Iterable[EntityRecord]) -> list[EntityRecord]:
        return sorted(
            records,
            key=lambda item: (
                item.kind.value,
                item.normalized_key or item.normalized_mpn or "",
                item.id,
            ),
        )

    @staticmethod
    def _sorted_facts(records: Iterable[FactRecord]) -> list[FactRecord]:
        return sorted(
            records,
            key=lambda item: (item.fact_type.value, repr(item.semantic_key), item.id),
        )


def summarize_records(records: Iterable[SourceRecord]) -> dict[str, int]:
    """Summarize Source statuses for the current source-only GUI."""

    summary = {status.value: 0 for status in RecordStatus}
    for record in records:
        summary[record.status.value] += 1
    return summary
