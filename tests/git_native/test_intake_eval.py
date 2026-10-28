"""Synthetic evaluator checks; no real source documents are test fixtures."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class IntakeEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic.json"
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        self.data = {
            "format": "pcbknowledge-independent-intake-v1", "canonical": False,
            "acceptance_status": "DRAFT",
            "sources": [{"id": "source-a", "device": "SYNTH-A", "status": "DRAFT",
                         "revision": "synthetic-rev", "sha256": None},
                        {"id": "source-b", "device": "SYNTH-B", "status": "DRAFT"}],
            "facts": [{"id": "fact-a", "source_id": "source-a", "status": "DRAFT",
                       "parameter": "stress", "conditions": {"invented_condition": "retained"},
                       "value": 1, "evidence": {"bbox": None, "visual_checked": False}},
                      {"id": "fact-b", "source_id": "source-a", "status": "DRAFT",
                       "parameter": "stress", "conditions": "synthetic exception", "value": 2}],
            "source_issues": [{"id": "warning-a", "source_id": "source-a",
                               "issue_status": "UNRESOLVED_SOURCE_WORDING",
                               "description": "Synthetic ambiguity, not source evidence."}],
        }
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        self.manifest = {
            "format": evaluation.FORMAT,
            "files": {self.relative: hashlib.sha256(self.path.read_bytes()).hexdigest()},
            "cases": [
                {"id": "facts", "command": "search", "query": "",
                 "filters": {"device": "SYNTH-A", "parameter": "stress"},
                 "expected": [self.relative + "#fact-a", self.relative + "#fact-b"]},
                {"id": "warnings", "command": "issues", "query": "ambiguity",
                 "filters": {"source_id": "source-a"}, "expected": [self.relative + "#warning-a"]},
                {"id": "unknown", "command": "search", "query": "",
                 "filters": {"device": "UNKNOWN"}, "expected": []},
            ],
        }

    def test_actual_cli_replay_and_stable_receipt(self) -> None:
        first = evaluation.evaluate(self.root, self.manifest)
        self.assertEqual(first, evaluation.evaluate(self.root, self.manifest))
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(first["case_count"], 3)
        self.assertEqual(first["fact_count"], 2)
        self.assertEqual(first["dataset_sha256"], evaluation.fingerprint(self.manifest["files"]))

    def test_mutated_cli_output_fails_even_when_ids_and_counts_match(self) -> None:
        def wrong_source(items):
            items[0]["source"]["id"] = "source-b"

        def omit_warning(items):
            items[0]["source_issues"] = []

        def lose_condition(items):
            del items[0]["fact"]["conditions"]

        def fake_verification(items):
            items[0]["evidence_verification"] = "VERIFIED"

        def fake_canonical(items):
            items[0]["canonical"] = True

        def numeric_false(items):
            items[0]["canonical"] = 0  # Python 0 == False must not attest to JSON false.

        def lose_provenance(items):
            del items[0]["fact"]["evidence"]

        for mutation in (wrong_source, omit_warning, lose_condition, fake_verification,
                         fake_canonical, numeric_false, lose_provenance):
            with self.subTest(mutation=mutation.__name__):
                def runner(root, case):
                    items = evaluation.run_cli(root, case)
                    if case["id"] == "facts":
                        mutation(items)
                    return items

                report = evaluation.evaluate(self.root, self.manifest, runner=runner)
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["cases"][0]["passed"])
                self.assertEqual(report["cases"][0]["actual"], self.manifest["cases"][0]["expected"])

    def test_missing_extra_or_reordered_candidates_fail(self) -> None:
        for mutate in (lambda items: items[:1], lambda items: items + items[:1],
                       lambda items: list(reversed(items))):
            with self.subTest(mutation=mutate):
                def runner(root, case):
                    items = evaluation.run_cli(root, case)
                    return mutate(items) if case["id"] == "facts" else items

                self.assertEqual(evaluation.evaluate(self.root, self.manifest, runner=runner)["status"], "FAIL")

    def test_changed_dataset_bytes_fail_before_running_cli(self) -> None:
        self.path.write_text(json.dumps(self.data) + "\n", encoding="utf-8")
        runner = mock.Mock()
        with self.assertRaisesRegex(evaluation.EvaluationError, "dataset bytes or batch set changed"):
            evaluation.evaluate(self.root, self.manifest, runner=runner)
        runner.assert_not_called()

    def test_extra_batch_and_missing_expected_reference_fail(self) -> None:
        extra = self.path.with_name("extra.json")
        extra.write_bytes(self.path.read_bytes())
        with self.assertRaisesRegex(evaluation.EvaluationError, "batch set changed"):
            evaluation.evaluate(self.root, self.manifest)
        extra.unlink()
        self.manifest["cases"][0]["expected"] = [self.relative + "#absent"]
        with self.assertRaisesRegex(evaluation.EvaluationError, "expected reference is absent"):
            evaluation.evaluate(self.root, self.manifest)

    def test_dataset_edit_during_replay_fails(self) -> None:
        def runner(root, case):
            items = evaluation.run_cli(root, case)
            self.path.write_text(json.dumps(self.data) + "\n", encoding="utf-8")
            return items

        with self.assertRaisesRegex(evaluation.EvaluationError, "dataset changed during evaluation"):
            evaluation.evaluate(self.root, self.manifest, runner=runner)

    def test_invalid_manifests_cannot_report_vacuous_pass(self) -> None:
        variants = []
        for key, value in (("cases", []), ("files", {}), ("format", "unknown")):
            manifest = copy.deepcopy(self.manifest)
            manifest[key] = value
            variants.append(manifest)
        for key, value in (("filters", {"unknown": "x"}), ("filters", {"device": " "}),
                           ("expected", ["duplicate", "duplicate"]), ("command", "validate")):
            manifest = copy.deepcopy(self.manifest)
            manifest["cases"][0][key] = value
            variants.append(manifest)
        duplicate = copy.deepcopy(self.manifest)
        duplicate["cases"].append(duplicate["cases"][0])
        variants.append(duplicate)
        for manifest in variants:
            with self.subTest(manifest=manifest), self.assertRaises(evaluation.EvaluationError):
                evaluation.evaluate(self.root, manifest)

    def test_cli_failure_timeout_and_invalid_json_are_not_passes(self) -> None:
        for response in (subprocess.CompletedProcess([], 2, "", "invalid filter"),
                         subprocess.CompletedProcess([], 0, "not json", ""),
                         subprocess.CompletedProcess([], 0, "{}", "")):
            with self.subTest(response=response), mock.patch.object(evaluation.subprocess, "run", return_value=response):
                self.assertEqual(evaluation.evaluate(self.root, self.manifest)["status"], "FAIL")
        with mock.patch.object(evaluation.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic", 30)):
            self.assertEqual(evaluation.evaluate(self.root, self.manifest)["status"], "FAIL")

    def test_main_reports_success_failure_and_invalid_input_exit_codes(self) -> None:
        manifest_path = self.root / "cases.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        args = ["--repo", str(self.root), "--cases", str(manifest_path)]
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(evaluation.main(args), 0)
        self.assertEqual(json.loads(stdout.getvalue())["manifest_sha256"],
                         hashlib.sha256(manifest_path.read_bytes()).hexdigest())
        self.manifest["cases"][0]["expected"] = []
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(evaluation.main(args), 1)
        manifest_path.write_text("{}", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(evaluation.main(args), 2)


if __name__ == "__main__":
    unittest.main()
