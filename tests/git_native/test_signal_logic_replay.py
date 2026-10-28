"""Signal/logic manifest contracts and invented semantic-corruption probes."""
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


class SignalLogicManifestTests(unittest.TestCase):
    def test_successor_preserves_all_prior_cases_pins_and_dispositions(self) -> None:
        root = evaluation.REPO_ROOT
        old = json.loads((root / "evals/intake-retrieval-network-memory-power.json").read_bytes())
        current = json.loads((root / "evals/intake-retrieval-signal-logic.json").read_bytes())
        evaluation.validate_manifest(current)
        self.assertEqual(current["cases"][:len(old["cases"])], old["cases"])
        self.assertEqual({path: current["files"][path] for path in old["files"]}, old["files"])
        self.assertEqual((len(current["files"]), len(current["cases"])), (13, 159))
        # This historical supplement and all three earlier manifests are immutable.
        historical = {
            "intake-retrieval-100.json": "d4a166b49de4f421a0e08fae2eb636d43a500e515ca1b2db8c9c6f36d9c934b4",
            "intake-retrieval-125.json": "371c4922c17931eeb87d792a294e2565588a85851a5225e690772774170c6f22",
            "intake-retrieval-network-memory-power.json": "335daafda35cb1be4e3675e829b2274ecb0b80f90e29667e874a84a817320dd6",
            "intake-dispositions-2026-10-28.json": "ce8007f9dbe35f07281ddd232d426b25003d31b38f54ee89e301775c93f48ce5",
        }
        for filename, digest in historical.items():
            self.assertEqual(hashlib.sha256((root / "evals" / filename).read_bytes()).hexdigest(), digest)

    def test_new_cases_cover_every_fact_and_warning_with_exact_payload_pins(self) -> None:
        root = evaluation.REPO_ROOT
        manifest = json.loads((root / "evals/intake-retrieval-signal-logic.json").read_bytes())
        additions = manifest["cases"][108:]
        self.assertEqual(len(additions), 51)
        selected = {ref for case in additions for ref in case["expected"]}
        for stem in ("mcp6002-signal-chain-constraints", "sn74hc00-input-output-constraints"):
            path = "knowledge/intake/" + stem + ".json"
            payload = (root / path).read_bytes()
            data = json.loads(payload)
            self.assertEqual(manifest["files"][path], hashlib.sha256(payload).hexdigest())
            self.assertEqual((len(data["sources"]), len(data["facts"]), len(data["source_issues"])), (1, 7, 3))
            self.assertEqual(data["acceptance_status"], "AGENT_REVIEWED_UNDER_OWNER_DELEGATION")
            self.assertFalse(data["canonical"])
            self.assertFalse(data["human_reviewed"])
            for record in data["facts"] + data["source_issues"]:
                self.assertIn(path + "#" + record["id"], selected)
            for fact in data["facts"]:
                self.assertTrue(any(
                    case["command"] == "search"
                    and case["filters"] == {"source_id": fact["source_id"], "parameter": fact["parameter"]}
                    and case["expected"] == [path + "#" + fact["id"]]
                    for case in additions))
        self.assertEqual(sum(not case["expected"] for case in additions), 32)
        self.assertEqual(sum(case["command"] == "issues" and bool(case["expected"]) for case in additions), 2)
        # Wrong identities cannot retrieve either a fact or an inherited warning.
        negative_issues = [case for case in additions if case["command"] == "issues" and not case["expected"]]
        self.assertEqual(len(negative_issues), 7)


class SyntheticSignalLogicPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = "knowledge/intake/synthetic-signal-logic.json"
        path = self.root / self.relative
        path.parent.mkdir(parents=True)
        # Entirely invented symbolic data, not extracted manufacturer specifications.
        facts = [
            {"id": "signal", "kind": "typical_characteristic", "parameter": "dynamic_response",
             "value": {"typical": 23, "guaranteed_minimum": None},
             "conditions": {"noise_gain": "specified", "universal_isolation": False}},
            {"id": "swing", "kind": "electrical_characteristic", "parameter": "saturation",
             "value": {"high_bound": "output_at_least_supply_minus_gap", "linear_rail_swing": False},
             "conditions": {"overdrive": "specified", "load": "specified"}},
            {"id": "input", "kind": "recommended_operating", "parameter": "input_edges",
             "value": {"edge_limit": "input_rise_and_fall", "interpolated_threshold": None},
             "conditions": {"input_type": "ordinary_CMOS", "supply_points": [3, 7]}},
            {"id": "current", "kind": "absolute_maximum", "parameter": "output_current",
             "value": {"stress_is_drive_permission": False, "all_outputs_entitled": False},
             "conditions": {"supply_ground_total": "separate_limit", "thermal_budget": "unknown"}},
            {"id": "layout", "kind": "application_guidance", "parameter": "bypass",
             "value": {"excluded_figure": "OTHER_PACKAGE", "pin_map": "selected_package_table"},
             "conditions": {"board_validated": False}},
        ]
        for fact in facts:
            fact.update(source_id="synthetic", status="DRAFT")
        data = {
            "format": "pcbknowledge-independent-intake-v1", "canonical": False, "acceptance_status": "DRAFT",
            "sources": [{"id": "synthetic", "manufacturer": "Invented", "device": "SYNTH-LOGIC",
                         "package": "SYNTH-PACKAGE", "full_orderable_mpn": None, "status": "DRAFT"}],
            "facts": facts,
            "source_issues": [
                {"id": "inputs", "source_id": "synthetic", "issue_status": "UNRESOLVED_APPLICATION_INPUTS",
                 "missing_inputs": ["source", "load", "board"], "answer": "UNKNOWN"},
                {"id": "figure", "source_id": "synthetic", "issue_status": "UNRESOLVED_SOURCE_SCOPE_MISMATCH",
                 "excluded_from_pin_mapping": True, "manufacturer_correction": False},
            ],
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        self.manifest = {
            "format": evaluation.FORMAT,
            "files": {self.relative: hashlib.sha256(path.read_bytes()).hexdigest()},
            "cases": [
                {"id": fact["id"], "command": "search", "query": "",
                 "filters": {"source_id": "synthetic", "parameter": fact["parameter"]},
                 "expected": [self.relative + "#" + fact["id"]]} for fact in facts
            ] + [{"id": "warnings", "command": "issues", "query": "",
                  "filters": {"source_id": "synthetic"},
                  "expected": [self.relative + "#figure", self.relative + "#inputs"]}],
        }

    def test_complete_payload_and_two_warning_kinds_replay(self) -> None:
        result = evaluation.evaluate(self.root, self.manifest)
        self.assertEqual((result["status"], result["fact_count"], result["case_count"]), ("PASS", 5, 6))

    def test_unchanged_ids_cannot_hide_signal_or_logic_semantic_corruption(self) -> None:
        mutations = [
            ("signal", lambda item: item["fact"]["value"].update(guaranteed_minimum=23)),
            ("signal", lambda item: item["fact"]["conditions"].update(universal_isolation=True)),
            ("signal", lambda item: item["source"].update(full_orderable_mpn="INVENTED-ORDERABLE")),
            ("swing", lambda item: item["fact"]["value"].update(high_bound="output_at_most_supply_minus_gap")),
            ("swing", lambda item: item["fact"]["value"].update(linear_rail_swing=True)),
            ("swing", lambda item: item["fact"]["conditions"].pop("load")),
            ("input", lambda item: item["fact"]["value"].update(edge_limit="output_propagation_delay")),
            ("input", lambda item: item["fact"]["value"].update(interpolated_threshold=5)),
            ("input", lambda item: item["fact"]["conditions"].update(input_type="Schmitt_trigger")),
            ("current", lambda item: item["fact"].update(kind="recommended_operating")),
            ("current", lambda item: item["fact"]["value"].update(stress_is_drive_permission=True)),
            ("current", lambda item: item["fact"]["value"].update(all_outputs_entitled=True)),
            ("layout", lambda item: item["fact"]["value"].update(pin_map="excluded_figure")),
            ("layout", lambda item: item["fact"]["conditions"].update(board_validated=True)),
            ("layout", lambda item: item.update(source_issues=[])),
            ("warnings", lambda item: item["source_issue"].update(excluded_from_pin_mapping=False)),
            ("warnings", lambda item: item["source_issue"].update(manufacturer_correction=True)),
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
                self.assertEqual(failed["actual"], next(
                    case["expected"] for case in self.manifest["cases"] if case["id"] == target))
