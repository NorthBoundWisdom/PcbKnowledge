"""Synthetic reset, interface and discrete-condition preservation checks.

Invented values and devices only. These checks detect changed retrieval payloads;
they neither validate manufacturer specifications nor reason about circuit safety.
"""
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


class ResetInterfaceSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = "knowledge/intake/synthetic-reset-interface.json"
        path = self.root / relative
        path.parent.mkdir(parents=True)
        source = {"id": "synthetic", "device": "SYNTH-X", "manufacturer": "Synthetic",
                  "package": "SYNTH-PKG", "status": "DRAFT"}
        specifications = {
            "reset": {
                "kind": "functional_description",
                "value": {"nominal_rail": 7, "trip_point": 6,
                          "delay_typical": 13, "delay_guaranteed": None},
                "conditions": {"threshold_variant": "SYNTH-FIXED", "ct_mode": "external",
                               "mr_release_required": True, "sense_recovery_required": True,
                               "output_valid_supply_minimum": 3,
                               "pull_up_domain": "receiver-checked-domain",
                               "receiver_thresholds": "unknown"}},
            "interface": {
                "kind": "conditional_interface_characteristic",
                "value": {"common_mode": [-2, 8], "stress": [-9, 19],
                          "enable_maximum": 11, "propagation_maximum": 5,
                          "system_esd_certified": False},
                "conditions": {"failsafe": ["open-input", "bounded-differential"],
                               "termination": "line-end-and-load-dependent",
                               "timing_row": "SYNTH-X-only", "load_capacitance": 17,
                               "measurement_threshold": "defined-test-crossing",
                               "standby_wake_is_distinct": True}},
            "mosfet": {
                "kind": "electrical_characteristic",
                "value": {"threshold_test_current_uA": 17, "full_on_proven": False},
                "conditions": {"thermal_duration": "short-test-only",
                               "gate_drive": "selected-load-dependent"}},
            "rectifier": {
                "kind": "electrical_characteristic",
                "value": {"surge_is_repetitive": False, "continuous_current": 3},
                "conditions": {"rating_temperature_kind": "lead", "lead_temperature": 41,
                               "surge_waveform": "single-half-wave", "surge_duration": 7,
                               "forward_voltage_test": "pulsed", "pulse_width": 19,
                               "pulse_duty_maximum": 2}},
        }
        facts = [{"id": name, "source_id": "synthetic", "status": "DRAFT",
                  "parameter": name, **specification}
                 for name, specification in specifications.items()]
        data = {"format": "pcbknowledge-independent-intake-v1", "canonical": False,
                "acceptance_status": "DRAFT", "sources": [source], "facts": facts,
                "source_issues": [{"id": "application-unknown", "source_id": "synthetic",
                                   "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                                   "answer": "UNKNOWN",
                                   "missing_inputs": ["receiver", "load", "board", "transients"]}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        cases = [{"id": name, "command": "search", "query": "",
                  "filters": {"source_id": "synthetic", "parameter": name},
                  "expected": [relative + "#" + name]} for name in specifications]
        cases.append({"id": "warnings", "command": "issues", "query": "",
                      "filters": {"source_id": "synthetic"},
                      "expected": [relative + "#application-unknown"]})
        self.manifest = {"format": evaluation.FORMAT,
                         "files": {relative: hashlib.sha256(path.read_bytes()).hexdigest()},
                         "cases": cases}
        # Actual CLI outputs are captured once, then independently corrupted.
        self.outputs = {case["id"]: evaluation.run_cli(self.root, case) for case in cases}

    def assert_mutations_rejected(self, target, mutations) -> None:
        for label, mutate in mutations:
            with self.subTest(target=target, mutation=label):
                def runner(root, case):
                    items = copy.deepcopy(self.outputs[case["id"]])
                    if case["id"] == target:
                        mutate(items[0])
                    return items

                report = evaluation.evaluate(self.root, self.manifest, runner=runner)
                self.assertEqual(report["status"], "FAIL")
                failed = next(case for case in report["cases"] if case["id"] == target)
                self.assertFalse(failed["passed"])
                expected = next(case["expected"] for case in self.manifest["cases"]
                                if case["id"] == target)
                # Rejection must concern semantics, not changed candidate identity/count.
                self.assertEqual(failed["actual"], expected)

    def test_complete_synthetic_payloads_replay_without_safety_or_verification_upgrade(self) -> None:
        report = evaluation.evaluate(self.root, self.manifest)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual((report["fact_count"], report["case_count"]), (4, 5))
        for items in self.outputs.values():
            for item in items:
                self.assertIs(item["canonical"], False)
                self.assertEqual(item["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertEqual(self.outputs["warnings"][0]["source_issue"]["answer"], "UNKNOWN")

    def test_reset_qualifiers_cannot_change_with_same_candidate(self) -> None:
        self.assert_mutations_rejected("reset", [
            ("wrong_threshold", lambda x: x["fact"]["conditions"].update(threshold_variant="other")),
            ("wrong_package", lambda x: x["source"].update(package="OTHER-PKG")),
            ("nominal_is_trip", lambda x: x["fact"]["value"].update(trip_point=7)),
            ("typical_delay_guarantee", lambda x: x["fact"]["value"].update(delay_guaranteed=13)),
            ("ct_mode_confusion", lambda x: x["fact"]["conditions"].update(ct_mode="fixed")),
            ("omit_mr_release", lambda x: x["fact"]["conditions"].pop("mr_release_required")),
            ("omit_sense_recovery", lambda x: x["fact"]["conditions"].pop("sense_recovery_required")),
            ("invalid_low_supply", lambda x: x["fact"]["conditions"].update(output_valid_supply_minimum=0)),
            ("omit_pull_up_domain", lambda x: x["fact"]["conditions"].pop("pull_up_domain")),
            ("assume_receiver", lambda x: x["fact"]["conditions"].update(receiver_thresholds="compatible")),
        ])

    def test_interface_conditions_cannot_become_universal_bus_qualification(self) -> None:
        self.assert_mutations_rejected("interface", [
            ("common_mode_from_stress", lambda x: x["fact"]["value"].update(common_mode=[-9, 19])),
            ("missing_failsafe", lambda x: x["fact"]["conditions"].pop("failsafe")),
            ("universal_termination", lambda x: x["fact"]["conditions"].update(termination="all-buses")),
            ("other_timing_row", lambda x: x["fact"]["conditions"].update(timing_row="SYNTH-Y")),
            ("omit_load", lambda x: x["fact"]["conditions"].pop("load_capacitance")),
            ("omit_crossing", lambda x: x["fact"]["conditions"].pop("measurement_threshold")),
            ("enable_equals_propagation", lambda x: x["fact"]["value"].update(enable_maximum=5)),
            ("ignore_standby_wake", lambda x: x["fact"]["conditions"].update(standby_wake_is_distinct=False)),
            ("esd_system_certification", lambda x: x["fact"]["value"].update(system_esd_certified=True)),
        ])

    def test_discrete_conditions_and_unknowns_cannot_be_promoted(self) -> None:
        self.assert_mutations_rejected("mosfet", [
            ("threshold_is_full_on", lambda x: x["fact"]["value"].update(full_on_proven=True)),
            ("erase_threshold_current", lambda x: x["fact"]["value"].pop("threshold_test_current_uA")),
            ("short_is_steady_state", lambda x: x["fact"]["conditions"].update(thermal_duration="continuous")),
            ("universal_gate_drive", lambda x: x["fact"]["conditions"].update(gate_drive="any-controller")),
        ])
        self.assert_mutations_rejected("rectifier", [
            ("lead_is_ambient", lambda x: x["fact"]["conditions"].update(rating_temperature_kind="ambient")),
            ("omit_rating_temperature", lambda x: x["fact"]["conditions"].pop("lead_temperature")),
            ("surge_repetition", lambda x: x["fact"]["value"].update(surge_is_repetitive=True)),
            ("omit_waveform", lambda x: x["fact"]["conditions"].pop("surge_waveform")),
            ("omit_surge_duration", lambda x: x["fact"]["conditions"].pop("surge_duration")),
            ("pulsed_is_continuous", lambda x: x["fact"]["conditions"].update(forward_voltage_test="continuous")),
            ("omit_pulse_width", lambda x: x["fact"]["conditions"].pop("pulse_width")),
            ("omit_pulse_duty", lambda x: x["fact"]["conditions"].pop("pulse_duty_maximum")),
        ])
        self.assert_mutations_rejected("warnings", [
            ("unknown_is_safe", lambda x: x["source_issue"].update(answer="SAFE")),
            ("drop_missing_inputs", lambda x: x["source_issue"].update(missing_inputs=[])),
        ])


if __name__ == "__main__":
    unittest.main()
