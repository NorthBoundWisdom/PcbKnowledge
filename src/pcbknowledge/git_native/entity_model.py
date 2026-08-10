"""EntityRecordV1 and EvidenceAnchorV1 models."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math
import json
from .authority_common import *
from .authority_common import _ENTITY_ID, _SOURCE_ID, _canonical_json, _enum_value, _optional_text, _reject_extra_keys, _required_mapping, _required_text, _revision_token
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
    def manufacturer(cls, record_id: str, raw_name: str, *, prepared_by: PreparedBy) -> EntityRecord:
        return cls(id=record_id, kind=EntityKind.MANUFACTURER, prepared_by=prepared_by, raw_name=_required_text(raw_name, "raw_name", limit=300), normalized_key=normalize_lookup(raw_name)).validate()

    @classmethod
    def component(cls, record_id: str, manufacturer_id: str, raw_mpn: str, *, family: str | None = None, prepared_by: PreparedBy) -> EntityRecord:
        return cls(id=record_id, kind=EntityKind.COMPONENT, prepared_by=prepared_by, manufacturer_id=manufacturer_id, raw_mpn=_required_text(raw_mpn, "raw_mpn", limit=300), normalized_mpn=normalize_lookup(raw_mpn), family=_optional_text(family, "family", limit=300)).validate()

    @classmethod
    def package(cls, record_id: str, raw_name: str, *, prepared_by: PreparedBy) -> EntityRecord:
        return cls(id=record_id, kind=EntityKind.PACKAGE, prepared_by=prepared_by, raw_name=_required_text(raw_name, "raw_name", limit=300), normalized_key=normalize_lookup(raw_name)).validate()

    @classmethod
    def from_dict(cls, value: object) -> EntityRecord:
        data = _required_mapping(value, "entity record")
        allowed = {"schema_version", "id", "kind", "prepared_by", "raw_name", "normalized_key", "manufacturer_id", "raw_mpn", "normalized_mpn", "family", "note"}
        _reject_extra_keys(data, allowed, "entity record")
        if data.get("schema_version") != ENTITY_SCHEMA_VERSION:
            raise RecordValidationError(f"entity schema_version must equal {ENTITY_SCHEMA_VERSION}")
        record = cls(id=_required_text(data.get("id"), "id", limit=45), kind=EntityKind(_enum_value(EntityKind, data.get("kind"), "kind")), prepared_by=PreparedBy(_enum_value(PreparedBy, data.get("prepared_by"), "prepared_by")), raw_name=_optional_text(data.get("raw_name"), "raw_name", limit=300), normalized_key=_optional_text(data.get("normalized_key"), "normalized_key", limit=300), manufacturer_id=_optional_text(data.get("manufacturer_id"), "manufacturer_id", limit=45), raw_mpn=_optional_text(data.get("raw_mpn"), "raw_mpn", limit=300), normalized_mpn=_optional_text(data.get("normalized_mpn"), "normalized_mpn", limit=300), family=_optional_text(data.get("family"), "family", limit=300), note=_optional_text(data.get("note"), "note", limit=2000))
        return record.validate()

    @classmethod
    def from_json(cls, payload: str) -> EntityRecord:
        try:
            return cls.from_dict(json.loads(payload))
        except json.JSONDecodeError as error:
            raise RecordValidationError(f"entity record is not valid JSON: {error.msg}") from error

    def validate(self) -> EntityRecord:
        if _ENTITY_ID.fullmatch(self.id) is None:
            raise RecordValidationError("entity id must match ent_<24-32 lowercase hex characters>")
        if self.kind in {EntityKind.MANUFACTURER, EntityKind.PACKAGE}:
            if self.raw_name is None or self.normalized_key is None:
                raise RecordValidationError(f"{self.kind.value} requires raw_name and normalized_key")
            if normalize_lookup(self.raw_name) != self.normalized_key:
                raise RecordValidationError("normalized_key does not match raw_name")
            if any(value is not None for value in (self.manufacturer_id, self.raw_mpn, self.normalized_mpn, self.family)):
                raise RecordValidationError(f"{self.kind.value} contains component-only fields")
        elif self.kind is EntityKind.COMPONENT:
            if self.manufacturer_id is None or _ENTITY_ID.fullmatch(self.manufacturer_id) is None:
                raise RecordValidationError("COMPONENT requires a valid manufacturer_id")
            if self.raw_mpn is None or self.normalized_mpn is None:
                raise RecordValidationError("COMPONENT requires raw_mpn and normalized_mpn")
            if normalize_lookup(self.raw_mpn) != self.normalized_mpn:
                raise RecordValidationError("normalized_mpn does not match raw_mpn")
            if self.raw_name is not None or self.normalized_key is not None:
                raise RecordValidationError("COMPONENT must use raw_mpn, not raw_name")
        return self

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": self.schema_version, "id": self.id, "kind": self.kind.value, "prepared_by": self.prepared_by.value, "raw_name": self.raw_name, "normalized_key": self.normalized_key, "manufacturer_id": self.manufacturer_id, "raw_mpn": self.raw_mpn, "normalized_mpn": self.normalized_mpn, "family": self.family, "note": self.note}

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
    def create(cls, source_id: str, page: int, *, bbox: tuple[float, float, float, float] | None = None, quote: str | None = None) -> EvidenceAnchor:
        normalized_quote = _optional_text(quote, "quote", limit=8000)
        digest = None if normalized_quote is None else hashlib.sha256(normalized_quote.encode("utf-8")).hexdigest()
        return cls(source_id, page, "PDF_NORMALIZED_V1", bbox, normalized_quote, digest).validate()

    @classmethod
    def from_dict(cls, value: object) -> EvidenceAnchor:
        data = _required_mapping(value, "evidence anchor")
        _reject_extra_keys(data, {"source_id", "page", "coordinate_space", "bbox", "quote", "quote_sha256"}, "evidence anchor")
        raw_bbox = data.get("bbox")
        bbox: tuple[float, float, float, float] | None
        if raw_bbox is None:
            bbox = None
        elif isinstance(raw_bbox, list) and len(raw_bbox) == 4 and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in raw_bbox):
            bbox = tuple(float(item) for item in raw_bbox)  # type: ignore[assignment]
        else:
            raise RecordValidationError("evidence anchor bbox must be four numbers or null")
        page = data.get("page")
        if not isinstance(page, int) or isinstance(page, bool):
            raise RecordValidationError("evidence anchor page must be an integer")
        return cls(source_id=_required_text(data.get("source_id"), "source_id", limit=40), page=page, coordinate_space=_required_text(data.get("coordinate_space"), "coordinate_space", limit=50), bbox=bbox, quote=_optional_text(data.get("quote"), "quote", limit=8000), quote_sha256=_optional_text(data.get("quote_sha256"), "quote_sha256", limit=64)).validate()

    def validate(self) -> EvidenceAnchor:
        if _SOURCE_ID.fullmatch(self.source_id) is None:
            raise RecordValidationError("evidence anchor source_id is invalid")
        if self.page < 1:
            raise RecordValidationError("evidence anchor page must be 1-based")
        if self.coordinate_space != "PDF_NORMALIZED_V1":
            raise RecordValidationError("unsupported evidence anchor coordinate_space")
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if not all(math.isfinite(value) for value in self.bbox):
                raise RecordValidationError("evidence anchor bbox must be finite")
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                raise RecordValidationError("evidence anchor bbox must be normalized to [0,1]")
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
        return self.bbox is not None and self.quote is not None and self.quote_sha256 is not None

    def to_dict(self) -> dict[str, object]:
        return {"source_id": self.source_id, "page": self.page, "coordinate_space": self.coordinate_space, "bbox": None if self.bbox is None else list(self.bbox), "quote": self.quote, "quote_sha256": self.quote_sha256}
