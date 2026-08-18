"""Executable P0.4a pilot scenarios for private PcbKnowledge workspaces.

The scenario runner is deliberately read-only. It executes negative and regression
queries against one explicitly selected knowledge workspace without creating false
Source/Entity/Fact authority. Results are bound to the exact working authority
fingerprint and published Git commit so stale receipts cannot silently close a pilot.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    FactRecord,
    ParameterLimitKind,
    ParameterLimitPayload,
    ReviewAction,
    SourceRecord,
    normalize_lookup,
)
from pcbknowledge.git_native.pilot_eval import (
    PilotCase,
    PilotCaseCategory,
    PilotCaseStatus,
    PilotEvaluationError,
    PilotEvaluationManifest,
)
from pcbknowledge.git_native.store import AuthoritySnapshot, KnowledgeRepository


PILOT_SCENARIO_FORMAT = "pcbknowledge-pilot-scenarios-v1"
PILOT_SCENARIO_REPORT_FORMAT = "pcbknowledge-pilot-scenario-report-v1"

_SCENARIO_ID = re.compile(r"scenario_[a-z0-9][a-z0-9_-]{2,79}\Z")
_CASE_ID = re.compile(r"case_[a-z0-9][a-z0-9_-]{2,79}\Z")
_SYMBOLIC_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_AUTHORITY_ID = re.compile(r"(?:pk|ent|fact)_[0-9a-f]{24,32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PilotScenarioKind(StrEnum):
    COMPONENT_LOOKUP = "COMPONENT_LOOKUP"
    PACKAGE_LOOKUP = "PACKAGE_LOOKUP"
    SOURCE_REVISION_LOOKUP = "SOURCE_REVISION_LOOKUP"
    SOURCE_LICENSE_GATE = "SOURCE_LICENSE_GATE"
    SOURCE_SUPERSEDES = "SOURCE_SUPERSEDES"
    PIN_FACT_LOOKUP = "PIN_FACT_LOOKUP"
    PARAMETER_LIMIT_LOOKUP = "PARAMETER_LIMIT_LOOKUP"
    PARAMETER_LIMIT_DISTINCTION = "PARAMETER_LIMIT_DISTINCTION"
    FACT_CONFLICT = "FACT_CONFLICT"
    ANCHOR_INTEGRITY = "ANCHOR_INTEGRITY"
    REVIEW_HISTORY = "REVIEW_HISTORY"
    PUBLICATION_VISIBILITY = "PUBLICATION_VISIBILITY"
    CHANGE_SCOPE = "CHANGE_SCOPE"


class PilotScenarioSnapshot(StrEnum):
    WORKING = "WORKING"
    PUBLISHED = "PUBLISHED"


_KIND_CATEGORY_COMPATIBILITY: dict[PilotScenarioKind, frozenset[PilotCaseCategory]] = {
    PilotScenarioKind.COMPONENT_LOOKUP: frozenset(
        {PilotCaseCategory.WRONG_MPN, PilotCaseCategory.UNKNOWN}
    ),
    PilotScenarioKind.PACKAGE_LOOKUP: frozenset(
        {PilotCaseCategory.WRONG_PACKAGE, PilotCaseCategory.UNKNOWN}
    ),
    PilotScenarioKind.SOURCE_REVISION_LOOKUP: frozenset(
        {PilotCaseCategory.WRONG_REVISION, PilotCaseCategory.UNKNOWN}
    ),
    PilotScenarioKind.SOURCE_LICENSE_GATE: frozenset(
        {PilotCaseCategory.LICENSE_BLOCK}
    ),
    PilotScenarioKind.SOURCE_SUPERSEDES: frozenset(
        {PilotCaseCategory.SUPERSEDE}
    ),
    PilotScenarioKind.PIN_FACT_LOOKUP: frozenset(
        {
            PilotCaseCategory.WRONG_PACKAGE,
            PilotCaseCategory.UNKNOWN,
            PilotCaseCategory.CONFLICT,
            PilotCaseCategory.TABLE_PIN,
        }
    ),
    PilotScenarioKind.PARAMETER_LIMIT_LOOKUP: frozenset(
        {
            PilotCaseCategory.WRONG_REVISION,
            PilotCaseCategory.UNKNOWN,
            PilotCaseCategory.CONFLICT,
            PilotCaseCategory.FOOTNOTE_LIMIT,
        }
    ),
    PilotScenarioKind.PARAMETER_LIMIT_DISTINCTION: frozenset(
        {PilotCaseCategory.ABS_MAX_VS_RECOMMENDED}
    ),
    PilotScenarioKind.FACT_CONFLICT: frozenset({PilotCaseCategory.CONFLICT}),
    PilotScenarioKind.ANCHOR_INTEGRITY: frozenset(
        {PilotCaseCategory.ANCHOR_DRIFT}
    ),
    PilotScenarioKind.REVIEW_HISTORY: frozenset(
        {PilotCaseCategory.REVIEW_HISTORY}
    ),
    PilotScenarioKind.PUBLICATION_VISIBILITY: frozenset(
        {PilotCaseCategory.UNCOMMITTED_APPROVAL}
    ),
    PilotScenarioKind.CHANGE_SCOPE: frozenset(
        {PilotCaseCategory.MIXED_COMMIT}
    ),
}


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


def _required_text(value: object, label: str, *, limit: int = 500) -> str:
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


def _optional_text(value: object, label: str, *, limit: int = 500) -> str | None:
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


def _authority_id(value: object, label: str, *, prefix: str | None = None) -> str:
    result = _required_text(value, label, limit=50)
    if _AUTHORITY_ID.fullmatch(result) is None:
        raise PilotEvaluationError(f"{label} is not a canonical authority id")
    if prefix is not None and not result.startswith(prefix):
        raise PilotEvaluationError(f"{label} must start with {prefix}")
    return result


def _symbolic_code(value: object, label: str) -> str:
    result = _required_text(value, label, limit=64)
    if _SYMBOLIC_CODE.fullmatch(result) is None:
        raise PilotEvaluationError(f"{label} must be an uppercase symbolic code")
    return result


def _string_list(
    value: object,
    label: str,
    *,
    limit: int = 120,
    require_nonempty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PilotEvaluationError(f"{label} must be an array")
    result = tuple(_required_text(item, f"{label} item", limit=limit) for item in value)
    if require_nonempty and not result:
        raise PilotEvaluationError(f"{label} must not be empty")
    if len(set(result)) != len(result):
        raise PilotEvaluationError(f"{label} must not contain duplicates")
    return result


def _enum(enum_type: type[StrEnum], value: object, label: str) -> StrEnum:
    if not isinstance(value, str):
        raise PilotEvaluationError(f"{label} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise PilotEvaluationError(f"{label} has an unsupported value") from error


@dataclass(frozen=True, slots=True)
class PilotScenario:
    scenario_id: str
    pilot_case_id: str
    kind: PilotScenarioKind
    expected_code: str
    parameters: Mapping[str, object]
    snapshot: PilotScenarioSnapshot = PilotScenarioSnapshot.WORKING
    notes: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> "PilotScenario":
        data = _mapping(value, "pilot scenario")
        _reject_extra(
            data,
            {
                "id",
                "pilot_case_id",
                "kind",
                "expected_code",
                "snapshot",
                "parameters",
                "notes",
            },
            "pilot scenario",
        )
        raw_snapshot = data.get("snapshot", PilotScenarioSnapshot.WORKING.value)
        scenario = cls(
            scenario_id=_required_text(data.get("id"), "pilot scenario id", limit=80),
            pilot_case_id=_required_text(
                data.get("pilot_case_id"), "pilot scenario pilot_case_id", limit=80
            ),
            kind=PilotScenarioKind(
                _enum(PilotScenarioKind, data.get("kind"), "pilot scenario kind")
            ),
            expected_code=_symbolic_code(
                data.get("expected_code"), "pilot scenario expected_code"
            ),
            snapshot=PilotScenarioSnapshot(
                _enum(
                    PilotScenarioSnapshot,
                    raw_snapshot,
                    "pilot scenario snapshot",
                )
            ),
            parameters=_mapping(data.get("parameters", {}), "pilot scenario parameters"),
            notes=_optional_text(data.get("notes"), "pilot scenario notes", limit=4000),
        )
        return scenario.validate()

    def validate(self) -> "PilotScenario":
        if _SCENARIO_ID.fullmatch(self.scenario_id) is None:
            raise PilotEvaluationError(
                "pilot scenario id must match scenario_<lowercase-name>"
            )
        if _CASE_ID.fullmatch(self.pilot_case_id) is None:
            raise PilotEvaluationError(
                "pilot scenario pilot_case_id must match case_<lowercase-name>"
            )
        _validate_parameters(self.kind, self.parameters)
        if self.kind in {
            PilotScenarioKind.PUBLICATION_VISIBILITY,
            PilotScenarioKind.CHANGE_SCOPE,
        } and self.snapshot is not PilotScenarioSnapshot.WORKING:
            raise PilotEvaluationError(
                f"{self.kind.value} uses the working workspace context"
            )
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.scenario_id,
            "pilot_case_id": self.pilot_case_id,
            "kind": self.kind.value,
            "expected_code": self.expected_code,
            "snapshot": self.snapshot.value,
            "parameters": dict(self.parameters),
            "notes": self.notes,
        }


def _validate_parameters(
    kind: PilotScenarioKind, parameters: Mapping[str, object]
) -> None:
    allowed: set[str]
    required: set[str]

    if kind is PilotScenarioKind.COMPONENT_LOOKUP:
        allowed = required = {"manufacturer_id", "raw_mpn"}
        _authority_id(parameters.get("manufacturer_id"), "manufacturer_id", prefix="ent_")
        _required_text(parameters.get("raw_mpn"), "raw_mpn", limit=300)
    elif kind is PilotScenarioKind.PACKAGE_LOOKUP:
        allowed = required = {"raw_name"}
        _required_text(parameters.get("raw_name"), "raw_name", limit=300)
    elif kind is PilotScenarioKind.SOURCE_REVISION_LOOKUP:
        allowed = {"document_number", "revision", "publisher"}
        required = {"document_number", "revision"}
        _required_text(parameters.get("document_number"), "document_number", limit=200)
        _required_text(parameters.get("revision"), "revision", limit=200)
        if "publisher" in parameters:
            _required_text(parameters.get("publisher"), "publisher", limit=256)
    elif kind is PilotScenarioKind.SOURCE_LICENSE_GATE:
        allowed = required = {"source_id"}
        _authority_id(parameters.get("source_id"), "source_id", prefix="pk_")
    elif kind is PilotScenarioKind.SOURCE_SUPERSEDES:
        allowed = required = {"source_id", "target_source_id"}
        _authority_id(parameters.get("source_id"), "source_id", prefix="pk_")
        _authority_id(
            parameters.get("target_source_id"), "target_source_id", prefix="pk_"
        )
    elif kind is PilotScenarioKind.PIN_FACT_LOOKUP:
        allowed = required = {"component_id", "package_id", "pin_number"}
        _authority_id(parameters.get("component_id"), "component_id", prefix="ent_")
        _authority_id(parameters.get("package_id"), "package_id", prefix="ent_")
        _required_text(parameters.get("pin_number"), "pin_number", limit=100)
    elif kind is PilotScenarioKind.PARAMETER_LIMIT_LOOKUP:
        allowed = required = {"component_id", "parameter", "limit_kind"}
        _authority_id(parameters.get("component_id"), "component_id", prefix="ent_")
        _required_text(parameters.get("parameter"), "parameter", limit=300)
        _enum(
            ParameterLimitKind,
            parameters.get("limit_kind"),
            "parameter limit_kind",
        )
    elif kind is PilotScenarioKind.PARAMETER_LIMIT_DISTINCTION:
        allowed = required = {"component_id", "parameter"}
        _authority_id(parameters.get("component_id"), "component_id", prefix="ent_")
        _required_text(parameters.get("parameter"), "parameter", limit=300)
    elif kind is PilotScenarioKind.FACT_CONFLICT:
        allowed = required = {"fact_id"}
        _authority_id(parameters.get("fact_id"), "fact_id", prefix="fact_")
    elif kind is PilotScenarioKind.ANCHOR_INTEGRITY:
        allowed = {"fact_id", "source_id", "page", "quote_sha256"}
        required = {"fact_id", "source_id", "page"}
        _authority_id(parameters.get("fact_id"), "fact_id", prefix="fact_")
        _authority_id(parameters.get("source_id"), "source_id", prefix="pk_")
        page = parameters.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise PilotEvaluationError("anchor page must be a positive integer")
        if "quote_sha256" in parameters:
            digest = _required_text(
                parameters.get("quote_sha256"), "quote_sha256", limit=64
            )
            if _SHA256.fullmatch(digest) is None:
                raise PilotEvaluationError(
                    "quote_sha256 must be a lowercase SHA-256 digest"
                )
    elif kind is PilotScenarioKind.REVIEW_HISTORY:
        allowed = required = {"record_id", "actions"}
        _authority_id(parameters.get("record_id"), "record_id")
        actions = _string_list(
            parameters.get("actions"),
            "review actions",
            limit=32,
            require_nonempty=True,
        )
        for action in actions:
            _enum(ReviewAction, action, "review action")
    elif kind is PilotScenarioKind.PUBLICATION_VISIBILITY:
        allowed = required = {"record_id"}
        _authority_id(parameters.get("record_id"), "record_id")
    elif kind is PilotScenarioKind.CHANGE_SCOPE:
        allowed = required = set()
    else:  # pragma: no cover - enum exhaustiveness
        raise PilotEvaluationError(f"unsupported pilot scenario kind: {kind.value}")

    _reject_extra(parameters, allowed, f"{kind.value} parameters")
    missing = sorted(required - set(parameters))
    if missing:
        raise PilotEvaluationError(
            f"{kind.value} parameters are missing: {', '.join(missing)}"
        )


@dataclass(frozen=True, slots=True)
class PilotScenarioSuite:
    dataset_name: str
    scenarios: tuple[PilotScenario, ...]
    notes: str | None = None
    format: str = PILOT_SCENARIO_FORMAT

    @classmethod
    def from_dict(cls, value: object) -> "PilotScenarioSuite":
        data = _mapping(value, "pilot scenario suite")
        _reject_extra(
            data,
            {"format", "dataset_name", "scenarios", "notes"},
            "pilot scenario suite",
        )
        raw_scenarios = data.get("scenarios")
        if not isinstance(raw_scenarios, list):
            raise PilotEvaluationError("pilot scenario suite scenarios must be an array")
        suite = cls(
            format=_required_text(
                data.get("format"), "pilot scenario suite format", limit=64
            ),
            dataset_name=_required_text(
                data.get("dataset_name"), "pilot scenario dataset_name", limit=200
            ),
            scenarios=tuple(PilotScenario.from_dict(item) for item in raw_scenarios),
            notes=_optional_text(
                data.get("notes"), "pilot scenario suite notes", limit=4000
            ),
        )
        return suite.validate()

    @classmethod
    def from_json(cls, payload: str) -> "PilotScenarioSuite":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise PilotEvaluationError(
                f"pilot scenario suite is not valid JSON: {error.msg}"
            ) from error
        return cls.from_dict(value)

    @classmethod
    def from_path(cls, path: Path) -> "PilotScenarioSuite":
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise PilotEvaluationError(
                f"pilot scenario suite is not a regular file: {resolved}"
            )
        if resolved.stat().st_size > 1_000_000:
            raise PilotEvaluationError("pilot scenario suite exceeds 1 MiB")
        try:
            payload = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise PilotEvaluationError(
                "pilot scenario suite must be UTF-8"
            ) from error
        return cls.from_json(payload)

    def validate(self) -> "PilotScenarioSuite":
        if self.format != PILOT_SCENARIO_FORMAT:
            raise PilotEvaluationError(
                f"pilot scenario suite format must equal {PILOT_SCENARIO_FORMAT}"
            )
        scenario_ids = [scenario.scenario_id for scenario in self.scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise PilotEvaluationError("pilot scenario ids must be unique")
        case_ids = [scenario.pilot_case_id for scenario in self.scenarios]
        if len(set(case_ids)) != len(case_ids):
            raise PilotEvaluationError(
                "one pilot case may be bound to at most one executable scenario"
            )
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "dataset_name": self.dataset_name,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "notes": self.notes,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=False
        ) + "\n"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PilotScenarioResult:
    scenario_id: str
    pilot_case_id: str
    kind: PilotScenarioKind
    expected_code: str
    observed_code: str
    passed: bool
    detail: str
    related_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.scenario_id,
            "pilot_case_id": self.pilot_case_id,
            "kind": self.kind.value,
            "expected_code": self.expected_code,
            "observed_code": self.observed_code,
            "status": "PASS" if self.passed else "FAIL",
            "detail": self.detail,
            "related_ids": list(self.related_ids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "PilotScenarioResult":
        data = _mapping(value, "pilot scenario result")
        _reject_extra(
            data,
            {
                "id",
                "pilot_case_id",
                "kind",
                "expected_code",
                "observed_code",
                "status",
                "detail",
                "related_ids",
            },
            "pilot scenario result",
        )
        status = _required_text(data.get("status"), "scenario result status", limit=8)
        if status not in {"PASS", "FAIL"}:
            raise PilotEvaluationError(
                "scenario result status must be PASS or FAIL"
            )
        related = _string_list(
            data.get("related_ids", []),
            "scenario result related_ids",
            limit=50,
        )
        for record_id in related:
            if _AUTHORITY_ID.fullmatch(record_id) is None:
                raise PilotEvaluationError(
                    f"scenario result related id is invalid: {record_id}"
                )
        expected = _symbolic_code(
            data.get("expected_code"), "scenario result expected_code"
        )
        observed = _symbolic_code(
            data.get("observed_code"), "scenario result observed_code"
        )
        result = cls(
            scenario_id=_required_text(data.get("id"), "scenario result id", limit=80),
            pilot_case_id=_required_text(
                data.get("pilot_case_id"), "scenario result pilot_case_id", limit=80
            ),
            kind=PilotScenarioKind(
                _enum(PilotScenarioKind, data.get("kind"), "scenario result kind")
            ),
            expected_code=expected,
            observed_code=observed,
            passed=status == "PASS",
            detail=_required_text(data.get("detail"), "scenario result detail", limit=4000),
            related_ids=related,
        )
        if _SCENARIO_ID.fullmatch(result.scenario_id) is None:
            raise PilotEvaluationError("scenario result id is invalid")
        if _CASE_ID.fullmatch(result.pilot_case_id) is None:
            raise PilotEvaluationError("scenario result pilot_case_id is invalid")
        if result.passed != (expected == observed):
            raise PilotEvaluationError(
                "scenario result PASS/FAIL must agree with expected/observed codes"
            )
        return result


@dataclass(frozen=True, slots=True)
class PilotScenarioReport:
    dataset_name: str
    suite_sha256: str
    workspace: str
    working_fingerprint: str
    git_state_fingerprint: str
    published_ref: str
    published_commit: str | None
    results: tuple[PilotScenarioResult, ...]
    format: str = PILOT_SCENARIO_REPORT_FORMAT

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "dataset_name": self.dataset_name,
            "suite_sha256": self.suite_sha256,
            "workspace": self.workspace,
            "working_fingerprint": self.working_fingerprint,
            "git_state_fingerprint": self.git_state_fingerprint,
            "published_ref": self.published_ref,
            "published_commit": self.published_commit,
            "status": "PASS" if self.passed else "FAIL",
            "results": [result.to_dict() for result in self.results],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"

    @classmethod
    def from_dict(cls, value: object) -> "PilotScenarioReport":
        data = _mapping(value, "pilot scenario report")
        _reject_extra(
            data,
            {
                "format",
                "dataset_name",
                "suite_sha256",
                "workspace",
                "working_fingerprint",
                "git_state_fingerprint",
                "published_ref",
                "published_commit",
                "status",
                "results",
            },
            "pilot scenario report",
        )
        if data.get("format") != PILOT_SCENARIO_REPORT_FORMAT:
            raise PilotEvaluationError(
                f"pilot scenario report format must equal {PILOT_SCENARIO_REPORT_FORMAT}"
            )
        suite_sha256 = _required_text(
            data.get("suite_sha256"), "scenario report suite_sha256", limit=64
        )
        fingerprint = _required_text(
            data.get("working_fingerprint"),
            "scenario report working_fingerprint",
            limit=64,
        )
        git_fingerprint = _required_text(
            data.get("git_state_fingerprint"),
            "scenario report git_state_fingerprint",
            limit=64,
        )
        if _SHA256.fullmatch(suite_sha256) is None:
            raise PilotEvaluationError("scenario report suite_sha256 is invalid")
        if _SHA256.fullmatch(fingerprint) is None:
            raise PilotEvaluationError(
                "scenario report working_fingerprint is invalid"
            )
        if _SHA256.fullmatch(git_fingerprint) is None:
            raise PilotEvaluationError(
                "scenario report git_state_fingerprint is invalid"
            )
        raw_results = data.get("results")
        if not isinstance(raw_results, list):
            raise PilotEvaluationError("scenario report results must be an array")
        results = tuple(PilotScenarioResult.from_dict(item) for item in raw_results)
        report = cls(
            format=PILOT_SCENARIO_REPORT_FORMAT,
            dataset_name=_required_text(
                data.get("dataset_name"), "scenario report dataset_name", limit=200
            ),
            suite_sha256=suite_sha256,
            workspace=_required_text(
                data.get("workspace"), "scenario report workspace", limit=4096
            ),
            working_fingerprint=fingerprint,
            git_state_fingerprint=git_fingerprint,
            published_ref=_required_text(
                data.get("published_ref"), "scenario report published_ref", limit=500
            ),
            published_commit=_optional_text(
                data.get("published_commit"), "scenario report published_commit", limit=64
            ),
            results=results,
        )
        status = _required_text(data.get("status"), "scenario report status", limit=8)
        if status not in {"PASS", "FAIL"}:
            raise PilotEvaluationError("scenario report status must be PASS or FAIL")
        if (status == "PASS") != report.passed:
            raise PilotEvaluationError(
                "scenario report status does not match its result set"
            )
        if report.published_commit is not None and not re.fullmatch(
            r"[0-9a-f]{40}", report.published_commit
        ):
            raise PilotEvaluationError("scenario report published_commit is invalid")
        ids = [item.scenario_id for item in report.results]
        if len(set(ids)) != len(ids):
            raise PilotEvaluationError("scenario report result ids must be unique")
        case_ids = [item.pilot_case_id for item in report.results]
        if len(set(case_ids)) != len(case_ids):
            raise PilotEvaluationError(
                "scenario report pilot_case_id values must be unique"
            )
        return report

    @classmethod
    def from_json(cls, payload: str) -> "PilotScenarioReport":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise PilotEvaluationError(
                f"pilot scenario report is not valid JSON: {error.msg}"
            ) from error
        return cls.from_dict(value)

    @classmethod
    def from_path(cls, path: Path) -> "PilotScenarioReport":
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise PilotEvaluationError(
                f"pilot scenario report is not a regular file: {resolved}"
            )
        if resolved.stat().st_size > 2_000_000:
            raise PilotEvaluationError("pilot scenario report exceeds 2 MiB")
        try:
            return cls.from_json(resolved.read_text(encoding="utf-8"))
        except UnicodeDecodeError as error:
            raise PilotEvaluationError(
                "pilot scenario report must be UTF-8"
            ) from error


def snapshot_fingerprint(snapshot: AuthoritySnapshot) -> str:
    digest = hashlib.sha256()
    for prefix, records in (
        ("SOURCE", snapshot.sources),
        ("ENTITY", snapshot.entities),
        ("FACT", snapshot.facts),
    ):
        for record in sorted(records, key=lambda item: item.id):
            digest.update(prefix.encode("ascii"))
            digest.update(b"\0")
            digest.update(record.id.encode("ascii"))
            digest.update(b"\0")
            digest.update(record.canonical_json().encode("utf-8"))
    return digest.hexdigest()


def git_state_fingerprint(repository: KnowledgeRepository) -> str:
    changes = repository.git_changes()
    digest = hashlib.sha256()
    digest.update(repository.git_change_scope().value.encode("ascii"))
    digest.update(b"\0")
    for line in changes.status_lines:
        digest.update(line.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _active_facts(snapshot: AuthoritySnapshot) -> tuple[FactRecord, ...]:
    superseded = {
        fact.supersedes for fact in snapshot.facts if fact.supersedes is not None
    }
    return tuple(fact for fact in snapshot.facts if fact.id not in superseded)


def _record(snapshot: AuthoritySnapshot, record_id: str) -> SourceRecord | FactRecord | object | None:
    for collection in (snapshot.sources, snapshot.entities, snapshot.facts):
        for record in collection:
            if record.id == record_id:
                return record
    return None


def _lookup_code(matches: Sequence[object]) -> str:
    if not matches:
        return "UNKNOWN"
    if len(matches) == 1:
        return "EXACT"
    return "CONFLICT"


def _run_one(
    repository: KnowledgeRepository,
    scenario: PilotScenario,
    *,
    working: AuthoritySnapshot,
    published: AuthoritySnapshot,
) -> PilotScenarioResult:
    snapshot = working if scenario.snapshot is PilotScenarioSnapshot.WORKING else published
    parameters = scenario.parameters
    observed: str
    detail: str
    related: tuple[str, ...] = ()

    if scenario.kind is PilotScenarioKind.COMPONENT_LOOKUP:
        manufacturer_id = str(parameters["manufacturer_id"])
        key = normalize_lookup(str(parameters["raw_mpn"]))
        matches = tuple(
            entity
            for entity in snapshot.entities
            if entity.kind is EntityKind.COMPONENT
            and entity.manufacturer_id == manufacturer_id
            and entity.normalized_mpn == key
        )
        observed = _lookup_code(matches)
        related = tuple(item.id for item in matches)
        detail = f"Exact component lookup returned {len(matches)} canonical matches."
    elif scenario.kind is PilotScenarioKind.PACKAGE_LOOKUP:
        key = normalize_lookup(str(parameters["raw_name"]))
        matches = tuple(
            entity
            for entity in snapshot.entities
            if entity.kind is EntityKind.PACKAGE and entity.normalized_key == key
        )
        observed = _lookup_code(matches)
        related = tuple(item.id for item in matches)
        detail = f"Exact package lookup returned {len(matches)} canonical matches."
    elif scenario.kind is PilotScenarioKind.SOURCE_REVISION_LOOKUP:
        document_number = str(parameters["document_number"]).strip()
        revision = str(parameters["revision"]).strip()
        publisher = parameters.get("publisher")
        matches = tuple(
            source
            for source in snapshot.sources
            if source.document_number == document_number
            and source.revision == revision
            and (
                publisher is None
                or source.source.publisher == str(publisher).strip()
            )
        )
        observed = _lookup_code(matches)
        related = tuple(item.id for item in matches)
        detail = f"Exact Source revision lookup returned {len(matches)} matches."
    elif scenario.kind is PilotScenarioKind.SOURCE_LICENSE_GATE:
        source_id = str(parameters["source_id"])
        source = next((item for item in snapshot.sources if item.id == source_id), None)
        if source is None:
            observed = "UNKNOWN"
            detail = "Source does not exist in the selected snapshot."
        elif source.agent_processing_allowed:
            observed = "ALLOWED"
            related = (source.id,)
            detail = f"Source license {source.license_class.value} permits processing."
        else:
            observed = "BLOCKED"
            related = (source.id,)
            detail = f"Source license {source.license_class.value} blocks processing."
    elif scenario.kind is PilotScenarioKind.SOURCE_SUPERSEDES:
        source_id = str(parameters["source_id"])
        target_id = str(parameters["target_source_id"])
        source = next((item for item in snapshot.sources if item.id == source_id), None)
        if source is None:
            observed = "UNKNOWN"
            detail = "Source does not exist in the selected snapshot."
        elif source.supersedes is None:
            observed = "NO_RELATION"
            related = (source.id,)
            detail = "Source has no supersedes relationship."
        elif source.supersedes == target_id:
            observed = "MATCH"
            related = (source.id, target_id)
            detail = "Source supersedes the expected exact revision."
        else:
            observed = "MISMATCH"
            related = (source.id, source.supersedes)
            detail = "Source supersedes a different revision."
    elif scenario.kind is PilotScenarioKind.PIN_FACT_LOOKUP:
        component_id = str(parameters["component_id"])
        package_id = str(parameters["package_id"])
        pin_number = str(parameters["pin_number"]).strip()
        matches = tuple(
            fact
            for fact in _active_facts(snapshot)
            if isinstance(fact.payload, ComponentPinPayload)
            and fact.payload.component_id == component_id
            and fact.payload.package_id == package_id
            and fact.payload.pin_number == pin_number
        )
        observed = _lookup_code(matches)
        related = tuple(item.id for item in matches)
        detail = f"Exact pin Fact lookup returned {len(matches)} active matches."
    elif scenario.kind is PilotScenarioKind.PARAMETER_LIMIT_LOOKUP:
        component_id = str(parameters["component_id"])
        parameter = str(parameters["parameter"]).strip()
        limit_kind = ParameterLimitKind(str(parameters["limit_kind"]))
        matches = tuple(
            fact
            for fact in _active_facts(snapshot)
            if isinstance(fact.payload, ParameterLimitPayload)
            and fact.payload.component_id == component_id
            and fact.payload.parameter == parameter
            and fact.payload.limit_kind is limit_kind
        )
        observed = _lookup_code(matches)
        related = tuple(item.id for item in matches)
        detail = (
            f"Exact {limit_kind.value} parameter Fact lookup returned "
            f"{len(matches)} active matches."
        )
    elif scenario.kind is PilotScenarioKind.PARAMETER_LIMIT_DISTINCTION:
        component_id = str(parameters["component_id"])
        parameter = str(parameters["parameter"]).strip()
        matches = tuple(
            fact
            for fact in _active_facts(snapshot)
            if isinstance(fact.payload, ParameterLimitPayload)
            and fact.payload.component_id == component_id
            and fact.payload.parameter == parameter
        )
        absolute = tuple(
            fact
            for fact in matches
            if fact.payload.limit_kind is ParameterLimitKind.ABSOLUTE_MAXIMUM
        )
        recommended = tuple(
            fact
            for fact in matches
            if fact.payload.limit_kind is ParameterLimitKind.RECOMMENDED_OPERATING
        )
        related = tuple(item.id for item in (*absolute, *recommended))
        if len(absolute) > 1 or len(recommended) > 1:
            observed = "CONFLICT"
            detail = "Multiple active Facts exist for one required limit kind."
        elif not absolute or not recommended:
            observed = "MISSING_SIDE"
            detail = "Absolute-maximum and recommended-operating Facts are not both present."
        else:
            observed = "DISTINCT"
            detail = "Absolute-maximum and recommended-operating Facts resolve separately."
    elif scenario.kind is PilotScenarioKind.FACT_CONFLICT:
        fact_id = str(parameters["fact_id"])
        fact = next((item for item in snapshot.facts if item.id == fact_id), None)
        if fact is None:
            observed = "UNKNOWN"
            detail = "Fact does not exist in the selected snapshot."
        else:
            conflicting_ids = tuple(
                other_id
                for conflict in snapshot.conflicts
                if fact.id in conflict.fact_ids
                for other_id in conflict.fact_ids
                if other_id != fact.id
            )
            if conflicting_ids:
                observed = "CONFLICT"
                related = (fact.id, *dict.fromkeys(conflicting_ids))
                detail = "Fact participates in an unresolved semantic conflict."
            else:
                observed = "CLEAR"
                related = (fact.id,)
                detail = "Fact has no unresolved semantic conflict."
    elif scenario.kind is PilotScenarioKind.ANCHOR_INTEGRITY:
        fact_id = str(parameters["fact_id"])
        source_id = str(parameters["source_id"])
        page = int(parameters["page"])
        expected_hash = parameters.get("quote_sha256")
        fact = next((item for item in snapshot.facts if item.id == fact_id), None)
        if fact is None:
            observed = "UNKNOWN"
            detail = "Fact does not exist in the selected snapshot."
        else:
            anchors = tuple(
                anchor
                for anchor in fact.evidence_anchors
                if anchor.source_id == source_id and anchor.page == page
            )
            related = (fact.id, source_id)
            if not anchors:
                observed = "UNKNOWN"
                detail = "No anchor matches the expected Source and page."
            elif not any(anchor.complete for anchor in anchors):
                observed = "INCOMPLETE"
                detail = "Matching anchor exists but is incomplete."
            elif expected_hash is not None and not any(
                anchor.quote_sha256 == expected_hash for anchor in anchors
            ):
                observed = "DRIFT"
                detail = "Matching anchor quote hash differs from the expected digest."
            else:
                observed = "MATCH"
                detail = "Complete anchor matches Source, page, and optional quote hash."
    elif scenario.kind is PilotScenarioKind.REVIEW_HISTORY:
        record_id = str(parameters["record_id"])
        record = _record(snapshot, record_id)
        if record is None or not hasattr(record, "review_history"):
            observed = "UNKNOWN"
            detail = "Reviewable record does not exist in the selected snapshot."
        else:
            expected_actions = tuple(str(item) for item in parameters["actions"])
            actual_actions = tuple(
                event.action.value for event in record.review_history
            )
            related = (record_id,)
            if actual_actions == expected_actions:
                observed = "MATCH"
                detail = "Review history exactly matches the required action sequence."
            else:
                observed = "MISMATCH"
                detail = (
                    "Review history differs from the required exact action sequence: "
                    + ",".join(actual_actions)
                )
    elif scenario.kind is PilotScenarioKind.PUBLICATION_VISIBILITY:
        record_id = str(parameters["record_id"])
        working_ids = {
            item.id
            for collection in (working.sources, working.entities, working.facts)
            for item in collection
        }
        published_ids = {
            item.id
            for collection in (published.sources, published.entities, published.facts)
            for item in collection
        }
        if record_id in working_ids and record_id in published_ids:
            observed = "PUBLISHED"
            related = (record_id,)
            detail = "Record exists in both working authority and Published Knowledge."
        elif record_id in working_ids:
            observed = "WORKING_ONLY"
            related = (record_id,)
            detail = "Record exists only in mutable working authority."
        elif record_id in published_ids:
            observed = "PUBLISHED_ONLY"
            related = (record_id,)
            detail = "Record exists only in the selected published snapshot."
        else:
            observed = "MISSING"
            detail = "Record is absent from both working and published authority."
    elif scenario.kind is PilotScenarioKind.CHANGE_SCOPE:
        observed = repository.git_change_scope().value
        detail = "Observed current next-commit scope without mutating Git state."
    else:  # pragma: no cover - enum exhaustiveness
        raise PilotEvaluationError(
            f"unsupported pilot scenario kind: {scenario.kind.value}"
        )

    return PilotScenarioResult(
        scenario_id=scenario.scenario_id,
        pilot_case_id=scenario.pilot_case_id,
        kind=scenario.kind,
        expected_code=scenario.expected_code,
        observed_code=observed,
        passed=observed == scenario.expected_code,
        detail=detail,
        related_ids=tuple(dict.fromkeys(related)),
    )


def run_pilot_scenarios(
    repository: KnowledgeRepository,
    suite: PilotScenarioSuite,
    *,
    published_ref: str = "HEAD",
) -> PilotScenarioReport:
    suite.validate()
    working = repository.validate_all(require_canonical=True)
    published = repository.read_published_snapshot(ref=published_ref)
    results = tuple(
        _run_one(
            repository,
            scenario,
            working=working,
            published=published,
        )
        for scenario in suite.scenarios
    )
    return PilotScenarioReport(
        dataset_name=suite.dataset_name,
        suite_sha256=suite.digest,
        workspace=str(repository.root),
        working_fingerprint=snapshot_fingerprint(working),
        git_state_fingerprint=git_state_fingerprint(repository),
        published_ref=published_ref,
        published_commit=published.commit,
        results=results,
    )


def _validate_report_binding(
    repository: KnowledgeRepository,
    report: PilotScenarioReport,
    *,
    published_ref: str,
) -> None:
    working = repository.validate_all(require_canonical=True)
    published = repository.read_published_snapshot(ref=published_ref)
    current_fingerprint = snapshot_fingerprint(working)
    if report.working_fingerprint != current_fingerprint:
        raise PilotEvaluationError(
            "pilot scenario report is stale: working authority fingerprint changed"
        )
    if report.git_state_fingerprint != git_state_fingerprint(repository):
        raise PilotEvaluationError(
            "pilot scenario report is stale: Git working-state fingerprint changed"
        )
    if report.published_commit != published.commit:
        raise PilotEvaluationError(
            "pilot scenario report is stale: published commit changed"
        )


def apply_scenario_report(
    manifest: PilotEvaluationManifest,
    report: PilotScenarioReport,
    repository: KnowledgeRepository,
    *,
    published_ref: str = "HEAD",
) -> PilotEvaluationManifest:
    manifest.validate()
    _validate_report_binding(repository, report, published_ref=published_ref)
    if manifest.dataset_name != report.dataset_name:
        raise PilotEvaluationError(
            "pilot evaluation and scenario report dataset_name must match"
        )

    results_by_case = {result.pilot_case_id: result for result in report.results}
    cases_by_id = {case.case_id: case for case in manifest.cases}
    missing_cases = sorted(set(results_by_case) - set(cases_by_id))
    if missing_cases:
        raise PilotEvaluationError(
            "scenario report references missing pilot case " + missing_cases[0]
        )

    effective_cases: list[PilotCase] = []
    for case in manifest.cases:
        result = results_by_case.get(case.case_id)
        if result is None:
            effective_cases.append(case)
            continue
        if case.category not in _KIND_CATEGORY_COMPATIBILITY[result.kind]:
            raise PilotEvaluationError(
                f"scenario {result.scenario_id} kind {result.kind.value} "
                f"is not compatible with pilot category {case.category.value}"
            )
        if case.expected_code != result.expected_code:
            raise PilotEvaluationError(
                f"scenario {result.scenario_id} expected_code disagrees with pilot case"
            )
        status = PilotCaseStatus.PASS if result.passed else PilotCaseStatus.FAIL
        if case.status is not PilotCaseStatus.NOT_RUN:
            if case.status is not status or case.observed_code != result.observed_code:
                raise PilotEvaluationError(
                    f"pilot case {case.case_id} manual receipt disagrees with "
                    "executable scenario result"
                )
        effective_cases.append(
            replace(
                case,
                status=status,
                observed_code=result.observed_code,
            ).validate()
        )

    return replace(manifest, cases=tuple(effective_cases)).validate()


def example_scenario_suite_payload() -> dict[str, object]:
    manufacturer = "ent_" + "1" * 24
    component = "ent_" + "2" * 24
    package = "ent_" + "3" * 24
    source_new = "pk_" + "4" * 24
    source_old = "pk_" + "5" * 24
    fact = "fact_" + "6" * 24
    return {
        "format": PILOT_SCENARIO_FORMAT,
        "dataset_name": "private-pcb-pilot",
        "scenarios": [
            {
                "id": "scenario_wrong_mpn",
                "pilot_case_id": "case_wrong_mpn",
                "kind": "COMPONENT_LOOKUP",
                "expected_code": "UNKNOWN",
                "snapshot": "WORKING",
                "parameters": {
                    "manufacturer_id": manufacturer,
                    "raw_mpn": "INTENTIONALLY-WRONG-MPN",
                },
                "notes": "Wrong raw input belongs here, never in canonical Entity authority.",
            },
            {
                "id": "scenario_wrong_package",
                "pilot_case_id": "case_wrong_package",
                "kind": "PIN_FACT_LOOKUP",
                "expected_code": "UNKNOWN",
                "snapshot": "WORKING",
                "parameters": {
                    "component_id": component,
                    "package_id": package,
                    "pin_number": "999",
                },
                "notes": None,
            },
            {
                "id": "scenario_wrong_revision",
                "pilot_case_id": "case_wrong_revision",
                "kind": "SOURCE_REVISION_LOOKUP",
                "expected_code": "UNKNOWN",
                "snapshot": "WORKING",
                "parameters": {
                    "document_number": "REPLACE-WITH-DOCUMENT-NUMBER",
                    "revision": "INTENTIONALLY-WRONG",
                },
                "notes": None,
            },
            {
                "id": "scenario_limit_distinction",
                "pilot_case_id": "case_abs_max_recommended",
                "kind": "PARAMETER_LIMIT_DISTINCTION",
                "expected_code": "DISTINCT",
                "snapshot": "WORKING",
                "parameters": {
                    "component_id": component,
                    "parameter": "Input voltage",
                },
                "notes": None,
            },
            {
                "id": "scenario_license_block",
                "pilot_case_id": "case_license_block",
                "kind": "SOURCE_LICENSE_GATE",
                "expected_code": "BLOCKED",
                "snapshot": "WORKING",
                "parameters": {"source_id": source_new},
                "notes": "Point this at a deliberately blocked Source used only for policy evaluation.",
            },
            {
                "id": "scenario_supersedes",
                "pilot_case_id": "case_supersede",
                "kind": "SOURCE_SUPERSEDES",
                "expected_code": "MATCH",
                "snapshot": "WORKING",
                "parameters": {
                    "source_id": source_new,
                    "target_source_id": source_old,
                },
                "notes": None,
            },
            {
                "id": "scenario_anchor_integrity",
                "pilot_case_id": "case_anchor_drift",
                "kind": "ANCHOR_INTEGRITY",
                "expected_code": "MATCH",
                "snapshot": "WORKING",
                "parameters": {
                    "fact_id": fact,
                    "source_id": source_new,
                    "page": 1,
                },
                "notes": None,
            },
        ],
        "notes": (
            "Replace placeholder canonical IDs after private ingestion. Add review-history, "
            "publication-visibility, conflict, and change-scope scenarios as the pilot needs them."
        ),
    }


def write_example_scenario_suite(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists():
        raise PilotEvaluationError(
            f"refusing to overwrite existing scenario suite: {resolved}"
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(
            example_scenario_suite_payload(),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return resolved
