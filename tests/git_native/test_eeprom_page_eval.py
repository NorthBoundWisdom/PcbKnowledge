"""Synthetic geometry and semantic regressions, not EEPROM hardware validation."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from configs import pcbknowledge_eeprom_page_eval as ee


class EepromPageTests(unittest.TestCase):
    def test_fixed_cases_and_full_source_payloads(self):
        report = ee.evaluate(ee.REPO_ROOT)
        self.assertEqual(report["evaluation_status"], "PASS")
        self.assertEqual(report["case_count"], 17)
        self.assertEqual(report, ee.evaluate(ee.REPO_ROOT))
        evidence = report["evidence"]
        original = json.loads((ee.REPO_ROOT / ee.BATCH).read_bytes())
        facts = {f["id"]: f for f in original["facts"]}
        issues = {i["id"]: i for i in original["source_issues"]}
        self.assertEqual(len(evidence["facts"]), 7)
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

    def test_requested_boundaries_have_literal_expected_plans(self):
        cases = {name: (inputs, expected) for name, inputs, expected in ee._scenarios()}
        for name, sizes in (("cross_page", [2, 2]), ("aligned_page", [64]),
                            ("three_chunks", [1, 64, 1]), ("last_byte", [1]), ("last_page", [64])):
            inputs, expected = cases[name]
            actual = ee._calculate(inputs)
            self.assertEqual(actual, expected)
            self.assertEqual([t["length"] for t in actual["transactions"]], sizes)
        refused = ee._calculate(ee._inputs(32767, 2))
        self.assertEqual(refused["outcome"], "NOT_EVALUABLE")
        self.assertEqual(refused["transactions"], [])
        self.assertIsNone(refused["address_roles"])

    def test_internal_geometry_grid_preserves_every_requested_byte_once(self):
        for page in (0, 1, 127, 510, 511):
            for offset in range(64):
                start = page * 64 + offset
                for length in (1, 2, 63, 64, 65, 127, 129):
                    result = ee._calculate(ee._inputs(start, length))
                    if start + length > 32768:
                        self.assertEqual(result["transactions"], [])
                        self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                        continue
                    covered = []
                    for transaction in result["transactions"]:
                        address, size = transaction["start"], transaction["length"]
                        self.assertGreater(size, 0)
                        self.assertLessEqual(size, 64)
                        self.assertEqual(address // 64, (address + size - 1) // 64)
                        self.assertEqual(transaction["data_offset"], len(covered))
                        self.assertEqual(transaction["word_address_bytes"], [address // 256, address % 256])
                        covered.extend(range(address, address + size))
                    self.assertEqual(covered, list(range(start, start + length)))
        self.assertEqual([t["length"] for t in ee._calculate(ee._inputs(62, 66))["transactions"]], [2, 64])

    def test_strict_validation_rejects_without_truncation_or_aliasing(self):
        for key in ("start", "length"):
            for value in (None, True, False, -1, 1.0, "1", [], {}, float("nan"), 10**100):
                with self.subTest(key=key, value=value):
                    result = ee._calculate({**ee._inputs(), key: value})
                    self.assertEqual(result["outcome"], "NOT_EVALUABLE")
                    self.assertEqual(result["transactions"], [])
            inputs = ee._inputs()
            del inputs[key]
            self.assertEqual(ee._calculate(inputs)["reason"], "missing_or_extra_input")
        for start, length in ((32768, 1), (65535, 1), (0, 32769), (0, 0), (32704, 65)):
            self.assertEqual(ee._calculate(ee._inputs(start, length))["transactions"], [])
        for key in ee.IDENTITY:
            self.assertEqual(ee._calculate({**ee._inputs(), key: "other"})["outcome"], "NOT_EVALUABLE")
        self.assertEqual(ee._calculate({**ee._inputs(), "model": "sequential_read"})["outcome"], "NOT_EVALUABLE")
        self.assertEqual(ee._calculate({**ee._inputs(), "page_bytes": 128})["reason"], "missing_or_extra_input")
        self.assertEqual(ee._calculate(None)["reason"], "missing_or_extra_input")

    def test_address_roles_and_unknowns_never_invent_controller_acceptance(self):
        for bits in ([0, 0, 0], [0, 1, 1], [1, 0, 1], [1, 1, 1]):
            result = ee._calculate({**ee._inputs(0x1234, 2), "A2_A1_A0": bits})
            roles = result["address_roles"]
            target = 80 + bits[0] * 4 + bits[1] * 2 + bits[2]
            self.assertEqual(roles["seven_bit_target"], target)
            self.assertEqual(roles["write_control_byte"], target * 2)
            self.assertEqual(roles["read_control_byte"], target * 2 + 1)
            self.assertEqual(roles["controller_argument"], target)
            self.assertEqual(result["transactions"][0]["word_address_bytes"], [18, 52])
        for change in ({"A2_A1_A0": None}, {"controller_convention": None}):
            result = ee._calculate({**ee._inputs(), **change})
            self.assertIsNone(result["address_roles"]["controller_argument"])
            self.assertEqual(result["circuit_qualification"], "NOT_ESTABLISHED")
        for pins in ([], [0, 0], [0, 0, 0, 0], [True, 0, 0], [2, 0, 0], "000", [0.0, 0, 0]):
            self.assertEqual(ee._calculate({**ee._inputs(), "A2_A1_A0": pins})["outcome"], "NOT_EVALUABLE")
        for key in ("controller_convention", "WP_at_valid_Stop_window", "matching_write_poll_ACK"):
            self.assertEqual(ee._calculate({**ee._inputs(), key: "unsupported"})["outcome"], "NOT_EVALUABLE")

    def test_wrap_and_ACK_do_not_establish_programming(self):
        counterexample = ee._wrap_counterexample()
        self.assertEqual(counterexample["hypothetical_unsplit_addresses"], [62, 63, 0, 1])
        self.assertNotEqual(counterexample["hypothetical_unsplit_addresses"], counterexample["intended_addresses"])
        high = ee._calculate({**ee._inputs(), "WP_at_valid_Stop_window": "HIGH", "matching_write_poll_ACK": "READY"})
        self.assertEqual(high["programming"], "NO_PROGRAMMING_UNDER_VALID_WP_HIGH_ASSUMPTION")
        self.assertFalse(high["data_verified"])
        for wp in (None, "LOW"):
            result = ee._calculate({**ee._inputs(), "WP_at_valid_Stop_window": wp, "matching_write_poll_ACK": "READY"})
            self.assertEqual(result["programming"], "NOT_ESTABLISHED")
            for key in ("data_verified", "WP_timing_qualified", "supply_qualified", "persistence_qualified", "lifetime_qualified"):
                self.assertFalse(result[key])

    def test_inputs_and_fixture_oracles_are_independent(self):
        inputs = ee._inputs()
        old = copy.deepcopy(inputs)
        ee._calculate(inputs)
        self.assertEqual(inputs, old)
        cases = ee._scenarios()
        cases[0][1]["A2_A1_A0"][0] = 1
        cases[0][2]["address_roles"]["controller_argument"] = 999
        self.assertEqual(cases[1][1]["A2_A1_A0"], [0, 0, 0])
        self.assertEqual(cases[1][2]["address_roles"]["controller_argument"], 80)

    def test_complete_output_mutations_fail_literal_oracle(self):
        pristine = ee._calculate
        mutations = [
            (["transactions", 0, "length"], 4),
            (["transactions", 1, "start"], 0),
            (["transactions", 1, "data_offset"], 0),
            (["transactions", 1, "word_address_bytes"], [64, 0]),
            (["address_roles", "seven_bit_target"], 160),
            (["address_roles", "write_control_byte"], 161),
            (["address_roles", "controller_argument"], 160),
            (["address_roles", "word_address_order"], "LOW_BYTE_FIRST"),
            (["inter_transaction_requirement"], "ONE_STOP_AFTER_ALL_CHUNKS"),
            (["programming"], "PROGRAMMED"),
            (["data_verified"], True), (["WP_timing_qualified"], True),
            (["supply_qualified"], True), (["persistence_qualified"], True),
            (["lifetime_qualified"], True), (["circuit_qualification"], "ESTABLISHED"),
        ]
        for keys, value in mutations:
            def wrong(inputs):
                result = pristine(inputs)
                if inputs == ee._inputs():
                    node = result
                    for key in keys[:-1]:
                        node = node[key]
                    node[keys[-1]] = value
                return result
            with self.subTest(keys=keys), mock.patch.object(ee, "_calculate", side_effect=wrong):
                report = ee.evaluate(ee.REPO_ROOT)
                self.assertEqual(report["evaluation_status"], "FAIL")
                self.assertFalse(report["cases"][0]["passed"])
        with mock.patch.object(ee, "_wrap_counterexample", return_value={"hypothetical_unsplit_addresses": [62, 63, 64, 65]}):
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
            with self.assertRaises(ee.PageEvaluationError):
                ee.evaluate(root)
            path.unlink()
            with self.assertRaises(ee.PageEvaluationError):
                ee.evaluate(root)
        first = ee._evidence(ee.REPO_ROOT)
        second = copy.deepcopy(first)
        second["issues"] = []
        with mock.patch.object(ee, "_evidence", side_effect=[first, second]):
            with self.assertRaisesRegex(ee.PageEvaluationError, "changed during"):
                ee.evaluate(ee.REPO_ROOT)

    def test_actual_CLI_and_exit_status_contract(self):
        run = subprocess.run([sys.executable, str(ee.REPO_ROOT / "configs/pcbknowledge_eeprom_page_eval.py"),
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
