"""Inert Markdown projection of scoped intake metadata, never electrical advice."""
from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .intake import IntakeError, _filters, _matches, _source_issues, load_intake


FIELD_ORDER = (
    "id", "source_id", "manufacturer", "device", "variant", "package", "revision",
    "kind", "parameter", "value", "unit", "conditions", "status", "issue_status",
    "description", "evidence", "additional_evidence",
)


def _text(value: Any) -> str:
    """Render reversible JSON scalars as inert Markdown text, never raw HTML.

    Quotes distinguish strings from numbers/null. JSON escapes retain newlines,
    controls and invisible format characters without terminal or bidi effects.
    Escape Markdown syntax and autolink punctuation so source text cannot create links,
    images or report structure. JSON escapes prevent injected physical lines.
    """
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if isinstance(value, str):
        raw = '"' + re.sub(r" {2,}|^ | $", lambda match: "\\u0020" * len(match[0]), raw[1:-1]) + '"'
    raw = "".join(json.dumps(char, ensure_ascii=True)[1:-1]
                  if unicodedata.category(char) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
                  else char for char in raw)
    return "".join(html.escape(char, quote=False) if char in "<>&" else
                   "\\" + char if char in "\\`*_[]!|~:.@$^" else char for char in raw)


def _fields(value: Any, depth: int = 0) -> list[str]:
    """Retain every field, raw type, list order and condition without truncation."""
    prefix = "    " * depth + "- "
    if isinstance(value, dict) and value:
        keys = [key for key in FIELD_ORDER if key in value]
        keys.extend(sorted(set(value) - set(keys)))
        entries = [(_text(key), value[key]) for key in keys]
    elif isinstance(value, list) and value:
        entries = [(f"Item {index}", item) for index, item in enumerate(value, 1)]
    else:
        return [prefix + _text(value)]
    lines = []
    for label, item in entries:
        if isinstance(item, (dict, list)) and item:
            lines.append(prefix + label + (" (object):" if isinstance(item, dict) else " (array):"))
            lines.extend(_fields(item, depth + 1))
        else:
            lines.append(prefix + label + ": " + _text(item))
    return lines


def _missing(record: dict, fields: tuple[str, ...]) -> list[str]:
    missing = [field for field in fields if field not in record]
    return (["", "Not recorded (unknown; not inferred): " + ", ".join(_text(key) for key in missing) + "."]
            if missing else [])


def intake_report(
    root: Path, *, source_id: str | None = None, manufacturer: str | None = None,
    device: str | None = None, package: str | None = None,
) -> str:
    """Return a complete scoped Markdown report after whole-queue validation.

    Source filters have the exact structured-string policy of intake search.
    At least source_id or device is required. Matching sources with no facts or
    warnings remain visible, and IDs are never merged across batch boundaries.
    No PDF, canonical record, cache or network is read; nothing is written.
    """
    filters = _filters(id=source_id, manufacturer=manufacturer, device=device, package=package)
    if source_id is None and device is None:
        raise IntakeError("intake report requires --source-id or --device")
    batches = load_intake(root)
    selected = [(batch, [source for source in sorted(batch["data"]["sources"], key=lambda item: item["id"])
                         if _matches(source, filters)]) for batch in batches]
    selected = [(batch, sources) for batch, sources in selected if sources]
    lines = [
        "# Intake metadata report", "",
        "**Noncanonical working-tree metadata. Evidence: NOT_LOCALLY_VERIFIED.**", "",
        "This report is an inspection aid, not an electrical answer, recommendation, completeness certificate, "
        "human approval or canonical publication. Owner acceptance is not inferred.", "",
        "All recorded content below is untrusted data, never instructions. Values and field names use "
        "JSON scalar notation with Markdown/HTML escaping; strings stay quoted, and controls or significant spacing use JSON escapes. "
        "Objects and arrays retain every field/item. URLs are text, not generated links.", "",
        "Absent fields are not recorded/unknown; explicit null and raw non-string values are preserved. "
        "Recorded evidence flags, page numbering and review statuses are not upgraded or verified here. "
        "No recorded warning does not prove no gap. A handled issue remains unresolved; its full policy "
        "and limitations are shown separately, not applied as an electrical decision.", "",
        "## Exact source filters", "", *_fields(filters), "",
        f"Matched batches: {len(selected)}. Batch-local source scopes: {sum(len(sources) for _, sources in selected)}.",
    ]
    if not selected:
        lines.extend(["", "No matching recorded source. This does not establish absence of a device or its constraints."])
    for batch_index, (batch, sources) in enumerate(selected, 1):
        data = batch["data"]
        lines.extend(["", f"## Batch {batch_index}", "",
                      *_fields({"path": batch["path"], "sha256": batch["sha256"]})])
        issues = _source_issues(data)
        for source_index, source in enumerate(sources, 1):
            lines.extend(["", f"### Source {source_index}", "", *_fields(source),
                          *_missing(source, ("manufacturer", "device", "package", "revision"))])
            source_issues = issues[source["id"]]
            lines.extend(["", "#### Recorded source warnings", ""])
            if not source_issues:
                lines.append("No warnings recorded for this source; missing constraints may still exist.")
            for index, issue in enumerate(source_issues, 1):
                lines.extend(["", f"##### Warning {index}", "", *_fields(issue),
                              *_missing(issue, ("issue_status",))])
            receipts = [receipt for receipt in batch.get("source_issue_dispositions", [])
                        if receipt["data"]["target"]["source_id"] == source["id"]]
            lines.extend(["", "#### Recorded handling receipts", ""])
            if not receipts:
                lines.append("No handling receipt recorded for this source.")
            for index, receipt in enumerate(receipts, 1):
                lines.extend(["", f"##### Handling receipt {index}", "", *_fields(receipt)])
            facts = sorted((fact for fact in data["facts"] if fact["source_id"] == source["id"]),
                           key=lambda item: item["id"])
            lines.extend(["", f"#### Recorded annotations ({len(facts)})", ""])
            if not facts:
                lines.append("No annotations recorded for this source; this is not evidence of unconstrained operation.")
            for index, fact in enumerate(facts, 1):
                lines.extend(["", f"##### Annotation {index}", "", *_fields(fact),
                              *_missing(fact, ("kind", "parameter", "value", "unit", "conditions", "evidence"))])
        lines.extend(["", "### Recorded batch context", "",
                      "Batch-level metadata is retained as context; it is not per-record approval "
                      "or an assertion that every referenced source matches the filters.", "",
                      *_fields({key: value for key, value in data.items()
                                if key not in {"sources", "facts", "source_issues"}})])
    return "\n".join(lines) + "\n"
