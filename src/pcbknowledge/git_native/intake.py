"""Read-only, explicitly noncanonical curation queue access.

Intake annotations are searchable review material, never canonical Fact records.
Agent review under owner delegation is not a human approval or evidence-byte
verification. This module neither opens original documents nor mutates records.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


INTAKE_FORMAT = "pcbknowledge-independent-intake-v1"
MAX_INTAKE_BYTES = 1_000_000
NONCANONICAL_STATUSES = frozenset({
    "DRAFT", "PENDING_USER_REVIEW", "DRAFT_AWAITING_HUMAN_REVIEW",
    "AGENT_REVIEWED_UNDER_OWNER_DELEGATION",
})


class IntakeError(ValueError):
    """A curation batch is unsafe, ambiguous, or falsely claims authority."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise IntakeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise IntakeError(f"non-finite JSON constant: {value}")


def _check_claims(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"canonical", "approved", "published", "human_approved"} and child is not False:
                raise IntakeError(f"intake must not claim {key}")
            if key in {"status", "acceptance_status"} and (
                not isinstance(child, str) or child not in NONCANONICAL_STATUSES
            ):
                raise IntakeError(f"unsupported noncanonical status: {child!r}")
            _check_claims(child)
    elif isinstance(value, list):
        for child in value:
            _check_claims(child)


def _validate_batch(data: Any) -> dict:
    if not isinstance(data, dict) or data.get("format") != INTAKE_FORMAT:
        raise IntakeError(f"intake format must be {INTAKE_FORMAT}")
    if data.get("canonical") is not False:
        raise IntakeError("intake canonical must be explicitly false")
    if not isinstance(data.get("acceptance_status"), str) or data["acceptance_status"] not in NONCANONICAL_STATUSES:
        raise IntakeError("intake requires an explicit noncanonical acceptance_status")
    _check_claims(data)
    delegated = "AGENT_REVIEWED_UNDER_OWNER_DELEGATION"
    if any(
        record.get("acceptance_status") == delegated or record.get("status") == delegated
        for record in [data, *[item for key in ("sources", "facts")
                              for item in (data.get(key) if isinstance(data.get(key), list) else [])
                              if isinstance(item, dict)]]
    ):
        review = data.get("review")
        if (not isinstance(review, dict) or review.get("actor_type") != "AGENT"
                or review.get("authority") != "OWNER_DELEGATION"
                or not isinstance(review.get("actor_id"), str)
                or not review["actor_id"].strip()):
            raise IntakeError("delegated intake review requires explicit AGENT/OWNER_DELEGATION provenance")
    source_ids: set[str] = set()
    for kind in ("sources", "facts"):
        records = data.get(kind)
        if not isinstance(records, list):
            raise IntakeError(f"intake {kind} must be an array")
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise IntakeError(f"intake {kind} entries must be objects")
            identifier = record.get("id")
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
                raise IntakeError(f"intake {kind} require unique nonempty string ids")
            seen.add(identifier)
            if not isinstance(record.get("status"), str) or record["status"] not in NONCANONICAL_STATUSES:
                raise IntakeError(f"intake {kind} require explicit noncanonical status")
            if kind == "facts" and (not isinstance(record.get("source_id"), str)
                                    or record["source_id"] not in source_ids):
                raise IntakeError(f"intake fact {identifier} has an unknown source_id")
        if kind == "sources":
            source_ids = seen
    return data


def load_intake(root: Path) -> list[dict]:
    """Load sorted queue JSON batches only; never read canonical knowledge data.

    Each result has ``path``, ``canonical=False``, ``data``, and an explicit
    ``evidence_verification=NOT_LOCALLY_VERIFIED`` projection. Original bytes
    have not been checked by this reader, even when metadata contains a hash.
    Markdown notes are not batches. Invalid batches fail the whole read clearly.
    """

    directory = root / "knowledge" / "intake"
    if (root / "knowledge").is_symlink() or directory.is_symlink():
        raise IntakeError("intake directories must not be symlinks")
    if not directory.exists():
        return _attach_dispositions(root, [])
    if not directory.is_dir():
        raise IntakeError("knowledge/intake must be a directory")
    batches: list[dict] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise IntakeError(f"intake symlink is forbidden: {path.relative_to(root)}")
        if path.is_dir() or path.suffix != ".json":
            continue
        relative = path.relative_to(root).as_posix()
        if not path.is_file() or path.stat().st_size > MAX_INTAKE_BYTES:
            raise IntakeError(f"intake must be a regular file <= {MAX_INTAKE_BYTES} bytes: {relative}")
        try:
            with path.open("rb") as stream:
                payload = stream.read(MAX_INTAKE_BYTES + 1)
            if len(payload) > MAX_INTAKE_BYTES:
                raise IntakeError(f"intake exceeds size limit: {relative}")
            data = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
            data = _validate_batch(data)
        except (UnicodeError, json.JSONDecodeError, IntakeError) as error:
            raise IntakeError(f"invalid intake {relative}: {error}") from error
        batches.append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest(), "canonical": False,
                        "evidence_verification": "NOT_LOCALLY_VERIFIED", "data": data})
    return _attach_dispositions(root, batches)


def _attach_dispositions(root: Path, batches: list[dict]) -> list[dict]:
    from .intake_dispositions import load_dispositions

    by_path = {batch["path"]: batch for batch in batches}
    for batch in batches:
        _source_issues(batch["data"])
    for receipt in load_dispositions(root, batches):
        target = receipt["data"]["target"]["batch_path"]
        by_path[target].setdefault("source_issue_dispositions", []).append(receipt)
    return batches


