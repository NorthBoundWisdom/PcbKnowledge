"""Synthetic semantic regressions for measurement, reference and timing candidates."""
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


class MeasurementTimingPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic-measurement-timing.json"
        path = self.root / self.relative
        path.parent.mkdir(parents=True)
        # Invented symbolic examples, not manufacturer specifications.
        facts = [
            {"id": "monitor", "kind": "register_semantics", "parameter": "measurement",
             "value": {"signed_shunt": True, "status_bits_are_voltage": False,
                       "current_requires_calibration": True, "ack_is_fresh": False,
                       "read_clear_sequence": "UNRESOLVED",
                       "prior_readiness_survives_reads": "UNKNOWN"},
             "conditions": {"grade": "SYNTH-A", "conversion_mode": "specified"}},
            {"id": "reference", "kind": "application_guidance", "parameter": "divider_stability",
             "value": {"reference_current_term": "retained", "curve_is_guarantee": False,
                       "equation_sign_conflict": "UNRESOLVED", "accuracy_guarantee": False},
             "conditions": {"capacitor": "unknown", "cathode_budget": "all_load_extremes",
                            "full_loop_stability": "UNKNOWN", "resistor_roles": "source_figure",
                            "reference_current_direction": "source_figure", "bias": "specified"}},
            {"id": "timer", "kind": "application_example", "parameter": "timing",
             "value": {"duty_convention": "source_low_time", "RC_is_guarantee": False},
             "conditions": {"trigger_released": True, "topology": "specified",
                            "startup": "UNKNOWN", "timing_test_supply": "specified"}},
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
                                   "missing_inputs": ["shunt", "load", "timing_components"], "answer": "UNKNOWN"}]}
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
            ("monitor", lambda item: item["fact"]["value"].update(signed_shunt=False)),
            ("monitor", lambda item: item["fact"]["value"].update(status_bits_are_voltage=True)),
            ("monitor", lambda item: item["fact"]["value"].update(current_requires_calibration=False)),
            ("monitor", lambda item: item["fact"]["value"].update(ack_is_fresh=True)),
            ("monitor", lambda item: item["fact"]["conditions"].update(grade="SYNTH-B")),
            ("monitor", lambda item: item["fact"]["value"].update(read_clear_sequence="GUARANTEED")),
            ("monitor", lambda item: item["fact"]["value"].update(prior_readiness_survives_reads=True)),
            ("monitor", lambda item: item.update(source_issues=[])),
            ("reference", lambda item: item["fact"]["value"].pop("reference_current_term")),
            ("reference", lambda item: item["fact"]["value"].update(curve_is_guarantee=True)),
            ("reference", lambda item: item["fact"]["conditions"].update(full_loop_stability="SAFE")),
            ("reference", lambda item: item["fact"]["conditions"].pop("cathode_budget")),
            ("reference", lambda item: item["fact"]["value"].pop("equation_sign_conflict")),
            ("reference", lambda item: item["fact"]["value"].update(accuracy_guarantee=True)),
            ("reference", lambda item: item["fact"]["conditions"].pop("resistor_roles")),
            ("reference", lambda item: item["fact"]["conditions"].pop("reference_current_direction")),
            ("reference", lambda item: item["fact"]["conditions"].pop("bias")),
            ("reference", lambda item: item.update(source_issues=[])),
            ("timer", lambda item: item["fact"]["value"].update(duty_convention="high_time")),
            ("timer", lambda item: item["fact"]["value"].update(RC_is_guarantee=True)),
            ("timer", lambda item: item["fact"]["conditions"].update(trigger_released=False)),
            ("timer", lambda item: item["fact"]["conditions"].update(startup="GUARANTEED")),
            ("timer", lambda item: item["fact"]["conditions"].pop("timing_test_supply")),
            ("timer", lambda item: item.update(source_issues=[])),
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


class MeasurementTimingManifestTests(unittest.TestCase):
    def test_successor_preserves_prior_cases_and_all_payloads(self) -> None:
        root = evaluation.REPO_ROOT
        old_path = root / "evals/intake-retrieval-signal-logic.json"
        old = json.loads(old_path.read_bytes())
        current = json.loads((root / "evals/intake-retrieval-measurement-timing-operational.json").read_bytes())
        evaluation.validate_manifest(current)
        self.assertEqual(current["cases"][:len(old["cases"])], old["cases"])
        self.assertEqual({path: current["files"][path] for path in old["files"]}, old["files"])
        self.assertEqual((len(current["files"]), len(current["cases"])), (16, 230))
        additions = current["cases"][len(old["cases"]):]
        selected = {ref for case in additions for ref in case["expected"]}
        for path in set(current["files"]) - set(old["files"]):
            payload = (root / path).read_bytes()
            data = json.loads(payload)
            self.assertEqual(current["files"][path], hashlib.sha256(payload).hexdigest())
            self.assertEqual(data["acceptance_status"], "AGENT_REVIEWED_UNDER_OWNER_DELEGATION")
            self.assertFalse(data["canonical"])
            self.assertFalse(data["human_reviewed"])
            for record in data["facts"] + data["source_issues"]:
                self.assertIn(path + "#" + record["id"], selected)
            for fact in data["facts"]:
                self.assertTrue(any(case["command"] == "search"
                    and case["filters"] == {"source_id": fact["source_id"], "parameter": fact["parameter"]}
                    and case["expected"] == [path + "#" + fact["id"]] for case in additions))
        self.assertEqual(sum(not case["expected"] for case in additions), 43)

    def test_operational_successor_changes_only_reviewed_ina_pin(self) -> None:
        root = evaluation.REPO_ROOT
        initial = json.loads((root / "evals/intake-retrieval-measurement-timing.json").read_bytes())
        current = json.loads((root / "evals/intake-retrieval-measurement-timing-operational.json").read_bytes())
        self.assertEqual(initial["cases"], current["cases"])
        changed = {path for path in initial["files"] if initial["files"][path] != current["files"][path]}
        self.assertEqual(changed, {"knowledge/intake/ina219-measurement-calibration-constraints.json"})
        self.assertEqual(set(initial["files"]), set(current["files"]))

    def test_historical_signal_logic_manifest_and_cli_selection_are_preserved(self) -> None:
        root = evaluation.REPO_ROOT
        self.assertEqual(hashlib.sha256((root / "evals/intake-retrieval-signal-logic.json").read_bytes()).hexdigest(),
                         "4985a7d23fdb42c91dfc31a6002d80501d605c1099dee5ca335399f1bf3fbe80")
        ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        replay_lines = [line for line in ci.splitlines() if "pcbknowledge_intake_eval.py" in line]
        self.assertEqual(len(replay_lines), 2)
        for line in replay_lines:
            self.assertIn("--cases evals/intake-retrieval-translation-loadswitch.json", line)
            self.assertIn("--dispositions evals/intake-dispositions-2026-10-28.json", line)
