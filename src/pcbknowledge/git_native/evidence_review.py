"""Application projection for visual Fact-to-PDF evidence review."""

from __future__ import annotations

from dataclasses import dataclass

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    FactRecord,
    ParameterLimitPayload,
    SourceRecord,
)
from pcbknowledge.git_native.store import KnowledgeRepository, RecordNotFoundError


@dataclass(frozen=True, slots=True)
class EvidenceReviewAnchorView:
    index: int
    anchor_id: str
    source_id: str
    source_label: str
    source_revision: str
    source_document_number: str | None
    source_type: str
    license_class: str
    page: int
    coordinate_space: str
    bbox: tuple[float, float, float, float] | None
    quote: str | None
    quote_sha256: str | None
    complete: bool
    evidence_url: str | None
    blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class FactEvidenceReviewView:
    fact_id: str
    fact_title: str
    fact_type: str
    subject_context: tuple[str, ...]
    conditions: tuple[str, ...]
    applicability: tuple[str, ...]
    anchors: tuple[EvidenceReviewAnchorView, ...]


class EvidenceReviewApplication:
    """Build evidence-review state without creating a second authority path."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    @staticmethod
    def _source_label(source: SourceRecord) -> str:
        return source.title or source.document_number or source.id

    @staticmethod
    def _fact_title(fact: FactRecord) -> str:
        payload = fact.payload
        if isinstance(payload, ComponentPinPayload):
            return f"Pin {payload.pin_number} · {payload.pin_name or payload.primary_function}"
        assert isinstance(payload, ParameterLimitPayload)
        return f"{payload.parameter} · {payload.limit_kind.value}"

    def fact_review(self, fact_id: str) -> FactEvidenceReviewView:
        snapshot = self.repository.validate_all(require_canonical=True)
        fact = next((item for item in snapshot.facts if item.id == fact_id), None)
        if fact is None:
            raise RecordNotFoundError("fact not found")
        source_map = {source.id: source for source in snapshot.sources}
        entity_map = {entity.id: entity for entity in snapshot.entities}

        payload = fact.payload
        if isinstance(payload, ComponentPinPayload):
            component = entity_map[payload.component_id]
            package = entity_map[payload.package_id]
            subject_context = (
                f"Component: {component.raw_mpn or component.id}",
                f"Package: {package.raw_name or package.id}",
            )
        else:
            assert isinstance(payload, ParameterLimitPayload)
            component = entity_map[payload.component_id]
            subject_context = (f"Component: {component.raw_mpn or component.id}",)

        anchors: list[EvidenceReviewAnchorView] = []
        for index, anchor in enumerate(fact.evidence_anchors, start=1):
            source = source_map[anchor.source_id]
            blocked_reason: str | None = None
            evidence_url: str | None = None
            if not source.agent_processing_allowed:
                blocked_reason = (
                    "Evidence processing is blocked by Source license policy: "
                    f"{source.license_class.value}."
                )
            elif not source.evidence.present:
                blocked_reason = "The referenced Source has no PDF evidence."
            else:
                evidence_url = f"/sources/{source.id}/evidence"

            anchors.append(
                EvidenceReviewAnchorView(
                    index=index,
                    anchor_id=f"evidence-anchor-{index}",
                    source_id=source.id,
                    source_label=self._source_label(source),
                    source_revision=source.revision or "Unknown",
                    source_document_number=source.document_number,
                    source_type=source.source_type.value,
                    license_class=source.license_class.value,
                    page=anchor.page,
                    coordinate_space=anchor.coordinate_space,
                    bbox=anchor.bbox,
                    quote=anchor.quote,
                    quote_sha256=anchor.quote_sha256,
                    complete=anchor.complete,
                    evidence_url=evidence_url,
                    blocked_reason=blocked_reason,
                )
            )

        return FactEvidenceReviewView(
            fact_id=fact.id,
            fact_title=self._fact_title(fact),
            fact_type=fact.fact_type.value,
            subject_context=subject_context,
            conditions=fact.conditions,
            applicability=fact.applicability,
            anchors=tuple(anchors),
        )
