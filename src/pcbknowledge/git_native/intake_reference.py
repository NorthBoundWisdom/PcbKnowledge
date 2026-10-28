"""Pure, read-only batch-local references shared by Agent CLI and workbench."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Mapping

from pcbknowledge.git_native.intake import (
    IntakeError, load_intake, _search_loaded_facts, _search_loaded_issues,
)


class IntakeItemNotFound(IntakeError):
    """No exact batch-local item exists."""


class StaleIntakeItem(IntakeError):
    """Current validated metadata differs from the requested byte pin."""


@dataclass(frozen=True, slots=True)
class IntakeReference:
    workspace: Path
    batch_sha256: str
    context_sha256: str
    record_type: str
    candidate: dict

    def selectors(self) -> dict[str, str]:
        record = self.candidate["fact" if self.record_type == "fact" else "source_issue"]
        return {"batch": self.candidate["path"], "id": record["id"],
                "type": self.record_type, "sha256": self.batch_sha256,
                "context": self.context_sha256}

    def projection(self, *, captured: bool) -> dict:
        return {"format": "pcbknowledge-intake-reference-v1",
                "operation": "CAPTURE_CURRENT_METADATA" if captured else "VERIFY_PINNED_METADATA",
                "canonical": False, "evidence_verification": "NOT_LOCALLY_VERIFIED",
                "reference": self.selectors(), "candidate": self.candidate}


def candidate_digest(candidate: dict) -> str:
    """Fingerprint the full current projection, including linked receipt hashes."""
    payload = json.dumps(candidate, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _selectors(parameters: Mapping[str, list[str]], *, pinned: bool) -> dict[str, str]:
    required = {"batch", "id", "type"} | ({"sha256", "context"} if pinned else set())
    if set(parameters) != required:
        raise IntakeError("Intake reference requires exactly " + ", ".join(sorted(required)) + ".")
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
    if pinned and any(re.fullmatch(r"[0-9a-f]{64}", values[key]) is None
                      for key in ("sha256", "context")):
        raise IntakeError("Item digests must be 64 lowercase hexadecimal digits.")
    if values["type"] not in {"fact", "issue"}:
        raise IntakeError("Item type must be fact or issue.")
    return values


def _read_reference(root: Path, values: Mapping[str, str], *, pinned: bool) -> IntakeReference:
    # Both capture and verification derive all evidence and pins from one load.
    batches = load_intake(root)
    selected = [batch for batch in batches if batch["path"] == values["batch"]]
    if not selected:
        raise IntakeItemNotFound("Intake batch not found in the selected workspace.")
    batch = selected[0]
    if pinned and batch["sha256"] != values["sha256"]:
        raise StaleIntakeItem("Stale intake reference: batch bytes changed. Review current evidence before capturing a new reference.")
    search = _search_loaded_facts if values["type"] == "fact" else _search_loaded_issues
    record_key = "fact" if values["type"] == "fact" else "source_issue"
    candidates = [candidate for candidate in search(selected)
                  if candidate[record_key]["id"] == values["id"]]
    if not candidates:
        raise IntakeItemNotFound("Intake record not found in the pinned batch and record type.")
    digest = candidate_digest(candidates[0])
    if pinned and digest != values["context"]:
        raise StaleIntakeItem("Stale intake context: candidate or linked disposition metadata changed. Review a new reference.")
    return IntakeReference(root, batch["sha256"], digest, values["type"], candidates[0])


def capture_intake_reference(root: Path, parameters: Mapping[str, list[str]]) -> IntakeReference:
    """Explicitly capture current metadata; never claim an older pin was verified."""
    return _read_reference(root, _selectors(parameters, pinned=False), pinned=False)


def resolve_intake_reference(root: Path, parameters: Mapping[str, list[str]]) -> IntakeReference:
    """Require both supplied pins; no refresh, fallback or optional digest."""
    return _read_reference(root, _selectors(parameters, pinned=True), pinned=True)
