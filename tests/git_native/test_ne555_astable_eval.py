"""Fixed synthetic model arithmetic and refusals, never oscillator qualification."""
from __future__ import annotations

import contextlib
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from configs import pcbknowledge_ne555_astable_eval as ne


class Ne555AstableTests(unittest.TestCase):
    def test_fixed_report_preserves_full_source_payloads(self):
        report = ne.evaluate(ne.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "PASS")
        self.assertEqual(report["case_count"], 10)
        self.assertEqual(report, ne.evaluate(ne.REPO_ROOT))
        evidence = report["evidence"]
        self.assertEqual(evidence["files"], ne.PINS)
        self.assertEqual(len(evidence["facts"]), 29)
        self.assertEqual(len(evidence["issues"]), 9)
        for path in ne.PINS:
            original = json.loads((ne.REPO_ROOT / path).read_bytes())
            sources = {s["id"]: s for s in original["sources"]}
            facts = {f["id"]: f for f in original["facts"]}
            issues = {i["id"]: i for i in original.get("source_issues", [])}
            for item in evidence["facts"]:
                if item["fact"]["id"] not in facts:
                    continue
                self.assertEqual(item["fact"], facts[item["fact"]["id"]])
                source = sources[item["fact"]["source_id"]]
                self.assertEqual(item["source"], source)
                self.assertEqual(item["source_issues"], sorted(
                    [i for i in issues.values() if i["source_id"] == source["id"]],
                    key=lambda i: i["id"]))
        self.assertFalse(evidence["canonical"])
        self.assertFalse(evidence["human_reviewed"])
        self.assertEqual(evidence["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertTrue(all(i["source"]["id"] not in ne.EXCLUDED_SOURCES
                            for i in evidence["facts"] + evidence["issues"]))

    def test_model_arithmetic_is_not_hardware_accuracy(self):
        result = ne._calculate(ne._inputs())
        nominal = result["nominal"]
        self.assertEqual(F(nominal["high_time_s"]) + F(nominal["low_time_s"]),
                         F(nominal["period_s"]))
        self.assertEqual(nominal["high_waveform_fraction"], "2/3")
        self.assertEqual(nominal["low_driver_fraction"], "1/3")
        self.assertEqual(nominal["frequency_from_rounded_formula_Hz"], "480")
        self.assertAlmostEqual(float(F(nominal["reciprocal_rounded_period_Hz"])), 481.000481, places=6)
        self.assertNotEqual(F(nominal["rounded_coefficient_product"]), 1)
        self.assertIsNone(result["hardware_timing_interval"])
        self.assertEqual(result["hardware_accuracy"], "UNKNOWN")
        self.assertEqual(result["working_component_selection"], "NOT_ESTABLISHED")

    def test_fixed_scope_rejects_missing_extra_and_changed_inputs(self):
        for key in ne._inputs():
            for value in (None, False, "unsupported", "NaN", "Infinity"):
                inputs = ne._inputs()
                inputs[key] = value
                with self.subTest(key=key, value=value):
                    result = ne._calculate(inputs)
                    self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                    self.assertIsNone(result["nominal"])
            inputs = ne._inputs()
            del inputs[key]
            self.assertEqual(ne._calculate(inputs)["outcome"], "NOT_EVALUABLE")
        for extra in ({"initial_C_tolerance_percent": "10"}, {"typical_ppm_per_C": "150"},
                      {"guaranteed_frequency_Hz": ["430", "530"]}):
            self.assertIsNone(ne._calculate({**ne._inputs(), **extra})["nominal"])

    def test_inputs_are_immutable_and_fixtures_independent(self):
        inputs = ne._inputs()
        before = copy.deepcopy(inputs)
        ne._calculate(inputs)
        self.assertEqual(inputs, before)
        cases = ne._scenarios()
        cases[0][1]["C_F"] = None
        self.assertEqual(cases[1][1]["C_F"], "0.0000001")
        self.assertEqual(ne._inputs(), before)

    def test_semantic_mutations_fail_regression(self):
        pristine = ne._calculate
        mutations = (
            ("nominal", "frequency_from_rounded_formula_Hz", "1000000/2079"),
            ("nominal", "reciprocal_rounded_period_Hz", "480"),
            ("nominal", "high_waveform_fraction", "1/3"),
            ("nominal", "low_driver_fraction", "2/3"),
            ("nominal", "rounded_coefficient_product", "1"),
            (None, "hardware_timing_interval", ["432", "528"]),
            (None, "hardware_accuracy", "GUARANTEED"),
            (None, "working_component_selection", "C0603C104K5RACTU"),
            (None, "circuit_qualification", "ESTABLISHED"),
        )
        for section, key, value in mutations:
            def changed(inputs):
                result = pristine(inputs)
                if result["nominal"] is not None:
                    (result[section] if section else result)[key] = value
                return result
            with self.subTest(key=key), mock.patch.object(ne, "_calculate", side_effect=changed):
                report = ne.evaluate(ne.REPO_ROOT)
                self.assertEqual(report["evaluation_status"], "FAIL")
                self.assertFalse(report["cases"][0]["passed"])

    def test_pinned_metadata_is_required_and_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ne.PINS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ne.REPO_ROOT / relative).read_bytes())
            self.assertEqual(ne.evaluate(root)["evaluation_status"], "PASS")
            for relative in ne.PINS:
                target = root / relative
                original = target.read_bytes()
                target.write_bytes(original + b"\n")
                with self.assertRaises(ne.AstableEvaluationError):
                    ne.evaluate(root)
                target.write_bytes(original)
            target.unlink()
            with self.assertRaises(ne.AstableEvaluationError):
                ne.evaluate(root)

    def test_mid_evaluation_evidence_change_fails_closed(self):
        first = ne._evidence(ne.REPO_ROOT)
        second = copy.deepcopy(first)
        second["issues"] = []
        with mock.patch.object(ne, "_evidence", side_effect=[first, second]):
            with self.assertRaisesRegex(ne.AstableEvaluationError, "changed during"):
                ne.evaluate(ne.REPO_ROOT)

    def test_actual_cli_and_exit_status_contract(self):
        environment = {**os.environ, "PYTHONPATH": str(ne.REPO_ROOT / "src")}
        run = subprocess.run([sys.executable, str(ne.REPO_ROOT / "configs/pcbknowledge_ne555_astable_eval.py"),
                              "--repo", str(ne.REPO_ROOT)], capture_output=True, text=True,
                             env=environment, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["circuit_qualification"], "NOT_ESTABLISHED")
        with mock.patch.object(ne, "_calculate", return_value={}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ne.main(["--repo", str(ne.REPO_ROOT)]), 1)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ne.main(["--repo", directory]), 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ne.main(["--repo", str(ne.REPO_ROOT), "--input", "circuit.json"])


if __name__ == "__main__":
    unittest.main()
