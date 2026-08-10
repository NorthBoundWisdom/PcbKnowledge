"""SourceRecordV1 model."""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
from .authority_common import *
from .authority_common import _SOURCE_ID, _approve, _canonical_json, _enum_value, _optional_text, _reject, _reject_extra_keys, _required_mapping, _required_text, _revision_token, _submit, _validate_review_state
@dataclass(frozen=True, slots=True)
class SourceRecord:
    id: str
    source_type: SourceType = SourceType.DATASHEET
    status: RecordStatus = RecordStatus.DRAFT
    prepared_by: PreparedBy = PreparedBy.HUMAN
    title: str | None = None
    document_number: str | None = None
    revision: str | None = None
    source: SourceLocation = SourceLocation()
    license_class: LicenseClass = LicenseClass.UNKNOWN
    license_note: str | None = None
    evidence: Evidence = Evidence()
    preparation_note: str | None = None
    review_history: tuple[ReviewEvent, ...] = ()
    review: Review = Review()
    supersedes: str | None = None
    schema_version: int = SOURCE_SCHEMA_VERSION

    @classmethod
    def new(cls, record_id: str, *, prepared_by: PreparedBy, source_type: SourceType = SourceType.DATASHEET) -> SourceRecord:
        return cls(id=record_id, prepared_by=prepared_by, source_type=source_type).validate()

    @classmethod
    def from_dict(cls, value: object) -> SourceRecord:
        data = _required_mapping(value, "source record")
        allowed = {"schema_version", "id", "source_type", "status", "prepared_by", "title", "document_number", "revision", "source", "license", "evidence", "preparation_note", "review_history", "review", "supersedes"}
        _reject_extra_keys(data, allowed, "source record")
        if data.get("schema_version") != SOURCE_SCHEMA_VERSION:
            raise RecordValidationError(f"source schema_version must equal {SOURCE_SCHEMA_VERSION}")
        license_data = _required_mapping(data.get("license"), "license")
        _reject_extra_keys(license_data, {"class", "note"}, "license")
        raw_history = data.get("review_history")
        if not isinstance(raw_history, list):
            raise RecordValidationError("review_history must be an array")
        record = cls(
            schema_version=SOURCE_SCHEMA_VERSION,
            id=_required_text(data.get("id"), "id", limit=40),
            source_type=SourceType(_enum_value(SourceType, data.get("source_type"), "source_type")),
            status=RecordStatus(_enum_value(RecordStatus, data.get("status"), "status")),
            prepared_by=PreparedBy(_enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")),
            title=_optional_text(data.get("title"), "title", limit=500),
            document_number=_optional_text(data.get("document_number"), "document_number", limit=200),
            revision=_optional_text(data.get("revision"), "revision", limit=200),
            source=SourceLocation.from_dict(data.get("source")),
            license_class=LicenseClass(_enum_value(LicenseClass, license_data.get("class"), "license.class")),
            license_note=_optional_text(license_data.get("note"), "license.note", limit=2000),
            evidence=Evidence.from_dict(data.get("evidence")),
            preparation_note=_optional_text(data.get("preparation_note"), "preparation_note", limit=4000),
            review_history=tuple(ReviewEvent.from_dict(item) for item in raw_history),
            review=Review.from_dict(data.get("review")),
            supersedes=_optional_text(data.get("supersedes"), "supersedes", limit=40),
        )
        return record.validate()

    @classmethod
    def from_json(cls, payload: str) -> SourceRecord:
        try:
            return cls.from_dict(json.loads(payload))
        except json.JSONDecodeError as error:
            raise RecordValidationError(f"source record is not valid JSON: {error.msg}") from error

    def validate(self) -> SourceRecord:
        if _SOURCE_ID.fullmatch(self.id) is None:
            raise RecordValidationError("source id must match pk_<24-32 lowercase hex characters>")
        if self.supersedes is not None:
            if _SOURCE_ID.fullmatch(self.supersedes) is None:
                raise RecordValidationError("supersedes must be a valid source id")
            if self.supersedes == self.id:
                raise RecordValidationError("a source cannot supersede itself")
        _validate_review_state(self.status, self.review_history, self.review, missing_fields=self.missing_fields)
        return self

    @property
    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.title is None: missing.append("title")
        if self.revision is None: missing.append("revision")
        if self.source.locator is None and self.source.publisher is None: missing.append("source")
        if self.license_class is LicenseClass.UNKNOWN: missing.append("license")
        if not self.evidence.present: missing.append("evidence")
        return tuple(missing)

    @property
    def agent_processing_allowed(self) -> bool:
        return self.license_class.agent_processing_allowed

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.status in {RecordStatus.DRAFT, RecordStatus.REJECTED}: return ("EDIT", "SUBMIT")
        if self.status is RecordStatus.READY_FOR_REVIEW: return ("HUMAN_APPROVE", "HUMAN_REJECT")
        return ()

    def edit(self, *, title: str | None, document_number: str | None, revision: str | None, source_locator: str | None, source_publisher: str | None, license_class: LicenseClass, license_note: str | None, evidence: Evidence, preparation_note: str | None, supersedes: str | None, source_type: SourceType | None = None) -> SourceRecord:
        if self.status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            raise RecordTransitionError("only DRAFT or REJECTED sources can be edited")
        candidate = replace(
            self, status=RecordStatus.DRAFT,
            source_type=self.source_type if source_type is None else source_type,
            title=_optional_text(title, "title", limit=500),
            document_number=_optional_text(document_number, "document_number", limit=200),
            revision=_optional_text(revision, "revision", limit=200),
            source=SourceLocation(_optional_text(source_locator, "source.locator", limit=2048), _optional_text(source_publisher, "source.publisher", limit=256)),
            license_class=license_class,
            license_note=_optional_text(license_note, "license.note", limit=2000), evidence=evidence,
            preparation_note=_optional_text(preparation_note, "preparation_note", limit=4000),
            review=Review(), supersedes=_optional_text(supersedes, "supersedes", limit=40),
        )
        return candidate.validate()

    def submit(self) -> SourceRecord:
        status, history, review = _submit(self.status, self.review_history)
        return replace(self, status=status, review_history=history, review=review).validate()

    def approve(self, comment: str | None) -> SourceRecord:
        status, history, review = _approve(self.status, self.review_history, comment, missing_fields=self.missing_fields)
        return replace(self, status=status, review_history=history, review=review).validate()

    def reject(self, comment: str | None) -> SourceRecord:
        status, history, review = _reject(self.status, self.review_history, comment)
        return replace(self, status=status, review_history=history, review=review).validate()

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "id": self.id, "source_type": self.source_type.value, "status": self.status.value, "prepared_by": self.prepared_by.value, "title": self.title, "document_number": self.document_number, "revision": self.revision, "source": self.source.to_dict(), "license": {"class": self.license_class.value, "note": self.license_note}, "evidence": self.evidence.to_dict(), "preparation_note": self.preparation_note, "review_history": [item.to_dict() for item in self.review_history], "review": self.review.to_dict(), "supersedes": self.supersedes}

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def revision_token(self) -> str:
        return _revision_token(self.to_dict())
