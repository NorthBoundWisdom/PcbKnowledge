"""Append-only containment receipts, separate from immutable intake observations.

A disposition never resolves manufacturer wording or verifies local source bytes.
Every linkage is checked against the complete selected intake snapshot before any
receipt is exposed. There is no fallback to an unpinned or similarly named source.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .intake import IntakeError, MAX_INTAKE_BYTES, _check_claims, _reject_constant, _unique_object

DISPOSITION_FORMAT = "pcbknowledge-intake-disposition-v1"
DISPOSITION_DIRECTORY = "knowledge/intake-dispositions"


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _finite_number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _range(value: Any) -> bool:
    return (isinstance(value, dict) and set(value) == {"min", "max", "inclusive"}
            and value["inclusive"] is True
            and all(_finite_number(value[k]) for k in ("min", "max"))
            and value["min"] <= value["max"])


def _validate(data: Any, batches: dict[str, dict]) -> None:
    if not isinstance(data, dict) or data.get("format") != DISPOSITION_FORMAT:
        raise IntakeError(f"disposition format must be {DISPOSITION_FORMAT}")
    fields = {"format", "id", "canonical", "human_reviewed", "manufacturer_confirmed", "recorded_on",
              "acceptance_status", "disposition_status", "source_issue_status", "basis", "target",
              "summary", "policy", "evidence", "remaining_evidence_needed", "review", "history_policy"}
    if set(data) != fields or not all(_text(data.get(k)) for k in
                                     ("summary", "remaining_evidence_needed", "history_policy")):
        raise IntakeError("disposition has missing or unsupported receipt fields")
    _check_claims(data)
    for key in ("canonical", "human_reviewed", "manufacturer_confirmed"):
        if data.get(key) is not False:
            raise IntakeError(f"disposition {key} must be explicitly false")
    if (not _text(data.get("id")) or not _text(data.get("recorded_on"))
            or data.get("acceptance_status") != "AGENT_REVIEWED_UNDER_OWNER_DELEGATION"
            or data.get("disposition_status") != "CONTAINED_BY_CONSERVATIVE_SUBSET"
            or data.get("source_issue_status") != "UNRESOLVED_SOURCE_WORDING"
            or data.get("basis") != "AGENT_CONSERVATIVE_INTERSECTION"):
        raise IntakeError("disposition requires explicit containment, not source resolution")
    try:
        date.fromisoformat(data["recorded_on"])
    except ValueError as error:
        raise IntakeError("invalid disposition date") from error
    review = data.get("review")
    if (not isinstance(review, dict)
            or set(review) != {"actor_type", "actor_id", "authority", "reviewed_at", "independent_reviewer", "independent_review_basis"}
            or not _text(review.get("independent_review_basis")) or review.get("actor_type") != "AGENT"
            or review.get("authority") != "OWNER_DELEGATION"
            or not _text(review.get("actor_id")) or not _text(review.get("reviewed_at"))
            or not _text(review.get("independent_reviewer"))
            or review.get("independent_reviewer") == review.get("actor_id")):
        raise IntakeError("disposition requires actual independent Agent review provenance")
    try:
        reviewed = datetime.fromisoformat(review["reviewed_at"])
        if reviewed.tzinfo is None or reviewed.date() != date.fromisoformat(data["recorded_on"]):
            raise ValueError("review/record date mismatch or missing timezone")
    except ValueError as error:
        raise IntakeError("invalid disposition review timestamp") from error
    target = data.get("target")
    required = {"batch_path", "batch_sha256", "issue_id", "source_id", "source_sha256",
                "device", "package", "revision"}
    if not isinstance(target, dict) or set(target) != required or not all(_text(v) for v in target.values()):
        raise IntakeError("disposition target requires exact batch, issue, source and identity pins")
    if not _digest(target["batch_sha256"]) or not _digest(target["source_sha256"]):
        raise IntakeError("disposition target requires SHA-256 byte pins")
    batch = batches.get(target["batch_path"])
    if batch is None:
        raise IntakeError("orphan disposition batch target")
    if batch["sha256"] != target["batch_sha256"]:
        raise IntakeError("stale disposition batch SHA-256")
    source = next((s for s in batch["data"]["sources"] if s["id"] == target["source_id"]), None)
    if (source is None or source.get("pdf_sha256") != target["source_sha256"]
            or any(source.get(k) != target[k] for k in ("device", "package", "revision"))):
        raise IntakeError("disposition source identity or SHA-256 mismatch")
    issues = batch["data"].get("source_issues", [])
    if not isinstance(issues, list) or any(not isinstance(i, dict) for i in issues):
        raise IntakeError("invalid disposition source issue collection")
    issue = [i for i in issues if i.get("id") == target["issue_id"]]
    if (len(issue) != 1 or issue[0].get("source_id") != target["source_id"]
            or issue[0].get("source_sha256") != target["source_sha256"]
            or issue[0].get("issue_status") != data["source_issue_status"]):
        raise IntakeError("disposition issue linkage or historical state mismatch")
    policy = data.get("policy")
    if (not isinstance(policy, dict)
            or set(policy) != {"screening_only", "parameter", "supply_v", "ambient_c", "inside_result", "outside_result", "automatic_recommendation", "limitations"}
            or policy.get("screening_only") is not True
            or policy.get("parameter") != "supply_voltage_vs_ambient_temperature"
            or not _range(policy.get("supply_v")) or not _range(policy.get("ambient_c"))
            or policy.get("inside_result") != "WITHIN_CONSERVATIVE_SUPPLY_AMBIENT_SUBSET"
            or policy.get("outside_result") != "NOT_ESTABLISHED"
            or policy.get("automatic_recommendation") is not False
            or not isinstance(policy.get("limitations"), list) or not policy["limitations"]
            or not all(_text(item) for item in policy["limitations"])):
        raise IntakeError("disposition must preserve bounded preliminary screening and unknown outside")
    _validate_evidence(data["evidence"], target, source)


def _validate_evidence(evidence: Any, target: dict, source: dict) -> None:
    if not isinstance(evidence, list) or not evidence:
        raise IntakeError("disposition requires dated evidence receipts")
    roles = set()
    for item in evidence:
        fields = {"role", "url", "sha256", "byte_size", "accessed_on", "retrieved_at", "revision",
                  "revision_date", "pdf_pages", "locators", "method", "finding",
                  "redistribution_license", "latest_revision_guaranteed"}
        if (not isinstance(item, dict) or set(item) != fields
                or not isinstance(item.get("role"), str)
                or item.get("role") not in {"HISTORICAL_SOURCE", "RECHECK_DATASHEET", "RELATED_ERRATA", "OFFICIAL_PRODUCT_PAGE"}
                or item["role"] in roles or not _text(item.get("url"))
                or not item["url"].startswith("https://") or not _text(item.get("accessed_on"))
                or not _digest(item.get("sha256")) or type(item.get("byte_size")) is not int
                or item["byte_size"] <= 0 or item.get("latest_revision_guaranteed") is not False
                or not all(_text(item.get(k)) for k in
                           ("finding", "retrieved_at", "method", "redistribution_license"))):
            raise IntakeError("invalid disposition evidence receipt")
        try:
            accessed = date.fromisoformat(item["accessed_on"])
            retrieved = datetime.fromisoformat(item["retrieved_at"])
            if retrieved.tzinfo is None or retrieved.date() != accessed:
                raise ValueError("access/retrieval date mismatch or missing timezone")
        except ValueError as error:
            raise IntakeError("invalid evidence access date") from error
        roles.add(item["role"])
        if item["role"] == "HISTORICAL_SOURCE" and (
            item["sha256"] != target["source_sha256"] or item["revision"] != target["revision"]
        ):
            raise IntakeError("historical evidence must identify the exact target source")
        if item["role"] == "HISTORICAL_SOURCE" and any(
            key in source and source[key] != item[field]
            for key, field in (("pdf_byte_size", "byte_size"), ("pdf_pages", "pdf_pages"))
        ):
            raise IntakeError("historical evidence size/page count contradicts pinned source metadata")
        if item["role"] == "OFFICIAL_PRODUCT_PAGE":
            if any(item[k] is not None for k in ("revision", "revision_date", "pdf_pages")) or item["locators"] != []:
                raise IntakeError("HTML evidence must not claim PDF geometry")
            continue
        if (type(item["pdf_pages"]) is not int or item["pdf_pages"] < 1
                or not _text(item["revision"]) or not _text(item["revision_date"])
                or not isinstance(item["locators"], list) or not item["locators"]):
            raise IntakeError("PDF evidence requires revision and visual page locators")
        seen = set()
        for locator in item["locators"]:
            if (not isinstance(locator, dict)
                    or set(locator) != {"printed_page", "pdf_page_index", "section", "visual_checked"}
                    or type(locator["printed_page"]) is not int or locator["printed_page"] < 1
                    or type(locator["pdf_page_index"]) is not int
                    or not 0 <= locator["pdf_page_index"] < item["pdf_pages"]
                    or locator["pdf_page_index"] in seen or not _text(locator["section"])
                    or locator["visual_checked"] is not True):
                raise IntakeError("invalid or duplicate visual evidence locator")
            seen.add(locator["pdf_page_index"])
    if not {"HISTORICAL_SOURCE", "RECHECK_DATASHEET"} <= roles:
        raise IntakeError("disposition requires historical source and rechecked datasheet evidence")


def load_dispositions(root: Path, batches: list[dict]) -> list[dict]:
    """Read and validate all supplements; absence is allowed, invalidity is not."""
    directory = root / DISPOSITION_DIRECTORY
    if (root / "knowledge").is_symlink() or directory.is_symlink():
        raise IntakeError("disposition directories must not be symlinks")
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise IntakeError(f"{DISPOSITION_DIRECTORY} must be a directory")
    batch_index = {batch["path"]: batch for batch in batches}
    results, identifiers, targets = [], set(), set()
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise IntakeError("disposition symlink is forbidden")
        if path.is_dir() or path.suffix != ".json":
            continue
        if not path.is_file() or path.stat().st_size > MAX_INTAKE_BYTES:
            raise IntakeError("disposition must be a bounded regular JSON file")
        with path.open("rb") as stream:
            payload = stream.read(MAX_INTAKE_BYTES + 1)
        if len(payload) > MAX_INTAKE_BYTES:
            raise IntakeError("disposition exceeds size limit")
        try:
            data = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
            _validate(data, batch_index)
        except (UnicodeError, json.JSONDecodeError, IntakeError) as error:
            raise IntakeError(f"invalid disposition {path.relative_to(root)}: {error}") from error
        target = (data["target"]["batch_path"], data["target"]["issue_id"])
        if data["id"] in identifiers or target in targets:
            raise IntakeError("duplicate disposition id or ambiguous issue target")
        identifiers.add(data["id"])
        targets.add(target)
        results.append({"path": path.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(payload).hexdigest(), "canonical": False,
                        "evidence_verification": "NOT_LOCALLY_VERIFIED", "data": data})
    return results
