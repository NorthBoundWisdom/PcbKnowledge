"""Read-only inventory of recorded intake scope, evidence metadata and gaps.

Counts describe annotations, not complete components or electrical readiness.
The existing intake reader owns validation; this projection does not open source
originals, infer evidence grades, or turn historical acceptance into authority.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .intake import load_intake


def _counts(values: Iterable[Any]) -> list[dict]:
    """Keep raw JSON values distinct, including non-string metadata and null."""
    counts = Counter(json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values)
    return [{"value": json.loads(value), "count": counts[value]} for value in sorted(counts)]


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _recorded_metadata(facts: list[dict]) -> dict:
    evidence = [fact.get("evidence") for fact in facts]
    objects = [item if isinstance(item, dict) else {} for item in evidence]
    return {
        "record_count": len(facts),
        "record_statuses": _counts(fact["status"] for fact in facts),
        "fact_kinds": _counts(fact.get("kind") for fact in facts),
        "evidence_levels": _counts(item.get("evidence_level") for item in objects),
        # Historical batches use different flags. Never merge them into a new
        # evidence grade, especially when they contradict one another.
        "visual_checked": _counts(item.get("visual_checked") for item in objects),
        "visual_page_review": _counts(item.get("visual_page_review") for item in objects),
        "evidence_reviewers": _counts(item.get("reviewer") for item in objects),
        "evidence_collectors": _counts(item.get("collector") for item in objects),
        "evidence_missing_or_nonobject_count": sum(not isinstance(item, dict) for item in evidence),
    }


def intake_coverage(root: Path) -> dict:
    """Summarize the complete selected queue after fail-closed intake validation.

    Source IDs and record IDs are batch-local. Device-label grouping compares
    only exact nonempty structured manufacturer/device strings; it is not an
    identity resolution operation. Missing or non-string labels stay ungrouped.
    Metadata histograms retain raw values; null means absent or explicitly null.
    """
    batches = load_intake(root)
    batch_rows: list[dict] = []
    facts: list[dict] = []
    issues: list[dict] = []
    dispositions: list[dict] = []
    device_labels: dict[tuple[str, str], list[dict]] = {}
    ungrouped = 0
    source_count = 0
    for batch in batches:
        data = batch["data"]
        batch_issues = sorted(data.get("source_issues", []), key=lambda item: item["id"])
        receipts = batch.get("source_issue_dispositions", [])
        facts.extend(data["facts"])
        issues.extend(batch_issues)
        dispositions.extend(receipts)
        source_rows = []
        for source in sorted(data["sources"], key=lambda item: item["id"]):
            source_count += 1
            reference = {"path": batch["path"], "source_id": source["id"]}
            labels = (source.get("manufacturer"), source.get("device"))
            if all(_nonempty_string(value) for value in labels):
                device_labels.setdefault(labels, []).append(reference)
            else:
                ungrouped += 1
            source_issues = []
            for issue in batch_issues:
                if issue["source_id"] == source["id"]:
                    source_issues.append({
                        "issue": issue,
                        "dispositions": [receipt for receipt in receipts
                                         if receipt["data"]["target"]["issue_id"] == issue["id"]],
                    })
            source_facts = [fact for fact in data["facts"] if fact["source_id"] == source["id"]]
            source_rows.append({
                "source": source,
                "record_ids": sorted(fact["id"] for fact in source_facts),
                "recorded_metadata": _recorded_metadata(source_facts),
                "source_issues": source_issues,
            })
        batch_rows.append({
            "path": batch["path"], "sha256": batch["sha256"],
            "acceptance_status": data["acceptance_status"],
            "review": data.get("review"), "review_history": data.get("review_history"),
            "source_review_receipts": data.get("source_review_receipts"),
            "limitations": data.get("limitations"),
            "source_scope_count": len(source_rows),
            "recorded_metadata": _recorded_metadata(data["facts"]),
            "sources": source_rows,
        })
    unresolved = sum(isinstance(issue.get("issue_status"), str)
                     and issue["issue_status"].startswith("UNRESOLVED_") for issue in issues)
    return {
        "format": "pcbknowledge-intake-coverage-v1", "canonical": False,
        "evidence_verification": "NOT_LOCALLY_VERIFIED",
        "scope": "SELECTED_WORKTREE_INTAKE_METADATA",
        "limitations": [
            "Counts describe recorded annotations, not completeness, electrical readiness or design approval.",
            "Evidence labels and flags are recorded metadata, not original-byte verification by this reader.",
            "Device labels are exact manufacturer/device strings, not resolved orderable or package identities.",
            "A handling disposition does not resolve the original source issue; no recorded issue is not proof of no gap.",
            "Owner acceptance is not inferred. Historical snapshot-specific receipts do not cover new or changed records.",
        ],
        "summary": {
            "batch_count": len(batches), "batch_local_source_scope_count": source_count,
            "distinct_device_label_count": len(device_labels),
            "source_scopes_without_device_labels": ungrouped,
            "recorded_metadata": _recorded_metadata(facts),
            "source_issue_count": len(issues),
            "explicitly_unresolved_source_issue_count": unresolved,
            "source_issue_statuses": _counts(issue.get("issue_status") for issue in issues),
            "handled_disposition_count": len(dispositions),
            "disposition_statuses": _counts(receipt["data"]["disposition_status"] for receipt in dispositions),
        },
        "device_labels": [
            {"manufacturer": manufacturer, "device": device, "source_scopes": references}
            for (manufacturer, device), references in sorted(device_labels.items())
        ],
        "batches": batch_rows,
    }
