"""Typed application/view-model layer for the local review workbench."""

from __future__ import annotations

from dataclasses import dataclass
import secrets
from typing import Iterable

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    EntityRecord,
    FactRecord,
    LicenseClass,
    ParameterLimitPayload,
    PreparedBy,
    RecordStatus,
    RecordValidationError,
    SourceRecord,
)
from pcbknowledge.git_native.review_closure import (
    ReviewClosureApplication,
    ReviewDecisionView,
)
from pcbknowledge.git_native.store import (
    AuthoritySnapshot,
    FactConflict,
    KnowledgeRepository,
    RecordConflictError,
    RecordNotFoundError,
    RepositoryError,
)


@dataclass(frozen=True, slots=True)
class LinkView:
    id: str
    label: str
    href: str
    role: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewEventView:
    action: str
    comment: str | None


@dataclass(frozen=True, slots=True)
class SourceDraftInput:
    title: str | None
    document_number: str | None
    revision: str | None
    source_publisher: str | None
    source_locator: str | None
    license_class: LicenseClass
    license_note: str | None
    preparation_note: str | None
    supersedes: str | None


@dataclass(frozen=True, slots=True)
class SourceView:
    id: str
    display_title: str
    title: str | None
    source_type: str
    status: str
    prepared_by: str
    document_number: str | None
    revision: str | None
    publisher: str | None
    locator: str | None
    license_class: str
    license_note: str | None
    preparation_note: str | None
    evidence_sha256: str | None
    evidence_byte_size: int | None
    missing_fields: tuple[str, ...]
    review_history: tuple[ReviewEventView, ...]
    revision_token: str
    supersedes: LinkView | None
    successors: tuple[LinkView, ...]
    facts: tuple[LinkView, ...]


@dataclass(frozen=True, slots=True)
class EntityView:
    id: str
    kind: str
    label: str
    prepared_by: str
    normalized_identity: str
    family: str | None
    note: str | None
    manufacturer: LinkView | None
    related_entities: tuple[LinkView, ...]
    facts: tuple[LinkView, ...]


@dataclass(frozen=True, slots=True)
class EvidenceAnchorView:
    source: LinkView
    page: int
    bbox: tuple[float, float, float, float] | None
    quote: str | None
    quote_sha256: str | None
    complete: bool


@dataclass(frozen=True, slots=True)
class FactView:
    id: str
    fact_type: str
    title: str
    status: str
    prepared_by: str
    payload_rows: tuple[tuple[str, str], ...]
    entities: tuple[LinkView, ...]
    sources: tuple[LinkView, ...]
    anchors: tuple[EvidenceAnchorView, ...]
    conditions: tuple[str, ...]
    applicability: tuple[str, ...]
    missing_fields: tuple[str, ...]
    blockers: tuple[str, ...]
    conflicts: tuple[LinkView, ...]
    review_history: tuple[ReviewEventView, ...]
    revision_token: str
    supersedes: LinkView | None
    successors: tuple[LinkView, ...]


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    kind: str
    id: str
    title: str
    href: str
    prepared_by: str
    blockers: tuple[str, ...]
    context: str


@dataclass(frozen=True, slots=True)
class WorkbenchOverview:
    review_items: tuple[ReviewQueueItem, ...]
    source_count: int
    entity_count: int
    fact_count: int
    conflict_count: int
    change_count: int
    change_scope: str


