"""Strict, deterministic models for the Git-native typed authority.

The executable contract intentionally lives in this module.  Source, Entity and
Fact JSON files are the canonical records; schemas mirror this code and are not
an independent write path.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence


SOURCE_SCHEMA_VERSION = 1
ENTITY_SCHEMA_VERSION = 1
FACT_SCHEMA_VERSION = 1

SOURCE_ID_PATTERN = re.compile(r"pk_[0-9a-f]{24,32}\Z")
ENTITY_ID_PATTERN = re.compile(r"ent_[0-9a-f]{24,32}\Z")
FACT_ID_PATTERN = re.compile(r"fact_[0-9a-f]{24,32}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_UNSET = object()


class RecordValidationError(ValueError):
    """An authority object is malformed or violates a domain invariant."""


class RecordTransitionError(ValueError):
    """A requested review-state transition is not allowed."""


class RecordStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PreparedBy(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"


class SourceType(StrEnum):
    DATASHEET = "DATASHEET"
    APPLICATION_NOTE = "APPLICATION_NOTE"
    REFERENCE_DESIGN = "REFERENCE_DESIGN"
    PCN = "PCN"
    FAB_CAPABILITY = "FAB_CAPABILITY"
    INTERNAL_GUIDELINE = "INTERNAL_GUIDELINE"


class LicenseClass(StrEnum):
    UNKNOWN = "UNKNOWN"
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"
    OPEN_LICENSE = "OPEN_LICENSE"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    LICENSED_BLOCKED_FOR_AI = "LICENSED_BLOCKED_FOR_AI"

    @property
    def agent_processing_allowed(self) -> bool:
        """Whether policy permits an Agent/model to process source contents."""

        return self in {
            LicenseClass.PUBLIC_REFERENCE,
            LicenseClass.OPEN_LICENSE,
            LicenseClass.INTERNAL,
        }


class ReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewAction(StrEnum):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EntityKind(StrEnum):
    MANUFACTURER = "MANUFACTURER"
    COMPONENT = "COMPONENT"
    PACKAGE = "PACKAGE"


class FactType(StrEnum):
    COMPONENT_PIN = "COMPONENT_PIN"
    PARAMETER_LIMIT = "PARAMETER_LIMIT"


class ParameterLimitKind(StrEnum):
    ABSOLUTE_MAXIMUM = "ABSOLUTE_MAXIMUM"
    RECOMMENDED_OPERATING = "RECOMMENDED_OPERATING"
    ELECTRICAL_CHARACTERISTIC = "ELECTRICAL_CHARACTERISTIC"


def _reject_extra_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extras = set(value) - allowed
    if extras:
        names = ", ".join(sorted(extras))
        raise RecordValidationError(f"{label} contains unsupported fields: {names}")


def _required_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise RecordValidationError(f"{label} must be an object")
    return value


def _optional_text(value: object, label: str, *, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordValidationError(f"{label} must be a string or null")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > limit:
        raise RecordValidationError(f"{label} exceeds {limit} characters")
    if "\x00" in normalized:
        raise RecordValidationError(f"{label} contains a NUL byte")
    return normalized


def _optional_verbatim_text(value: object, label: str, *, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordValidationError(f"{label} must be a string or null")
    if not value.strip():
        return None
    if len(value) > limit:
        raise RecordValidationError(f"{label} exceeds {limit} characters")
    if "\x00" in value:
        raise RecordValidationError(f"{label} contains a NUL byte")
    return value


def _required_text(value: object, label: str, *, limit: int) -> str:
    result = _optional_text(value, label, limit=limit)
    if result is None:
        raise RecordValidationError(f"{label} is required")
    return result


def _enum_value(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    if not isinstance(value, str):
        raise RecordValidationError(f"{label} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise RecordValidationError(f"{label} has an unsupported value") from error


def _validate_enum(value: object, enum_type: type[StrEnum], label: str) -> None:
    if not isinstance(value, enum_type):
        raise RecordValidationError(f"{label} has an unsupported value")


def _tuple_text(value: object, label: str, *, item_limit: int = 500) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RecordValidationError(f"{label} must be an array")
    return tuple(
        _required_text(item, f"{label} item", limit=item_limit) for item in value
    )


def _validate_text_tuple(
    value: object, label: str, *, item_limit: int = 500
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise RecordValidationError(f"{label} must be a tuple")
    normalized = tuple(
        _required_text(item, f"{label} item", limit=item_limit) for item in value
    )
    if normalized != value:
        raise RecordValidationError(f"{label} items must be normalized")
    return normalized


def normalize_lookup(value: str) -> str:
    """Create a deterministic exact-lookup key while preserving the raw value."""

    raw = _required_text(value, "lookup value", limit=500)
    compatibility = unicodedata.normalize("NFKC", raw).upper()
    normalized = "".join(character for character in compatibility if character.isalnum())
    if not normalized:
        raise RecordValidationError("lookup value normalizes to empty")
    return normalized


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _revision_token(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _deterministic_id(prefix: str, namespace: str, key: str) -> str:
    normalized = _required_text(key, "idempotency_key", limit=500)
    digest = hashlib.sha256(
        f"pcbknowledge:{namespace}\0{normalized}".encode("utf-8")
    ).hexdigest()
    return f"{prefix}{digest[:24]}"


def deterministic_source_id(idempotency_key: str) -> str:
    return _deterministic_id("pk_", "source-v1", idempotency_key)


def deterministic_record_id(idempotency_key: str) -> str:
    """Compatibility name for callers that create Source records."""

    return deterministic_source_id(idempotency_key)


def deterministic_entity_id(kind: EntityKind, idempotency_key: str) -> str:
    _validate_enum(kind, EntityKind, "entity kind")
    return _deterministic_id("ent_", f"entity-v1:{kind.value}", idempotency_key)


def deterministic_fact_id(idempotency_key: str) -> str:
    return _deterministic_id("fact_", "fact-v1", idempotency_key)


@dataclass(frozen=True, slots=True)
class Evidence:
    path: str | None = None
    sha256: str | None = None
    byte_size: int | None = None
    media_type: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> Evidence:
        data = _required_mapping(value, "evidence")
        _reject_extra_keys(
            data, {"path", "sha256", "byte_size", "media_type"}, "evidence"
        )
        evidence = cls(
            path=_optional_text(data.get("path"), "evidence.path", limit=256),
            sha256=_optional_text(data.get("sha256"), "evidence.sha256", limit=64),
            byte_size=data.get("byte_size"),
            media_type=_optional_text(
                data.get("media_type"), "evidence.media_type", limit=64
            ),
        )
        return evidence.validate()

    def validate(self) -> Evidence:
        values = (self.path, self.sha256, self.byte_size, self.media_type)
        if all(item is None for item in values):
            return self
        if any(item is None for item in values):
            raise RecordValidationError(
                "evidence fields must be either all present or all null"
            )
        if (
            not isinstance(self.byte_size, int)
            or isinstance(self.byte_size, bool)
            or self.byte_size <= 0
        ):
            raise RecordValidationError("evidence.byte_size must be a positive integer")
        assert self.path is not None
        assert self.sha256 is not None
        assert self.media_type is not None
        if _optional_text(self.path, "evidence.path", limit=256) != self.path:
            raise RecordValidationError("evidence.path must be normalized")
        if SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise RecordValidationError("evidence.sha256 must be lowercase SHA-256")
        expected = f"evidence/sha256/{self.sha256[:2]}/{self.sha256}.pdf"
        if self.path != expected:
            raise RecordValidationError(
                "evidence.path must be derived from evidence.sha256"
            )
        if self.media_type != "application/pdf":
            raise RecordValidationError("only application/pdf evidence is supported")
        return self

    @property
    def present(self) -> bool:
        return self.sha256 is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class Review:
    decision: ReviewDecision | None = None
    comment: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> Review:
        data = _required_mapping(value, "review")
        _reject_extra_keys(data, {"decision", "comment"}, "review")
        raw_decision = data.get("decision")
        decision = (
            None
            if raw_decision is None
            else ReviewDecision(
                _enum_value(ReviewDecision, raw_decision, "review.decision")
            )
        )
        review = cls(
            decision=decision,
            comment=_optional_text(data.get("comment"), "review.comment", limit=4000),
        )
        return review.validate()

    def validate(self) -> Review:
        if self.decision is not None:
            _validate_enum(self.decision, ReviewDecision, "review.decision")
        normalized = _optional_text(self.comment, "review.comment", limit=4000)
        if normalized != self.comment:
            raise RecordValidationError("review.comment must be normalized")
        if self.decision is ReviewDecision.REJECTED and self.comment is None:
            raise RecordValidationError("a rejected review requires comment")
        if self.decision is None and self.comment is not None:
            raise RecordValidationError("review.comment requires review.decision")
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": None if self.decision is None else self.decision.value,
            "comment": self.comment,
        }


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    action: ReviewAction
    comment: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> ReviewEvent:
        data = _required_mapping(value, "review_history item")
        _reject_extra_keys(data, {"action", "comment"}, "review_history item")
        return cls(
            action=ReviewAction(
                _enum_value(ReviewAction, data.get("action"), "review_history.action")
            ),
            comment=_optional_text(
                data.get("comment"), "review_history.comment", limit=4000
            ),
        ).validate()

    def validate(self) -> ReviewEvent:
        _validate_enum(self.action, ReviewAction, "review_history.action")
        normalized = _optional_text(
            self.comment, "review_history.comment", limit=4000
        )
        if normalized != self.comment:
            raise RecordValidationError("review_history.comment must be normalized")
        if self.action is ReviewAction.REJECTED and self.comment is None:
            raise RecordValidationError(
                "a rejected review history event requires comment"
            )
        if self.action is ReviewAction.SUBMITTED and self.comment is not None:
            raise RecordValidationError(
                "a submitted review history event cannot carry comment"
            )
        return self

    def to_dict(self) -> dict[str, object]:
        return {"action": self.action.value, "comment": self.comment}


def _review_last_action(history: Sequence[ReviewEvent]) -> ReviewAction | None:
    index = 0
    last_action: ReviewAction | None = None
    while index < len(history):
        if not isinstance(history[index], ReviewEvent):
            raise RecordValidationError(
                "review_history contains an unsupported value"
            )
        submitted = history[index].validate()
        if submitted.action is not ReviewAction.SUBMITTED:
            raise RecordValidationError(
                "review history must start or resume with SUBMITTED"
            )
        last_action = submitted.action
        index += 1
        if index == len(history):
            break

        if not isinstance(history[index], ReviewEvent):
            raise RecordValidationError(
                "review_history contains an unsupported value"
            )
        decision = history[index].validate()
        if decision.action not in {ReviewAction.APPROVED, ReviewAction.REJECTED}:
            raise RecordValidationError(
                "review history requires APPROVED or REJECTED after SUBMITTED"
            )
        last_action = decision.action
        index += 1
        if decision.action is ReviewAction.APPROVED and index != len(history):
            raise RecordValidationError("review history cannot continue after approval")
    return last_action


def _validate_review_state(
    status: RecordStatus,
    history: tuple[ReviewEvent, ...],
    review: Review,
    *,
    missing_fields: Sequence[str] = (),
) -> None:
    _validate_enum(status, RecordStatus, "status")
    if not isinstance(history, tuple):
        raise RecordValidationError("review_history must be a tuple")
    if not isinstance(review, Review):
        raise RecordValidationError("review must be a Review object")
    review.validate()
    last_action = _review_last_action(history)
    if status is RecordStatus.DRAFT:
        if last_action not in {None, ReviewAction.REJECTED}:
            raise RecordValidationError(
                "DRAFT review history must be empty or end with REJECTED"
            )
        if review != Review():
            raise RecordValidationError("DRAFT cannot carry a current review decision")
    elif status is RecordStatus.READY_FOR_REVIEW:
        if last_action is not ReviewAction.SUBMITTED:
            raise RecordValidationError(
                "READY_FOR_REVIEW requires a trailing SUBMITTED event"
            )
        if review != Review():
            raise RecordValidationError(
                "READY_FOR_REVIEW cannot carry a current review decision"
            )
    elif status is RecordStatus.APPROVED:
        if last_action is not ReviewAction.APPROVED:
            raise RecordValidationError(
                "APPROVED requires a trailing APPROVED review event"
            )
        expected = Review(ReviewDecision.APPROVED, history[-1].comment)
        if review != expected:
            raise RecordValidationError(
                "APPROVED current review must match its trailing history event"
            )
        if missing_fields:
            raise RecordValidationError(
                "APPROVED is missing required fields: " + ", ".join(missing_fields)
            )
    elif status is RecordStatus.REJECTED:
        if last_action is not ReviewAction.REJECTED:
            raise RecordValidationError(
                "REJECTED requires a trailing REJECTED review event"
            )
        expected = Review(ReviewDecision.REJECTED, history[-1].comment)
        if review != expected:
            raise RecordValidationError(
                "REJECTED current review must match its trailing history event"
            )


def _submit(
    status: RecordStatus, history: tuple[ReviewEvent, ...]
) -> tuple[RecordStatus, tuple[ReviewEvent, ...], Review]:
    if status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
        raise RecordTransitionError("only DRAFT or REJECTED records can be submitted")
    return (
        RecordStatus.READY_FOR_REVIEW,
        (*history, ReviewEvent(ReviewAction.SUBMITTED)),
        Review(),
    )


def _approve(
    status: RecordStatus,
    history: tuple[ReviewEvent, ...],
    comment: str | None,
    *,
    missing_fields: Sequence[str],
) -> tuple[RecordStatus, tuple[ReviewEvent, ...], Review]:
    if status is not RecordStatus.READY_FOR_REVIEW:
        raise RecordTransitionError(
            "only READY_FOR_REVIEW records can be approved"
        )
    if missing_fields:
        raise RecordTransitionError(
            "cannot approve while fields are missing: " + ", ".join(missing_fields)
        )
    normalized = _optional_text(comment, "review.comment", limit=4000)
    event = ReviewEvent(ReviewAction.APPROVED, normalized)
    return (
        RecordStatus.APPROVED,
        (*history, event),
        Review(ReviewDecision.APPROVED, normalized),
    )


def _reject(
    status: RecordStatus,
    history: tuple[ReviewEvent, ...],
    comment: str | None,
) -> tuple[RecordStatus, tuple[ReviewEvent, ...], Review]:
    if status is not RecordStatus.READY_FOR_REVIEW:
        raise RecordTransitionError(
            "only READY_FOR_REVIEW records can be rejected"
        )
    normalized = _optional_text(comment, "review.comment", limit=4000)
    if normalized is None:
        raise RecordTransitionError("rejection requires a review comment")
    event = ReviewEvent(ReviewAction.REJECTED, normalized)
    return (
        RecordStatus.REJECTED,
        (*history, event),
        Review(ReviewDecision.REJECTED, normalized),
    )


@dataclass(frozen=True, slots=True)
class SourceLocation:
    locator: str | None = None
    publisher: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> SourceLocation:
        data = _required_mapping(value, "source")
        _reject_extra_keys(data, {"locator", "publisher"}, "source")
        return cls(
            locator=_optional_text(data.get("locator"), "source.locator", limit=2048),
            publisher=_optional_text(
                data.get("publisher"), "source.publisher", limit=256
            ),
        ).validate()

    def validate(self) -> SourceLocation:
        if _optional_text(self.locator, "source.locator", limit=2048) != self.locator:
            raise RecordValidationError("source.locator must be normalized")
        if (
            _optional_text(self.publisher, "source.publisher", limit=256)
            != self.publisher
        ):
            raise RecordValidationError("source.publisher must be normalized")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"locator": self.locator, "publisher": self.publisher}


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
    def new(
        cls,
        source_id: str,
        *,
        prepared_by: PreparedBy,
        source_type: SourceType = SourceType.DATASHEET,
    ) -> SourceRecord:
        return cls(
            id=source_id, prepared_by=prepared_by, source_type=source_type
        ).validate()

    @classmethod
    def from_dict(cls, value: object) -> SourceRecord:
        data = _required_mapping(value, "source record")
        allowed = {
            "schema_version",
            "id",
            "source_type",
            "status",
            "prepared_by",
            "title",
            "document_number",
            "revision",
            "source",
            "license",
            "evidence",
            "preparation_note",
            "review_history",
            "review",
            "supersedes",
        }
        _reject_extra_keys(data, allowed, "source record")
        if data.get("schema_version") != SOURCE_SCHEMA_VERSION:
            raise RecordValidationError(
                f"source schema_version must equal {SOURCE_SCHEMA_VERSION}"
            )
        license_data = _required_mapping(data.get("license"), "license")
        _reject_extra_keys(license_data, {"class", "note"}, "license")
        raw_history = data.get("review_history")
        if not isinstance(raw_history, list):
            raise RecordValidationError("review_history must be an array")
        return cls(
            schema_version=SOURCE_SCHEMA_VERSION,
            id=_required_text(data.get("id"), "id", limit=40),
            source_type=SourceType(
                _enum_value(SourceType, data.get("source_type"), "source_type")
            ),
            status=RecordStatus(
                _enum_value(RecordStatus, data.get("status"), "status")
            ),
            prepared_by=PreparedBy(
                _enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")
            ),
            title=_optional_text(data.get("title"), "title", limit=500),
            document_number=_optional_text(
                data.get("document_number"), "document_number", limit=200
            ),
            revision=_optional_text(data.get("revision"), "revision", limit=200),
            source=SourceLocation.from_dict(data.get("source")),
            license_class=LicenseClass(
                _enum_value(
                    LicenseClass, license_data.get("class"), "license.class"
                )
            ),
            license_note=_optional_text(
                license_data.get("note"), "license.note", limit=2000
            ),
            evidence=Evidence.from_dict(data.get("evidence")),
            preparation_note=_optional_text(
                data.get("preparation_note"), "preparation_note", limit=4000
            ),
            review_history=tuple(
                ReviewEvent.from_dict(item) for item in raw_history
            ),
            review=Review.from_dict(data.get("review")),
            supersedes=_optional_text(data.get("supersedes"), "supersedes", limit=40),
        ).validate()

    @classmethod
    def from_json(cls, payload: str) -> SourceRecord:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RecordValidationError(
                f"source record is not valid JSON: {error.msg}"
            ) from error
        return cls.from_dict(value)

    def validate(self) -> SourceRecord:
        if self.schema_version != SOURCE_SCHEMA_VERSION:
            raise RecordValidationError(
                f"source schema_version must equal {SOURCE_SCHEMA_VERSION}"
            )
        if SOURCE_ID_PATTERN.fullmatch(self.id) is None:
            raise RecordValidationError(
                "source id must match pk_<24-32 lowercase hex characters>"
            )
        _validate_enum(self.source_type, SourceType, "source_type")
        _validate_enum(self.prepared_by, PreparedBy, "prepared_by")
        for value, label, limit in (
            (self.title, "title", 500),
            (self.document_number, "document_number", 200),
            (self.revision, "revision", 200),
            (self.license_note, "license.note", 2000),
            (self.preparation_note, "preparation_note", 4000),
        ):
            if _optional_text(value, label, limit=limit) != value:
                raise RecordValidationError(f"{label} must be normalized")
        if not isinstance(self.source, SourceLocation):
            raise RecordValidationError("source must be a SourceLocation")
        self.source.validate()
        _validate_enum(self.license_class, LicenseClass, "license.class")
        if not isinstance(self.evidence, Evidence):
            raise RecordValidationError("evidence must be an Evidence object")
        self.evidence.validate()
        if self.supersedes is not None:
            if SOURCE_ID_PATTERN.fullmatch(self.supersedes) is None:
                raise RecordValidationError("supersedes must be a valid source id")
            if self.supersedes == self.id:
                raise RecordValidationError("a source cannot supersede itself")
        _validate_review_state(
            self.status,
            self.review_history,
            self.review,
            missing_fields=self.missing_fields,
        )
        return self

    @property
    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.title is None:
            missing.append("title")
        if self.revision is None:
            missing.append("revision")
        if self.source.locator is None and self.source.publisher is None:
            missing.append("source")
        if self.license_class is LicenseClass.UNKNOWN:
            missing.append("license")
        if self.license_class in {
            LicenseClass.RESTRICTED,
            LicenseClass.LICENSED_BLOCKED_FOR_AI,
        } and self.license_note is None:
            missing.append("license_note")
        if not self.evidence.present:
            missing.append("evidence")
        return tuple(missing)

    @property
    def agent_processing_allowed(self) -> bool:
        return self.license_class.agent_processing_allowed

    @property
    def next_actions(self) -> tuple[str, ...]:
        if self.status in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            return ("EDIT", "SUBMIT")
        if self.status is RecordStatus.READY_FOR_REVIEW:
            return ("HUMAN_APPROVE", "HUMAN_REJECT")
        return ()

    def edit(
        self,
        *,
        title: str | None,
        document_number: str | None,
        revision: str | None,
        source_locator: str | None,
        source_publisher: str | None,
        license_class: LicenseClass,
        license_note: str | None,
        evidence: Evidence,
        preparation_note: str | None,
        supersedes: str | None,
        source_type: SourceType | None = None,
    ) -> SourceRecord:
        if self.status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            raise RecordTransitionError(
                "only DRAFT or REJECTED sources can be edited"
            )
        candidate = replace(
            self,
            status=RecordStatus.DRAFT,
            source_type=self.source_type if source_type is None else source_type,
            title=_optional_text(title, "title", limit=500),
            document_number=_optional_text(
                document_number, "document_number", limit=200
            ),
            revision=_optional_text(revision, "revision", limit=200),
            source=SourceLocation(
                locator=_optional_text(
                    source_locator, "source.locator", limit=2048
                ),
                publisher=_optional_text(
                    source_publisher, "source.publisher", limit=256
                ),
            ),
            license_class=license_class,
            license_note=_optional_text(license_note, "license.note", limit=2000),
            evidence=evidence,
            preparation_note=_optional_text(
                preparation_note, "preparation_note", limit=4000
            ),
            review=Review(),
            supersedes=_optional_text(supersedes, "supersedes", limit=40),
        )
        return candidate.validate()

    def submit(self) -> SourceRecord:
        status, history, review = _submit(self.status, self.review_history)
        return replace(
            self, status=status, review_history=history, review=review
        ).validate()

    def approve(self, comment: str | None) -> SourceRecord:
        status, history, review = _approve(
            self.status,
            self.review_history,
            comment,
            missing_fields=self.missing_fields,
        )
        return replace(
            self, status=status, review_history=history, review=review
        ).validate()

    def reject(self, comment: str | None) -> SourceRecord:
        status, history, review = _reject(
            self.status, self.review_history, comment
        )
        return replace(
            self, status=status, review_history=history, review=review
        ).validate()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "source_type": self.source_type.value,
            "status": self.status.value,
            "prepared_by": self.prepared_by.value,
            "title": self.title,
            "document_number": self.document_number,
            "revision": self.revision,
            "source": self.source.to_dict(),
            "license": {
                "class": self.license_class.value,
                "note": self.license_note,
            },
            "evidence": self.evidence.to_dict(),
            "preparation_note": self.preparation_note,
            "review_history": [event.to_dict() for event in self.review_history],
            "review": self.review.to_dict(),
            "supersedes": self.supersedes,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def revision_token(self) -> str:
        return _revision_token(self.to_dict())


@dataclass(frozen=True, slots=True)
class EntityRecord:
    id: str
    kind: EntityKind
    prepared_by: PreparedBy
    raw_name: str | None = None
    normalized_key: str | None = None
    manufacturer_id: str | None = None
    raw_mpn: str | None = None
    normalized_mpn: str | None = None
    family: str | None = None
    note: str | None = None
    schema_version: int = ENTITY_SCHEMA_VERSION

    @classmethod
    def manufacturer(
        cls, entity_id: str, raw_name: str, *, prepared_by: PreparedBy
    ) -> EntityRecord:
        return cls(
            id=entity_id,
            kind=EntityKind.MANUFACTURER,
            prepared_by=prepared_by,
            raw_name=_required_text(raw_name, "raw_name", limit=300),
            normalized_key=normalize_lookup(raw_name),
        ).validate()

    @classmethod
    def component(
        cls,
        entity_id: str,
        manufacturer_id: str,
        raw_mpn: str,
        *,
        family: str | None = None,
        prepared_by: PreparedBy,
    ) -> EntityRecord:
        return cls(
            id=entity_id,
            kind=EntityKind.COMPONENT,
            prepared_by=prepared_by,
            manufacturer_id=manufacturer_id,
            raw_mpn=_required_text(raw_mpn, "raw_mpn", limit=300),
            normalized_mpn=normalize_lookup(raw_mpn),
            family=_optional_text(family, "family", limit=300),
        ).validate()

    @classmethod
    def package(
        cls, entity_id: str, raw_name: str, *, prepared_by: PreparedBy
    ) -> EntityRecord:
        return cls(
            id=entity_id,
            kind=EntityKind.PACKAGE,
            prepared_by=prepared_by,
            raw_name=_required_text(raw_name, "raw_name", limit=300),
            normalized_key=normalize_lookup(raw_name),
        ).validate()

    @classmethod
    def from_dict(cls, value: object) -> EntityRecord:
        data = _required_mapping(value, "entity record")
        allowed = {
            "schema_version",
            "id",
            "kind",
            "prepared_by",
            "raw_name",
            "normalized_key",
            "manufacturer_id",
            "raw_mpn",
            "normalized_mpn",
            "family",
            "note",
        }
        _reject_extra_keys(data, allowed, "entity record")
        if data.get("schema_version") != ENTITY_SCHEMA_VERSION:
            raise RecordValidationError(
                f"entity schema_version must equal {ENTITY_SCHEMA_VERSION}"
            )
        return cls(
            schema_version=ENTITY_SCHEMA_VERSION,
            id=_required_text(data.get("id"), "id", limit=45),
            kind=EntityKind(_enum_value(EntityKind, data.get("kind"), "kind")),
            prepared_by=PreparedBy(
                _enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")
            ),
            raw_name=_optional_text(data.get("raw_name"), "raw_name", limit=300),
            normalized_key=_optional_text(
                data.get("normalized_key"), "normalized_key", limit=500
            ),
            manufacturer_id=_optional_text(
                data.get("manufacturer_id"), "manufacturer_id", limit=45
            ),
            raw_mpn=_optional_text(data.get("raw_mpn"), "raw_mpn", limit=300),
            normalized_mpn=_optional_text(
                data.get("normalized_mpn"), "normalized_mpn", limit=500
            ),
            family=_optional_text(data.get("family"), "family", limit=300),
            note=_optional_text(data.get("note"), "note", limit=2000),
        ).validate()

    @classmethod
    def from_json(cls, payload: str) -> EntityRecord:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RecordValidationError(
                f"entity record is not valid JSON: {error.msg}"
            ) from error
        return cls.from_dict(value)

    def validate(self) -> EntityRecord:
        if self.schema_version != ENTITY_SCHEMA_VERSION:
            raise RecordValidationError(
                f"entity schema_version must equal {ENTITY_SCHEMA_VERSION}"
            )
        if ENTITY_ID_PATTERN.fullmatch(self.id) is None:
            raise RecordValidationError(
                "entity id must match ent_<24-32 lowercase hex characters>"
            )
        _validate_enum(self.kind, EntityKind, "kind")
        _validate_enum(self.prepared_by, PreparedBy, "prepared_by")
        for value, label, limit in (
            (self.raw_name, "raw_name", 300),
            (self.normalized_key, "normalized_key", 500),
            (self.manufacturer_id, "manufacturer_id", 45),
            (self.raw_mpn, "raw_mpn", 300),
            (self.normalized_mpn, "normalized_mpn", 500),
            (self.family, "family", 300),
            (self.note, "note", 2000),
        ):
            if _optional_text(value, label, limit=limit) != value:
                raise RecordValidationError(f"{label} must be normalized")

        if self.kind in {EntityKind.MANUFACTURER, EntityKind.PACKAGE}:
            if self.raw_name is None or self.normalized_key is None:
                raise RecordValidationError(
                    f"{self.kind.value} requires raw_name and normalized_key"
                )
            if normalize_lookup(self.raw_name) != self.normalized_key:
                raise RecordValidationError("normalized_key does not match raw_name")
            if any(
                value is not None
                for value in (
                    self.manufacturer_id,
                    self.raw_mpn,
                    self.normalized_mpn,
                    self.family,
                )
            ):
                raise RecordValidationError(
                    f"{self.kind.value} contains component-only fields"
                )
        elif self.kind is EntityKind.COMPONENT:
            if (
                self.manufacturer_id is None
                or ENTITY_ID_PATTERN.fullmatch(self.manufacturer_id) is None
            ):
                raise RecordValidationError(
                    "COMPONENT requires a valid manufacturer_id"
                )
            if self.raw_mpn is None or self.normalized_mpn is None:
                raise RecordValidationError(
                    "COMPONENT requires raw_mpn and normalized_mpn"
                )
            if normalize_lookup(self.raw_mpn) != self.normalized_mpn:
                raise RecordValidationError(
                    "normalized_mpn does not match raw_mpn"
                )
            if self.raw_name is not None or self.normalized_key is not None:
                raise RecordValidationError(
                    "COMPONENT must use raw_mpn, not raw_name"
                )
        return self

    @property
    def identity_key(self) -> tuple[str, ...]:
        if self.kind is EntityKind.COMPONENT:
            assert self.manufacturer_id is not None
            assert self.normalized_mpn is not None
            return (self.kind.value, self.manufacturer_id, self.normalized_mpn)
        assert self.normalized_key is not None
        return (self.kind.value, self.normalized_key)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "kind": self.kind.value,
            "prepared_by": self.prepared_by.value,
            "raw_name": self.raw_name,
            "normalized_key": self.normalized_key,
            "manufacturer_id": self.manufacturer_id,
            "raw_mpn": self.raw_mpn,
            "normalized_mpn": self.normalized_mpn,
            "family": self.family,
            "note": self.note,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def revision_token(self) -> str:
        return _revision_token(self.to_dict())


@dataclass(frozen=True, slots=True)
class EvidenceAnchor:
    source_id: str
    page: int
    coordinate_space: str = "PDF_NORMALIZED_V1"
    bbox: tuple[float, float, float, float] | None = None
    quote: str | None = None
    quote_sha256: str | None = None

    @classmethod
    def create(
        cls,
        source_id: str,
        page: int,
        *,
        bbox: tuple[float, float, float, float] | None = None,
        quote: str | None = None,
    ) -> EvidenceAnchor:
        normalized_quote = _optional_verbatim_text(quote, "quote", limit=8000)
        digest = (
            None
            if normalized_quote is None
            else hashlib.sha256(normalized_quote.encode("utf-8")).hexdigest()
        )
        normalized_bbox = (
            None if bbox is None else tuple(float(value) for value in bbox)
        )
        return cls(
            source_id=source_id,
            page=page,
            bbox=normalized_bbox,  # type: ignore[arg-type]
            quote=normalized_quote,
            quote_sha256=digest,
        ).validate()

    @classmethod
    def from_dict(cls, value: object) -> EvidenceAnchor:
        data = _required_mapping(value, "evidence anchor")
        _reject_extra_keys(
            data,
            {
                "source_id",
                "page",
                "coordinate_space",
                "bbox",
                "quote",
                "quote_sha256",
            },
            "evidence anchor",
        )
        raw_bbox = data.get("bbox")
        bbox: tuple[float, float, float, float] | None
        if raw_bbox is None:
            bbox = None
        elif (
            isinstance(raw_bbox, list)
            and len(raw_bbox) == 4
            and all(
                isinstance(item, (int, float)) and not isinstance(item, bool)
                for item in raw_bbox
            )
        ):
            bbox = tuple(float(item) for item in raw_bbox)  # type: ignore[assignment]
        else:
            raise RecordValidationError(
                "evidence anchor bbox must be four numbers or null"
            )
        page = data.get("page")
        if not isinstance(page, int) or isinstance(page, bool):
            raise RecordValidationError("evidence anchor page must be an integer")
        return cls(
            source_id=_required_text(data.get("source_id"), "source_id", limit=40),
            page=page,
            coordinate_space=_required_text(
                data.get("coordinate_space"), "coordinate_space", limit=50
            ),
            bbox=bbox,
            quote=_optional_verbatim_text(data.get("quote"), "quote", limit=8000),
            quote_sha256=_optional_text(
                data.get("quote_sha256"), "quote_sha256", limit=64
            ),
        ).validate()

    def validate(self) -> EvidenceAnchor:
        if SOURCE_ID_PATTERN.fullmatch(self.source_id) is None:
            raise RecordValidationError("evidence anchor source_id is invalid")
        if not isinstance(self.page, int) or isinstance(self.page, bool) or self.page < 1:
            raise RecordValidationError("evidence anchor page must be 1-based")
        if self.coordinate_space != "PDF_NORMALIZED_V1":
            raise RecordValidationError(
                "unsupported evidence anchor coordinate_space"
            )
        if self.bbox is not None:
            if not isinstance(self.bbox, tuple) or len(self.bbox) != 4:
                raise RecordValidationError(
                    "evidence anchor bbox must be four numbers or null"
                )
            if not all(
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                for value in self.bbox
            ):
                raise RecordValidationError("evidence anchor bbox must be finite")
            x0, y0, x1, y1 = self.bbox
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                raise RecordValidationError(
                    "evidence anchor bbox must be normalized to [0,1]"
                )
        if _optional_verbatim_text(self.quote, "quote", limit=8000) != self.quote:
            raise RecordValidationError("evidence anchor quote is invalid")
        if self.quote is None:
            if self.quote_sha256 is not None:
                raise RecordValidationError("quote_sha256 requires quote")
        else:
            expected = hashlib.sha256(self.quote.encode("utf-8")).hexdigest()
            if self.quote_sha256 != expected:
                raise RecordValidationError("quote_sha256 does not match quote")
        return self

    @property
    def complete(self) -> bool:
        return (
            self.bbox is not None
            and self.quote is not None
            and self.quote_sha256 is not None
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "page": self.page,
            "coordinate_space": self.coordinate_space,
            "bbox": None if self.bbox is None else list(self.bbox),
            "quote": self.quote,
            "quote_sha256": self.quote_sha256,
        }


@dataclass(frozen=True, slots=True)
class ComponentPinPayload:
    component_id: str
    package_id: str
    pin_number: str
    pin_name: str | None
    primary_function: str
    alternate_functions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: object) -> ComponentPinPayload:
        data = _required_mapping(value, "component pin payload")
        _reject_extra_keys(
            data,
            {
                "component_id",
                "package_id",
                "pin_number",
                "pin_name",
                "primary_function",
                "alternate_functions",
            },
            "component pin payload",
        )
        return cls(
            component_id=_required_text(
                data.get("component_id"), "component_id", limit=45
            ),
            package_id=_required_text(
                data.get("package_id"), "package_id", limit=45
            ),
            pin_number=_required_text(
                data.get("pin_number"), "pin_number", limit=100
            ),
            pin_name=_optional_text(data.get("pin_name"), "pin_name", limit=200),
            primary_function=_required_text(
                data.get("primary_function"), "primary_function", limit=500
            ),
            alternate_functions=_tuple_text(
                data.get("alternate_functions"),
                "alternate_functions",
                item_limit=500,
            ),
        ).validate()

    def validate(self) -> ComponentPinPayload:
        if ENTITY_ID_PATTERN.fullmatch(self.component_id) is None:
            raise RecordValidationError("component pin component_id is invalid")
        if ENTITY_ID_PATTERN.fullmatch(self.package_id) is None:
            raise RecordValidationError("component pin package_id is invalid")
        for value, label, limit in (
            (self.pin_number, "pin_number", 100),
            (self.pin_name, "pin_name", 200),
            (self.primary_function, "primary_function", 500),
        ):
            normalized = (
                _required_text(value, label, limit=limit)
                if label != "pin_name"
                else _optional_text(value, label, limit=limit)
            )
            if normalized != value:
                raise RecordValidationError(f"{label} must be normalized")
        _validate_text_tuple(
            self.alternate_functions, "alternate_functions", item_limit=500
        )
        return self

    @property
    def subject_entity_ids(self) -> tuple[str, ...]:
        return (self.component_id, self.package_id)

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (
            FactType.COMPONENT_PIN.value,
            self.component_id,
            self.package_id,
            self.pin_number,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "package_id": self.package_id,
            "pin_number": self.pin_number,
            "pin_name": self.pin_name,
            "primary_function": self.primary_function,
            "alternate_functions": list(self.alternate_functions),
        }


@dataclass(frozen=True, slots=True)
class ParameterLimitPayload:
    component_id: str
    parameter: str
    limit_kind: ParameterLimitKind
    minimum: float | int | None
    typical: float | int | None
    maximum: float | int | None
    unit: str

    @staticmethod
    def _number(value: object, label: str) -> float | int | None:
        if value is None:
            return None
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise RecordValidationError(
                f"{label} must be a finite JSON number or null"
            )
        return value

    @classmethod
    def from_dict(cls, value: object) -> ParameterLimitPayload:
        data = _required_mapping(value, "parameter limit payload")
        _reject_extra_keys(
            data,
            {
                "component_id",
                "parameter",
                "limit_kind",
                "minimum",
                "typical",
                "maximum",
                "unit",
            },
            "parameter limit payload",
        )
        return cls(
            component_id=_required_text(
                data.get("component_id"), "component_id", limit=45
            ),
            parameter=_required_text(
                data.get("parameter"), "parameter", limit=300
            ),
            limit_kind=ParameterLimitKind(
                _enum_value(
                    ParameterLimitKind, data.get("limit_kind"), "limit_kind"
                )
            ),
            minimum=cls._number(data.get("minimum"), "minimum"),
            typical=cls._number(data.get("typical"), "typical"),
            maximum=cls._number(data.get("maximum"), "maximum"),
            unit=_required_text(data.get("unit"), "unit", limit=100),
        ).validate()

    def validate(self) -> ParameterLimitPayload:
        if ENTITY_ID_PATTERN.fullmatch(self.component_id) is None:
            raise RecordValidationError("parameter limit component_id is invalid")
        _validate_enum(self.limit_kind, ParameterLimitKind, "limit_kind")
        if _required_text(self.parameter, "parameter", limit=300) != self.parameter:
            raise RecordValidationError("parameter must be normalized")
        if _required_text(self.unit, "unit", limit=100) != self.unit:
            raise RecordValidationError("unit must be normalized")
        if self.minimum is self.typical is self.maximum is None:
            raise RecordValidationError(
                "parameter limit requires at least one numeric value"
            )
        values = (
            ("minimum", self.minimum),
            ("typical", self.typical),
            ("maximum", self.maximum),
        )
        for label, value in values:
            self._number(value, label)
        ordered = [float(item) for _label, item in values if item is not None]
        if ordered != sorted(ordered):
            raise RecordValidationError(
                "parameter limit values must satisfy minimum <= typical <= maximum"
            )
        return self

    @property
    def subject_entity_ids(self) -> tuple[str, ...]:
        return (self.component_id,)

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (
            FactType.PARAMETER_LIMIT.value,
            self.component_id,
            normalize_lookup(self.parameter),
            self.limit_kind.value,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "parameter": self.parameter,
            "limit_kind": self.limit_kind.value,
            "minimum": self.minimum,
            "typical": self.typical,
            "maximum": self.maximum,
            "unit": self.unit,
        }


FactPayload = ComponentPinPayload | ParameterLimitPayload


@dataclass(frozen=True, slots=True)
class FactRecord:
    id: str
    fact_type: FactType
    payload: FactPayload
    prepared_by: PreparedBy
    status: RecordStatus = RecordStatus.DRAFT
    conditions: tuple[str, ...] = ()
    applicability: tuple[str, ...] = ()
    evidence_anchors: tuple[EvidenceAnchor, ...] = ()
    review_history: tuple[ReviewEvent, ...] = ()
    review: Review = Review()
    supersedes: str | None = None
    schema_version: int = FACT_SCHEMA_VERSION

    @classmethod
    def new(
        cls,
        fact_id: str,
        *,
        fact_type: FactType,
        payload: FactPayload,
        prepared_by: PreparedBy,
        conditions: tuple[str, ...] = (),
        applicability: tuple[str, ...] = (),
        evidence_anchors: tuple[EvidenceAnchor, ...] = (),
    ) -> FactRecord:
        return cls(
            id=fact_id,
            fact_type=fact_type,
            payload=payload,
            prepared_by=prepared_by,
            conditions=conditions,
            applicability=applicability,
            evidence_anchors=evidence_anchors,
        ).validate()

    @classmethod
    def from_dict(cls, value: object) -> FactRecord:
        data = _required_mapping(value, "fact record")
        allowed = {
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
        }
        _reject_extra_keys(data, allowed, "fact record")
        if data.get("schema_version") != FACT_SCHEMA_VERSION:
            raise RecordValidationError(
                f"fact schema_version must equal {FACT_SCHEMA_VERSION}"
            )
        fact_type = FactType(
            _enum_value(FactType, data.get("fact_type"), "fact_type")
        )
        payload: FactPayload
        if fact_type is FactType.COMPONENT_PIN:
            payload = ComponentPinPayload.from_dict(data.get("payload"))
        else:
            payload = ParameterLimitPayload.from_dict(data.get("payload"))
        raw_history = data.get("review_history")
        raw_anchors = data.get("evidence_anchors")
        if not isinstance(raw_history, list):
            raise RecordValidationError("review_history must be an array")
        if not isinstance(raw_anchors, list):
            raise RecordValidationError("evidence_anchors must be an array")
        return cls(
            schema_version=FACT_SCHEMA_VERSION,
            id=_required_text(data.get("id"), "id", limit=50),
            fact_type=fact_type,
            payload=payload,
            prepared_by=PreparedBy(
                _enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")
            ),
            status=RecordStatus(
                _enum_value(RecordStatus, data.get("status"), "status")
            ),
            conditions=_tuple_text(data.get("conditions"), "conditions"),
            applicability=_tuple_text(data.get("applicability"), "applicability"),
            evidence_anchors=tuple(
                EvidenceAnchor.from_dict(item) for item in raw_anchors
            ),
            review_history=tuple(
                ReviewEvent.from_dict(item) for item in raw_history
            ),
            review=Review.from_dict(data.get("review")),
            supersedes=_optional_text(data.get("supersedes"), "supersedes", limit=50),
        ).validate()

    @classmethod
    def from_json(cls, payload: str) -> FactRecord:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RecordValidationError(
                f"fact record is not valid JSON: {error.msg}"
            ) from error
        return cls.from_dict(value)

    def validate(self) -> FactRecord:
        if self.schema_version != FACT_SCHEMA_VERSION:
            raise RecordValidationError(
                f"fact schema_version must equal {FACT_SCHEMA_VERSION}"
            )
        if FACT_ID_PATTERN.fullmatch(self.id) is None:
            raise RecordValidationError(
                "fact id must match fact_<24-32 lowercase hex characters>"
            )
        _validate_enum(self.fact_type, FactType, "fact_type")
        _validate_enum(self.prepared_by, PreparedBy, "prepared_by")
        if self.supersedes is not None:
            if FACT_ID_PATTERN.fullmatch(self.supersedes) is None:
                raise RecordValidationError(
                    "fact supersedes must be a valid fact id"
                )
            if self.supersedes == self.id:
                raise RecordValidationError("a fact cannot supersede itself")
        if self.fact_type is FactType.COMPONENT_PIN:
            if not isinstance(self.payload, ComponentPinPayload):
                raise RecordValidationError(
                    "COMPONENT_PIN requires ComponentPinPayload"
                )
        elif not isinstance(self.payload, ParameterLimitPayload):
            raise RecordValidationError(
                "PARAMETER_LIMIT requires ParameterLimitPayload"
            )
        self.payload.validate()
        _validate_text_tuple(self.conditions, "conditions")
        _validate_text_tuple(self.applicability, "applicability")
        if not isinstance(self.evidence_anchors, tuple):
            raise RecordValidationError("evidence_anchors must be a tuple")
        for anchor in self.evidence_anchors:
            if not isinstance(anchor, EvidenceAnchor):
                raise RecordValidationError(
                    "evidence_anchors contains an unsupported value"
                )
            anchor.validate()
        _validate_review_state(
            self.status,
            self.review_history,
            self.review,
            missing_fields=self.missing_fields,
        )
        return self

    @property
    def missing_fields(self) -> tuple[str, ...]:
        if not self.evidence_anchors:
            return ("evidence_anchors",)
        if not all(anchor.complete for anchor in self.evidence_anchors):
            return ("complete_evidence_anchor",)
        return ()

    @property
    def subject_entity_ids(self) -> tuple[str, ...]:
        return self.payload.subject_entity_ids

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(anchor.source_id for anchor in self.evidence_anchors))

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (
            *self.payload.semantic_key,
            tuple(self.conditions),
            tuple(self.applicability),
        )

    def edit(
        self,
        *,
        payload: FactPayload | None = None,
        conditions: tuple[str, ...] | None = None,
        applicability: tuple[str, ...] | None = None,
        evidence_anchors: tuple[EvidenceAnchor, ...] | None = None,
        supersedes: str | None | object = _UNSET,
    ) -> FactRecord:
        if self.status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            raise RecordTransitionError(
                "only DRAFT or REJECTED facts can be edited"
            )
        return replace(
            self,
            status=RecordStatus.DRAFT,
            payload=self.payload if payload is None else payload,
            conditions=self.conditions if conditions is None else conditions,
            applicability=(
                self.applicability if applicability is None else applicability
            ),
            evidence_anchors=(
                self.evidence_anchors
                if evidence_anchors is None
                else evidence_anchors
            ),
            supersedes=(
                self.supersedes
                if supersedes is _UNSET
                else _optional_text(supersedes, "supersedes", limit=50)
            ),
            review=Review(),
        ).validate()

    def submit(self) -> FactRecord:
        status, history, review = _submit(self.status, self.review_history)
        return replace(
            self, status=status, review_history=history, review=review
        ).validate()

    def approve(self, comment: str | None) -> FactRecord:
        status, history, review = _approve(
            self.status,
            self.review_history,
            comment,
            missing_fields=self.missing_fields,
        )
        return replace(
            self, status=status, review_history=history, review=review
        ).validate()

    def reject(self, comment: str | None) -> FactRecord:
        status, history, review = _reject(
            self.status, self.review_history, comment
        )
        return replace(
            self, status=status, review_history=history, review=review
        ).validate()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "fact_type": self.fact_type.value,
            "status": self.status.value,
            "prepared_by": self.prepared_by.value,
            "payload": self.payload.to_dict(),
            "conditions": list(self.conditions),
            "applicability": list(self.applicability),
            "evidence_anchors": [
                anchor.to_dict() for anchor in self.evidence_anchors
            ],
            "review_history": [event.to_dict() for event in self.review_history],
            "review": self.review.to_dict(),
            "supersedes": self.supersedes,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def revision_token(self) -> str:
        return _revision_token(self.to_dict())
