"""Synthetic DC arithmetic and refusal checks; no real-board qualification."""
from __future__ import annotations

import contextlib
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from configs import pcbknowledge_resistor_dc_eval as dc


class ResistorDcTests(unittest.TestCase):
    def scenario(self):
        return dc._scenarios()[0][1]

    def test_fixed_cases_and_complete_original_evidence(self):
        report = dc.evaluate(dc.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "PASS")
        self.assertEqual(report["case_count"], 14)
        self.assertEqual(report, dc.evaluate(dc.REPO_ROOT))
        evidence = report["evidence"]
        self.assertEqual(len(evidence["facts"]), 7)
        self.assertEqual(len(evidence["issues"]), 3)
        self.assertFalse(evidence["canonical"])
        self.assertFalse(evidence["human_reviewed"])
        self.assertEqual(evidence["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        batch = json.loads((dc.REPO_ROOT / dc.BATCH).read_bytes())
        originals = {fact["id"]: fact for fact in batch["facts"]}
        source = batch["sources"][0]
        warnings = sorted(batch["source_issues"], key=lambda item: item["id"])
        for candidate in evidence["facts"]:
            self.assertEqual(candidate["fact"], originals[candidate["fact"]["id"]])
            self.assertEqual(candidate["source"], source)
            self.assertEqual(candidate["source_issues"], warnings)

    def test_document_exact_numbers_and_display_rounding(self):
        result = dc._calculate(self.scenario(), F(1, 10))
        self.assertEqual(result, dc._scenarios()[0][2])
        bounds = result["bounds"]
        self.assertEqual(bounds["current_A_exact"], ["19/40800", "3/5600"])
        self.assertEqual(bounds["power_W_exact"], ["361/163200", "9/3200"])
        self.assertEqual(bounds["upper_power_over_standard_P70_exact"], "9/320")
        self.assertEqual(result["operating_resistance_guarantee"], "NOT_ESTABLISHED")

    def test_grid_points_are_enclosed(self):
        bounds = dc._calculate(self.scenario(), F(1, 10))["bounds"]
        ilo, ihi = map(F, bounds["current_A_exact"])
        plo, phi = map(F, bounds["power_W_exact"])
        for vi in range(21):
            v = F(19, 4) + F(vi, 40)
            for ri in range(21):
                r = 9800 + 20 * ri
                self.assertLessEqual(ilo, v / r)
                self.assertLessEqual(v / r, ihi)
                self.assertLessEqual(plo, v * v / r)
                self.assertLessEqual(v * v / r, phi)

    def test_outward_rounding_contains_exact_values(self):
        for value in (F(0), F(1, 3), F(1, 10**20), F(361, 163200), F(9, 3200), F(123456, 7)):
            lower = F(dc._outward_milli(value, False)) / 1000
            upper = F(dc._outward_milli(value, True)) / 1000
            self.assertLessEqual(lower, value)
            self.assertLessEqual(value, upper)
            self.assertLessEqual(upper - lower, F(1, 10**9))

    def test_changed_voltage_changes_calculation_not_qualification(self):
        scenario = self.scenario()
        scenario["terminal_voltage_V"] = ["50", "50"]
        result = dc._calculate(scenario, F(1, 10))
        self.assertEqual(result["bounds"]["power_W_exact"], ["25/102", "25/98"])
        self.assertGreater(F(result["bounds"]["upper_power_over_standard_P70_exact"]), 1)
        self.assertEqual(result["thermal_qualification"], "NOT_ESTABLISHED")
        self.assertEqual(result["circuit_qualification"], "NOT_ESTABLISHED")
        self.assertEqual(result["bounds"]["reference_comparison_scope"],
                         "NUMERICAL_ONLY_NOT_ALLOWABLE_POWER")

    def test_nominal_tolerance_cannot_supply_operating_interval(self):
        scenario = self.scenario()
        scenario["operating_resistance_Ohm"] = ["9900", "10100"]
        scenario["resistance_basis"] = "nominal_plus_initial_tolerance"
        result = dc._calculate(scenario, F(1, 10))
        self.assertEqual(result["outcome"], "NOT_EVALUABLE")
        self.assertIsNone(result["bounds"])
        del scenario["resistance_basis"]
        self.assertEqual(dc._calculate(scenario, F(1, 10))["unknowns"],
                         ["operating_resistance_not_supplied"])

    def test_missing_invalid_nonpositive_and_reversed_intervals(self):
        for key in ("terminal_voltage_V", "operating_resistance_Ohm"):
            for interval in (None, [], "5", ["1"], ["1", "2", "3"], ["2", "1"],
                             [False, "2"], ["0", 3.0], ["NaN", "3"], ["0", "Infinity"],
                             ["0", "3/1"], ["0", "1e2"], ["0", "9" * 41]):
                with self.subTest(key=key, interval=interval):
                    result = dc._calculate({**self.scenario(), key: interval}, F(1, 10))
                    self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                    self.assertIn(key, result["unknowns"])
        for interval in (["0", "1"], ["-1", "1"], ["0", "0"]):
            self.assertIsNone(dc._calculate({**self.scenario(), "operating_resistance_Ohm": interval},
                                           F(1, 10))["bounds"])
        both = {**self.scenario(), "terminal_voltage_V": None, "operating_resistance_Ohm": None}
        self.assertEqual(dc._calculate(both, F(1, 10))["unknowns"],
                         ["terminal_voltage_V", "operating_resistance_Ohm"])

    def test_wrong_identity_revision_model_and_waveform(self):
        for key, value in (("manufacturer", "other"), ("device", "other"),
                           ("package", "0805"), ("revision", "old"),
                           ("waveform", "ac_rms"), ("waveform", "repeated_pulse"),
                           ("model", None)):
            with self.subTest(key=key):
                result = dc._calculate({**self.scenario(), key: value}, F(1, 10))
                self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                self.assertIsNone(result["bounds"])

    def test_reference_cannot_switch_to_extended_mode(self):
        with self.assertRaises(dc.DcEvaluationError):
            dc._calculate(self.scenario(), F(1, 8))

    def test_inputs_and_independent_fixtures_are_not_mutated(self):
        scenario = self.scenario()
        original = copy.deepcopy(scenario)
        dc._calculate(scenario, F(1, 10))
        self.assertEqual(scenario, original)
        fixtures = dc._scenarios()
        fixtures[0][1]["operating_resistance_Ohm"][0] = "0"
        self.assertEqual(fixtures[1][1]["operating_resistance_Ohm"][0], "9800")
        self.assertEqual(self.scenario(), original)

    def test_byte_identity_missing_warnings_and_invalid_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / dc.BATCH
            path.parent.mkdir(parents=True)
            original = (dc.REPO_ROOT / dc.BATCH).read_bytes()
            path.write_bytes(original)
            self.assertEqual(dc.evaluate(root)["evaluation_status"], "PASS")
            altered = json.loads(original)
            altered["source_issues"] = []
            for payload in (original + b"\n", b"{}", json.dumps(altered).encode(),
                            original.replace(b"14-Apr-2026", b"14-Apr-2025")):
                path.write_bytes(payload)
                with self.assertRaises((dc.DcEvaluationError, dc.IntakeError)):
                    dc.evaluate(root)
            path.unlink()
            with self.assertRaises(dc.DcEvaluationError):
                dc.evaluate(root)

    def test_evidence_changes_during_evaluation_fail_closed(self):
        first = dc._evidence(dc.REPO_ROOT)
        second = copy.deepcopy(first)
        second["issues"] = []
        with mock.patch.object(dc, "_evidence", side_effect=[first, second]):
            with self.assertRaisesRegex(dc.DcEvaluationError, "changed during"):
                dc.evaluate(dc.REPO_ROOT)

    def test_wrong_arithmetic_and_qualification_mutations_fail_evaluation(self):
        pristine = dc._calculate
        def wrong(scenario, reference):
            result = pristine(scenario, reference)
            if result["bounds"] is not None:
                result["bounds"]["power_W_exact"] = ["0", "0"]
            return result
        with mock.patch.object(dc, "_calculate", side_effect=wrong):
            self.assertEqual(dc.evaluate(dc.REPO_ROOT)["evaluation_status"], "FAIL")
        for key in ("circuit_qualification", "thermal_qualification", "operating_resistance_guarantee"):
            def promote(scenario, reference):
                result = pristine(scenario, reference)
                result[key] = "ESTABLISHED"
                return result
            with mock.patch.object(dc, "_calculate", side_effect=promote):
                report = dc.evaluate(dc.REPO_ROOT)
                self.assertEqual(report["evaluation_status"], "FAIL")
                self.assertTrue(all(not case["passed"] for case in report["cases"]))

    def test_cli_is_fixed_input_and_exit_status_is_not_circuit_status(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(dc.main(["--repo", str(dc.REPO_ROOT)]), 0)
        self.assertEqual(json.loads(stream.getvalue())["circuit_qualification"], "NOT_ESTABLISHED")
        with mock.patch.object(dc, "_calculate", return_value={}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dc.main(["--repo", str(dc.REPO_ROOT)]), 1)
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dc.main(["--repo", root]), 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            dc.main(["--repo", str(dc.REPO_ROOT), "--input", "board.json"])


if __name__ == "__main__":
    unittest.main()
