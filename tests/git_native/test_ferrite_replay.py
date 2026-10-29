"""Invented ferrite metadata test preservation, not filter performance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticFerriteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic-ferrite.json"
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        # Every identity, number and test condition here is invented.
        values = {
            "identity": {"orderable": "SYNTH-BEAD-517", "package": "SYNTH-CHIP"},
            "impedance": {"nominal_ohm": 517, "tolerance_percent": 17,
                "frequency_hz": 83000000, "test_signal_v": 0.037,
                "ambient_c": 24, "dc_bias_a": None, "signal_amplitude_convention": None},
            "resistance": {"maximum_dc_ohm": 0.073,
                "hot_resistance_ohm": None},
            "current": {"rated_a": 1.83, "rating_basis_rise_c": 31,
                "hot_ambient_current_a": None, "fixture_and_airflow": None},
            "curve": {"components": ["Z", "R", "X"],
                "scope": "qualitative frequency-dependent plot", "min_typ_max_classification": None,
                "guaranteed_biased_curve": None, "installed_attenuation_db": None},
        }
        self.data = {"format": "pcbknowledge-independent-intake-v1",
            "canonical": False, "acceptance_status": "DRAFT",
            "sources": [{"id": "synthetic", "manufacturer": "Synthetic",
                "device": "SYNTH-BEAD-517", "package": "SYNTH-CHIP",
                "revision": "Synthetic R2", "status": "DRAFT"}],
            "facts": [{"id": key, "source_id": "synthetic", "parameter": key,
                "kind": "identity" if key == "identity" else "electrical_characteristic",
                "value": value, "status": "DRAFT"} for key, value in values.items()],
            "source_issues": [
                {"id": "thermal-warning", "source_id": "synthetic",
                    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                    "missing": ["board temperature", "current waveform", "mounting"]},
                {"id": "filter-warning", "source_id": "synthetic",
                    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                    "missing": ["source impedance", "load impedance", "noise spectrum"],
                    "value": {"rail_qualified": False, "guaranteed_attenuation_db": None}},
            ]}
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        self.original_bytes = self.path.read_bytes()
        cases = [{"id": key, "command": "search", "query": "",
            "filters": {"source_id": "synthetic", "parameter": key},
            "expected": [self.relative + "#" + key]} for key in values]
        cases += [{"id": issue["id"], "command": "issues", "query": issue["id"],
            "filters": {"source_id": "synthetic"},
            "expected": [self.relative + "#" + issue["id"]]}
            for issue in self.data["source_issues"]]
        self.manifest = {"format": evaluation.FORMAT,
            "files": {self.relative: hashlib.sha256(self.original_bytes).hexdigest()},
            "cases": cases}
        # Obtain real CLI responses once; no mutation may change the baseline.
        self.baselines = {case["id"]: json.dumps(evaluation.run_cli(self.root, case),
            sort_keys=True) for case in cases}

    def test_full_payload_preserves_separate_conditions_and_warnings(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)["status"], "PASS")
        for fact in self.data["facts"]:
            item = json.loads(self.baselines[fact["id"]])[0]
            self.assertEqual(item["fact"], fact)
            self.assertEqual(item["source"], self.data["sources"][0])
            self.assertEqual(item["source_issues"], sorted(self.data["source_issues"], key=lambda x: x["id"]))
            self.assertFalse(item["canonical"])
            self.assertEqual(item["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_same_ids_do_not_hide_condition_loss_or_claim_promotion(self):
        mutations = [
            ("identity", ["fact", "value", "orderable"], "SYNTH-BEAD-OTHER"),
            ("identity", ["source", "revision"], "Synthetic R3"),
            ("impedance", ["fact", "value", "frequency_hz"], 0),
            ("impedance", ["fact", "value", "test_signal_v"], None),
            ("impedance", ["fact", "value", "signal_amplitude_convention"], "RMS"),
            ("impedance", ["fact", "value", "ambient_c"], None),
            ("impedance", ["fact", "value", "tolerance_percent"], 0),
            ("impedance", ["fact", "value", "dc_bias_a"], 1.83),
            ("resistance", ["fact", "value", "maximum_dc_ohm"], 517),
            ("resistance", ["fact", "value", "hot_resistance_ohm"], 0.073),
            ("current", ["fact", "value", "rating_basis_rise_c"], None),
            ("current", ["fact", "value", "hot_ambient_current_a"], 1.83),
            ("current", ["fact", "value", "fixture_and_airflow"], "any PCB"),
            ("curve", ["fact", "value", "components"], ["DC resistance"]),
            ("curve", ["fact", "value", "scope"], "guaranteed flat impedance"),
            ("curve", ["fact", "value", "guaranteed_biased_curve"], True),
            ("curve", ["fact", "value", "min_typ_max_classification"], "typical"),
            ("curve", ["fact", "value", "installed_attenuation_db"], 20),
            ("current", ["source_issues"], []),
            ("impedance", ["canonical"], True),
            ("impedance", ["evidence_verification"], "VERIFIED"),
            ("thermal-warning", ["source_issue", "missing"], []),
            ("filter-warning", ["source_issue", "missing"], []),
            ("filter-warning", ["source_issue", "value", "rail_qualified"], True),
            ("filter-warning", ["source_issue", "value", "guaranteed_attenuation_db"], 20),
        ]
        for target, keys, value in mutations:
            with self.subTest(target=target, keys=keys):
                def runner(root, case):
                    items = json.loads(self.baselines[case["id"]])
                    if case["id"] == target:
                        node = items[0]
                        for key in keys[:-1]:
                            node = node[key]
                        node[keys[-1]] = value
                    return items
                report = evaluation.evaluate(self.root, self.manifest, runner=runner)
                self.assertEqual(report["status"], "FAIL")
                failed = next(case for case in report["cases"] if case["id"] == target)
                self.assertFalse(failed["passed"])
                # The ID still matches: the failure must depend on full metadata.
                expected = next(case["expected"] for case in self.manifest["cases"]
                    if case["id"] == target)
                self.assertEqual(failed["actual"], expected)
                self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.assertEqual(evaluation.evaluate(self.root, self.manifest,
            runner=lambda root, case: json.loads(self.baselines[case["id"]]))["status"], "PASS")

    def test_wrong_scope_and_unavailable_guarantees_return_no_candidates(self):
        negatives = [
            ("search", {"device": "SYNTH-BEAD-OTHER"}),
            ("issues", {"package": "SYNTH-OTHER-CHIP"}),
            ("search", {"manufacturer": "Other Synthetic Supplier"}),
            ("search", {"parameter": "guaranteed_installed_attenuation"}),
            ("search", {"parameter": "hot_ambient_current_guarantee"}),
        ]
        for index, (command, filters) in enumerate(negatives):
            case = {"id": "negative-" + str(index), "command": command, "query": "",
                "filters": {"source_id": "synthetic", **filters}, "expected": []}
            with self.subTest(command=command, filters=filters):
                self.assertEqual(evaluation.run_cli(self.root, case), [])
                self.assertEqual(evaluation.evaluate(self.root,
                    {**self.manifest, "cases": [case]})["status"], "PASS")
        # Empty selection is not an attenuation, hot-current or rail qualification.
        self.assertIsNone(json.loads(self.baselines["curve"])[0]["fact"]["value"]
            ["installed_attenuation_db"])
        self.assertFalse(json.loads(self.baselines["filter-warning"])[0]["source_issue"]
            ["value"]["rail_qualified"])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class FerriteSuccessorTests(unittest.TestCase):
    def test_small_successor_preserves_history_and_accepted_source_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / "evals/intake-retrieval-photodiode.json"
        old = evaluation.load_manifest(base_path)
        self.assertEqual((len(old["cases"]), len(old["files"])), (764, 35))
        path = root / "evals/intake-retrieval-ferrite.json"
        delta = json.loads(path.read_bytes())
        self.assertEqual(delta["format"], "pcbknowledge-intake-retrieval-delta-v1")
        self.assertEqual(delta["base"], {"path": base_path.name,
            "sha256": "2aabda45b880b5bf9d5ee91e9e80b0934591191a9e362e2428eb2abaa67fc757"})
        self.assertEqual((len(delta["cases"]), len(delta["files"])), (16, 1))
        new = evaluation.load_manifest(path)
        evaluation.validate_manifest(new)
        self.assertEqual(new["cases"][:len(old["cases"])], old["cases"])
        self.assertEqual({name: new["files"][name] for name in old["files"]}, old["files"])
        relative = "knowledge/intake/mh2029-ferrite-constraints.json"
        self.assertEqual(set(new["files"]) - set(old["files"]), {relative})
        for suffix, digest in {
            ".json": "775888fa8e72583c65aa350d63ded06002a7142246db64ff92d976f7c936137b",
            "-review.md": "a20de997d72729e5818e9c0a4c6bb5041c63c2ba07aefb9cacca9ca930709031",
        }.items():
            pair_path = root / ("knowledge/intake/mh2029-ferrite-constraints" + suffix)
            self.assertEqual(hashlib.sha256(pair_path.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data["acceptance_status"], "AGENT_REVIEWED_UNDER_OWNER_DELEGATION")
        self.assertFalse(data["canonical"])
        self.assertFalse(data["human_reviewed"])
        self.assertEqual((len(data["facts"]), len(data["source_issues"])), (5, 3))
        self.assertEqual(new["files"][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new["cases"][len(old["cases"]):]
        self.assertEqual(len(additions), 16)
        self.assertEqual(sum(not case["expected"] for case in additions), 9)
        self.assertEqual({ref for case in additions for ref in case["expected"]},
            {relative + "#" + record["id"] for record in data["facts"] + data["source_issues"]})
        for fact in data["facts"]:
            self.assertTrue(any(case["command"] == "search" and case["query"] == ""
                and case["filters"] == {"source_id": fact["source_id"], "parameter": fact["parameter"]}
                and case["expected"] == [relative + "#" + fact["id"]] for case in additions))
        self.assertTrue(any(case["command"] == "issues" and not case["expected"]
            for case in additions))
