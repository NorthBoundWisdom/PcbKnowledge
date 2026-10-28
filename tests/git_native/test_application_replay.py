"""Application-manifest wiring and synthetic condition-preservation regressions."""
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


class ApplicationManifestTests(unittest.TestCase):
    def test_aggregate_keeps_original_cases_and_pins_without_rewriting_history(self) -> None:
        root = evaluation.REPO_ROOT
        old = json.loads((root / "evals/intake-retrieval-100.json").read_text(encoding="utf-8"))
        aggregate = json.loads((root / "evals/intake-retrieval-125.json").read_text(encoding="utf-8"))
        evaluation.validate_manifest(aggregate)
        self.assertEqual(aggregate["cases"][:len(old["cases"])], old["cases"])
        self.assertEqual({p: aggregate["files"][p] for p in old["files"]}, old["files"])
        self.assertEqual(len(aggregate["files"]), 8)
        additions = aggregate["cases"][len(old["cases"]):]
        positive_refs = {ref for case in additions for ref in case["expected"]}
        for prefix, count in (("ldo-app-ti-", 4), ("ldo-app-st-", 4),
                              ("ads1115-app-", 9), ("uln2003a-app-", 8)):
            for number in range(1, count + 1):
                self.assertTrue(any(ref.endswith(f"#{prefix}{number:02d}") for ref in positive_refs))
        self.assertEqual(sum(case["command"] == "issues" for case in additions), 4)
        self.assertEqual(sum(not case["expected"] for case in additions), 16)

    def test_current_ci_requires_aggregate_and_separate_dispositions(self) -> None:
        workflow = (evaluation.REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        replay_lines = [line for line in workflow.splitlines() if "pcbknowledge_intake_eval.py --repo" in line]
        self.assertEqual(len(replay_lines), 2)
        for line in replay_lines:
            self.assertIn("--cases evals/intake-retrieval-measurement-timing.json", line)
            self.assertIn("--dispositions evals/intake-dispositions-2026-10-28.json", line)


class SyntheticApplicationPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic-application.json"
        path = self.root / self.relative
        path.parent.mkdir(parents=True)
        # Invented data only: these values are not manufacturer specifications.
        data = {
            "format": "pcbknowledge-independent-intake-v1", "canonical": False,
            "acceptance_status": "DRAFT",
            "sources": [{"id": "synthetic-source", "device": "SYNTH-APP",
                         "manufacturer": "Synthetic", "package": "SYNTH-PKG", "status": "DRAFT"}],
            "facts": [{"id": "typical", "source_id": "synthetic-source", "status": "DRAFT",
                       "kind": "typical_characteristic", "parameter": "loading",
                       "value": {"typical": 7, "guaranteed_maximum": None},
                       "conditions": {"mode": "synthetic-mode", "temperature": 17}},
                      {"id": "current-limit", "source_id": "synthetic-source", "status": "DRAFT",
                       "kind": "electrical_characteristic", "parameter": "current_limit",
                       "value": {"limit": 9, "continuous_load_entitlement": False},
                       "conditions": {"test_voltage": 13, "simultaneous_channels": 1}}],
            "source_issues": [{"id": "unknown-load", "source_id": "synthetic-source",
                               "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                               "missing_inputs": ["board", "load"], "answer": "UNKNOWN"}],
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        self.manifest = {"format": evaluation.FORMAT,
                         "files": {self.relative: hashlib.sha256(path.read_bytes()).hexdigest()},
                         "cases": [
                             {"id": "loading", "command": "search", "query": "",
                              "filters": {"source_id": "synthetic-source", "parameter": "loading"},
                              "expected": [self.relative + "#typical"]},
                             {"id": "current", "command": "search", "query": "",
                              "filters": {"source_id": "synthetic-source", "parameter": "current_limit"},
                              "expected": [self.relative + "#current-limit"]},
                             {"id": "unknown", "command": "issues", "query": "",
                              "filters": {"source_id": "synthetic-source"},
                              "expected": [self.relative + "#unknown-load"]},
                         ]}

    def test_complete_conditions_and_unknowns_replay_without_new_verification(self) -> None:
        result = evaluation.evaluate(self.root, self.manifest)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual((result["fact_count"], result["case_count"]), (2, 3))

    def test_same_ids_cannot_promote_typical_current_or_unknown_results(self) -> None:
        mutations = [
            ("loading", lambda item: item["fact"].update(kind="guaranteed_limit")),
            ("loading", lambda item: item["fact"]["value"].update(guaranteed_maximum=7)),
            ("loading", lambda item: item["fact"]["conditions"].update(mode="different")),
            ("current", lambda item: item["fact"]["value"].update(continuous_load_entitlement=True)),
            ("current", lambda item: item["fact"]["conditions"].update(simultaneous_channels=7)),
            ("unknown", lambda item: item["source_issue"].update(answer="SAFE")),
            ("unknown", lambda item: item["source_issue"].update(missing_inputs=[])),
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
                expected = next(case["expected"] for case in self.manifest["cases"] if case["id"] == target)
                self.assertEqual(failed["actual"], expected)
