"""Synthetic register arithmetic, not analog accuracy or a device state machine."""
from __future__ import annotations

import contextlib
import copy
from fractions import Fraction as F
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from configs import pcbknowledge_ina219_register_eval as ee


class Ina219RegisterTests(unittest.TestCase):
    def test_fixed_cases_and_full_source_payloads(self):
        report = ee.evaluate(ee.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "PASS")
        self.assertEqual(report["case_count"], 10)
        self.assertEqual(report, ee.evaluate(ee.REPO_ROOT))
        evidence = report["evidence"]
        original = json.loads((ee.REPO_ROOT / ee.BATCH).read_bytes())
        facts = {f["id"]: f for f in original["facts"]}
        issues = {i["id"]: i for i in original["source_issues"]}
        self.assertEqual(len(evidence["facts"]), 8)
        self.assertEqual(len(evidence["issues"]), 3)
        for candidate in evidence["facts"]:
            self.assertEqual(candidate["fact"], facts[candidate["fact"]["id"]])
            self.assertEqual(candidate["source"], original["sources"][0])
            self.assertEqual(candidate["source_issues"], sorted(issues.values(), key=lambda i: i["id"]))
        for candidate in evidence["issues"]:
            self.assertEqual(candidate["source_issue"], issues[candidate["source_issue"]["id"]])
            self.assertEqual(candidate["source"], original["sources"][0])
        self.assertFalse(evidence["canonical"])
        self.assertFalse(evidence["human_reviewed"])
        self.assertEqual(evidence["evidence_verification"], "NOT_LOCALLY_VERIFIED")

    def test_literal_arithmetic_and_independent_register_inputs(self):
        result = ee._calculate(ee._inputs())
        self.assertEqual(result, ee._expected())
        self.assertEqual(result["calibration"]["candidate_exact"], "2048/5")
        self.assertEqual(result["calibration"]["truncated"], 409)
        self.assertEqual(result["calibration"]["effective_FS0_zero"], 408)
        changed = ee._calculate({**ee._inputs(), "shunt_register": 100})
        self.assertEqual(changed["raw"]["shunt_uV"], 1000)
        self.assertEqual(changed["scaled"], result["scaled"])
        self.assertEqual(changed["readiness_sequence"], "BLOCKED")

    def test_all_low_bus_bits_excluded_from_voltage_and_OVF_suppresses_scale(self):
        for high in (0, 1, 1000, 8191):
            for low in range(8):
                result = ee._calculate({**ee._inputs(), "bus_register": high * 8 + low})
                self.assertEqual(result["raw"], {"shunt_uV": -1000, "bus_mV": high * 4,
                                                "CNVR": (low >> 1) & 1, "OVF": low & 1})
                self.assertEqual(result["scaled"] is None, bool(low & 1))
                self.assertEqual(result["analog_validity"], "UNKNOWN")
                self.assertEqual(result["freshness_and_coherence"], "UNKNOWN")
                self.assertEqual(result["readiness_sequence"], "BLOCKED")

    def test_signed_and_unsigned_numeric_boundaries(self):
        for code, signed in ((0, 0), (1, 1), (32767, 32767), (32768, -32768), (65535, -1)):
            result = ee._calculate({**ee._inputs(), "shunt_register": code,
                                    "current_register": code, "power_register": code})
            self.assertEqual(result["raw"]["shunt_uV"], signed * 10)
            self.assertEqual(F(result["scaled"]["current_A_exact"]), F(signed, 1000))
            self.assertEqual(F(result["scaled"]["power_W_exact"]), F(code, 50))

    def test_odd_even_calibration_and_invalid_calibration_never_mask_overflow(self):
        # Exact synthetic scales produce odd/even truncated candidates without float arithmetic.
        for resistance, candidate, effective in (("0.1", 409, 408), ("0.01", 4096, 4096),
                                                 ("0.2", 204, 204)):
            result = ee._calculate({**ee._inputs(), "shunt_Ohm": resistance, "actual_calibration": effective})
            self.assertEqual(result["calibration"]["truncated"], candidate)
            self.assertEqual(result["calibration"]["effective_FS0_zero"], effective)
            self.assertIsNotNone(result["scaled"])
        for lsb, effective in (("0.02048", 2), ("0.00000062501", 65534)):
            result = ee._calculate({**ee._inputs(), "current_lsb_A": lsb, "shunt_Ohm": "1", "actual_calibration": effective})
            self.assertEqual(result["calibration"]["effective_FS0_zero"], effective)
            self.assertIsNotNone(result["scaled"])
        overflow = ee._calculate({**ee._inputs(), "current_lsb_A": "0.000000625", "shunt_Ohm": "1"})
        self.assertEqual(overflow["reason"], "calibration_outside_representable_range")
        self.assertIsNone(overflow["calibration"])
        # Candidate 1 truncates to 1 then fixed FS0 yields zero; no zero-load inference.
        zero = ee._calculate({**ee._inputs(), "current_lsb_A": "0.04096", "shunt_Ohm": "1", "actual_calibration": 0})
        self.assertEqual(zero["calibration"]["effective_FS0_zero"], 0)
        self.assertEqual(zero["reason"], "effective_calibration_zero")
        for lsb in ("1", "0.000000001"):
            result = ee._calculate({**ee._inputs(), "current_lsb_A": lsb})
            self.assertIsNone(result["calibration"])
            self.assertIsNone(result["scaled"])
        for actual in (None, 0, 410):
            result = ee._calculate({**ee._inputs(), "actual_calibration": actual})
            self.assertIsNone(result["scaled"])
            self.assertEqual(result["scale_consistency"], "NOT_ESTABLISHED")
        for actual in (True, -2, 409, 65536, 408.0, "408"):
            self.assertEqual(ee._calculate({**ee._inputs(), "actual_calibration": actual})["outcome"], "NOT_EVALUABLE")

    def test_strict_inputs_refuse_not_guess(self):
        for key in ("shunt_register", "bus_register", "current_register", "power_register"):
            for value in (None, True, -1, 65536, 1.0, "1", [], {}):
                result = ee._calculate({**ee._inputs(), key: value})
                self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                self.assertIsNone(result["raw"])
                self.assertIsNone(result["scaled"])
        for key in ("current_lsb_A", "shunt_Ohm"):
            for value in (None, True, 0, "0", "-0.1", "1e-3", "NaN", "Infinity", "9" * 41):
                result = ee._calculate({**ee._inputs(), key: value})
                self.assertIsNone(result["scaled"])
                self.assertEqual(result["reason"], "missing_or_invalid_positive_scale_inputs")
        for key in (*ee.IDENTITY, "model", "shunt_representation"):
            self.assertEqual(ee._calculate({**ee._inputs(), key: "unsupported"})["outcome"], "NOT_EVALUABLE")
        for key in ee._inputs():
            inputs = ee._inputs(); del inputs[key]
            self.assertEqual(ee._calculate(inputs)["reason"], "missing_or_extra_input")
        self.assertEqual(ee._calculate({**ee._inputs(), "physical_accuracy": "guaranteed"})["reason"], "missing_or_extra_input")

    def test_input_immutability_and_independent_oracles(self):
        inputs = ee._inputs(); original = copy.deepcopy(inputs)
        ee._calculate(inputs)
        self.assertEqual(inputs, original)
        cases = ee._scenarios()
        cases[0][2]["raw"]["CNVR"] = 999
        self.assertEqual(cases[1][2]["raw"]["CNVR"], 1)

    def test_complete_numeric_and_authority_output_mutations_fail(self):
        pristine = ee._calculate
        mutations = [
            (["raw", "shunt_uV"], 654360), (["raw", "bus_mV"], 32008),
            (["calibration", "truncated"], 410), (["calibration", "effective_FS0_zero"], 409),
            (["calibration", "actual"], None), (["calibration", "declared_power_lsb_W"], "1/1000"),
            (["scaled", "current_A_exact"], "16359/250"), (["scaled", "power_W_exact"], "-5"),
            (["scale_consistency"], "IDEAL_GAIN_PROVED"), (["physical_accuracy"], "GUARANTEED"),
            (["analog_validity"], "VALID"), (["freshness_and_coherence"], "FRESH"),
            (["readiness_sequence"], "RESOLVED"), (["circuit_qualification"], "ESTABLISHED"),
        ]
        for keys, value in mutations:
            def changed(inputs):
                result = pristine(inputs)
                if inputs == ee._inputs():
                    node = result
                    for key in keys[:-1]: node = node[key]
                    node[keys[-1]] = value
                return result
            with self.subTest(keys=keys), mock.patch.object(ee, "_calculate", side_effect=changed):
                report = ee.evaluate(ee.REPO_ROOT)
                self.assertEqual(report["evaluation_status"], "FAIL")
                self.assertFalse(report["cases"][0]["passed"])
        def invented(inputs):
            result = pristine(inputs)
            if result["scaled"] is None: result["scaled"] = {"current_A_exact": "0", "power_W_exact": "0"}
            return result
        with mock.patch.object(ee, "_calculate", side_effect=invented):
            self.assertEqual(ee.evaluate(ee.REPO_ROOT)["evaluation_status"], "FAIL")

    def test_pinned_bytes_missing_metadata_and_race_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ee.BATCH
            path.parent.mkdir(parents=True)
            original = (ee.REPO_ROOT / ee.BATCH).read_bytes()
            path.write_bytes(original)
            self.assertEqual(ee.evaluate(root)["evaluation_status"], "PASS")
            path.write_bytes(original + b"\n")
            with self.assertRaises(ee.RegisterEvaluationError):
                ee.evaluate(root)
            path.unlink()
            with self.assertRaises(ee.RegisterEvaluationError):
                ee.evaluate(root)
        first = ee._evidence(ee.REPO_ROOT)
        second = copy.deepcopy(first)
        second["issues"] = []
        with mock.patch.object(ee, "_evidence", side_effect=[first, second]):
            with self.assertRaisesRegex(ee.RegisterEvaluationError, "changed during"):
                ee.evaluate(ee.REPO_ROOT)

    def test_actual_CLI_and_exit_status_contract(self):
        run = subprocess.run([sys.executable, str(ee.REPO_ROOT / "configs/pcbknowledge_ina219_register_eval.py"),
                              "--repo", str(ee.REPO_ROOT)], capture_output=True, text=True, check=False,
                             env={**os.environ, "PYTHONPATH": str(ee.REPO_ROOT / "src")})
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["evaluation_status"], "PASS")
        with mock.patch.object(ee, "_calculate", return_value={}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ee.main(["--repo", str(ee.REPO_ROOT)]), 1)
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ee.main(["--repo", root]), 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ee.main(["--repo", str(ee.REPO_ROOT), "--input", "board.json"])


if __name__ == "__main__":
    unittest.main()
