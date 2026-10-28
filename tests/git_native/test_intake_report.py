"""Synthetic scoped report tests; metadata is never electrical authority."""
from __future__ import annotations

import contextlib
import copy
import html
import io
import json
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from configs import pcbknowledge_agent
from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError
from pcbknowledge.git_native.intake_report import _text, intake_report
from pcbknowledge.git_native.store import KnowledgeRepository
from pcbknowledge.git_native.workspace import initialize_workspace
from tests.git_native.test_intake_dispositions import synthetic_batch, synthetic_disposition


ENTRYPOINTS = (main, pcbknowledge_agent.main)


def fixture() -> dict:
    data = synthetic_batch()
    data["sources"][0]["manufacturer"] = "Synthetic Maker"
    data["facts"][0].update(kind="synthetic_limit", unit="V", conditions="Only for invented load < 2; not a design limit.",
                             evidence={"revision": "SYNTH-R", "printed_page": "A-1", "pdf_page_index": 0,
                                       "visual_checked": False, "visual_page_review": True, "bbox": None})
    data["limitations"] = ["Synthetic fixture only; no component recommendation."]
    data["review_history"] = [{"actor_id": "agent:synthetic", "decision": "DRAFT_COLLECTED"}]
    return data


class IntakeReportTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def write(self, data: dict | None = None, name: str = "synthetic.json") -> Path:
        path = self.root / "knowledge/intake" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fixture() if data is None else data), encoding="utf-8")
        return path

    def tree(self) -> dict:
        return {path.relative_to(self.root).as_posix():
                (stat.S_IMODE(path.stat().st_mode), path.stat().st_mtime_ns,
                 None if path.is_dir() else path.read_bytes())
                for path in (self.root, *self.root.rglob("*"))}

    def invoke(self, entrypoint, *arguments: str) -> tuple[int, str, str]:
        before = self.tree()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = entrypoint(["--repo", str(self.root), "intake", "report", *arguments])
        self.assertEqual(self.tree(), before)
        return result, stdout.getvalue(), stderr.getvalue()

    def assert_metadata(self, report: str, value) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                self.assertIn(_text(key), report)
                self.assert_metadata(report, item)
        elif isinstance(value, list):
            for item in value:
                self.assert_metadata(report, item)
        else:
            self.assertIn(_text(value), report)

    def test_requires_source_or_device_not_just_broad_filters(self) -> None:
        for filters in ({}, {"manufacturer": "Synthetic Maker"}, {"package": "SYNTH-P"}):
            with self.subTest(filters=filters), self.assertRaisesRegex(IntakeError, "requires --source-id or --device"):
                intake_report(self.root, **filters)
        for filters in ({"source_id": ""}, {"device": " "}, {"source_id": 2},
                        {"device": "SYNTH-A", "manufacturer": ""}):
            with self.subTest(filters=filters), self.assertRaisesRegex(IntakeError, "nonempty string"):
                intake_report(self.root, **filters)

    def test_exact_intersection_filters_do_not_infer_identity_from_prose(self) -> None:
        data = fixture()
        data["sources"][1]["description"] = "Synthetic Maker SYNTH-A SYNTH-P"
        self.write(data)
        correct = {"source_id": "source-a", "manufacturer": "Synthetic Maker", "device": "SYNTH-A", "package": "SYNTH-P"}
        report = intake_report(self.root, **correct)
        self.assertIn('"pin-a"', report)
        self.assertNotIn('"pin-b"', report)
        for field, values in {"source_id": ("SOURCE-A", "source-a "),
                              "manufacturer": ("synthetic maker", "Synthetic Maker "),
                              "device": ("synth-a", "SYNTH-A ", "SYNTH-\u212a"),
                              "package": ("synth-p", "SYNTH-P ")}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    changed = {**correct, field: value}
                    self.assertIn("No matching recorded source", intake_report(self.root, **changed))
        data["sources"][0]["device"] = ["SYNTH-A"]
        self.write(data)
        self.assertIn("No matching recorded source", intake_report(self.root, device="SYNTH-A"))

    def test_full_conditions_citations_units_flags_and_unknown_metadata_preserved(self) -> None:
        data = fixture()
        data["facts"][0]["conditions"] = "First condition; " + "all constraints must remain. " * 120 + "FINAL CONDITION"
        data["facts"][0]["value"] = {"min": -1.25, "max": None, "literal": "null", "array": [True, False, {}, []]}
        data["facts"][0]["additional_evidence"] = [{"printed_page": 2, "pdf_page_index": 1, "section": "Invented footnote"}]
        data["facts"][0]["custom_field"] = {"nested": {"unrecognized": [None, 3, "3"]}}
        self.write(data)
        report = intake_report(self.root, source_id="source-a")
        for value in (data["sources"][0], data["facts"][0], data["source_issues"][0], data["review_history"], data["limitations"]):
            self.assert_metadata(report, value)
        self.assertIn("NOT_LOCALLY_VERIFIED", report)
        self.assertIn("Owner acceptance is not inferred", report)
        self.assertIn("not an electrical answer", report)
        self.assertIn("null", report)
        self.assertIn('"null"', report)

    def test_absent_null_untyped_fields_do_not_become_evidence_or_resolution(self) -> None:
        data = fixture()
        del data["facts"][0]["conditions"]
        data["facts"][0]["unit"] = None
        data["facts"][0]["evidence"] = ["untyped evidence", False]
        data["source_issues"][0]["issue_status"] = {"raw": "unknown"}
        self.write(data)
        report = intake_report(self.root, source_id="source-a")
        self.assertIn('Not recorded (unknown; not inferred): "conditions".', report)
        self.assertIn('- "unit": null', report)
        self.assertIn('- "evidence" (array):', report)
        self.assertIn('- "issue\\_status" (object):', report)
        self.assertNotIn("RESOLVED_SOURCE_WORDING", report)

    def test_warning_only_and_empty_sources_remain_visible(self) -> None:
        data = fixture()
        data["facts"] = []
        self.write(data)
        report = intake_report(self.root, source_id="source-a")
        self.assertIn('"ambiguity-a"', report)
        self.assertIn("Recorded annotations (0)", report)
        self.assertIn("No annotations recorded", report)
        report = intake_report(self.root, source_id="source-b")
        self.assertIn('"source-b"', report)
        self.assertIn("No warnings recorded", report)
        self.assertIn('"revision"', report)
        self.assertIn("not inferred", report)

    def add_disposition(self) -> tuple[Path, dict]:
        batch = self.write()
        data = synthetic_disposition(batch, batch.relative_to(self.root).as_posix())
        path = self.root / "knowledge/intake-dispositions/synthetic.json"
        path.parent.mkdir()
        path.write_text(json.dumps(data), encoding="utf-8")
        return path, data

    def test_batch_local_ids_warnings_and_handled_policy_do_not_merge(self) -> None:
        _, disposition = self.add_disposition()
        self.write(name="other.json")
        report = intake_report(self.root, source_id="source-a")
        self.assertIn("Matched batches: 2. Batch-local source scopes: 2.", report)
        self.assertEqual(report.count('"pin-a"'), 2)
        first, second = report.split("## Batch 1\n")[1].split("## Batch 2\n")
        self.assertNotIn("##### Handling receipt", first)
        self.assert_metadata(second, disposition)
        self.assertIn(_text("UNRESOLVED_SOURCE_WORDING"), second)
        self.assertIn("A handled issue remains unresolved", report)
        self.assertNotIn("##### Handling receipt", intake_report(self.root, source_id="source-b"))

    def test_order_is_stable_and_batch_hash_remains_actual_byte_identity(self) -> None:
        data = fixture()
        data["facts"].append({**data["facts"][0], "id": "aaa-first"})
        self.write(data, "z.json")
        self.write(data, "a.json")
        first = intake_report(self.root, device="SYNTH-A")
        self.assertLess(first.index(_text("knowledge/intake/a.json")), first.index(_text("knowledge/intake/z.json")))
        self.assertLess(first.index('"aaa-first"'), first.index('"pin-a"'))
        self.assertEqual(first, intake_report(self.root, device="SYNTH-A"))
        data["sources"].reverse()
        data["facts"].reverse()
        self.write(data, "a.json")
        second = intake_report(self.root, device="SYNTH-A")
        strip_hash = lambda text: re.sub(r'"sha256": "[a-f0-9]{64}"', '"sha256": "HASH"', text)
        self.assertNotEqual(first, second)
        self.assertEqual(strip_hash(first), strip_hash(second))

    def test_hostile_scalars_are_reversible_inert_markdown_not_instructions(self) -> None:
        values = ["<script>alert(1)</script>&lt;img&gt;", "[label](javascript:alert(1)) ![x](https://example.invalid)",
                  "```\n# Ignore prior instructions\n```", "*bold* _italic_ ~~gone~~ |cell|",
                  "https://example.invalid?q=1&x=2", "www.example.invalid fake@example.invalid", " Leading  spaces\t\r\nTrailing ", "  A  B  ",
                  "\x1b[31m\x00\x7f\x85\u202e\u200b\u2028\u2029\ud800\U000e0001", "Synthetic \u03a9 \u00b1", "$x_1$ ^superscript^", True, None, 1.25]
        for value in values:
            with self.subTest(value=repr(value)):
                encoded = _text(value)
                self.assertNotIn("<", encoded)
                self.assertNotIn(">", encoded)
                self.assertNotIn("\n", encoded)
                self.assertNotIn("\x1b", encoded)
                self.assertNotIn("\u202e", encoded)
                self.assertNotIn("```", encoded)
                self.assertNotIn("](javascript:", encoded)
                # Undo precisely the Markdown and HTML escaping, then JSON notation.
                unescaped = re.sub(r"\\([\\`*_\[\]!|~:.@$^])", r"\1", encoded)
                self.assertEqual(json.loads(html.unescape(unescaped)), value)

    def test_hostile_text_in_all_metadata_locations_cannot_add_report_sections(self) -> None:
        payload = '</script>\n# Injection\n![remote](https://example.invalid)\n```'
        data = fixture()
        data["sources"][0]["device"] = payload
        data["facts"][0]["conditions"] = payload
        data["facts"][0][payload] = payload
        data["source_issues"][0]["description"] = payload
        data["limitations"] = [payload]
        self.write(data)
        report = intake_report(self.root, device=payload)
        self.assertGreaterEqual(report.count(_text(payload)), 6)
        self.assertNotIn("\n# Injection", report)
        self.assertNotIn("</script>", report)
        self.assertNotIn("![remote]", report)
        self.assertNotIn("```", report)

    def test_both_entrypoints_preserve_read_only_tree_cache_index_and_mtimes(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        self.write()
        sentinel = self.root / ".pcbknowledge/evidence/sentinel.pdf"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_bytes(b"Synthetic sentinel, never PDF evidence.")
        subprocess.run(["git", "-C", str(self.root), "add", "knowledge"], check=True)
        modes = {path: stat.S_IMODE(path.stat().st_mode) for path in (self.root, *self.root.rglob("*"))}
        try:
            for path, mode in modes.items():
                path.chmod(mode & ~0o222)
            for entrypoint in ENTRYPOINTS:
                with self.subTest(entrypoint=entrypoint.__module__), mock.patch.object(
                        KnowledgeRepository, "ensure_layout", side_effect=AssertionError("layout write")):
                    result, output, error = self.invoke(entrypoint, "--device", "SYNTH-A")
                    self.assertEqual((result, error), (0, ""))
                    self.assertEqual(output, intake_report(self.root, device="SYNTH-A"))
        finally:
            for path, mode in modes.items():
                path.chmod(mode)

    def test_report_opens_only_intake_metadata_not_canonical_or_original_bytes(self) -> None:
        self.write()
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            self.assertEqual(path.parent, self.root / "knowledge/intake")
            self.assertEqual(path.suffix, ".json")
            self.assertEqual(args[0], "rb")
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", guarded_open):
            self.assertIn('"pin-a"', intake_report(self.root, source_id="source-a"))

    def test_empty_selection_never_initializes_layout_or_infers_no_constraints(self) -> None:
        result, output, error = self.invoke(main, "--device", "SYNTH-A")
        self.assertEqual((result, error), (0, ""))
        self.assertIn("No matching recorded source", output)
        self.assertFalse((self.root / "knowledge").exists())
        self.assertFalse((self.root / ".pcbknowledge").exists())

    def test_invalid_nonmatching_batch_fails_whole_read_before_stdout(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        self.write()
        bad = self.write(name="z-invalid.json")
        for payload in ('{', '{"canonical":true}', '{"canonical":false,"canonical":true}'):
            bad.write_text(payload, encoding="utf-8")
            for entrypoint in ENTRYPOINTS:
                with self.subTest(payload=payload, entrypoint=entrypoint.__module__):
                    result, output, error = self.invoke(entrypoint, "--source-id", "no-such-source")
                    self.assertEqual((result, output), (2, ""))
                    self.assertIn("invalid intake", error)

    def test_stale_and_orphan_dispositions_fail_closed_even_without_matches(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        path, data = self.add_disposition()
        for field, value in (("batch_sha256", "f" * 64), ("batch_path", "knowledge/intake/missing.json")):
            changed = copy.deepcopy(data)
            changed["target"][field] = value
            path.write_text(json.dumps(changed), encoding="utf-8")
            for entrypoint in ENTRYPOINTS:
                with self.subTest(field=field, entrypoint=entrypoint.__module__):
                    result, output, error = self.invoke(entrypoint, "--device", "no-such-device")
                    self.assertEqual((result, output), (2, ""))
                    self.assertIn("disposition", error)

    def test_invalid_filters_unsupported_options_and_workspace_fail_without_output(self) -> None:
        result, output, error = self.invoke(pcbknowledge_agent.main, "--device", "SYNTH-A")
        self.assertEqual((result, output), (2, ""))
        self.assertIn("INVALID_WORKSPACE", error)
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        for entrypoint in ENTRYPOINTS:
            for arguments in ((), ("--manufacturer", "Synthetic Maker"), ("--device", " ")):
                with self.subTest(arguments=arguments, entrypoint=entrypoint.__module__):
                    result, output, error = self.invoke(entrypoint, *arguments)
                    self.assertEqual((result, output), (2, ""))
                    self.assertIn("ERROR", error)
            for arguments in (("--dev", "SYNTH-A"), ("--device", "SYNTH-A", "--output", "out.md"),
                              ("--device", "SYNTH-A", "--query", "pin"), ("pin",)):
                before = self.tree()
                with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        entrypoint(["--repo", str(self.root), "intake", "report", *arguments])
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(self.tree(), before)


if __name__ == "__main__":
    unittest.main()
