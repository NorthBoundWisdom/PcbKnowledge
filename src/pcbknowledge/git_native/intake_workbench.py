"""Read-only application projection for the selected workspace's intake queue."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping

from pcbknowledge.git_native.intake import IntakeError, search_intake, search_intake_issues

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
        search = search_intake if mode == "facts" else search_intake_issues
        matches = search(self.root, query, **filters)
        page_count = max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)
        number = int(page)
        if number > page_count:
            raise IntakeError("Intake page is outside the result range.")
        start = (number - 1) * PAGE_SIZE
        return IntakeBrowseView(self.root, mode, query, filters, number, page_count,
                                len(matches), tuple(matches[start:start + PAGE_SIZE]))
