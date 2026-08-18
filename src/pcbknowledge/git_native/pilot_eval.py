"""Pilot-dataset evaluation support for private PcbKnowledge workspaces.

The pilot harness deliberately keeps evaluation inputs outside canonical authority.
Wrong MPN/package/revision cases, visual acceptance receipts, and similar test
scenarios must not be represented as false Source/Entity/Fact records merely to
make evaluation convenient.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    FactType,
    LicenseClass,
    RecordStatus,
)
from pcbknowledge.git_native.store import AuthoritySnapshot, KnowledgeRepository


PILOT_EVAL_FORMAT = "pcbknowledge-pilot-eval-v1"
_CASE_ID = re.compile(r"case_[a-z0-9][a-z0-9_-]{2,79}\Z")
_ACCEPTANCE_ID = re.compile(r"visual_[a-z0-9][a-z0-9_-]{2,79}\Z")
_AUTHORITY_ID = re.compile(
    r"(?:pk|ent|fact)_[0-9a-f]{24,32}\Z"
)
_EXPECTED_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class PilotEvaluationError(ValueError):
    """A pilot evaluation manifest or receipt violates its contract."""


class PilotCaseCategory(StrEnum):
    WRONG_MPN = "WRONG_MPN"
    WRONG_PACKAGE = "WRONG_PACKAGE"
    WRONG_REVISION = "WRONG_REVISION"
    ABS_MAX_VS_RECOMMENDED = "ABS_MAX_VS_RECOMMENDED"
    UNKNOWN = "UNKNOWN"
    SUPERSEDE = "SUPERSEDE"
    CONFLICT = "CONFLICT"
    LICENSE_BLOCK = "LICENSE_BLOCK"
    ANCHOR_DRIFT = "ANCHOR_DRIFT"
    REVIEW_HISTORY = "REVIEW_HISTORY"
    UNCOMMITTED_APPROVAL = "UNCOMMITTED_APPROVAL"
    MIXED_COMMIT = "MIXED_COMMIT"
    WRONG_WORKSPACE = "WRONG_WORKSPACE"
    TABLE_PIN = "TABLE_PIN"
    FOOTNOTE_LIMIT = "FOOTNOTE_LIMIT"


NEGATIVE_CASE_CATEGORIES = frozenset(
    {
        PilotCaseCategory.WRONG_MPN,
        PilotCaseCategory.WRONG_PACKAGE,
        PilotCaseCategory.WRONG_REVISION,
        PilotCaseCategory.ABS_MAX_VS_RECOMMENDED,
        PilotCaseCategory.UNKNOWN,
        PilotCaseCategory.SUPERSEDE,
        PilotCaseCategory.CONFLICT,
        PilotCaseCategory.LICENSE_BLOCK,
        PilotCaseCategory.ANCHOR_DRIFT,
        PilotCaseCategory.REVIEW_HISTORY,
        PilotCaseCategory.UNCOMMITTED_APPROVAL,
        PilotCaseCategory.MIXED_COMMIT,
        PilotCaseCategory.WRONG_WORKSPACE,
    }
)


class PilotCaseStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    FAIL = "FAIL"


class VisualCharacteristic(StrEnum):
    TABLE = "TABLE"
    FOOTNOTE = "FOOTNOTE"
    MULTI_LINE = "MULTI_LINE"
    MULTI_ANCHOR = "MULTI_ANCHOR"
    RESIZE_ZOOM = "RESIZE_ZOOM"
    ROTATED_OR_CROPPED = "ROTATED_OR_CROPPED"
    COMPLEX_FONT = "COMPLEX_FONT"


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PilotEvaluationError(f"{label} must be an object")
    return value


def _reject_extra(data: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extras = sorted(set(data) - allowed)
    if extras:
        raise PilotEvaluationError(
            f"{label} contains unsupported fields: {', '.join(extras)}"
        )


def _required_text(value: object, label: str, *, limit: int) -> str:
    if not isinstance(value, str):
        raise PilotEvaluationError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise PilotEvaluationError(f"{label} is required")
    if len(normalized) > limit:
        raise PilotEvaluationError(f"{label} exceeds {limit} characters")
    if "\x00" in normalized:
        raise PilotEvaluationError(f"{label} contains a NUL byte")
    return normalized


def _optional_text(value: object, label: str, *, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PilotEvaluationError(f"{label} must be a string or null")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > limit:
        raise PilotEvaluationError(f"{label} exceeds {limit} characters")
    if "\x00" in normalized:
        raise PilotEvaluationError(f"{label} contains a NUL byte")
    return normalized


def _enum(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    if not isinstance(value, str):
        raise PilotEvaluationError(f"{label} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise PilotEvaluationError(f"{label} has an unsupported value") from error


def _string_tuple(value: object, label: str, *, limit: int = 120) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PilotEvaluationError(f"{label} must be an array")
    result = tuple(_required_text(item, f"{label} item", limit=limit) for item in value)
    if len(set(result)) != len(result):
        raise PilotEvaluationError(f"{label} must not contain duplicates")
    return result


@dataclass(frozen=True, slots=True)
class PilotCase:
    case_id: str
    category: PilotCaseCategory
    status: PilotCaseStatus
    expected_code: str
    observed_code: str | None
    related_ids: tuple[str, ...] = ()
    notes: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> "PilotCase":
        data = _mapping(value, "pilot case")
        _reject_extra(
            data,
            {
                "id",
                "category",
                "status",
                "expected_code",
                "observed_code",
                "related_ids",
                "notes",
            },
            "pilot case",
        )
        return cls(
            case_id=_required_text(data.get("id"), "pilot case id", limit=80),
            category=PilotCaseCategory(
                _enum(PilotCaseCategory, data.get("category"), "pilot case category")
            ),
            status=PilotCaseStatus(
                _enum(PilotCaseStatus, data.get("status"), "pilot case status")
            ),
            expected_code=_required_text(
                data.get("expected_code"), "pilot case expected_code", limit=64
            ),
            observed_code=_optional_text(
                data.get("observed_code"), "pilot case observed_code", limit=64
            ),
            related_ids=_string_tuple(
                data.get("related_ids", []), "pilot case related_ids", limit=50
            ),
            notes=_optional_text(data.get("notes"), "pilot case notes", limit=4000),
        ).validate()

    def validate(self) -> "PilotCase":
        if _CASE_ID.fullmatch(self.case_id) is None:
            raise PilotEvaluationError(
                "pilot case id must match case_<lowercase-name>"
            )
        if _EXPECTED_CODE.fullmatch(self.expected_code) is None:
            raise PilotEvaluationError(
                "pilot case expected_code must be an uppercase symbolic code"
            )
        if self.observed_code is not None and _EXPECTED_CODE.fullmatch(self.observed_code) is None:
            raise PilotEvaluationError(
                "pilot case observed_code must be an uppercase symbolic code"
            )
        for related_id in self.related_ids:
            if _AUTHORITY_ID.fullmatch(related_id) is None:
                raise PilotEvaluationError(
                    f"pilot case related id is not a canonical authority id: {related_id}"
                )
        if self.status is PilotCaseStatus.NOT_RUN:
            if self.observed_code is not None:
                raise PilotEvaluationError("NOT_RUN pilot case cannot have observed_code")
        else:
            if self.observed_code is None:
                raise PilotEvaluationError(
                    f"{self.status.value} pilot case requires observed_code"
                )
            matches = self.observed_code == self.expected_code
            if self.status is PilotCaseStatus.PASS and not matches:
                raise PilotEvaluationError(
                    "PASS pilot case observed_code must match expected_code"
                )
            if self.status is PilotCaseStatus.FAIL and matches:
                raise PilotEvaluationError(
                    "FAIL pilot case must record an observed_code different from expected_code"
                )
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.case_id,
            "category": self.category.value,
            "status": self.status.value,
            "expected_code": self.expected_code,
            "observed_code": self.observed_code,
            "related_ids": list(self.related_ids),
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class VisualAcceptance:
    acceptance_id: str
    source_id: str
    fact_id: str
    page: int
    characteristics: tuple[VisualCharacteristic, ...]
    status: PilotCaseStatus
    notes: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> "VisualAcceptance":
        data = _mapping(value, "visual acceptance")
        _reject_extra(
            data,
            {"id", "source_id", "fact_id", "page", "characteristics", "status", "notes"},
            "visual acceptance",
        )
        page = data.get("page")
        if not isinstance(page, int) or isinstance(page, bool):
            raise PilotEvaluationError("visual acceptance page must be an integer")
        raw_characteristics = data.get("characteristics")
        if not isinstance(raw_characteristics, list):
            raise PilotEvaluationError("visual acceptance characteristics must be an array")
        characteristics = tuple(
            VisualCharacteristic(
                _enum(VisualCharacteristic, item, "visual characteristic")
            )
            for item in raw_characteristics
        )
        return cls(
            acceptance_id=_required_text(data.get("id"), "visual acceptance id", limit=80),
            source_id=_required_text(data.get("source_id"), "visual source_id", limit=50),
            fact_id=_required_text(data.get("fact_id"), "visual fact_id", limit=50),
            page=page,
            characteristics=characteristics,
            status=PilotCaseStatus(
                _enum(PilotCaseStatus, data.get("status"), "visual acceptance status")
            ),
            notes=_optional_text(data.get("notes"), "visual acceptance notes", limit=4000),
        ).validate()

    def validate(self) -> "VisualAcceptance":
        if _ACCEPTANCE_ID.fullmatch(self.acceptance_id) is None:
            raise PilotEvaluationError(
                "visual acceptance id must match visual_<lowercase-name>"
            )
        if not self.source_id.startswith("pk_") or _AUTHORITY_ID.fullmatch(self.source_id) is None:
            raise PilotEvaluationError("visual acceptance source_id is invalid")
        if not self.fact_id.startswith("fact_") or _AUTHORITY_ID.fullmatch(self.fact_id) is None:
            raise PilotEvaluationError("visual acceptance fact_id is invalid")
        if self.page < 1:
            raise PilotEvaluationError("visual acceptance page must be 1-based")
        if not self.characteristics:
            raise PilotEvaluationError(
                "visual acceptance requires at least one characteristic"
            )
        if len(set(self.characteristics)) != len(self.characteristics):
            raise PilotEvaluationError(
                "visual acceptance characteristics must not contain duplicates"
            )
        if self.status is PilotCaseStatus.FAIL and self.notes is None:
            raise PilotEvaluationError("failed visual acceptance requires notes")
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.acceptance_id,
            "source_id": self.source_id,
            "fact_id": self.fact_id,
            "page": self.page,
            "characteristics": [item.value for item in self.characteristics],
            "status": self.status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class PilotEvaluationManifest:
    dataset_name: str
    cases: tuple[PilotCase, ...]
    visual_acceptance: tuple[VisualAcceptance, ...]
    notes: str | None = None
    format: str = PILOT_EVAL_FORMAT

    @classmethod
    def from_dict(cls, value: object) -> "PilotEvaluationManifest":
        data = _mapping(value, "pilot evaluation manifest")
        _reject_extra(
            data,
            {"format", "dataset_name", "cases", "visual_acceptance", "notes"},
            "pilot evaluation manifest",
        )
        raw_cases = data.get("cases")
        raw_visual = data.get("visual_acceptance")
        if not isinstance(raw_cases, list):
            raise PilotEvaluationError("pilot evaluation cases must be an array")
        if not isinstance(raw_visual, list):
            raise PilotEvaluationError(
                "pilot evaluation visual_acceptance must be an array"
            )
        manifest = cls(
            format=_required_text(data.get("format"), "pilot evaluation format", limit=64),
            dataset_name=_required_text(
                data.get("dataset_name"), "pilot dataset_name", limit=200
            ),
            cases=tuple(PilotCase.from_dict(item) for item in raw_cases),
            visual_acceptance=tuple(
                VisualAcceptance.from_dict(item) for item in raw_visual
            ),
            notes=_optional_text(data.get("notes"), "pilot evaluation notes", limit=4000),
        )
        return manifest.validate()

    @classmethod
    def from_json(cls, payload: str) -> "PilotEvaluationManifest":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise PilotEvaluationError(
                f"pilot evaluation manifest is not valid JSON: {error.msg}"
            ) from error
        return cls.from_dict(value)

    @classmethod
    def from_path(cls, path: Path) -> "PilotEvaluationManifest":
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise PilotEvaluationError(
                f"pilot evaluation manifest is not a regular file: {resolved}"
            )
        if resolved.stat().st_size > 1_000_000:
            raise PilotEvaluationError("pilot evaluation manifest exceeds 1 MiB")
        try:
            payload = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise PilotEvaluationError(
                "pilot evaluation manifest must be UTF-8"
            ) from error
        return cls.from_json(payload)

    def validate(self) -> "PilotEvaluationManifest":
        if self.format != PILOT_EVAL_FORMAT:
            raise PilotEvaluationError(
                f"pilot evaluation format must equal {PILOT_EVAL_FORMAT}"
            )
        case_ids = [case.case_id for case in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise PilotEvaluationError("pilot evaluation case ids must be unique")
        visual_ids = [item.acceptance_id for item in self.visual_acceptance]
        if len(set(visual_ids)) != len(visual_ids):
            raise PilotEvaluationError(
                "visual acceptance ids must be unique"
            )
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "dataset_name": self.dataset_name,
            "cases": [case.to_dict() for case in self.cases],
            "visual_acceptance": [item.to_dict() for item in self.visual_acceptance],
            "notes": self.notes,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False
        ) + "\n"


@dataclass(frozen=True, slots=True)
class SnapshotMetrics:
    source_count: int
    approved_source_count: int
    entity_count: int
    manufacturer_count: int
    component_count: int
    package_count: int
    fact_count: int
    approved_fact_count: int
    component_pin_fact_count: int
    parameter_limit_fact_count: int
    multi_package_component_count: int
    source_supersedes_count: int
    fact_supersedes_count: int
    multi_anchor_fact_count: int
    conditional_fact_count: int
    applicability_fact_count: int
    incomplete_source_count: int
    incomplete_fact_count: int
    ready_for_review_count: int
    rejected_count: int
    draft_count: int
    conflict_count: int
    blocked_source_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class PilotGate:
    name: str
    passed: bool
    actual: object
    expected: str
    detail: str
    required: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
            "actual": self.actual,
            "expected": self.expected,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class PilotReport:
    workspace: str
    published_ref: str
    published_commit: str | None
    working: SnapshotMetrics
    published: SnapshotMetrics
    negative_case_count: int
    case_pass_count: int
    case_fail_count: int
    case_not_run_count: int
    visual_pass_count: int
    visual_fail_count: int
    visual_not_run_count: int
    gates: tuple[PilotGate, ...]

    @property
    def passed(self) -> bool:
        return all(gate.passed for gate in self.gates if gate.required)

    def to_dict(self) -> dict[str, object]:
        return {
            "format": "pcbknowledge-pilot-report-v1",
            "status": "PASS" if self.passed else "INCOMPLETE_OR_FAIL",
            "workspace": self.workspace,
            "published_ref": self.published_ref,
            "published_commit": self.published_commit,
            "working": self.working.to_dict(),
            "published": self.published.to_dict(),
            "evaluation": {
                "negative_case_count": self.negative_case_count,
                "case_pass_count": self.case_pass_count,
                "case_fail_count": self.case_fail_count,
                "case_not_run_count": self.case_not_run_count,
                "visual_pass_count": self.visual_pass_count,
                "visual_fail_count": self.visual_fail_count,
                "visual_not_run_count": self.visual_not_run_count,
            },
            "gates": [gate.to_dict() for gate in self.gates],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"


def measure_snapshot(snapshot: AuthoritySnapshot) -> SnapshotMetrics:
    manufacturers = sum(
        entity.kind is EntityKind.MANUFACTURER for entity in snapshot.entities
    )
    components = sum(
        entity.kind is EntityKind.COMPONENT for entity in snapshot.entities
    )
    packages = sum(entity.kind is EntityKind.PACKAGE for entity in snapshot.entities)

    packages_by_component: dict[str, set[str]] = defaultdict(set)
    for fact in snapshot.facts:
        if isinstance(fact.payload, ComponentPinPayload):
            packages_by_component[fact.payload.component_id].add(
                fact.payload.package_id
            )

    all_reviewable = (*snapshot.sources, *snapshot.facts)
    return SnapshotMetrics(
        source_count=len(snapshot.sources),
        approved_source_count=sum(
            source.status is RecordStatus.APPROVED for source in snapshot.sources
        ),
        entity_count=len(snapshot.entities),
        manufacturer_count=manufacturers,
        component_count=components,
        package_count=packages,
        fact_count=len(snapshot.facts),
        approved_fact_count=sum(
            fact.status is RecordStatus.APPROVED for fact in snapshot.facts
        ),
        component_pin_fact_count=sum(
            fact.fact_type is FactType.COMPONENT_PIN for fact in snapshot.facts
        ),
        parameter_limit_fact_count=sum(
            fact.fact_type is FactType.PARAMETER_LIMIT for fact in snapshot.facts
        ),
        multi_package_component_count=sum(
            len(package_ids) >= 2 for package_ids in packages_by_component.values()
        ),
        source_supersedes_count=sum(
            source.supersedes is not None for source in snapshot.sources
        ),
        fact_supersedes_count=sum(
            fact.supersedes is not None for fact in snapshot.facts
        ),
        multi_anchor_fact_count=sum(
            len(fact.evidence_anchors) >= 2 for fact in snapshot.facts
        ),
        conditional_fact_count=sum(bool(fact.conditions) for fact in snapshot.facts),
        applicability_fact_count=sum(
            bool(fact.applicability) for fact in snapshot.facts
        ),
        incomplete_source_count=sum(
            bool(source.missing_fields) for source in snapshot.sources
        ),
        incomplete_fact_count=sum(bool(fact.missing_fields) for fact in snapshot.facts),
        ready_for_review_count=sum(
            record.status is RecordStatus.READY_FOR_REVIEW
            for record in all_reviewable
        ),
        rejected_count=sum(
            record.status is RecordStatus.REJECTED for record in all_reviewable
        ),
        draft_count=sum(
            record.status is RecordStatus.DRAFT for record in all_reviewable
        ),
        conflict_count=len(snapshot.conflicts),
        blocked_source_count=sum(
            source.license_class
            in {
                LicenseClass.UNKNOWN,
                LicenseClass.RESTRICTED,
                LicenseClass.LICENSED_BLOCKED_FOR_AI,
            }
            for source in snapshot.sources
        ),
    )


def validate_manifest_references(
    manifest: PilotEvaluationManifest,
    snapshot: AuthoritySnapshot,
) -> None:
    sources = {source.id: source for source in snapshot.sources}
    entities = {entity.id: entity for entity in snapshot.entities}
    facts = {fact.id: fact for fact in snapshot.facts}
    authority_ids = set(sources) | set(entities) | set(facts)

    for case in manifest.cases:
        missing = [item for item in case.related_ids if item not in authority_ids]
        if missing:
            raise PilotEvaluationError(
                f"pilot case {case.case_id} references missing authority {missing[0]}"
            )

    for acceptance in manifest.visual_acceptance:
        source = sources.get(acceptance.source_id)
        if source is None:
            raise PilotEvaluationError(
                f"visual acceptance {acceptance.acceptance_id} references missing source"
            )
        fact = facts.get(acceptance.fact_id)
        if fact is None:
            raise PilotEvaluationError(
                f"visual acceptance {acceptance.acceptance_id} references missing fact"
            )
        matching = tuple(
            anchor
            for anchor in fact.evidence_anchors
            if anchor.source_id == source.id and anchor.page == acceptance.page
        )
        if not matching:
            raise PilotEvaluationError(
                f"visual acceptance {acceptance.acceptance_id} does not match a Fact anchor"
            )
        if acceptance.status is PilotCaseStatus.PASS:
            if not source.evidence.present:
                raise PilotEvaluationError(
                    f"visual acceptance {acceptance.acceptance_id} Source has no PDF evidence"
                )
            if not source.agent_processing_allowed:
                raise PilotEvaluationError(
                    f"visual acceptance {acceptance.acceptance_id} Source is blocked by license policy"
                )
            if not any(anchor.complete for anchor in matching):
                raise PilotEvaluationError(
                    f"visual acceptance {acceptance.acceptance_id} has no complete matching anchor"
                )


def _category_passed(
    manifest: PilotEvaluationManifest, category: PilotCaseCategory
) -> bool:
    return any(
        case.category is category and case.status is PilotCaseStatus.PASS
        for case in manifest.cases
    )


def build_pilot_report(
    repository: KnowledgeRepository,
    manifest: PilotEvaluationManifest,
    *,
    published_ref: str = "HEAD",
) -> PilotReport:
    manifest.validate()
    working_snapshot = repository.validate_all(require_canonical=True)
    validate_manifest_references(manifest, working_snapshot)
    published_snapshot = repository.read_published_snapshot(ref=published_ref)

    working = measure_snapshot(working_snapshot)
    published = measure_snapshot(published_snapshot)
    negative_cases = tuple(
        case for case in manifest.cases if case.category in NEGATIVE_CASE_CATEGORIES
    )
    case_pass_count = sum(
        case.status is PilotCaseStatus.PASS for case in manifest.cases
    )
    case_fail_count = sum(
        case.status is PilotCaseStatus.FAIL for case in manifest.cases
    )
    case_not_run_count = sum(
        case.status is PilotCaseStatus.NOT_RUN for case in manifest.cases
    )
    visual_pass_count = sum(
        item.status is PilotCaseStatus.PASS for item in manifest.visual_acceptance
    )
    visual_fail_count = sum(
        item.status is PilotCaseStatus.FAIL for item in manifest.visual_acceptance
    )
    visual_not_run_count = sum(
        item.status is PilotCaseStatus.NOT_RUN for item in manifest.visual_acceptance
    )
    visual_characteristics = {
        characteristic
        for item in manifest.visual_acceptance
        if item.status is PilotCaseStatus.PASS
        for characteristic in item.characteristics
    }

    working_fully_reviewed = (
        working.source_count == working.approved_source_count
        and working.fact_count == working.approved_fact_count
        and working.ready_for_review_count == 0
        and working.rejected_count == 0
        and working.draft_count == 0
        and working.incomplete_source_count == 0
        and working.incomplete_fact_count == 0
        and working.conflict_count == 0
    )
    published_matches_working = (
        working.source_count == published.source_count
        and working.entity_count == published.entity_count
        and working.fact_count == published.fact_count
        and published.source_count == published.approved_source_count
        and published.fact_count == published.approved_fact_count
    )

    gates = (
        PilotGate(
            "component-count",
            3 <= working.component_count <= 5,
            working.component_count,
            "3..5",
            "Pilot targets 3-5 distinct Component entities.",
        ),
        PilotGate(
            "fact-count",
            20 <= working.fact_count <= 40,
            working.fact_count,
            "20..40",
            "Pilot targets 20-40 typed Facts before schema expansion.",
        ),
        PilotGate(
            "both-initial-fact-types",
            working.component_pin_fact_count > 0
            and working.parameter_limit_fact_count > 0,
            {
                "component_pin": working.component_pin_fact_count,
                "parameter_limit": working.parameter_limit_fact_count,
            },
            "both > 0",
            "Pilot must exercise both initial Fact families.",
        ),
        PilotGate(
            "multi-package-component",
            working.multi_package_component_count >= 1,
            working.multi_package_component_count,
            ">= 1",
            "At least one Component must have pin Facts across multiple Packages.",
        ),
        PilotGate(
            "source-revision-supersedes",
            working.source_supersedes_count >= 1,
            working.source_supersedes_count,
            ">= 1",
            "At least one explicit Source revision/supersedes chain is required.",
        ),
        PilotGate(
            "negative-case-count",
            5 <= len(negative_cases) <= 10,
            len(negative_cases),
            "5..10",
            "Wrong or ambiguous scenarios live in the evaluation manifest, not authority.",
        ),
        PilotGate(
            "all-evaluation-cases-run",
            case_not_run_count == 0,
            case_not_run_count,
            "0 NOT_RUN",
            "Every declared pilot case must have an explicit observation before closure.",
        ),
        PilotGate(
            "no-failed-evaluation-cases",
            case_fail_count == 0,
            case_fail_count,
            "0 FAIL",
            "A failing scenario keeps the pilot open until understood or intentionally rebaselined.",
        ),
        PilotGate(
            "unknown-preserved",
            _category_passed(manifest, PilotCaseCategory.UNKNOWN),
            _category_passed(manifest, PilotCaseCategory.UNKNOWN),
            "PASS UNKNOWN case",
            "At least one explicit unknown must remain unknown rather than being guessed.",
        ),
        PilotGate(
            "table-pin-case",
            _category_passed(manifest, PilotCaseCategory.TABLE_PIN),
            _category_passed(manifest, PilotCaseCategory.TABLE_PIN),
            "PASS TABLE_PIN case",
            "Pilot must exercise pin extraction/review from a table-like source region.",
        ),
        PilotGate(
            "footnote-limit-case",
            _category_passed(manifest, PilotCaseCategory.FOOTNOTE_LIMIT),
            _category_passed(manifest, PilotCaseCategory.FOOTNOTE_LIMIT),
            "PASS FOOTNOTE_LIMIT case",
            "Pilot must exercise a parameter limit whose interpretation depends on conditions/footnotes.",
        ),
        PilotGate(
            "visual-anchor-acceptance",
            visual_pass_count >= 1 and visual_fail_count == 0,
            {
                "pass": visual_pass_count,
                "fail": visual_fail_count,
                "not_run": visual_not_run_count,
            },
            ">= 1 PASS and 0 FAIL",
            "At least one real browser/PDF/anchor visual receipt is required.",
        ),
        PilotGate(
            "visual-resize-zoom",
            VisualCharacteristic.RESIZE_ZOOM in visual_characteristics,
            sorted(item.value for item in visual_characteristics),
            "RESIZE_ZOOM",
            "BBox alignment must be checked under browser resize or zoom.",
        ),
        PilotGate(
            "nontrivial-pdf-characteristic",
            bool(
                {
                    VisualCharacteristic.ROTATED_OR_CROPPED,
                    VisualCharacteristic.COMPLEX_FONT,
                }
                & visual_characteristics
            ),
            sorted(item.value for item in visual_characteristics),
            "ROTATED_OR_CROPPED or COMPLEX_FONT where available",
            "This is advisory because a chosen vendor PDF may not expose both characteristics.",
            required=False,
        ),
        PilotGate(
            "working-authority-reviewed",
            working_fully_reviewed,
            {
                "approved_sources": working.approved_source_count,
                "sources": working.source_count,
                "approved_facts": working.approved_fact_count,
                "facts": working.fact_count,
                "conflicts": working.conflict_count,
                "incomplete_sources": working.incomplete_source_count,
                "incomplete_facts": working.incomplete_fact_count,
            },
            "all Source/Fact authority approved and conflict-free",
            "Pilot completion requires the human review loop to be closed in the working tree.",
        ),
        PilotGate(
            "published-matches-working",
            published_matches_working,
            {
                "working": {
                    "sources": working.source_count,
                    "entities": working.entity_count,
                    "facts": working.fact_count,
                },
                "published": {
                    "sources": published.source_count,
                    "entities": published.entity_count,
                    "facts": published.fact_count,
                },
            },
            "published counts equal reviewed working authority",
            "Approval alone is not publication; the committed ref must contain the reviewed closure.",
        ),
    )

    return PilotReport(
        workspace=str(repository.root),
        published_ref=published_ref,
        published_commit=published_snapshot.commit,
        working=working,
        published=published,
        negative_case_count=len(negative_cases),
        case_pass_count=case_pass_count,
        case_fail_count=case_fail_count,
        case_not_run_count=case_not_run_count,
        visual_pass_count=visual_pass_count,
        visual_fail_count=visual_fail_count,
        visual_not_run_count=visual_not_run_count,
        gates=gates,
    )


def example_manifest_payload() -> dict[str, object]:
    """Return an editable, intentionally incomplete pilot manifest template."""

    cases = []
    for index, category in enumerate(
        (
            PilotCaseCategory.WRONG_MPN,
            PilotCaseCategory.WRONG_PACKAGE,
            PilotCaseCategory.WRONG_REVISION,
            PilotCaseCategory.UNKNOWN,
            PilotCaseCategory.LICENSE_BLOCK,
            PilotCaseCategory.TABLE_PIN,
            PilotCaseCategory.FOOTNOTE_LIMIT,
        ),
        start=1,
    ):
        cases.append(
            {
                "id": f"case_example_{index:02d}",
                "category": category.value,
                "status": PilotCaseStatus.NOT_RUN.value,
                "expected_code": "REPLACE_ME",
                "observed_code": None,
                "related_ids": [],
                "notes": "Replace with a private-workspace pilot scenario.",
            }
        )
    return {
        "format": PILOT_EVAL_FORMAT,
        "dataset_name": "replace-with-private-pilot-name",
        "cases": cases,
        "visual_acceptance": [
            {
                "id": "visual_example_anchor",
                "source_id": "pk_aaaaaaaaaaaaaaaaaaaaaaaa",
                "fact_id": "fact_aaaaaaaaaaaaaaaaaaaaaaaa",
                "page": 1,
                "characteristics": [
                    VisualCharacteristic.RESIZE_ZOOM.value,
                    VisualCharacteristic.TABLE.value,
                ],
                "status": PilotCaseStatus.NOT_RUN.value,
                "notes": "Replace IDs after real Source/Fact ingestion.",
            }
        ],
        "notes": "Evaluation metadata is not canonical engineering authority.",
    }


def write_example_manifest(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists():
        raise PilotEvaluationError(f"refusing to overwrite existing file: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(
            example_manifest_payload(),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return resolved
