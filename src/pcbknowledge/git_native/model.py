"""Strict, deterministic file model for Git-native knowledge records."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Mapping


SCHEMA_VERSION = 2
_ID_PATTERN = re.compile(r"pk_[0-9a-f]{24,32}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_KEYS = {
    "schema_version",
    "id",
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


class RecordValidationError(ValueError):
    """The repository record is malformed or violates a domain invariant."""


class RecordTransitionError(ValueError):
    """The requested state transition is not allowed."""


class RecordStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PreparedBy(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"


class LicenseClass(StrEnum):
    UNKNOWN = "UNKNOWN"
    OPEN = "OPEN"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"

    @property
    def agent_processing_allowed(self) -> bool:
        """Whether repository policy permits Agent/model processing of source contents.

        Schema v2 intentionally keeps the existing four-value wire format. RESTRICTED is the
        executable local representation for material covered by ADR-015's
        LICENSED_BLOCKED_FOR_AI policy until the broader SourceRecord schema lands.
        """
        return self in {LicenseClass.OPEN, LicenseClass.INTERNAL}


class ReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReviewAction(StrEnum):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


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


def _enum_value(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    if not isinstance(value, str):
        raise RecordValidationError(f"{label} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise RecordValidationError(f"{label} has an unsupported value") from error


@dataclass(frozen=True, slots=True)
class Source:
    locator: str | None = None
    publisher: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> Source:
        data = _required_mapping(value, "source")
        _reject_extra_keys(data, {"locator", "publisher"}, "source")
        return cls(
            locator=_optional_text(data.get("locator"), "source.locator", limit=2048),
            publisher=_optional_text(data.get("publisher"), "source.publisher", limit=256),
        )

    def to_dict(self) -> dict[str, object]:
        return {"locator": self.locator, "publisher": self.publisher}


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
        if _SHA256_PATTERN.fullmatch(sha256) is None:
            raise RecordValidationError("evidence.sha256 must be lowercase SHA-256")
        expected_path = f"evidence/sha256/{sha256[:2]}/{sha256}.pdf"
        if path != expected_path:
            raise RecordValidationError("evidence.path must be derived from evidence.sha256")
        if media_type != "application/pdf":
            raise RecordValidationError("only application/pdf evidence is supported")
        return cls(path=path, sha256=sha256, byte_size=byte_size, media_type=media_type)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "media_type": self.media_type,
        }

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
        raw_decision = data.get("decision")
        decision = (
            None
            if raw_decision is None
            else ReviewDecision(_enum_value(ReviewDecision, raw_decision, "review.decision"))
        )
        comment = _optional_text(data.get("comment"), "review.comment", limit=4000)
        if decision is ReviewDecision.REJECTED and comment is None:
            raise RecordValidationError("a rejected record requires review.comment")
        if decision is None and comment is not None:
            raise RecordValidationError("review.comment requires review.decision")
        return cls(decision=decision, comment=comment)

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
        action = ReviewAction(
            _enum_value(ReviewAction, data.get("action"), "review_history.action")
        )
        comment = _optional_text(data.get("comment"), "review_history.comment", limit=4000)
        if action is ReviewAction.REJECTED and comment is None:
            raise RecordValidationError("a rejected review history event requires comment")
        if action is ReviewAction.SUBMITTED and comment is not None:
            raise RecordValidationError("a submitted review history event cannot carry comment")
        return cls(action=action, comment=comment).validate()

    def validate(self) -> ReviewEvent:
        if not isinstance(self.action, ReviewAction):
            raise RecordValidationError("review_history.action has an unsupported value")
        normalized = _optional_text(
            self.comment, "review_history.comment", limit=4000
        )
        if normalized != self.comment:
            raise RecordValidationError("review_history.comment must be normalized")
        if self.action is ReviewAction.REJECTED and self.comment is None:
            raise RecordValidationError("a rejected review history event requires comment")
        if self.action is ReviewAction.SUBMITTED and self.comment is not None:
            raise RecordValidationError("a submitted review history event cannot carry comment")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"action": self.action.value, "comment": self.comment}


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    id: str
    status: RecordStatus = RecordStatus.DRAFT
    prepared_by: PreparedBy = PreparedBy.HUMAN
    title: str | None = None
    document_number: str | None = None
    revision: str | None = None
    source: Source = Source()
    license_class: LicenseClass = LicenseClass.UNKNOWN
    license_note: str | None = None
    evidence: Evidence = Evidence()
    preparation_note: str | None = None
    review_history: tuple[ReviewEvent, ...] = ()
    review: Review = Review()
    supersedes: str | None = None
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(cls, record_id: str, *, prepared_by: PreparedBy) -> KnowledgeRecord:
        return cls(id=record_id, prepared_by=prepared_by).validate()

    @classmethod
    def from_dict(cls, value: object) -> KnowledgeRecord:
        data = _required_mapping(value, "record")
        _reject_extra_keys(data, _RECORD_KEYS, "record")
        schema_version = data.get("schema_version")
        if schema_version != SCHEMA_VERSION:
            raise RecordValidationError(f"schema_version must equal {SCHEMA_VERSION}")
        license_data = _required_mapping(data.get("license"), "license")
        _reject_extra_keys(license_data, {"class", "note"}, "license")
        raw_history = data.get("review_history")
        if not isinstance(raw_history, list):
            raise RecordValidationError("review_history must be an array")
        record = cls(
            schema_version=SCHEMA_VERSION,
            id=_optional_text(data.get("id"), "id", limit=35) or "",
            status=RecordStatus(_enum_value(RecordStatus, data.get("status"), "status")),
            prepared_by=PreparedBy(
                _enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")
            ),
            title=_optional_text(data.get("title"), "title", limit=500),
            document_number=_optional_text(
                data.get("document_number"), "document_number", limit=200
            ),
            revision=_optional_text(data.get("revision"), "revision", limit=200),
            source=Source.from_dict(data.get("source")),
            license_class=LicenseClass(
                _enum_value(LicenseClass, license_data.get("class"), "license.class")
            ),
            license_note=_optional_text(license_data.get("note"), "license.note", limit=2000),
            evidence=Evidence.from_dict(data.get("evidence")),
            preparation_note=_optional_text(
                data.get("preparation_note"), "preparation_note", limit=4000
            ),
            review_history=tuple(ReviewEvent.from_dict(item) for item in raw_history),
            review=Review.from_dict(data.get("review")),
            supersedes=_optional_text(data.get("supersedes"), "supersedes", limit=35),
        )
        return record.validate()

    @classmethod
    def from_json(cls, payload: str) -> KnowledgeRecord:
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RecordValidationError(f"record is not valid JSON: {error.msg}") from error
        return cls.from_dict(value)

    def validate(self) -> KnowledgeRecord:
        if _ID_PATTERN.fullmatch(self.id) is None:
            raise RecordValidationError("id must match pk_<24-32 lowercase hex characters>")
        if self.supersedes is not None:
            if _ID_PATTERN.fullmatch(self.supersedes) is None:
                raise RecordValidationError("supersedes must be a valid record id")
            if self.supersedes == self.id:
                raise RecordValidationError("a record cannot supersede itself")

        last_action = self._validate_review_history_sequence()
        if self.status is RecordStatus.DRAFT:
            if last_action not in {None, ReviewAction.REJECTED}:
                raise RecordValidationError(
                    "DRAFT review history must be empty or end with REJECTED"
                )
            if self.review != Review():
                raise RecordValidationError("DRAFT cannot carry a current review decision")
        elif self.status is RecordStatus.READY_FOR_REVIEW:
            if last_action is not ReviewAction.SUBMITTED:
                raise RecordValidationError("READY_FOR_REVIEW requires a trailing SUBMITTED event")
            if self.review != Review():
                raise RecordValidationError(
                    "READY_FOR_REVIEW cannot carry a current review decision"
                )
        elif self.status is RecordStatus.APPROVED:
            if last_action is not ReviewAction.APPROVED:
                raise RecordValidationError("APPROVED requires a trailing APPROVED review event")
            expected = Review(
                decision=ReviewDecision.APPROVED,
                comment=self.review_history[-1].comment,
            )
            if self.review != expected:
                raise RecordValidationError(
                    "APPROVED current review must match its trailing history event"
                )
            if self.missing_fields:
                raise RecordValidationError(
                    "APPROVED is missing required fields: " + ", ".join(self.missing_fields)
                )
        elif self.status is RecordStatus.REJECTED:
            if last_action is not ReviewAction.REJECTED:
                raise RecordValidationError("REJECTED requires a trailing REJECTED review event")
            expected = Review(
                decision=ReviewDecision.REJECTED,
                comment=self.review_history[-1].comment,
            )
            if self.review != expected:
                raise RecordValidationError(
                    "REJECTED current review must match its trailing history event"
                )
        return self

    def _validate_review_history_sequence(self) -> ReviewAction | None:
        index = 0
        last_action: ReviewAction | None = None
        while index < len(self.review_history):
            submitted = self.review_history[index].validate()
            if submitted.action is not ReviewAction.SUBMITTED:
                raise RecordValidationError(
                    "review history must start or resume with SUBMITTED"
                )
            last_action = submitted.action
            index += 1
            if index == len(self.review_history):
                break

            decision = self.review_history[index].validate()
            if decision.action not in {ReviewAction.APPROVED, ReviewAction.REJECTED}:
                raise RecordValidationError(
                    "review history requires APPROVED or REJECTED after SUBMITTED"
                )
            last_action = decision.action
            index += 1
            if decision.action is ReviewAction.APPROVED and index != len(self.review_history):
                raise RecordValidationError("review history cannot continue after approval")
        return last_action

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

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "status": self.status.value,
            "prepared_by": self.prepared_by.value,
            "title": self.title,
            "document_number": self.document_number,
            "revision": self.revision,
            "source": self.source.to_dict(),
            "license": {"class": self.license_class.value, "note": self.license_note},
            "evidence": self.evidence.to_dict(),
            "preparation_note": self.preparation_note,
            "review_history": [event.to_dict() for event in self.review_history],
            "review": self.review.to_dict(),
            "supersedes": self.supersedes,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

    @property
    def revision_token(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

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
    ) -> KnowledgeRecord:
        if self.status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            raise RecordTransitionError("only DRAFT or REJECTED records can be edited")
        candidate = replace(
            self,
            status=RecordStatus.DRAFT,
            title=_optional_text(title, "title", limit=500),
            document_number=_optional_text(document_number, "document_number", limit=200),
            revision=_optional_text(revision, "revision", limit=200),
            source=Source(
                locator=_optional_text(source_locator, "source.locator", limit=2048),
                publisher=_optional_text(source_publisher, "source.publisher", limit=256),
            ),
            license_class=license_class,
            license_note=_optional_text(license_note, "license.note", limit=2000),
            evidence=evidence,
            preparation_note=_optional_text(
                preparation_note, "preparation_note", limit=4000
            ),
            review=Review(),
            supersedes=_optional_text(supersedes, "supersedes", limit=35),
        )
        return candidate.validate()

    def submit(self) -> KnowledgeRecord:
        if self.status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}:
            raise RecordTransitionError("only DRAFT or REJECTED records can be submitted")
        history = (*self.review_history, ReviewEvent(action=ReviewAction.SUBMITTED))
        return replace(
            self,
            status=RecordStatus.READY_FOR_REVIEW,
            review_history=history,
            review=Review(),
        ).validate()

    def approve(self, comment: str | None) -> KnowledgeRecord:
        if self.status is not RecordStatus.READY_FOR_REVIEW:
            raise RecordTransitionError("only READY_FOR_REVIEW records can be approved")
        if self.missing_fields:
            raise RecordTransitionError(
                "cannot approve while fields are missing: " + ", ".join(self.missing_fields)
            )
        normalized = _optional_text(comment, "review.comment", limit=4000)
        history = (
            *self.review_history,
            ReviewEvent(action=ReviewAction.APPROVED, comment=normalized),
        )
        return replace(
            self,
            status=RecordStatus.APPROVED,
            review_history=history,
            review=Review(
                decision=ReviewDecision.APPROVED,
                comment=normalized,
            ),
        ).validate()

    def reject(self, comment: str | None) -> KnowledgeRecord:
        if self.status is not RecordStatus.READY_FOR_REVIEW:
            raise RecordTransitionError("only READY_FOR_REVIEW records can be rejected")
        normalized = _optional_text(comment, "review.comment", limit=4000)
        if normalized is None:
            raise RecordTransitionError("rejection requires a review comment")
        history = (
            *self.review_history,
            ReviewEvent(action=ReviewAction.REJECTED, comment=normalized),
        )
        return replace(
            self,
            status=RecordStatus.REJECTED,
            review_history=history,
            review=Review(decision=ReviewDecision.REJECTED, comment=normalized),
        ).validate()


def deterministic_record_id(idempotency_key: str) -> str:
    normalized = _optional_text(idempotency_key, "idempotency_key", limit=200)
    if normalized is None:
        raise RecordValidationError("idempotency_key is required")
    digest = hashlib.sha256(f"pcbknowledge-git-native-v1\0{normalized}".encode()).hexdigest()
    return f"pk_{digest[:24]}"
