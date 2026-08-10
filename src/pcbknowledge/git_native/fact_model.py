"""FactRecordV1 typed fact models."""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
import math
from .authority_common import *
from .authority_common import _ENTITY_ID, _FACT_ID, _approve, _canonical_json, _enum_value, _optional_text, _reject, _reject_extra_keys, _required_mapping, _required_text, _revision_token, _submit, _tuple_text, _validate_review_state
from .entity_model import EvidenceAnchor

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
        _reject_extra_keys(data, {"component_id", "package_id", "pin_number", "pin_name", "primary_function", "alternate_functions"}, "component pin payload")
        return cls(_required_text(data.get("component_id"), "component_id", limit=45), _required_text(data.get("package_id"), "package_id", limit=45), _required_text(data.get("pin_number"), "pin_number", limit=100), _optional_text(data.get("pin_name"), "pin_name", limit=200), _required_text(data.get("primary_function"), "primary_function", limit=500), _tuple_text(data.get("alternate_functions"), "alternate_functions", item_limit=500)).validate()

    def validate(self) -> ComponentPinPayload:
        if _ENTITY_ID.fullmatch(self.component_id) is None or _ENTITY_ID.fullmatch(self.package_id) is None:
            raise RecordValidationError("component pin payload entity IDs are invalid")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"component_id": self.component_id, "package_id": self.package_id, "pin_number": self.pin_number, "pin_name": self.pin_name, "primary_function": self.primary_function, "alternate_functions": list(self.alternate_functions)}

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (FactType.COMPONENT_PIN.value, self.component_id, self.package_id, self.pin_number)

