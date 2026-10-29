"""Invented fuse metadata test preservation, not protection coordination."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticFuseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic-fuse.json"
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        # Every identity, number and test condition here is invented.
        values = {
            "identity": {"orderable": "SYNTH-FUSE-317", "package": "SYNTH-CHIP",
                "resettable": False, "response": "slow_blow"},
            "ratings": {"rated_current_a": 0.37, "rated_voltage_vdc": 31,
                "interrupt_current_a": 47, "interrupt_test_voltage_vdc": 31,
                "ambient_c": 23},
            "resistance": {"cold_typical_ohm": 0.83, "stated_tolerance_percent": 17, "ambient_c": 23,
                "measurement_current_fraction_of_rating": 0.07,
                "hot_resistance_ohm": None},
            "clearing": {"current_multiple": 2.7, "minimum_s": 0.07,
                "maximum_s": 31, "ambient_c": 23, "arbitrary_fault_time_s": None},
            "reliability": {"test_scope": "separate reliability fusing test",
                "test_current_multiple": 1.9, "test_maximum_seconds": 7,
                "ambient_c": None, "arbitrary_fault_time_s": None},
            "energy": {"melting_i2t_typical_a2s": 0.041, "calculation_current_multiple": 9, "total_clearing_i2t_a2s": None,
                "guaranteed_maximum_i2t_a2s": None},
            "curve": {"scope": "qualitative typical curves",
                "digitized_guaranteed_envelope": None, "protected_device_safe": None},
        }
        self.data = {"format": "pcbknowledge-independent-intake-v1",
            "canonical": False, "acceptance_status": "DRAFT",
            "sources": [{"id": "synthetic", "manufacturer": "Synthetic",
                "device": "SYNTH-FUSE-317", "package": "SYNTH-CHIP",
                "revision": "Synthetic R2", "status": "DRAFT"}],
            "facts": [{"id": key, "source_id": "synthetic", "parameter": key,
                "kind": "identity" if key == "identity" else "electrical_characteristic",
                "value": value, "status": "DRAFT"} for key, value in values.items()],
            "source_issues": [
                {"id": "coordination-warning", "source_id": "synthetic",
                    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                    "missing": ["prospective fault current", "fault waveform", "protected device limits"],
                    "value": {"system_protection_qualified": False}},
                {"id": "thermal-warning", "source_id": "synthetic",
                    "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                    "missing": ["ambient profile", "PCB mounting", "inrush history"]},
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
            ("identity", ["fact", "value", "resettable"], True),
            ("identity", ["fact", "value", "response"], "fast_blow"),
            ("identity", ["source", "revision"], "Synthetic R3"),
            ("ratings", ["fact", "value", "rated_current_a"], 47),
            ("ratings", ["fact", "value", "rated_voltage_vdc"], None),
            ("ratings", ["fact", "value", "interrupt_test_voltage_vdc"], None),
            ("ratings", ["fact", "value", "ambient_c"], None),
            ("resistance", ["fact", "value", "measurement_current_fraction_of_rating"], None),
            ("resistance", ["fact", "value", "ambient_c"], None),
            ("resistance", ["fact", "value", "hot_resistance_ohm"], 0.83),
            ("clearing", ["fact", "value", "current_multiple"], None),
            ("clearing", ["fact", "value", "minimum_s"], 31),
            ("clearing", ["fact", "value", "arbitrary_fault_time_s"], 31),
            ("reliability", ["fact", "value", "test_scope"], "clearing guarantee"),
            ("reliability", ["fact", "value", "arbitrary_fault_time_s"], 7),
            ("reliability", ["fact", "value", "test_current_multiple"], 2.7),
            ("reliability", ["fact", "value", "ambient_c"], 23),
            ("energy", ["fact", "value", "calculation_current_multiple"], None),
            ("resistance", ["fact", "value", "stated_tolerance_percent"], 0),
            ("energy", ["fact", "value", "total_clearing_i2t_a2s"], 0.041),
            ("energy", ["fact", "value", "guaranteed_maximum_i2t_a2s"], 0.041),
            ("curve", ["fact", "value", "digitized_guaranteed_envelope"], [0, 31]),
            ("curve", ["fact", "value", "protected_device_safe"], True),
            ("clearing", ["source_issues"], []),
            ("ratings", ["canonical"], True),
            ("ratings", ["evidence_verification"], "VERIFIED"),
            ("thermal-warning", ["source_issue", "missing"], []),
            ("coordination-warning", ["source_issue", "value", "system_protection_qualified"], True),
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
            ("search", {"device": "SYNTH-FUSE-OTHER"}),
            ("issues", {"package": "SYNTH-OTHER-CHIP"}),
            ("search", {"manufacturer": "Other Synthetic Supplier"}),
            ("search", {"parameter": "guaranteed_total_clearing_i2t"}),
            ("search", {"parameter": "guaranteed_arbitrary_fault_time"}),
        ]
        for index, (command, filters) in enumerate(negatives):
            case = {"id": "negative-" + str(index), "command": command, "query": "",
                "filters": {"source_id": "synthetic", **filters}, "expected": []}
            with self.subTest(command=command, filters=filters):
                self.assertEqual(evaluation.run_cli(self.root, case), [])
                self.assertEqual(evaluation.evaluate(self.root,
                    {**self.manifest, "cases": [case]})["status"], "PASS")
        # Empty selection does not establish protection or total clearing energy.
        self.assertIsNone(json.loads(self.baselines["energy"])[0]["fact"]["value"]
            ["total_clearing_i2t_a2s"])
        self.assertFalse(json.loads(self.baselines["coordination-warning"])[0]["source_issue"]
            ["value"]["system_protection_qualified"])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class FuseSuccessorTests(unittest.TestCase):
    def test_successor_preserves_history_and_accepted_source_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / "evals/intake-retrieval-ferrite.json"
        old = evaluation.load_manifest(base_path)
        self.assertEqual((len(old["cases"]), len(old["files"])), (780, 36))
        path = root / "evals/intake-retrieval-fuse.json"
        delta = json.loads(path.read_bytes())
        self.assertEqual(delta["format"], "pcbknowledge-intake-retrieval-delta-v1")
        self.assertEqual(delta["base"], {"path": base_path.name,
            "sha256": "ce6f2a96aa25da0fd3cbc775e39bd537b372b8fc95ee8e15db96bf00be33bea7"})
        self.assertEqual((len(delta["cases"]), len(delta["files"])), (15, 1))
        new = evaluation.load_manifest(path)
        evaluation.validate_manifest(new)
        self.assertEqual(new["cases"][:len(old["cases"])], old["cases"])
        self.assertEqual({name: new["files"][name] for name in old["files"]}, old["files"])
        relative = "knowledge/intake/sf1206s-fuse-constraints.json"
        self.assertEqual(set(new["files"]) - set(old["files"]), {relative})
        for suffix, digest in {
            ".json": "51516aa7067cd9e06867f423378aaeaae8e7363e446d48bfda040d7999eab3dc",
            "-review.md": "ad08b2ded07501f68e5d53f07e296ac2de8110bffabbb981fef78c8c77f8333b",
        }.items():
            pair = root / ("knowledge/intake/sf1206s-fuse-constraints" + suffix)
            self.assertEqual(hashlib.sha256(pair.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data["acceptance_status"], "AGENT_REVIEWED_UNDER_OWNER_DELEGATION")
        self.assertFalse(data["canonical"])
        self.assertFalse(data["human_reviewed"])
        self.assertEqual((len(data["facts"]), len(data["source_issues"])), (6, 3))
        self.assertEqual(new["files"][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new["cases"][len(old["cases"]):]
        self.assertEqual(len(additions), 15)
        self.assertEqual(sum(not case["expected"] for case in additions), 7)
        self.assertEqual({ref for case in additions for ref in case["expected"]},
            {relative + "#" + record["id"] for record in data["facts"] + data["source_issues"]})
        for fact in data["facts"]:
            self.assertTrue(any(case["command"] == "search" and case["query"] == ""
                and case["filters"] == {"source_id": fact["source_id"], "parameter": fact["parameter"]}
                and case["expected"] == [relative + "#" + fact["id"]] for case in additions))
        self.assertTrue(any(case["command"] == "issues" and not case["expected"]
            for case in additions))
