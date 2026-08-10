from __future__ import annotations
from .store_common import *
from .store_common import _SOURCE_FILENAME, _ENTITY_FILENAME, _FACT_FILENAME, _EVIDENCE_PATH, _DATA_ROOTS
class StoreCrudMixin:
    """Single authority facade used by GUI, Agent CLI, validation and packaging."""
    def __init__(self, root: Path) -> None:
        resolved = root.resolve()
        if not (resolved / ".git").exists(): raise RepositoryError(f"not a Git repository: {resolved}")
        self.root = resolved
        self.sources_dir = resolved / "knowledge" / "sources"
        self.entities_dir = resolved / "knowledge" / "entities"
        self.facts_dir = resolved / "knowledge" / "facts"
        self.legacy_records_dir = resolved / "knowledge" / "records"
        self.evidence_dir = resolved / "evidence" / "sha256"
        self.state_dir = resolved / ".pcbknowledge"
        self.records_dir = self.sources_dir
        self._thread_write_lock = threading.RLock(); self._write_lock_depth = 0; self._write_lock_stream: BinaryIO | None = None

    def ensure_layout(self) -> None:
        for directory in (self.sources_dir, self.entities_dir, self.facts_dir, self.evidence_dir):
            directory.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir(): raise RepositoryError(f"repository layout directory is unsafe: {directory}")
        self._reject_legacy_authority()

    def _reject_legacy_authority(self) -> None:
        if not self.legacy_records_dir.exists(): return
        entries = [item for item in self.legacy_records_dir.iterdir() if item.name != ".gitkeep"]
        if entries: raise RecordValidationError("legacy knowledge/records authority is retired; migrate to knowledge/sources")

    def source_path(self, source_id: str) -> Path:
        SourceRecord.new(source_id, prepared_by=PreparedBy.HUMAN); return self.sources_dir / f"{source_id}.json"
    def record_path(self, record_id: str) -> Path: return self.source_path(record_id)
    def entity_path(self, entity_id: str) -> Path:
        if not _ENTITY_FILENAME.fullmatch(f"{entity_id}.json"): raise RecordValidationError("invalid entity id")
        return self.entities_dir / f"{entity_id}.json"
    def fact_path(self, fact_id: str) -> Path:
        if not _FACT_FILENAME.fullmatch(f"{fact_id}.json"): raise RecordValidationError("invalid fact id")
        return self.facts_dir / f"{fact_id}.json"

    @staticmethod
    def _read_text(path: Path, *, label: str) -> str:
        try: stat = path.lstat()
        except FileNotFoundError as error: raise RecordNotFoundError(f"{label} not found") from error
        if path.is_symlink() or not path.is_file(): raise RecordValidationError(f"{label} path is not a regular file: {path}")
        if stat.st_size > MAX_RECORD_BYTES: raise RecordValidationError(f"{label} exceeds {MAX_RECORD_BYTES} bytes: {path}")
        try: return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error: raise RecordValidationError(f"{label} is not UTF-8: {path}") from error

    def load_source(self, source_id: str) -> SourceRecord:
        self.ensure_layout(); source = SourceRecord.from_json(self._read_text(self.source_path(source_id), label="source"))
        if source.id != source_id: raise RecordValidationError("source id does not match filename")
        return source
    def load(self, record_id: str) -> SourceRecord: return self.load_source(record_id)
    def load_entity(self, entity_id: str) -> EntityRecord:
        self.ensure_layout(); entity = EntityRecord.from_json(self._read_text(self.entity_path(entity_id), label="entity"))
        if entity.id != entity_id: raise RecordValidationError("entity id does not match filename")
        return entity
    def load_fact(self, fact_id: str) -> FactRecord:
        self.ensure_layout(); fact = FactRecord.from_json(self._read_text(self.fact_path(fact_id), label="fact"))
        if fact.id != fact_id: raise RecordValidationError("fact id does not match filename")
        return fact

    def list_sources(self, *, status: RecordStatus | None = None) -> list[SourceRecord]:
        if not self.sources_dir.exists(): return []
        result = [self.load_source(path.stem) for path in sorted(self.sources_dir.glob("pk_*.json"))]
        if status is not None: result = [item for item in result if item.status is status]
        return sorted(result, key=lambda item: ((item.title or "").casefold(), item.id))
    def list(self, *, status: RecordStatus | None = None) -> list[SourceRecord]: return self.list_sources(status=status)
    def list_entities(self, *, kind: EntityKind | None = None) -> list[EntityRecord]:
        if not self.entities_dir.exists(): return []
        result = [self.load_entity(path.stem) for path in sorted(self.entities_dir.glob("ent_*.json"))]
        if kind is not None: result = [item for item in result if item.kind is kind]
        return sorted(result, key=lambda item: (item.kind.value, item.normalized_key or item.normalized_mpn or "", item.id))
    def list_facts(self, *, status: RecordStatus | None = None) -> list[FactRecord]:
        if not self.facts_dir.exists(): return []
        result = [self.load_fact(path.stem) for path in sorted(self.facts_dir.glob("fact_*.json"))]
        if status is not None: result = [item for item in result if item.status is status]
        return sorted(result, key=lambda item: (item.fact_type.value, repr(item.semantic_key), item.id))

    def create_source(self, *, prepared_by: PreparedBy, idempotency_key: str | None = None, source_type: SourceType = SourceType.DATASHEET) -> SourceRecord:
        with self._write_lock():
            self.ensure_layout(); source_id = deterministic_record_id(idempotency_key) if idempotency_key is not None else f"pk_{secrets.token_hex(12)}"
            source = SourceRecord.new(source_id, prepared_by=prepared_by, source_type=source_type); path = self.source_path(source.id)
            if path.exists():
                existing = self.load_source(source.id)
                if existing.prepared_by is not prepared_by: raise RecordConflictError("idempotency key belongs to a different origin")
                return existing
            self._write_new(path, source.canonical_json()); return source
    def create(self, *, prepared_by: PreparedBy, idempotency_key: str | None = None) -> SourceRecord: return self.create_source(prepared_by=prepared_by, idempotency_key=idempotency_key)
    def insert_source(self, source: SourceRecord) -> None:
        with self._write_lock(): self.ensure_layout(); source.validate(); self._validate_source_refs_for_write(source); self._write_new(self.source_path(source.id), source.canonical_json())
    def insert(self, record: SourceRecord) -> None: self.insert_source(record)
    def save_source(self, previous: SourceRecord, updated: SourceRecord, expected_revision: str) -> None:
        with self._write_lock():
            current = self.load_source(previous.id); self._validate_optimistic(previous, current, updated.id, expected_revision); self._validate_append_only_review(previous.review_history, updated.review_history)
            if previous.status is RecordStatus.APPROVED and updated != previous: raise RecordTransitionError("approved sources are immutable; create a superseding source")
            updated.validate(); self._validate_source_refs_for_write(updated); self._atomic_replace(self.source_path(updated.id), updated.canonical_json()); self._prune_replaced_evidence(previous.evidence, updated.evidence)
    def save(self, previous: SourceRecord, updated: SourceRecord, expected_revision: str) -> None: self.save_source(previous, updated, expected_revision)

    def insert_entity(self, entity: EntityRecord) -> None:
        with self._write_lock():
            self.ensure_layout(); entity.validate()
            if entity.kind is EntityKind.COMPONENT:
                manufacturer = self.load_entity(entity.manufacturer_id or "")
                if manufacturer.kind is not EntityKind.MANUFACTURER: raise RecordValidationError("component manufacturer_id must reference MANUFACTURER")
            self._write_new(self.entity_path(entity.id), entity.canonical_json())
    def create_manufacturer(self, raw_name: str, *, prepared_by: PreparedBy, idempotency_key: str) -> EntityRecord:
        return self._insert_or_replay_entity(EntityRecord.manufacturer(deterministic_entity_id(EntityKind.MANUFACTURER, idempotency_key), raw_name, prepared_by=prepared_by))
    def create_component(self, manufacturer_id: str, raw_mpn: str, *, family: str | None, prepared_by: PreparedBy, idempotency_key: str) -> EntityRecord:
        return self._insert_or_replay_entity(EntityRecord.component(deterministic_entity_id(EntityKind.COMPONENT, idempotency_key), manufacturer_id, raw_mpn, family=family, prepared_by=prepared_by))
    def create_package(self, raw_name: str, *, prepared_by: PreparedBy, idempotency_key: str) -> EntityRecord:
        return self._insert_or_replay_entity(EntityRecord.package(deterministic_entity_id(EntityKind.PACKAGE, idempotency_key), raw_name, prepared_by=prepared_by))
    def _insert_or_replay_entity(self, entity: EntityRecord) -> EntityRecord:
        with self._write_lock():
            self.ensure_layout(); path = self.entity_path(entity.id)
            if path.exists():
                current = self.load_entity(entity.id)
                if current != entity: raise RecordConflictError("entity idempotency key exists with different content")
                return current
            self.insert_entity(entity); return entity

    def create_fact(self, *, idempotency_key: str, fact_type: FactType, payload: ComponentPinPayload | ParameterLimitPayload, prepared_by: PreparedBy, conditions: tuple[str, ...] = (), applicability: tuple[str, ...] = (), evidence_anchors=()) -> FactRecord:
        fact = FactRecord.new(deterministic_fact_id(idempotency_key), fact_type=fact_type, payload=payload, prepared_by=prepared_by, conditions=conditions, applicability=applicability, evidence_anchors=tuple(evidence_anchors))
        with self._write_lock():
            self.ensure_layout(); path = self.fact_path(fact.id)
            if path.exists():
                current = self.load_fact(fact.id)
                if current != fact: raise RecordConflictError("fact idempotency key exists with different content")
                return current
            self._validate_fact_refs(fact, self._maps()); self._write_new(path, fact.canonical_json()); return fact
    def insert_fact(self, fact: FactRecord) -> None:
        with self._write_lock(): self.ensure_layout(); fact.validate(); self._validate_fact_refs(fact, self._maps()); self._write_new(self.fact_path(fact.id), fact.canonical_json())
    def save_fact(self, previous: FactRecord, updated: FactRecord, expected_revision: str) -> None:
        with self._write_lock():
            current = self.load_fact(previous.id); self._validate_optimistic(previous, current, updated.id, expected_revision); self._validate_append_only_review(previous.review_history, updated.review_history)
            if previous.status is RecordStatus.APPROVED and updated != previous: raise RecordTransitionError("approved facts are immutable; create a superseding fact")
            updated.validate(); self._validate_fact_refs(updated, self._maps()); self._atomic_replace(self.fact_path(updated.id), updated.canonical_json())

    def inspect_pdf_bytes(self, payload: bytes) -> Evidence:
        if not payload.startswith(b"%PDF-"): raise EvidenceError("the selected file is not a PDF")
        if not payload or len(payload) > MAX_PDF_BYTES: raise EvidenceError(f"PDF must be between 1 and {MAX_PDF_BYTES} bytes")
        digest = hashlib.sha256(payload).hexdigest(); relative = Path("evidence") / "sha256" / digest[:2] / f"{digest}.pdf"
        return Evidence(relative.as_posix(), digest, len(payload), "application/pdf")
    def import_pdf_bytes(self, payload: bytes) -> Evidence:
        evidence = self.inspect_pdf_bytes(payload)
        with self._write_lock():
            self.ensure_layout(); assert evidence.path is not None; destination = self.root / evidence.path; destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.parent.is_symlink() or not destination.parent.is_dir(): raise EvidenceError("evidence digest directory is unsafe")
            if destination.exists(): self.verify_evidence(evidence); return evidence
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{evidence.sha256}.", suffix=".tmp", dir=destination.parent); temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream: stream.write(payload); stream.flush(); os.fsync(stream.fileno())
                try: os.link(temporary, destination)
                except FileExistsError: pass
            finally: temporary.unlink(missing_ok=True)
            self.verify_evidence(evidence); return evidence
    def import_pdf_path(self, source: Path) -> Evidence:
        resolved = source.expanduser().resolve()
        if not resolved.is_file(): raise EvidenceError("PDF source is not a regular file")
        if resolved.stat().st_size > MAX_PDF_BYTES: raise EvidenceError(f"PDF exceeds {MAX_PDF_BYTES} bytes")
        return self.import_pdf_bytes(resolved.read_bytes())
    def inspect_pdf_path(self, source: Path) -> Evidence:
        resolved = source.expanduser().resolve()
        if not resolved.is_file(): raise EvidenceError("PDF source is not a regular file")
        return self.inspect_pdf_bytes(resolved.read_bytes())
    def verify_evidence(self, evidence: Evidence) -> None:
        if not evidence.present: return
        assert evidence.path and evidence.sha256 and evidence.byte_size; path = self.root / evidence.path
        try: stat = path.lstat()
        except FileNotFoundError as error: raise EvidenceError(f"evidence file is missing: {evidence.path}") from error
        if path.is_symlink() or not path.is_file(): raise EvidenceError(f"evidence path is not a regular file: {evidence.path}")
        if stat.st_size != evidence.byte_size: raise EvidenceError(f"evidence size does not match source: {evidence.path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence.sha256: raise EvidenceError(f"evidence hash does not match source: {evidence.path}")
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-": raise EvidenceError(f"evidence is not a PDF: {evidence.path}")