@dataclass(frozen=True, slots=True)
class ParameterLimitPayload:
    component_id: str
    parameter: str
    limit_kind: ParameterLimitKind
    minimum: float | int | None
    typical: float | int | None
    maximum: float | int | None
    unit: str

    @classmethod
    def from_dict(cls, value: object) -> ParameterLimitPayload:
        data = _required_mapping(value, "parameter limit payload")
        _reject_extra_keys(data, {"component_id", "parameter", "limit_kind", "minimum", "typical", "maximum", "unit"}, "parameter limit payload")
        def number(name: str) -> float | int | None:
            raw = data.get(name)
            if raw is None: return None
            if not isinstance(raw, (int, float)) or isinstance(raw, bool) or not math.isfinite(float(raw)):
                raise RecordValidationError(f"{name} must be a finite JSON number or null")
            return raw
        return cls(_required_text(data.get("component_id"), "component_id", limit=45), _required_text(data.get("parameter"), "parameter", limit=300), ParameterLimitKind(_enum_value(ParameterLimitKind, data.get("limit_kind"), "limit_kind")), number("minimum"), number("typical"), number("maximum"), _required_text(data.get("unit"), "unit", limit=100)).validate()

    def validate(self) -> ParameterLimitPayload:
        if _ENTITY_ID.fullmatch(self.component_id) is None:
            raise RecordValidationError("parameter limit component_id is invalid")
        if self.minimum is self.typical is self.maximum is None:
            raise RecordValidationError("parameter limit requires at least one numeric value")
        for label, value in (("minimum", self.minimum), ("typical", self.typical), ("maximum", self.maximum)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))):
                raise RecordValidationError(f"{label} must be a finite JSON number")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"component_id": self.component_id, "parameter": self.parameter, "limit_kind": self.limit_kind.value, "minimum": self.minimum, "typical": self.typical, "maximum": self.maximum, "unit": self.unit}

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (FactType.PARAMETER_LIMIT.value, self.component_id, normalize_lookup(self.parameter), self.limit_kind.value)

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
    def new(cls, record_id: str, *, fact_type: FactType, payload: FactPayload, prepared_by: PreparedBy, conditions: tuple[str, ...] = (), applicability: tuple[str, ...] = (), evidence_anchors: tuple[EvidenceAnchor, ...] = ()) -> FactRecord:
        return cls(id=record_id, fact_type=fact_type, payload=payload, prepared_by=prepared_by, conditions=conditions, applicability=applicability, evidence_anchors=evidence_anchors).validate()

    @classmethod
    def from_dict(cls, value: object) -> FactRecord:
        data = _required_mapping(value, "fact record")
        allowed = {"schema_version", "id", "fact_type", "status", "prepared_by", "payload", "conditions", "applicability", "evidence_anchors", "review_history", "review", "supersedes"}
        _reject_extra_keys(data, allowed, "fact record")
        if data.get("schema_version") != FACT_SCHEMA_VERSION:
            raise RecordValidationError(f"fact schema_version must equal {FACT_SCHEMA_VERSION}")
        fact_type = FactType(_enum_value(FactType, data.get("fact_type"), "fact_type"))
        payload: FactPayload = ComponentPinPayload.from_dict(data.get("payload")) if fact_type is FactType.COMPONENT_PIN else ParameterLimitPayload.from_dict(data.get("payload"))
        raw_history, raw_anchors = data.get("review_history"), data.get("evidence_anchors")
        if not isinstance(raw_history, list) or not isinstance(raw_anchors, list):
            raise RecordValidationError("fact review_history and evidence_anchors must be arrays")
        return cls(schema_version=FACT_SCHEMA_VERSION, id=_required_text(data.get("id"), "id", limit=50), fact_type=fact_type, payload=payload, prepared_by=PreparedBy(_enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")), status=RecordStatus(_enum_value(RecordStatus, data.get("status"), "status")), conditions=_tuple_text(data.get("conditions"), "conditions"), applicability=_tuple_text(data.get("applicability"), "applicability"), evidence_anchors=tuple(EvidenceAnchor.from_dict(item) for item in raw_anchors), review_history=tuple(ReviewEvent.from_dict(item) for item in raw_history), review=Review.from_dict(data.get("review")), supersedes=_optional_text(data.get("supersedes"), "supersedes", limit=50)).validate()

    @classmethod
    def from_json(cls, payload: str) -> FactRecord:
        try: return cls.from_dict(json.loads(payload))
        except json.JSONDecodeError as error: raise RecordValidationError(f"fact record is not valid JSON: {error.msg}") from error

    def validate(self) -> FactRecord:
        if _FACT_ID.fullmatch(self.id) is None: raise RecordValidationError("fact id must match fact_<24-32 lowercase hex characters>")
        if self.supersedes is not None:
            if _FACT_ID.fullmatch(self.supersedes) is None: raise RecordValidationError("fact supersedes must be a valid fact id")
            if self.supersedes == self.id: raise RecordValidationError("a fact cannot supersede itself")
        if self.fact_type is FactType.COMPONENT_PIN and not isinstance(self.payload, ComponentPinPayload): raise RecordValidationError("COMPONENT_PIN requires ComponentPinPayload")
        if self.fact_type is FactType.PARAMETER_LIMIT and not isinstance(self.payload, ParameterLimitPayload): raise RecordValidationError("PARAMETER_LIMIT requires ParameterLimitPayload")
        self.payload.validate()
        for anchor in self.evidence_anchors: anchor.validate()
        _validate_review_state(self.status, self.review_history, self.review, missing_fields=self.missing_fields)
        return self

    @property
    def missing_fields(self) -> tuple[str, ...]:
        if not self.evidence_anchors: return ("evidence_anchors",)
        if not all(anchor.complete for anchor in self.evidence_anchors): return ("complete_evidence_anchor",)
        return ()

    @property
    def semantic_key(self) -> tuple[object, ...]:
        return (*self.payload.semantic_key, tuple(self.conditions), tuple(self.applicability))

    def edit_evidence(self, *, conditions: tuple[str, ...] | None = None, applicability: tuple[str, ...] | None = None, evidence_anchors: tuple[EvidenceAnchor, ...] | None = None, supersedes: str | None = None) -> FactRecord:
        if self.status not in {RecordStatus.DRAFT, RecordStatus.REJECTED}: raise RecordTransitionError("only DRAFT or REJECTED facts can be edited")
        return replace(self, status=RecordStatus.DRAFT, conditions=self.conditions if conditions is None else conditions, applicability=self.applicability if applicability is None else applicability, evidence_anchors=self.evidence_anchors if evidence_anchors is None else evidence_anchors, supersedes=self.supersedes if supersedes is None else _optional_text(supersedes, "supersedes", limit=50), review=Review()).validate()

    def submit(self) -> FactRecord:
        status, history, review = _submit(self.status, self.review_history); return replace(self, status=status, review_history=history, review=review).validate()
    def approve(self, comment: str | None) -> FactRecord:
        status, history, review = _approve(self.status, self.review_history, comment, missing_fields=self.missing_fields); return replace(self, status=status, review_history=history, review=review).validate()
    def reject(self, comment: str | None) -> FactRecord:
        status, history, review = _reject(self.status, self.review_history, comment); return replace(self, status=status, review_history=history, review=review).validate()

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "id": self.id, "fact_type": self.fact_type.value, "status": self.status.value, "prepared_by": self.prepared_by.value, "payload": self.payload.to_dict(), "conditions": list(self.conditions), "applicability": list(self.applicability), "evidence_anchors": [anchor.to_dict() for anchor in self.evidence_anchors], "review_history": [item.to_dict() for item in self.review_history], "review": self.review.to_dict(), "supersedes": self.supersedes}
    def canonical_json(self) -> str: return _canonical_json(self.to_dict())
    @property
    def revision_token(self) -> str: return _revision_token(self.to_dict())
