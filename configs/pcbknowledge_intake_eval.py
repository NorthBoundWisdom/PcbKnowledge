#!/usr/bin/env python3
"""Replay pinned intake retrieval cases through the real read-only Agent CLI.

This checks candidate selection and unchanged metadata, not electrical truth,
source bytes, visual evidence, canonical approval, or absence of unknowns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from pcbknowledge.git_native.intake import IntakeError, load_intake  # noqa: E402


FORMAT = "pcbknowledge-intake-retrieval-eval-v1"
DISPOSITION_EVAL_FORMAT = "pcbknowledge-intake-disposition-eval-v1"
SOURCE_FILTERS = {"source_id", "manufacturer", "device", "package"}
FACT_FILTERS = {"kind", "parameter"}


class EvaluationError(ValueError):
    """A replay input or CLI output cannot support an evaluation claim."""


def fingerprint(files: dict[str, str]) -> str:
    """Retain the exact byte-manifest convention of the original 100-item receipt."""
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()


def validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict) or set(manifest) != {"format", "files", "cases"}:
        raise EvaluationError("manifest must contain only format, files and cases")
    if manifest["format"] != FORMAT:
        raise EvaluationError(f"manifest format must be {FORMAT}")
    files = manifest["files"]
    if not isinstance(files, dict) or not files or any(
        not isinstance(path, str) or not isinstance(digest, str)
        or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest)
        for path, digest in files.items()
    ):
        raise EvaluationError("files must pin nonempty SHA-256 byte identities")
    if not isinstance(manifest["cases"], list) or not manifest["cases"]:
        raise EvaluationError("cases must be a nonempty array")
    seen: set[str] = set()
    for case in manifest["cases"]:
        if not isinstance(case, dict) or set(case) != {"id", "command", "query", "filters", "expected"}:
            raise EvaluationError("each case requires id, command, query, filters and expected only")
        if not isinstance(case["id"], str) or not case["id"].strip() or case["id"] in seen:
            raise EvaluationError("case ids must be unique nonempty strings")
        seen.add(case["id"])
        if case["command"] not in ("search", "issues") or not isinstance(case["query"], str):
            raise EvaluationError("case command/query is invalid")
        allowed = SOURCE_FILTERS | (FACT_FILTERS if case["command"] == "search" else set())
        filters = case["filters"]
        if not isinstance(filters, dict) or any(
            key not in allowed or not isinstance(value, str) or not value.strip()
            for key, value in filters.items()
        ):
            raise EvaluationError("case has an unsupported or empty filter")
        expected = case["expected"]
        if not isinstance(expected, list) or any(not isinstance(ref, str) for ref in expected):
            raise EvaluationError("expected must be an ordered array of batch-path#record-id strings")
        if len(set(expected)) != len(expected):
            raise EvaluationError("expected references must not repeat")


def run_cli(root: Path, case: dict) -> list[dict]:
    command = [sys.executable, str(REPO_ROOT / "configs/pcbknowledge_agent.py"),
               "--repo", str(root), "intake", case["command"]]
    if case["query"]:
        command.append(case["query"])
    for name, value in sorted(case["filters"].items()):
        command.extend(["--" + name.replace("_", "-"), value])
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            timeout=30, check=False)
    if result.returncode:
        raise EvaluationError(f"CLI exited {result.returncode}: {result.stderr.strip()}")
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise EvaluationError("CLI did not return JSON") from error
    if not isinstance(output, list) or any(not isinstance(item, dict) for item in output):
        raise EvaluationError("CLI did not return an array of candidate objects")
    return output


def expected_candidates(batches: list[dict], command: str) -> dict[str, dict]:
    """Build the preservation oracle from pinned input, never from search output.

    Selection is separately hand-specified in each reviewed case. Exact equality
    with these projections detects condition/evidence loss and warning leakage.
    """
    candidates: dict[str, dict] = {}
    for batch in batches:
        data = batch["data"]
        sources = {source["id"]: source for source in data["sources"]}
        warnings = data.get("source_issues", [])
        records = data["facts"] if command == "search" else warnings
        for record in records:
            source_id = record["source_id"]
            candidate = {"path": batch["path"], "canonical": False,
                         "acceptance_status": data["acceptance_status"],
                         "evidence_verification": "NOT_LOCALLY_VERIFIED",
                         "source": sources[source_id]}
            if command == "search":
                candidate.update(result_type="FACT_CANDIDATE", fact=record,
                                 source_issues=sorted(
                                     [issue for issue in warnings if issue["source_id"] == source_id],
                                     key=lambda issue: issue["id"]))
            else:
                candidate.update(result_type="SOURCE_ISSUE", source_issue=record)
            receipts = [receipt for receipt in batch.get("source_issue_dispositions", [])
                        if receipt["data"]["target"]["source_id"] == source_id
                        and (command == "search" or receipt["data"]["target"]["issue_id"] == record["id"])]
            if receipts:
                candidate["source_issue_dispositions"] = receipts
            candidates[f"{batch['path']}#{record['id']}"] = candidate
    return candidates


def disposition_files(batches: list[dict]) -> dict[str, str]:
    return {receipt["path"]: receipt["sha256"] for batch in batches
            for receipt in batch.get("source_issue_dispositions", [])}


def evaluate(root: Path, manifest: dict, *, runner: Callable = run_cli,
             disposition_manifest: dict | None = None) -> dict:
    validate_manifest(manifest)
    batches = load_intake(root)
    files = {batch["path"]: batch["sha256"] for batch in batches}
    if files != manifest["files"]:
        raise EvaluationError("dataset bytes or batch set changed; review cases before updating pins")
    supplements = disposition_files(batches)
    extra_cases = []
    if disposition_manifest is None:
        if supplements:
            raise EvaluationError("dispositions require a separately pinned --dispositions manifest")
    else:
        if not isinstance(disposition_manifest, dict) or disposition_manifest.get("format") != DISPOSITION_EVAL_FORMAT:
            raise EvaluationError(f"disposition manifest format must be {DISPOSITION_EVAL_FORMAT}")
        validate_manifest({**disposition_manifest, "format": FORMAT})
        if supplements != disposition_manifest["files"]:
            raise EvaluationError("disposition bytes or set changed; review cases before updating pins")
        extra_cases = disposition_manifest["cases"]
    cases = manifest["cases"] + extra_cases
    if len({case["id"] for case in cases}) != len(cases):
        raise EvaluationError("base and disposition case ids must be unique together")
    oracles = {command: expected_candidates(batches, command) for command in ("search", "issues")}
    results = []
    for case in cases:
        oracle = oracles[case["command"]]
        if any(ref not in oracle for ref in case["expected"]):
            raise EvaluationError(f"{case['id']}: expected reference is absent from pinned input")
        expected = [oracle[ref] for ref in case["expected"]]
        result = {"id": case["id"], "expected": case["expected"], "passed": False}
        try:
            actual = runner(root, case)
            record_key = "fact" if case["command"] == "search" else "source_issue"
            result["actual"] = [f"{item['path']}#{item[record_key]['id']}" for item in actual]
            # JSON equality preserves bool/int distinctions that Python == loses.
            result["passed"] = json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(
                expected, sort_keys=True, allow_nan=False)
            if not result["passed"]:
                result["error"] = "candidate selection/order or complete metadata differs from pinned input"
        except (ValueError, OSError, subprocess.TimeoutExpired, KeyError, TypeError) as error:
            result["error"] = str(error)
        results.append(result)
    # Detect edits made during the replay instead of attesting to a mixed dataset.
    after_batches = load_intake(root)
    after = {batch["path"]: batch["sha256"] for batch in after_batches}
    if after != files:
        raise EvaluationError("dataset changed during evaluation")
    if disposition_files(after_batches) != supplements:
        raise EvaluationError("dispositions changed during evaluation")
    return {"format": FORMAT, "status": "PASS" if all(r["passed"] for r in results) else "FAIL",
            "dataset_sha256": fingerprint(files), "batch_count": len(batches),
            "fact_count": sum(len(batch["data"]["facts"]) for batch in batches),
            "disposition_count": len(supplements), "dispositions_sha256": fingerprint(supplements),
            "base_case_count": len(manifest["cases"]), "disposition_case_count": len(extra_cases),
            "case_count": len(results), "cases": results,
            "limitations": "Candidate retrieval only; no new source-byte, visual, human or canonical verification."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--repo", type=Path, required=True, help="explicit intake workspace")
    parser.add_argument("--cases", type=Path, required=True, help="reviewed pinned case manifest")
    parser.add_argument("--dispositions", type=Path, help="separate reviewed pins/cases for handling supplements")
    args = parser.parse_args(argv)
    try:
        payload = args.cases.read_bytes()
        supplement_payload = args.dispositions.read_bytes() if args.dispositions else None
        report = evaluate(args.repo.resolve(), json.loads(payload),
                          disposition_manifest=json.loads(supplement_payload) if supplement_payload else None)
        if supplement_payload is not None:
            report["disposition_manifest_sha256"] = hashlib.sha256(supplement_payload).hexdigest()
        report["manifest_sha256"] = hashlib.sha256(payload).hexdigest()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 1
    except (EvaluationError, IntakeError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"pcbknowledge intake evaluation: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
