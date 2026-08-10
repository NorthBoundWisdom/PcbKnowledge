"""Deterministic Git-native authority models for PCB engineering knowledge."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence

SOURCE_SCHEMA_VERSION = 1
ENTITY_SCHEMA_VERSION = 1
FACT_SCHEMA_VERSION = 1
SCHEMA_VERSION = SOURCE_SCHEMA_VERSION

_SOURCE_ID = re.compile(r"pk_[0-9a-f]{24,32}\Z")
_ENTITY_ID = re.compile(r"ent_[0-9a-f]{24,32}\Z")
_FACT_ID = re.compile(r"fact_[0-9a-f]{24,32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LOOKUP_STRIP = re.compile(r"[^A-Z0-9]+")

class RecordValidationError(ValueError):
    """An authority object is malformed or violates an invariant."""

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
    OPEN = "OPEN_LICENSE"

    @classmethod
    def _missing_(cls, value: object) -> LicenseClass | None:
        if value == "OPEN":
            return cls.OPEN_LICENSE
        return None

    @property
    def agent_processing_allowed(self) -> bool:
        return self in {LicenseClass.PUBLIC_REFERENCE, LicenseClass.OPEN_LICENSE, LicenseClass.INTERNAL}

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
        raise RecordValidationError(f"{label} contains unsupported fields: {', '.join(sorted(extras))}")

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

def _tuple_text(value: object, label: str, *, item_limit: int = 500) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RecordValidationError(f"{label} must be an array")
    return tuple(_required_text(item, f"{label} item", limit=item_limit) for item in value)

def normalize_lookup(value: str) -> str:
    raw = _required_text(value, "lookup value", limit=500).upper()
    normalized = _LOOKUP_STRIP.sub("", raw)
    if not normalized:
        raise RecordValidationError("lookup value normalizes to empty")
    return normalized

def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

def _revision_token(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()

def _deterministic_id(prefix: str, namespace: str, key: str) -> str:
    normalized = _required_text(key, "idempotency_key", limit=500)
    digest = hashlib.sha256(f"pcbknowledge:{namespace}\0{normalized}".encode()).hexdigest()
    return f"{prefix}{digest[:24]}"

def deterministic_record_id(idempotency_key: str) -> str:
    return _deterministic_id("pk_", "source-v1", idempotency_key)

def deterministic_entity_id(kind: EntityKind, idempotency_key: str) -> str:
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
        _reject_extra_keys(data, {"path", "sha256", "byte_size", "media_type"}, "evidence")
        path = _optional_text(data.get("path"), "evidence.path", limit=256)
        sha256 = _optional_text(data.get("sha256"), "evidence.sha256", limit=64)
        byte_size = data.get("byte_size")
        media_type = _optional_text(data.get("media_type"), "evidence.media_type", limit=64)
        values = (path, sha256, byte_size, media_type)
        if all(item is None for item in values):
            return cls()
        if any(item is None for item in values):
            raise RecordValidationError("evidence fields must be either all present or all null")
        if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size <= 0:
            raise RecordValidationError("evidence.byte_size must be a positive integer")
        assert path is not None and sha256 is not None and media_type is not None
        if _SHA256.fullmatch(sha256) is None:
            raise RecordValidationError("evidence.sha256 must be lowercase SHA-256")
        expected = f"evidence/sha256/{sha256[:2]}/{sha256}.pdf"
        if path != expected:
            raise RecordValidationError("evidence.path must be derived from evidence.sha256")
        if media_type != "application/pdf":
            raise RecordValidationError("only application/pdf evidence is supported")
        return cls(path, sha256, byte_size, media_type)

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "sha256": self.sha256, "byte_size": self.byte_size, "media_type": self.media_type}

    @property
    def present(self) -> bool:
        return self.sha256 is not None

@dataclass(frozen=True, slots=True)
class Review:
    decision: ReviewDecision | None = None
    comment: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> Review:
        data = _required_mapping(value, "review")
        _reject_extra_keys(data, {"decision", "comment"}, "review")
        raw = data.get("decision")
        decision = None if raw is None else ReviewDecision(_enum_value(ReviewDecision, raw, "review.decision"))
        comment = _optional_text(data.get("comment"), "review.comment", limit=4000)
        if decision is ReviewDecision.REJECTED and comment is None:
            raise RecordValidationError("a rejected review requires comment")
        if decision is None and comment is not None:
            raise RecordValidationError("review.comment requires review.decision")
        return cls(decision, comment)

    def to_dict(self) -> dict[str, object]:
        return {"decision": None if self.decision is None else self.decision.value, "comment": self.comment}

@dataclass(frozen=True, slots=True)
class ReviewEvent:
    action: ReviewAction
    comment: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> ReviewEvent:
        data = _required_mapping(value, "review_history item")
        _reject_extra_keys(data, {"action", "comment"}, "review_history item")
        action = ReviewAction(_enum_value(ReviewAction, data.get("action"), "review_history.action"))
        comment = _optional_text(data.get("comment"), "review_history.comment", limit=4000)
        return cls(action, comment).validate()

    def validate(self) -> ReviewEvent:
        if self.action is ReviewAction.REJECTED and self.comment is None:
            raise RecordValidationError("a rejected review history event requires comment")
        if self.action is ReviewAction.SUBMITTED and self.comment is not None:
            raise RecordValidationError("a submitted review history event cannot carry comment")
        if self.comment is not None and _optional_text(self.comment, "review_history.comment", limit=4000) != self.comment:
            raise RecordValidationError("review_history.comment must be normalized")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"action": self.action.value, "comment": self.comment}

def _review_last_action(history: Sequence[ReviewEvent]) -> ReviewAction | None:
    index = 0
    last: ReviewAction | None = None
    while index < len(history):
        submitted = history[index].validate()
        if submitted.action is not ReviewAction.SUBMITTED:
            raise RecordValidationError("review history must start or resume with SUBMITTED")
        last = submitted.action
        index += 1
        if index == len(history):
            break
        decision = history[index].validate()
        if decision.action not in {ReviewAction.APPROVED, ReviewAction.REJECTED}:
            raise RecordValidationError("review history requires APPROVED or REJECTED after SUBMITTED")
        last = decision.action
        index += 1
        if decision.action is ReviewAction.APPROVED and index != len(history):
            raise RecordValidationError("review history cannot continue after approval")
    return last

def _validate_review_state(status: RecordStatus, history: tuple[ReviewEvent, ...], review: Review, *, missing_fields: Sequence[str] = ()) -> None:
    last = _review_last_action(history)
    if status is RecordStatus.DRAFT:
        if last not in {None, ReviewAction.REJECTED}:
            raise RecordValidationError("DRAFT review history must be empty or end with REJECTED")
        if review != Review():
            raise RecordValidationError("DRAFT cannot carry a current review decision")
    elif status is RecordStatus.READY_FOR_REVIEW:
        if last is not ReviewAction.SUBMITTED:
            raise RecordValidationError("READY_FOR_REVIEW requires a trailing SUBMITTED event")
        if review != Review():
            raise RecordValidationError("READY_FOR_REVIEW cannot carry a current review decision")
    elif status is RecordStatus.APPROVED:
        if last is not ReviewAction.APPROVED:
            raise RecordValidationError("APPROVED requires a trailing APPROVED review event")
        expected = Review(ReviewDecision.APPROVED, history[-1].comment)
        if review != expected:
            raise RecordValidationError("APPROVED current review must match its trailing history event")
        if missing_fields:
            raise RecordValidationError("APPROVED is missing required fields: " + ", ".join(missing_fields))
    elif status is RecordStatus.REJECTED:
        if last is not ReviewAction.REJECTED:
            raise RecordValidationError("REJECTED requires a trailing REJECTED review event")
        expected = Review(ReviewDecision.REJECTED, history[-1].comment)
        if review != expected:
            raise RecordValidationError("REJECTED current review must match its trailing history event")

def _submit(status: RecordStatus, history: tuple[ReviewEvent, ...]) -> tuple[RecordStatus, tuple[ReviewEvent, ...], Review]:
    if status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
        raise RecordTransitionError("only DRAFT or REJECTED records can be submitted")
    return RecordStatus.READY_FOR_REVIEW, (*history, ReviewEvent(ReviewAction.SUBMITTED)), Review()

def _approve(status: RecordStatus, history: tuple[ReviewEvent, ...], comment: str | None, *, missing_fields: Sequence[str]) -> tuple[RecordStatus, tuple[ReviewEvent, ...], Review]:
    if status is not RecordStatus.READY_FOR_REVIEW:
        raise RecordTransitionError("only READY_FOR_REVIEW records can be approved")
    if missing_fields:
        raise RecordTransitionError("cannot approve while fields are missing: " + ", ".join(missing_fields))
    normalized = _optional_text(comment, "review.comment", limit=4000)
    event = ReviewEvent(ReviewAction.APPROVED, normalized)
    return RecordStatus.APPROVED, (*history, event), Review(ReviewDecision.APPROVED, normalized)

def _reject(status: RecordStatus, history: tuple[ReviewEvent, ...], comment: str | None) -> tuple[RecordStatus, tuple[ReviewEvent, ...], Review]:
    if status is not RecordStatus.READY_FOR_REVIEW:
        raise RecordTransitionError("only READY_FOR_REVIEW records can be rejected")
    normalized = _optional_text(comment, "review.comment", limit=4000)
    if normalized is None:
        raise RecordTransitionError("rejection requires a review comment")
    event = ReviewEvent(ReviewAction.REJECTED, normalized)
    return RecordStatus.REJECTED, (*history, event), Review(ReviewDecision.REJECTED, normalized)

@dataclass(frozen=True, slots=True)
class SourceLocation:
    locator: str | None = None
    publisher: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> SourceLocation:
        data = _required_mapping(value, "source")
        _reject_extra_keys(data, {"locator", "publisher"}, "source")
        return cls(_optional_text(data.get("locator"), "source.locator", limit=2048), _optional_text(data.get("publisher"), "source.publisher", limit=256))

    def to_dict(self) -> dict[str, object]:
        return {"locator": self.locator, "publisher": self.publisher}

Source = SourceLocation
