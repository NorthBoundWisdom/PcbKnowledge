"""Synthetic retrieval hazards; identifiers mimic queries, not verified devices."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import (
    INTAKE_FORMAT, IntakeError, search_intake, search_intake_issues,
)


def fixture() -> dict:
    sources = [
        {"id": "ti-lm1117-q", "manufacturer": "TI", "device": "LM1117",
         "scope": "Synthetic SOT-223 prose, not a structured package",
         "selection_reason": "recommended synthetic fixture"},
        {"id": "st-ld1117", "manufacturer": "ST", "device": "LD1117STR",
         "package": "SOT-223", "scope": "Not TI LM1117 rating"},
        {"id": "ti-sn74hc00-h", "manufacturer": "TI", "device": "SN74HC00"},
        {"id": "nexperia-74hc00", "manufacturer": "Nexperia", "device": "74HC00",
         "scope": "Not SN74HC00"},
        {"id": "microchip-mcp23017", "manufacturer": "Microchip", "device": "MCP23017"},
        {"id": "ti-tps62160", "manufacturer": "TI", "device": "TPS62160"},
    ]
    # These values are invented regression inputs, not electrical authority.
    facts = [
        {"id": "ti-stress", "source_id": "ti-lm1117-q", "kind": "absolute_maximum",
         "parameter": "VIN_to_GND", "value": 20},
        {"id": "ti-operating", "source_id": "ti-lm1117-q", "kind": "recommended_operating",
         "parameter": "VIN_to_GND", "value": [3, 15]},
        {"id": "ti-pin", "source_id": "ti-lm1117-q", "kind": "pin",
         "parameter": "VIN_to_GND", "value": "input"},
        {"id": "st-stress", "source_id": "st-ld1117", "kind": "absolute_maximum",
         "parameter": "input_voltage", "value": 15, "conditions": {"default": True}},
        {"id": "st-exception", "source_id": "st-ld1117", "kind": "absolute_maximum",
         "parameter": "input_voltage", "value": 18, "conditions": {"duration": "short synthetic pulse"}},
        {"id": "ti-temperature", "source_id": "ti-sn74hc00-h", "kind": "electrical",
         "parameter": "threshold", "value": 1, "conditions": {"temperature_C": [-40, 85]}},
        {"id": "nx-temperature", "source_id": "nexperia-74hc00", "kind": "electrical",
         "parameter": "threshold", "value": 2, "conditions": {"temperature_C": [-40, 125]}},
        {"id": "gpio-supply", "source_id": "microchip-mcp23017", "kind": "pin",
         "parameter": "supply", "value": "supply pins", "conditions": {"caveat": "see source warning"}},
        {"id": "tps-ground", "source_id": "ti-tps62160", "kind": "pin",
         "parameter": "grounds", "value": "PGND"},
        {"id": "tps-pg", "source_id": "ti-tps62160", "kind": "pin",
         "parameter": "PG", "value": "power good", "conditions": {"off_state": "device switched off"}},
    ]
    for source in sources:
        source.update(status="DRAFT", revision="synthetic-rev", url="https://example.invalid/fixture")
    for fact in facts:
        fact.update(status="DRAFT", evidence_level="TEXT_LOCATOR_ONLY",
                    evidence={"page": 1, "bbox": None})
    return {"format": INTAKE_FORMAT, "canonical": False,
            "acceptance_status": "PENDING_USER_REVIEW", "sources": sources, "facts": facts,
            "source_issues": [{"id": "MCP23017-AMBIGUITY", "source_id": "microchip-mcp23017",
                               "issue_status": "UNRESOLVED_SOURCE_WORDING",
                               "description": "Synthetic ambiguity between two supply/temperature descriptions.",
                               "action": "Retain unresolved; do not infer an envelope.",
                               "evidence": [{"page": 1}, {"page": 4}],
                               "reviewer": "synthetic-agent"}]}


class IntakeFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "knowledge" / "intake"
        self.directory.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.data = fixture()
        self.write()

    def write(self, data: dict | None = None, name: str = "synthetic.json") -> None:
        (self.directory / name).write_text(json.dumps(self.data if data is None else data), encoding="utf-8")

    def ids(self, query: str = "", **filters: str) -> list[str]:
        return [match["fact"]["id"] for match in search_intake(self.root, query, **filters)]

    def cli(self, *args: str) -> tuple[int, list]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--repo", str(self.root), "intake", *args])
        return result, json.loads(output.getvalue())

    def test_negative_mentions_remain_lexical_not_identity(self) -> None:
        self.assertEqual(self.ids("LM1117 absolute"), ["st-exception", "st-stress", "ti-stress"])
        self.assertEqual(self.ids("absolute", source_id="ti-lm1117-q"), ["ti-stress"])
        self.assertEqual(self.ids("LM1117 absolute", manufacturer="TI"), ["ti-stress"])
        self.assertEqual(self.ids("absolute", device="LM1117"), ["ti-stress"])
        self.assertEqual(self.ids(source_id="Not TI LM1117 rating"), [])
        self.assertEqual(self.ids(manufacturer="Synthetic SOT-223 prose, not a structured package"), [])
        self.assertEqual(self.ids(device="https://example.invalid/fixture"), [])

    def test_filter_only_and_lexical_plus_filters_are_conjunctive(self) -> None:
        filters = {"device": "LM1117", "kind": "recommended_operating", "parameter": "VIN_to_GND"}
        self.assertEqual(self.ids(**filters), ["ti-operating"])
        self.assertEqual(self.ids("recommended VIN", **filters), ["ti-operating"])
        self.assertEqual(self.ids("absolute", **filters), [])
        self.assertEqual(self.ids(manufacturer="ST", **filters), [])
        self.assertEqual(self.ids(device="LM358B"), [])

    def test_temperature_conditions_are_unchanged(self) -> None:
        self.assertEqual(self.ids("SN74HC00 temperature"), ["nx-temperature", "ti-temperature"])
        result = search_intake(self.root, "temperature", source_id="ti-sn74hc00-h")
        self.assertEqual([match["fact"]["id"] for match in result], ["ti-temperature"])
        original = next(fact for fact in self.data["facts"] if fact["id"] == "ti-temperature")
        self.assertEqual(result[0]["fact"], original)
        self.assertEqual(result[0]["fact"]["parameter"], "threshold")

    def test_package_missing_or_wrong_type_fails_closed_without_prose_fallback(self) -> None:
        self.assertEqual(self.ids(package="SOT-223"), ["st-exception", "st-stress"])
        self.assertEqual(self.ids(source_id="ti-lm1117-q", package="SOT-223"), [])
        for value in (None, ["SOT-223"], {"name": "SOT-223"}, 123):
            self.data["sources"][1]["package"] = value
            self.write()
            self.assertEqual(self.ids(package="SOT-223"), [])

    def test_exact_policy_preserves_punctuation_case_unicode_and_whitespace(self) -> None:
        source = self.data["sources"][0]
        for device in ("AB-12", "AB12", "AB-12TR", "ab-12", " AB-12", "ＡＢ-12", "A\u0301B-12"):
            source["device"] = device
            self.write()
            self.assertEqual(self.ids(device=device), ["ti-operating", "ti-pin", "ti-stress"])
            if device != "AB-12":
                self.assertEqual(self.ids(device="AB-12"), [])
        self.assertEqual(self.ids(device="ÁB-12"), [])

    def test_unknown_filters_and_empty_values_fail_instead_of_being_ignored(self) -> None:
        with self.assertRaises(TypeError):
            search_intake(self.root, unknown="LM1117")
        with self.assertRaises(TypeError):
            search_intake_issues(self.root, parameter="PG")
        for value in ("", "   ", [], 123):
            with self.assertRaises(IntakeError):
                search_intake(self.root, device=value)
        for command, option in (("search", "--unknown"), ("search", "--manu"),
                                ("issues", "--parameter"), ("issues", "--dev")):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(["--repo", str(self.root), "intake", command, option, "value"])
            self.assertEqual(raised.exception.code, 2)

    def test_conditional_values_and_provenance_are_not_collapsed_or_promoted(self) -> None:
        result = search_intake(self.root, device="LD1117STR", parameter="input_voltage")
        self.assertEqual([match["fact"]["value"] for match in result], [18, 15])
        for match in result:
            self.assertEqual(match["fact"], next(fact for fact in self.data["facts"] if fact["id"] == match["fact"]["id"]))
            self.assertEqual(match["source"], self.data["sources"][1])
            self.assertEqual(match["result_type"], "FACT_CANDIDATE")
            self.assertFalse(match["canonical"])
            self.assertEqual(match["acceptance_status"], "PENDING_USER_REVIEW")
            self.assertEqual(match["evidence_verification"], "NOT_LOCALLY_VERIFIED")

    def test_exact_pg_parameter_does_not_match_pgnd_or_other_serialized_fields(self) -> None:
        self.assertEqual(self.ids("TPS62160 PG"), ["tps-ground", "tps-pg"])
        result = search_intake(self.root, "TPS62160 PG", parameter="PG")
        self.assertEqual([match["fact"]["id"] for match in result], ["tps-pg"])
        self.assertEqual(result[0]["fact"]["conditions"], {"off_state": "device switched off"})
        self.assertEqual(self.ids(parameter="PGND"), [])
        self.assertEqual(self.ids(parameter="pg"), [])

    def test_source_warning_inline_and_independent_route_preserve_full_warning(self) -> None:
        self.assertEqual(self.ids("MCP23017 AMBIGUITY"), [])
        facts = search_intake(self.root, "MCP23017 supply")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["source_issues"], self.data["source_issues"])
        warnings = search_intake_issues(self.root, "MCP23017 AMBIGUITY")
        self.assertEqual(len(warnings), 1)
        warning = warnings[0]
        self.assertEqual(warning["source_issue"], self.data["source_issues"][0])
        self.assertEqual(warning["result_type"], "SOURCE_ISSUE")
        self.assertNotIn("fact", warning)
        self.assertFalse(warning["canonical"])
        self.assertEqual(warning["evidence_verification"], "NOT_LOCALLY_VERIFIED")
        self.assertEqual(warning["path"], "knowledge/intake/synthetic.json")
        self.assertEqual(search_intake_issues(self.root, source_id="ti-lm1117-q"), [])
        self.assertTrue(all(not match["source_issues"] for match in search_intake(self.root, device="LM1117")))

    def test_warnings_remain_available_without_facts_and_do_not_leak_between_batches(self) -> None:
        other = copy.deepcopy(self.data)
        other["facts"] = []
        other["source_issues"][0]["description"] = "Other batch warning, same source ID"
        self.write(other, "other.json")
        warnings = search_intake_issues(self.root, source_id="microchip-mcp23017")
        self.assertEqual([match["path"] for match in warnings],
                         ["knowledge/intake/other.json", "knowledge/intake/synthetic.json"])
        result = search_intake(self.root, device="MCP23017")
        self.assertEqual(result[0]["source_issues"], self.data["source_issues"])
        self.assertEqual(len(result), 1)
        self.assertEqual(search_intake_issues(self.root, "not-present"), [])

    def test_warning_links_fail_closed_if_malformed_or_ambiguous(self) -> None:
        for issues in (None, {}, [123], [{"id": "x", "source_id": "unknown"}],
                       [{"id": "x", "source_id": "ti-lm1117-q"}] * 2):
            self.data["source_issues"] = issues
            self.write()
            for search in (search_intake, search_intake_issues):
                with self.assertRaises(IntakeError):
                    search(self.root)

    def test_stable_order_and_legacy_lexical_behavior(self) -> None:
        before = search_intake(self.root, "absolute")
        self.data["facts"].reverse()
        self.data["sources"].reverse()
        self.write()
        self.assertEqual(search_intake(self.root, "absolute"), before)
        self.assertEqual(self.ids("absolute"), ["st-exception", "st-stress", "ti-stress"])
        self.assertEqual(self.ids(), sorted(fact["id"] for fact in self.data["facts"]))

    def test_cli_filter_only_combined_and_warning_routes_are_read_only(self) -> None:
        path = self.directory / "synthetic.json"
        before = path.read_bytes()
        code, results = self.cli("search", "--device", "LM1117", "--kind", "recommended_operating",
                                 "--parameter", "VIN_to_GND")
        self.assertEqual(code, 0)
        self.assertEqual([result["fact"]["id"] for result in results], ["ti-operating"])
        code, results = self.cli("search", "absolute", "--source-id", "ti-lm1117-q", "--manufacturer", "TI")
        self.assertEqual(code, 0)
        self.assertEqual([result["fact"]["id"] for result in results], ["ti-stress"])
        code, results = self.cli("issues", "AMBIGUITY", "--device", "MCP23017")
        self.assertEqual(code, 0)
        self.assertEqual(results[0]["source_issue"], self.data["source_issues"][0])
        code, results = self.cli("issues", "--source-id", "microchip-mcp23017")
        self.assertEqual(code, 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