def _filters(**values: str | None) -> dict[str, str]:
    """Validate explicit filters without normalizing authoritative strings."""

    for name, value in values.items():
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise IntakeError(f"{name} filter must be a nonempty string")
    return {name: value for name, value in values.items() if value is not None}


def _matches(record: dict, filters: dict[str, str]) -> bool:
    # Missing, null, array and other non-string fields are unknown, not matches.
    return all(isinstance(record.get(key), str) and record[key] == value
               for key, value in filters.items())


def _source_issues(data: dict) -> dict[str, list[dict]]:
    """Index full warnings in this batch only; never infer source association."""

    result: dict[str, list[dict]] = {source["id"]: [] for source in data["sources"]}
    issues = data.get("source_issues", [])
    if not isinstance(issues, list):
        raise IntakeError("intake source_issues must be an array")
    identifiers: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            raise IntakeError("intake source_issues entries must be objects")
        identifier = issue.get("id")
        source_id = issue.get("source_id")
        if (not isinstance(identifier, str) or not identifier.strip()
                or identifier in identifiers):
            raise IntakeError("intake source_issues require unique nonempty string ids")
        if not isinstance(source_id, str) or source_id not in result:
            raise IntakeError(f"intake source issue {identifier} has an unknown source_id")
        identifiers.add(identifier)
        result[source_id].append(issue)
    for issues_for_source in result.values():
        issues_for_source.sort(key=lambda issue: issue["id"])
    return result


def _candidate(batch: dict, source: dict, issue_id: str | None = None) -> dict:
    result = {"path": batch["path"], "canonical": False,
              "acceptance_status": batch["data"]["acceptance_status"],
              "evidence_verification": "NOT_LOCALLY_VERIFIED", "source": source}
    receipts = [receipt for receipt in batch.get("source_issue_dispositions", [])
                if receipt["data"]["target"]["source_id"] == source["id"]
                and (issue_id is None or receipt["data"]["target"]["issue_id"] == issue_id)]
    if receipts:
        result["source_issue_dispositions"] = receipts
    return result


def search_intake(
    root: Path, query: str = "", *, source_id: str | None = None,
    manufacturer: str | None = None, device: str | None = None,
    package: str | None = None, kind: str | None = None, parameter: str | None = None,
) -> list[dict]:
    """Return noncanonical fact candidates, not synthesized electrical answers.

    Filters compare exact structured strings (case, Unicode and whitespace are
    significant), before case-folded AND lexical matching over fact/source JSON.
    Missing structured fields fail closed. No prose is used for identity. Empty
    queries support filter-only lookup or, with no filters, list all candidates.
    Full same-source warnings are attached independently of lexical terms; use
    search_intake_issues to find warnings even without a matching fact.
    """

    return _search_loaded_facts(load_intake(root), query, source_id=source_id,
                                manufacturer=manufacturer, device=device, package=package,
                                kind=kind, parameter=parameter)


def _search_loaded_facts(
    batches: list[dict], query: str = "", *, source_id: str | None = None,
    manufacturer: str | None = None, device: str | None = None,
    package: str | None = None, kind: str | None = None, parameter: str | None = None,
) -> list[dict]:
    """Project an already validated loader result without rereading mutable files."""
    source_filters = _filters(id=source_id, manufacturer=manufacturer, device=device,
                              package=package)
    fact_filters = _filters(kind=kind, parameter=parameter)
    terms = query.casefold().split()
    matches: list[dict] = []
    for batch in batches:
        data = batch["data"]
        sources = {source["id"]: source for source in data["sources"]}
        issues = _source_issues(data)
        for fact in sorted(data["facts"], key=lambda record: record["id"]):
            source = sources[fact["source_id"]]
            if not _matches(source, source_filters) or not _matches(fact, fact_filters):
                continue
            searchable = json.dumps([fact, source], ensure_ascii=False, sort_keys=True).casefold()
            if all(term in searchable for term in terms):
                matches.append({**_candidate(batch, source), "result_type": "FACT_CANDIDATE",
                                "fact": fact, "source_issues": issues[source["id"]]})
    return matches


def search_intake_issues(
    root: Path, query: str = "", *, source_id: str | None = None,
    manufacturer: str | None = None, device: str | None = None,
    package: str | None = None,
) -> list[dict]:
    """Retrieve source warnings separately from Facts, including without facts.

    Source filters have the same exact policy as search_intake. Optional lexical
    terms match warning/source JSON, not facts. An empty result does not establish
    the absence of ambiguities: unrecorded or differently worded issues may exist.
    """

    return _search_loaded_issues(load_intake(root), query, source_id=source_id,
                                 manufacturer=manufacturer, device=device, package=package)


def _search_loaded_issues(
    batches: list[dict], query: str = "", *, source_id: str | None = None,
    manufacturer: str | None = None, device: str | None = None,
    package: str | None = None,
) -> list[dict]:
    """Project validated warnings without changing their batch-local identity."""
    source_filters = _filters(id=source_id, manufacturer=manufacturer, device=device,
                              package=package)
    terms = query.casefold().split()
    matches: list[dict] = []
    for batch in batches:
        data = batch["data"]
        issues = _source_issues(data)
        for source in sorted(data["sources"], key=lambda record: record["id"]):
            if not _matches(source, source_filters):
                continue
            for issue in issues[source["id"]]:
                candidate = _candidate(batch, source, issue["id"])
                searchable = json.dumps([issue, source, candidate.get("source_issue_dispositions", [])],
                                        ensure_ascii=False, sort_keys=True).casefold()
                if all(term in searchable for term in terms):
                    matches.append({**candidate, "result_type": "SOURCE_ISSUE", "source_issue": issue})
    return matches
