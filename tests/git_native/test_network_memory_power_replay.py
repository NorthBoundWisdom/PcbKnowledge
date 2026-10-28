"""Synthetic semantic regressions for network, memory and power candidates."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class NetworkMemoryPowerPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic-interfaces.json"
        path = self.root / self.relative
        path.parent.mkdir(parents=True)
        # Invented symbolic examples, not manufacturer specifications.
        facts = [
            {"id": "network", "kind": "operating_constraint", "parameter": "common_mode",
             "value": {"continuous": "bounded", "stress_is_operation": False},
             "conditions": {"variant": "SYNTH-A", "receiver_active": True}},
            {"id": "memory", "kind": "transaction_constraint", "parameter": "page_write",
             "value": {"boundary": "wrap_within_page", "ack_is_persistence": False},
             "conditions": {"protection_sample": "transaction_stop", "completion": "poll_selected_target"}},
            {"id": "power", "kind": "application_guidance", "parameter": "LC_matrix",
             "value": {"checked_cells": [[2, 7], [3, 9]], "unchecked_allowed": False},
             "conditions": {"capacitance": "effective", "board_verified": False}},
        ]
        for fact in facts:
            fact.update(source_id="synthetic", status="DRAFT")
        data = {"format": "pcbknowledge-independent-intake-v1", "canonical": False,
                "acceptance_status": "DRAFT",
                "sources": [{"id": "synthetic", "manufacturer": "Invented", "device": "SYNTH-A",
                             "package": "SYNTH-PKG", "status": "DRAFT"}],
                "facts": facts,
                "source_issues": [{"id": "unknown", "source_id": "synthetic",
                                   "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                                   "missing_inputs": ["network", "transaction", "board"], "answer": "UNKNOWN"}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        self.manifest = {"format": evaluation.FORMAT,
                         "files": {self.relative: hashlib.sha256(path.read_bytes()).hexdigest()},
                         "cases": [{"id": fact["id"], "command": "search", "query": "",
                                    "filters": {"source_id": "synthetic", "parameter": fact["parameter"]},
                                    "expected": [self.relative + "#" + fact["id"]]} for fact in facts] +
                                   [{"id": "unknown", "command": "issues", "query": "",
                                     "filters": {"source_id": "synthetic"}, "expected": [self.relative + "#unknown"]}]}

    def test_complete_payload_replays_without_electrical_permission(self) -> None:
        result = evaluation.evaluate(self.root, self.manifest)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["case_count"], 4)

    def test_same_ids_do_not_hide_semantic_promotions(self) -> None:
        mutations = [
            ("network", lambda item: item["fact"]["value"].update(stress_is_operation=True)),
            ("network", lambda item: item["fact"]["conditions"].update(receiver_active=False)),
            ("memory", lambda item: item["fact"]["value"].update(boundary="continue_next_page")),
            ("memory", lambda item: item["fact"]["value"].update(ack_is_persistence=True)),
            ("memory", lambda item: item["fact"]["conditions"].update(protection_sample="any_time")),
            ("power", lambda item: item["fact"]["value"].update(unchecked_allowed=True)),
            ("power", lambda item: item["fact"]["conditions"].update(capacitance="nominal")),
            ("power", lambda item: item["fact"].update(kind="guaranteed_limit")),
            ("power", lambda item: item["fact"]["conditions"].update(board_verified=True)),
            ("unknown", lambda item: item["source_issue"].update(answer="SAFE")),
        ]
        for target, mutate in mutations:
            with self.subTest(target=target, mutation=mutate):
                def runner(root, case):
                    items = copy.deepcopy(evaluation.run_cli(root, case))
                    if case["id"] == target:
                        mutate(items[0])
                    return items
                result = evaluation.evaluate(self.root, self.manifest, runner=runner)
                self.assertEqual(result["status"], "FAIL")
                failed = next(case for case in result["cases"] if case["id"] == target)
                self.assertFalse(failed["passed"])
                self.assertEqual(failed["actual"], next(case["expected"] for case in self.manifest["cases"] if case["id"] == target))


class SuccessorManifestTests(unittest.TestCase):
    def test_successor_preserves_history_and_covers_new_payloads(self) -> None:
        root = evaluation.REPO_ROOT
        old = json.loads((root / "evals/intake-retrieval-125.json").read_text(encoding="utf-8"))
        current = json.loads((root / "evals/intake-retrieval-network-memory-power.json").read_text(encoding="utf-8"))
        evaluation.validate_manifest(current)
        for prior, successor in zip(old["cases"], current["cases"]):
            if prior["id"] == "legacy-pg-also-matches-pgnd":
                expected = copy.deepcopy(prior)
                expected["expected"] += [
                    "knowledge/intake/tps62160-component-layout-constraints.json#buck-app-" + suffix
                    for suffix in ("05", "07", "08")]
                self.assertEqual(successor, expected)
            else:
                self.assertEqual(successor, prior)
        self.assertEqual({path: current["files"][path] for path in old["files"]}, old["files"])
        self.assertEqual(len(current["files"]), 11)
        additions = current["cases"][len(old["cases"]):]
        selected = {ref for case in additions for ref in case["expected"]}
        for path in set(current["files"]) - set(old["files"]):
            data = json.loads((root / path).read_text(encoding="utf-8"))
            self.assertEqual(current["files"][path], hashlib.sha256((root / path).read_bytes()).hexdigest())
            for record in data["facts"] + data["source_issues"]:
                self.assertIn(path + "#" + record["id"], selected)
            self.assertFalse(data["canonical"])
            self.assertFalse(data["human_reviewed"])
        self.assertEqual(sum(case["command"] == "issues" for case in additions), 3)
        self.assertEqual(sum(not case["expected"] for case in additions), 18)

    def test_synthetic_page_crossing_is_not_next_page_write(self) -> None:
        # Invented request demonstrates lower-six-bit wrap, not a driver or hardware test.
        start = 0x003E
        wrapped = [(start & ~0x3F) | ((start + offset) & 0x3F) for offset in range(4)]
        self.assertEqual(wrapped, [0x003E, 0x003F, 0x0000, 0x0001])
        self.assertNotEqual(wrapped, [start + offset for offset in range(4)])
