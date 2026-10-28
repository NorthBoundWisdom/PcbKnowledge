"""Fixed synthetic engineering scenarios; no vendor originals or board fixtures."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from configs import pcbknowledge_ads1115_boundary_eval as boundary


class Ads1115BoundaryTests(unittest.TestCase):
    def scenario(self):
        return boundary._scenarios()[1][1]

    def test_real_bound_metadata_and_fixed_semantics(self):
        report = boundary.evaluate(boundary.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "PASS")
        self.assertEqual(report["case_count"], 14)
        self.assertTrue(all(case["passed"] for case in report["cases"]))
        self.assertEqual(report["circuit_qualification"], "NOT_ESTABLISHED")
        evidence = report["evidence"]
        self.assertEqual(evidence["files"], boundary.PINS)
        self.assertEqual(len(evidence["facts"]), 10)
        self.assertEqual(len(evidence["issues"]), 3)
        self.assertEqual(evidence["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertIs(evidence["canonical"], False)
        self.assertIs(evidence["human_reviewed"], False)
        for item in evidence["facts"][1:]:
            self.assertEqual([x["id"] for x in item["source_issues"]], list(boundary.WARNINGS))
            self.assertTrue(item["fact"]["conditions"])
            self.assertEqual(item["fact"]["evidence"]["source_sha256"], boundary.PDF_SHA)
        self.assertEqual(report, boundary.evaluate(boundary.REPO_ROOT))

    def test_same_evidence_different_input_changes_conclusion(self):
        scenario = self.scenario()
        self.assertEqual(boundary._compare_pins(scenario)["outcome"],
                         "NO_PIN_RAIL_VIOLATION_IN_STATED_INTERVALS")
        scenario["ainp_V"][1] = "4"
        result = boundary._compare_pins(scenario)
        self.assertEqual(result["violations"], ["ainp_V:ABOVE_VDD"])
        self.assertEqual(result["outcome"], "RECOMMENDED_PIN_RAIL_EXCEEDED")
        self.assertEqual(result["circuit_qualification"], "NOT_ESTABLISHED")

    def test_each_pin_not_only_the_difference(self):
        for changes, violation in (
            ({"ainp_V": ["4", "4"], "ainn_V": ["3", "3"]}, "ainp_V:ABOVE_VDD"),
            ({"ainp_V": ["1", "1"], "ainn_V": ["-0.1", "-0.1"]}, "ainn_V:BELOW_GND"),
            ({"ainp_V": ["-1", "-1"], "ainn_V": ["0", "0"]}, "ainp_V:BELOW_GND"),
            ({"ainp_V": ["3", "3"], "ainn_V": ["4", "4"]}, "ainn_V:ABOVE_VDD"),
        ):
            with self.subTest(changes=changes):
                result = boundary._compare_pins({**self.scenario(), **changes})
                self.assertEqual(result["violations"], [violation])

    def test_exact_decimal_endpoints_and_negative_difference(self):
        scenario = {**self.scenario(), "ainp_V": ["0", "0"], "ainn_V": ["0", "3.3"]}
        self.assertEqual(boundary._compare_pins(scenario)["violations"], [])
        scenario["ainn_V"][1] = "3.30000000000000000001"
        self.assertEqual(boundary._compare_pins(scenario)["violations"], ["ainn_V:ABOVE_VDD"])
        scenario["ainn_V"] = ["-0.00000000000000000001", "3.3"]
        self.assertEqual(boundary._compare_pins(scenario)["violations"], ["ainn_V:BELOW_GND"])

    def test_missing_pins_never_default_to_zero(self):
        for pin in ("ainp_V", "ainn_V"):
            scenario = self.scenario()
            del scenario[pin]
            result = boundary._compare_pins(scenario)
            self.assertEqual(result["outcome"], "NOT_EVALUABLE")
            self.assertEqual(result["unknowns"], [pin])

    def test_invalid_intervals_cannot_establish_no_violation(self):
        for interval in (None, "0..3", [], ["0"], ["0", "1", "2"], ["3", "0"],
                         [False, "3"], ["0", 3.0], ["NaN", "3"], ["0", "Infinity"],
                         ["0", "3/1"], ["0", "1e99999"], ["0", "9" * 41]):
            with self.subTest(interval=interval):
                result = boundary._compare_pins({**self.scenario(), "ainp_V": interval})
                self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                self.assertEqual(result["unknowns"], ["ainp_V"])

    def test_out_of_scope_identity_and_operating_state(self):
        for key, value in (("manufacturer", "other"), ("device", "ADS1015"),
                           ("package", "RUG"), ("revision", "SBAS444D"),
                           ("vdd_V", None), ("vdd_V", "5"), ("gnd_V", "0.1"),
                           ("ambient_C", "126"), ("power_state", "startup"),
                           ("pga_magnitude_V", "2.048")):
            with self.subTest(key=key, value=value):
                result = boundary._compare_pins({**self.scenario(), key: value})
                self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                self.assertTrue(result["unknowns"])

    def test_known_violation_does_not_erase_unknown_other_pin(self):
        result = boundary._compare_pins({**self.scenario(), "ainp_V": ["0", "4"], "ainn_V": None})
        self.assertEqual(result["outcome"], "RECOMMENDED_PIN_RAIL_EXCEEDED")
        self.assertEqual(result["unknowns"], ["ainn_V"])
        self.assertEqual(result["circuit_qualification"], "NOT_ESTABLISHED")

    def test_inputs_are_not_mutated(self):
        scenario = self.scenario()
        before = copy.deepcopy(scenario)
        boundary._compare_pins(scenario)
        self.assertEqual(scenario, before)

    def test_fixture_instances_are_independent(self):
        first = boundary._scenarios()
        first[1][1]["ainp_V"][0] = "changed"
        self.assertEqual(first[0][1]["ainp_V"][0], "0")
        self.assertEqual(boundary._scenarios()[1][1]["ainp_V"][0], "0")

    def test_missing_changed_and_invalid_metadata_fail_closed(self):
        # Copy only already-public metadata, not source documents or fixture data.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in boundary.PINS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((boundary.REPO_ROOT / relative).read_bytes())
            self.assertEqual(boundary.evaluate(root)["evaluation_status"], "PASS")
            path = root / boundary.APP_PATH
            original = path.read_bytes()
            for edit in (original + b"\n", b"{}", original.replace(b"SBAS444E", b"SBAS444D"),
                         original.replace(b"UNRESOLVED_APPLICATION_INPUTS", b"RESOLVED")):
                path.write_bytes(edit)
                with self.assertRaises((boundary.BoundaryEvaluationError, boundary.IntakeError)):
                    boundary.evaluate(root)
            path.unlink()
            with self.assertRaises(boundary.BoundaryEvaluationError):
                boundary.evaluate(root)

    def test_symlink_metadata_is_rejected(self):
        # Existing intake loader owns portable path-safety checks; simulate the
        # exact loader error rather than requiring symlink privileges on Windows.
        with mock.patch.object(boundary, "load_intake", side_effect=boundary.IntakeError("symlink forbidden")):
            with self.assertRaises(boundary.IntakeError):
                boundary.evaluate(boundary.REPO_ROOT)

    def test_evidence_tamper_during_evaluation_fails(self):
        first = boundary._evidence(boundary.REPO_ROOT)
        second = copy.deepcopy(first)
        second["facts"][0]["fact"]["conditions"] = "changed"
        with mock.patch.object(boundary, "_evidence", side_effect=[first, second]):
            with self.assertRaisesRegex(boundary.BoundaryEvaluationError, "changed during"):
                boundary.evaluate(boundary.REPO_ROOT)

    def test_wrong_conclusion_is_evaluation_failure_not_successful_retrieval(self):
        pristine = boundary._compare_pins
        def wrong(scenario):
            result = pristine(scenario)
            result["outcome"] = "NO_PIN_RAIL_VIOLATION_IN_STATED_INTERVALS"
            return result
        with mock.patch.object(boundary, "_compare_pins", side_effect=wrong):
            report = boundary.evaluate(boundary.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "FAIL")
        self.assertFalse(report["cases"][0]["passed"])

    def test_qualification_promotion_is_evaluation_failure(self):
        pristine = boundary._compare_pins
        def promote(scenario):
            result = pristine(scenario)
            result["circuit_qualification"] = "QUALIFIED"
            return result
        with mock.patch.object(boundary, "_compare_pins", side_effect=promote):
            report = boundary.evaluate(boundary.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "FAIL")
        self.assertTrue(all(not case["passed"] for case in report["cases"]))

    def test_cli_exit_codes_and_fixed_input_surface(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(boundary.main(["--repo", str(boundary.REPO_ROOT)]), 0)
        self.assertEqual(json.loads(stream.getvalue())["evaluation_status"], "PASS")
        with mock.patch.object(boundary, "_compare_pins", return_value={}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(boundary.main(["--repo", str(boundary.REPO_ROOT)]), 1)
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boundary.main(["--repo", root]), 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            boundary.main(["--repo", str(boundary.REPO_ROOT), "--input", "board.json"])


if __name__ == "__main__":
    unittest.main()
