"""Read-only, explicitly noncanonical curation queue access.

Intake annotations are searchable review material, never canonical Fact records.
Agent review under owner delegation is not a human approval or evidence-byte
verification. This module neither opens original documents nor mutates records.
"""

from __future__ import annotations

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
        return []
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
        batches.append({"path": relative, "canonical": False,
                        "evidence_verification": "NOT_LOCALLY_VERIFIED", "data": data})
    return batches


def search_intake(root: Path, query: str = "") -> list[dict]:
    """Return fact matches linked to their batch-local sources, without promotion.

    Whitespace-separated case-insensitive terms must all match the combined fact
    and source JSON. Empty queries list all candidates in stable batch/id order.
    """

    terms = query.casefold().split()
    matches: list[dict] = []
    for batch in load_intake(root):
        data = batch["data"]
        sources = {source["id"]: source for source in data["sources"]}
        for fact in sorted(data["facts"], key=lambda record: record["id"]):
            source = sources[fact["source_id"]]
            searchable = json.dumps([fact, source], ensure_ascii=False, sort_keys=True).casefold()
            if all(term in searchable for term in terms):
                matches.append({"path": batch["path"], "canonical": False,
                                "acceptance_status": data["acceptance_status"],
                                "evidence_verification": "NOT_LOCALLY_VERIFIED",
                                "fact": fact, "source": source})
    return matches
