"""Read-only application projection for the selected workspace's intake queue."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import hashlib
import json
from typing import Mapping

from pcbknowledge.git_native.intake import (
    IntakeError, load_intake, _search_loaded_facts, _search_loaded_issues,
)

FILTERS = ("source_id", "manufacturer", "device", "package", "kind", "parameter")
PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class IntakeBrowseView:
    workspace: Path
    mode: str
    query: str
    filters: Mapping[str, str]
    page_number: int
    page_count: int
    total_count: int
    candidates: tuple[dict, ...]
    batch_digests: Mapping[str, str]
    candidate_digests: tuple[str, ...]


class IntakeBrowseApplication:
    def __init__(self, root: Path) -> None:
        self.root = root

    def browse(self, parameters: Mapping[str, list[str]]) -> IntakeBrowseView:
        allowed = {*FILTERS, "q", "mode", "page"}
        if set(parameters) - allowed:
            raise IntakeError("Unsupported intake query parameter.")
        values = {}
        for name, entries in parameters.items():
            if (len(entries) != 1 or not isinstance(entries[0], str)
                    or len(entries[0]) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in entries[0])):
                raise IntakeError("Intake parameters require one bounded text value each.")
            values[name] = entries[0]
        mode = values.get("mode", "facts")
        if mode not in {"facts", "issues"}:
            raise IntakeError("Intake mode must be facts or issues.")
        page = values.get("page", "1")
        if re.fullmatch(r"[1-9][0-9]{0,5}", page) is None:
            raise IntakeError("Intake page must be a positive decimal integer.")
        filters = {name: values[name] for name in FILTERS if values.get(name, "") != ""}
        if mode == "issues" and ({"kind", "parameter"} & filters.keys()):
            raise IntakeError("Fact kind and parameter filters are not supported in issue mode.")
        query = values.get("q", "")
        batches = load_intake(self.root)
        search = _search_loaded_facts if mode == "facts" else _search_loaded_issues
        matches = search(batches, query, **filters)
        page_count = max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)
        number = int(page)
        if number > page_count:
            raise IntakeError("Intake page is outside the result range.")
        start = (number - 1) * PAGE_SIZE
        return IntakeBrowseView(self.root, mode, query, filters, number, page_count,
                                len(matches), tuple(matches[start:start + PAGE_SIZE]),
                                {batch["path"]: batch["sha256"] for batch in batches},
                                tuple(_candidate_digest(item) for item in matches[start:start + PAGE_SIZE]))

    def item(self, parameters: Mapping[str, list[str]]) -> "IntakeItemView":
        if set(parameters) != {"batch", "id", "sha256", "type", "context"}:
            raise IntakeError("An intake item requires exactly batch, id, sha256, context and type.")
        values = {}
        for key, entries in parameters.items():
            if (len(entries) != 1 or not isinstance(entries[0], str) or not entries[0]
                    or len(entries[0]) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in entries[0])):
                raise IntakeError("Item parameters require one nonempty bounded value each.")
            values[key] = entries[0]
        path = values["batch"]
        parts = PurePosixPath(path).parts
        if ("\\" in path or not path.startswith("knowledge/intake/")
                or not path.endswith(".json") or any(part in {".", ".."} for part in path.split("/"))
                or "" in path.split("/") or PurePosixPath(path).as_posix() != path
                or len(parts) < 3):
            raise IntakeError("Item batch must be a normalized intake JSON path.")
        if any(re.fullmatch(r"[0-9a-f]{64}", values[key]) is None for key in ("sha256", "context")):
            raise IntakeError("Item digests must be 64 lowercase hexadecimal digits.")
        if values["type"] not in {"fact", "issue"}:
            raise IntakeError("Item type must be fact or issue.")
        batches = load_intake(self.root)
        selected = [batch for batch in batches if batch["path"] == path]
        if not selected:
            raise IntakeItemNotFound("Intake batch not found in the selected workspace.")
        if selected[0]["sha256"] != values["sha256"]:
            raise StaleIntakeItem("Stale intake link: batch bytes changed. Return to browse and review the new evidence.")
        search = _search_loaded_facts if values["type"] == "fact" else _search_loaded_issues
        record_key = "fact" if values["type"] == "fact" else "source_issue"
        candidates = [candidate for candidate in search(selected)
                      if candidate[record_key]["id"] == values["id"]]
        if not candidates:
            raise IntakeItemNotFound("Intake record not found in the pinned batch and record type.")
        if _candidate_digest(candidates[0]) != values["context"]:
            raise StaleIntakeItem("Stale intake context: candidate or linked disposition metadata changed. Review a new link.")
        return IntakeItemView(self.root, values["sha256"], values["context"], values["type"], candidates[0])


class IntakeItemNotFound(IntakeError):
    """No exact batch-local item exists."""


class StaleIntakeItem(IntakeError):
    """Current validated metadata differs from the requested byte pin."""


@dataclass(frozen=True, slots=True)
class IntakeItemView:
    workspace: Path
    batch_sha256: str
    context_sha256: str
    record_type: str
    candidate: dict


def _candidate_digest(candidate: dict) -> str:
    """Fingerprint the full current projection, including linked receipt hashes."""
    payload = json.dumps(candidate, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