class WorkbenchApplication:
    """Build typed UI projections and execute human review operations."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository
        self.review_closure = ReviewClosureApplication(repository)

    def _snapshot(self) -> AuthoritySnapshot:
        return self.repository.validate_all(require_canonical=True)

    @staticmethod
    def _source_label(source: SourceRecord) -> str:
        return source.title or source.document_number or source.id

    @staticmethod
    def _entity_label(entity: EntityRecord) -> str:
        if entity.kind is EntityKind.COMPONENT:
            return entity.raw_mpn or entity.id
        return entity.raw_name or entity.id

    @staticmethod
    def _review_history(record: SourceRecord | FactRecord) -> tuple[ReviewEventView, ...]:
        return tuple(
            ReviewEventView(event.action.value, event.comment)
            for event in record.review_history
        )

    @classmethod
    def _source_link(cls, source: SourceRecord, *, role: str | None = None) -> LinkView:
        return LinkView(
            id=source.id,
            label=cls._source_label(source),
            href=f"/sources/{source.id}",
            role=role,
        )

    @classmethod
    def _entity_link(cls, entity: EntityRecord, *, role: str | None = None) -> LinkView:
        return LinkView(
            id=entity.id,
            label=cls._entity_label(entity),
            href=f"/entities/{entity.id}",
            role=role,
        )

    @staticmethod
    def _fact_title(fact: FactRecord) -> str:
        payload = fact.payload
        if isinstance(payload, ComponentPinPayload):
            name = payload.pin_name or payload.primary_function
            return f"Pin {payload.pin_number} · {name}"
        assert isinstance(payload, ParameterLimitPayload)
        return f"{payload.parameter} · {payload.limit_kind.value}"

    @classmethod
    def _fact_link(cls, fact: FactRecord, *, role: str | None = None) -> LinkView:
        return LinkView(
            id=fact.id,
            label=cls._fact_title(fact),
            href=f"/facts/{fact.id}",
            role=role,
        )

    @staticmethod
    def _find_by_id(records: Iterable[object], record_id: str, label: str):
        for record in records:
            if getattr(record, "id", None) == record_id:
                return record
        raise RecordNotFoundError(f"{label} not found")

    @staticmethod
    def _conflict_map(
        conflicts: tuple[FactConflict, ...],
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, tuple[str, ...]] = {}
        for conflict in conflicts:
            for fact_id in conflict.fact_ids:
                result[fact_id] = tuple(
                    candidate
                    for candidate in conflict.fact_ids
                    if candidate != fact_id
                )
        return result

    def overview(self) -> WorkbenchOverview:
        snapshot = self._snapshot()
        source_map = {source.id: source for source in snapshot.sources}
        conflict_map = self._conflict_map(snapshot.conflicts)
        items: list[ReviewQueueItem] = []

        for source in snapshot.sources:
            if source.status is not RecordStatus.READY_FOR_REVIEW:
                continue
            blockers = tuple(f"Missing {field}" for field in source.missing_fields)
            items.append(
                ReviewQueueItem(
                    kind="SOURCE",
                    id=source.id,
                    title=self._source_label(source),
                    href=f"/sources/{source.id}",
                    prepared_by=source.prepared_by.value,
                    blockers=blockers,
                    context=(
                        f"{source.source_type.value} · "
                        f"{source.revision or 'revision unknown'}"
                    ),
                )
            )

        for fact in snapshot.facts:
            if fact.status is not RecordStatus.READY_FOR_REVIEW:
                continue
            blockers = list(self._fact_blockers(fact, source_map, conflict_map))
            items.append(
                ReviewQueueItem(
                    kind="FACT",
                    id=fact.id,
                    title=self._fact_title(fact),
                    href=f"/facts/{fact.id}",
                    prepared_by=fact.prepared_by.value,
                    blockers=tuple(blockers),
                    context=fact.fact_type.value,
                )
            )

        items.sort(key=lambda item: (item.kind, item.title.casefold(), item.id))
        changes = self.repository.git_changes()
        return WorkbenchOverview(
            review_items=tuple(items),
            source_count=len(snapshot.sources),
            entity_count=len(snapshot.entities),
            fact_count=len(snapshot.facts),
            conflict_count=len(snapshot.conflicts),
            change_count=changes.count,
            change_scope=self.repository.git_change_scope().value,
        )

    def list_sources(
        self, *, status: RecordStatus | None = None
    ) -> tuple[SourceView, ...]:
        snapshot = self._snapshot()
        records = (
            snapshot.sources
            if status is None
            else tuple(source for source in snapshot.sources if source.status is status)
        )
        return tuple(self._source_view(source, snapshot) for source in records)

    def source_detail(self, source_id: str) -> SourceView:
        snapshot = self._snapshot()
        source = self._find_by_id(snapshot.sources, source_id, "source")
        assert isinstance(source, SourceRecord)
        return self._source_view(source, snapshot)

    def source_review_decision(self, source_id: str) -> ReviewDecisionView:
        return self.review_closure.source_decision(source_id)

    def _source_view(
        self, source: SourceRecord, snapshot: AuthoritySnapshot
    ) -> SourceView:
        source_map = {item.id: item for item in snapshot.sources}
        supersedes = (
            None
            if source.supersedes is None
            else self._source_link(source_map[source.supersedes], role="supersedes")
        )
        successors = tuple(
            self._source_link(item, role="successor")
            for item in snapshot.sources
            if item.supersedes == source.id
        )
        facts = tuple(
            self._fact_link(fact)
            for fact in snapshot.facts
            if source.id in fact.source_ids
        )
        return SourceView(
            id=source.id,
            display_title=self._source_label(source),
            title=source.title,
            source_type=source.source_type.value,
            status=source.status.value,
            prepared_by=source.prepared_by.value,
            document_number=source.document_number,
            revision=source.revision,
            publisher=source.source.publisher,
            locator=source.source.locator,
            license_class=source.license_class.value,
            license_note=source.license_note,
            preparation_note=source.preparation_note,
            evidence_sha256=source.evidence.sha256,
            evidence_byte_size=source.evidence.byte_size,
            missing_fields=source.missing_fields,
            review_history=self._review_history(source),
            revision_token=source.revision_token,
            supersedes=supersedes,
            successors=successors,
            facts=facts,
        )

    def list_entities(
        self, *, kind: EntityKind | None = None
    ) -> tuple[EntityView, ...]:
        snapshot = self._snapshot()
        records = (
            snapshot.entities
            if kind is None
            else tuple(entity for entity in snapshot.entities if entity.kind is kind)
        )
        return tuple(self._entity_view(entity, snapshot) for entity in records)

    def entity_detail(self, entity_id: str) -> EntityView:
        snapshot = self._snapshot()
        entity = self._find_by_id(snapshot.entities, entity_id, "entity")
        assert isinstance(entity, EntityRecord)
        return self._entity_view(entity, snapshot)

    def _entity_view(
        self, entity: EntityRecord, snapshot: AuthoritySnapshot
    ) -> EntityView:
        entity_map = {item.id: item for item in snapshot.entities}
        manufacturer = None
        related: list[LinkView] = []
        if entity.kind is EntityKind.COMPONENT:
            assert entity.manufacturer_id is not None
            manufacturer = self._entity_link(
                entity_map[entity.manufacturer_id], role="manufacturer"
            )
        elif entity.kind is EntityKind.MANUFACTURER:
            related.extend(
                self._entity_link(item, role="component")
                for item in snapshot.entities
                if item.kind is EntityKind.COMPONENT
                and item.manufacturer_id == entity.id
            )

        facts = tuple(
            self._fact_link(fact)
            for fact in snapshot.facts
            if entity.id in fact.subject_entity_ids
        )
        normalized_identity = (
            entity.normalized_mpn
            if entity.kind is EntityKind.COMPONENT
            else entity.normalized_key
        )
        return EntityView(
            id=entity.id,
            kind=entity.kind.value,
            label=self._entity_label(entity),
            prepared_by=entity.prepared_by.value,
            normalized_identity=normalized_identity or "",
            family=entity.family,
            note=entity.note,
            manufacturer=manufacturer,
            related_entities=tuple(related),
            facts=facts,
        )

    def list_facts(
        self, *, status: RecordStatus | None = None
    ) -> tuple[FactView, ...]:
        snapshot = self._snapshot()
        records = (
            snapshot.facts
            if status is None
            else tuple(fact for fact in snapshot.facts if fact.status is status)
        )
        return tuple(self._fact_view(fact, snapshot) for fact in records)

    def fact_detail(self, fact_id: str) -> FactView:
        snapshot = self._snapshot()
        fact = self._find_by_id(snapshot.facts, fact_id, "fact")
        assert isinstance(fact, FactRecord)
        return self._fact_view(fact, snapshot)

    def fact_review_decision(self, fact_id: str) -> ReviewDecisionView:
        return self.review_closure.fact_decision(fact_id)

    def _fact_view(self, fact: FactRecord, snapshot: AuthoritySnapshot) -> FactView:
        entity_map = {entity.id: entity for entity in snapshot.entities}
        source_map = {source.id: source for source in snapshot.sources}
        fact_map = {item.id: item for item in snapshot.facts}
        conflict_map = self._conflict_map(snapshot.conflicts)

        payload = fact.payload
        entity_links: list[LinkView] = []
        rows: list[tuple[str, str]] = []
        if isinstance(payload, ComponentPinPayload):
            entity_links.extend(
                (
                    self._entity_link(entity_map[payload.component_id], role="component"),
                    self._entity_link(entity_map[payload.package_id], role="package"),
                )
            )
            rows.extend(
                (
                    ("Pin number", payload.pin_number),
                    ("Pin name", payload.pin_name or "Unknown"),
                    ("Primary function", payload.primary_function),
                    (
                        "Alternate functions",
                        ", ".join(payload.alternate_functions) or "None",
                    ),
                )
            )
        else:
            assert isinstance(payload, ParameterLimitPayload)
            entity_links.append(
                self._entity_link(entity_map[payload.component_id], role="component")
            )
            rows.extend(
                (
                    ("Parameter", payload.parameter),
                    ("Limit kind", payload.limit_kind.value),
                    ("Minimum", self._format_number(payload.minimum, payload.unit)),
                    ("Typical", self._format_number(payload.typical, payload.unit)),
                    ("Maximum", self._format_number(payload.maximum, payload.unit)),
                    ("Unit", payload.unit),
                )
            )

        source_links = tuple(
            self._source_link(source_map[source_id])
            for source_id in fact.source_ids
        )
        anchors = tuple(
            EvidenceAnchorView(
                source=self._source_link(source_map[anchor.source_id]),
                page=anchor.page,
                bbox=anchor.bbox,
                quote=anchor.quote,
                quote_sha256=anchor.quote_sha256,
                complete=anchor.complete,
            )
            for anchor in fact.evidence_anchors
        )
        conflicting = tuple(
            self._fact_link(fact_map[other_id], role="conflict")
            for other_id in conflict_map.get(fact.id, ())
        )
        supersedes = (
            None
            if fact.supersedes is None
            else self._fact_link(fact_map[fact.supersedes], role="supersedes")
        )
        successors = tuple(
            self._fact_link(item, role="successor")
            for item in snapshot.facts
            if item.supersedes == fact.id
        )
        blockers = self._fact_blockers(fact, source_map, conflict_map)
        return FactView(
            id=fact.id,
            fact_type=fact.fact_type.value,
            title=self._fact_title(fact),
            status=fact.status.value,
            prepared_by=fact.prepared_by.value,
            payload_rows=tuple(rows),
            entities=tuple(entity_links),
            sources=source_links,
            anchors=anchors,
            conditions=fact.conditions,
            applicability=fact.applicability,
            missing_fields=fact.missing_fields,
            blockers=blockers,
            conflicts=conflicting,
            review_history=self._review_history(fact),
            revision_token=fact.revision_token,
            supersedes=supersedes,
            successors=successors,
        )

    @staticmethod
    def _format_number(value: float | int | None, unit: str) -> str:
        return "Unknown" if value is None else f"{value:g} {unit}"

    @staticmethod
    def _fact_blockers(
        fact: FactRecord,
        source_map: dict[str, SourceRecord],
        conflict_map: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        blockers = [f"Missing {field}" for field in fact.missing_fields]
        if conflict_map.get(fact.id):
            blockers.append("Semantic conflict is unresolved")
        for source_id in fact.source_ids:
            source = source_map[source_id]
            if source.status is not RecordStatus.APPROVED:
                blockers.append(
                    f"Source {source_id} is {source.status.value}, not APPROVED"
                )
            if not source.evidence.present:
                blockers.append(f"Source {source_id} has no PDF evidence")
            if not source.agent_processing_allowed:
                blockers.append(
                    f"Source {source_id} license {source.license_class.value} "
                    "blocks evidence review"
                )
        return tuple(dict.fromkeys(blockers))

    def create_source(
        self, draft: SourceDraftInput, *, pdf_payload: bytes | None
    ) -> SourceRecord:
        source = SourceRecord.new(
            f"pk_{secrets.token_hex(12)}", prepared_by=PreparedBy.HUMAN
        )
        evidence = (
            source.evidence
            if not pdf_payload
            else self.repository.inspect_pdf_bytes(pdf_payload)
        )
        candidate = self._edited_source(source, draft, evidence=evidence)
        self._validate_source_supersedes(candidate)
        if pdf_payload:
            imported = self.repository.import_pdf_bytes(pdf_payload)
            if imported != candidate.evidence:
                raise RepositoryError("PDF evidence identity changed during import")
        self.repository.insert_source(candidate)
        return candidate

    def update_source(
        self,
        source_id: str,
        *,
        expected_revision: str,
        draft: SourceDraftInput,
        pdf_payload: bytes | None,
    ) -> SourceRecord:
        current = self.repository.load_source(source_id)
        return self._save_source_draft(
            current, expected_revision, draft, pdf_payload=pdf_payload
        )

    def _save_source_draft(
        self,
        current: SourceRecord,
        expected_revision: str,
        draft: SourceDraftInput,
        *,
        pdf_payload: bytes | None,
    ) -> SourceRecord:
        if current.revision_token != expected_revision:
            raise RecordConflictError(
                "The source changed after this page loaded. Refresh and retry."
            )
        evidence = (
            current.evidence
            if not pdf_payload
            else self.repository.inspect_pdf_bytes(pdf_payload)
        )
        updated = self._edited_source(current, draft, evidence=evidence)
        self._validate_source_supersedes(updated)
        if pdf_payload:
            imported = self.repository.import_pdf_bytes(pdf_payload)
            if imported != updated.evidence:
                raise RepositoryError("PDF evidence identity changed during import")
        self.repository.save_source(current, updated, expected_revision)
        return updated

    @staticmethod
    def _edited_source(
        current: SourceRecord, draft: SourceDraftInput, *, evidence
    ) -> SourceRecord:
        return current.edit(
            title=draft.title,
            document_number=draft.document_number,
            revision=draft.revision,
            source_locator=draft.source_locator,
            source_publisher=draft.source_publisher,
            license_class=draft.license_class,
            license_note=draft.license_note,
            evidence=evidence,
            preparation_note=draft.preparation_note,
            supersedes=draft.supersedes,
        )

    def _validate_source_supersedes(self, source: SourceRecord) -> None:
        if source.supersedes is None:
            return
        target = self.repository.load_source(source.supersedes)
        if target.source_type is not source.source_type:
            raise RecordValidationError(
                "source supersedes must reference the same source_type"
            )

    def submit_source(self, source_id: str, *, expected_revision: str) -> SourceRecord:
        return self.repository.submit_source(
            source_id, expected_revision=expected_revision
        )

    def approve_source(
        self,
        source_id: str,
        *,
        expected_revision: str,
        comment: str | None,
    ) -> SourceRecord:
        decision = self.source_review_decision(source_id)
        self.review_closure.require_approval(decision)
        return self.repository.approve_source(
            source_id,
            expected_revision=expected_revision,
            comment=comment,
        )

    def reject_source(
        self,
        source_id: str,
        *,
        expected_revision: str,
        comment: str,
    ) -> SourceRecord:
        decision = self.source_review_decision(source_id)
        self.review_closure.require_rejection(decision)
        return self.repository.reject_source(
            source_id,
            expected_revision=expected_revision,
            comment=comment,
        )

    def approve_fact(
        self,
        fact_id: str,
        *,
        expected_revision: str,
        comment: str | None,
    ) -> FactRecord:
        decision = self.fact_review_decision(fact_id)
        self.review_closure.require_approval(decision)
        return self.repository.approve_fact(
            fact_id,
            expected_revision=expected_revision,
            comment=comment,
        )

    def reject_fact(
        self,
        fact_id: str,
        *,
        expected_revision: str,
        comment: str,
    ) -> FactRecord:
        decision = self.fact_review_decision(fact_id)
        self.review_closure.require_rejection(decision)
        return self.repository.reject_fact(
            fact_id,
            expected_revision=expected_revision,
            comment=comment,
        )
