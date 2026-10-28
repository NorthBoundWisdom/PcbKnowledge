"""Bounded additive evaluation manifests; all documents here are synthetic."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace
from tests.git_native.test_intake_filters import fixture


def case(identifier: str) -> dict:
    return {"id": identifier, "command": "search", "query": "", "filters": {"device": "ABSENT"}, "expected": []}


class IntakeEvalCompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.base = {"format": evaluation.FORMAT, "files": {"knowledge/intake/a.json": "a" * 64},
                     "cases": [case("old") ]}
        self.write("base.json", self.base)
        self.delta = {"format": evaluation.DELTA_FORMAT,
                      "base": {"path": "base.json", "sha256": self.digest("base.json")},
                      "files": {"knowledge/intake/b.json": "b" * 64}, "cases": [case("new")]}
        self.write("delta.json", self.delta)

    def write(self, name, data):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    def digest(self, name):
        return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def load(self):
        return evaluation.load_manifest(self.root / "delta.json")

    def test_standalone_and_exact_additive_union_with_dependency_receipt(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(evaluation.load_manifest(self.root / "base.json"), self.base)
        composed, payload, receipts = evaluation._load_manifest(self.root / "delta.json")
        self.assertEqual(composed, {"format": evaluation.FORMAT,
            "files": {**self.base["files"], **self.delta["files"]}, "cases": self.base["cases"] + self.delta["cases"]})
        self.assertEqual(payload, before["delta.json"])
        self.assertEqual(receipts, {"base.json": self.digest("base.json")})
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)
        self.assertEqual(evaluation._load_manifest(self.root / "base.json")[2], {})

    def test_recursive_case_only_delta_preserves_order(self):
        next_delta = {"format": evaluation.DELTA_FORMAT,
                      "base": {"path": "delta.json", "sha256": self.digest("delta.json")},
                      "files": {}, "cases": [case("newest")]}
        self.write("next.json", next_delta)
        result, _, receipts = evaluation._load_manifest(self.root / "next.json")
        self.assertEqual([c["id"] for c in result["cases"]], ["old", "new", "newest"])
        self.assertEqual(receipts, {name: self.digest(name) for name in ("base.json", "delta.json")})

    def test_changed_baseline_bytes_rejected_not_rebased(self):
        (self.root / "base.json").write_bytes((self.root / "base.json").read_bytes() + b"\n")
        with self.assertRaisesRegex(evaluation.EvaluationError, "SHA-256 mismatch"):
            self.load()

    def test_repeated_or_replaced_pins_and_duplicate_case_ids_rejected(self):
        for digest in ("a" * 64, "f" * 64):
            changed = copy.deepcopy(self.delta)
            changed["files"]["knowledge/intake/a.json"] = digest
            self.write("delta.json", changed)
            with self.assertRaisesRegex(evaluation.EvaluationError, "cannot be repeated or replaced"):
                self.load()
        changed = copy.deepcopy(self.delta)
        changed["cases"][0]["id"] = "old"
        self.write("delta.json", changed)
        with self.assertRaisesRegex(evaluation.EvaluationError, "case ids"):
            self.load()

    def test_unsafe_base_paths_rejected(self):
        for path in ("../base.json", "/base.json", "./base.json", "a//b.json", "a/../base.json",
                     "C:/base.json", "a\\base.json", "https://example.invalid/base.json", "base.json\x00",
                     "base.txt", "", "a/" * 17 + "base.json",
                     "sub/.. /base.json", "sub/.../base.json", "dir./base.json",
                     "dir /base.json", "base.json.", "base.json "):
            changed = copy.deepcopy(self.delta)
            changed["base"]["path"] = path
            self.write("delta.json", changed)
            with self.subTest(path=path):
                # Assert lexical refusal on every OS, not a missing-file error.
                with self.assertRaisesRegex(evaluation.EvaluationError, "normalized relative"):
                    evaluation._base_path(self.root, path)
                with self.assertRaises(evaluation.EvaluationError):
                    self.load()

    def test_links_and_reparse_metadata_fail_before_payload_read(self):
        original = Path.lstat
        def fake(path):
            value = original(path)
            if path.name == "base.json":
                from types import SimpleNamespace
                return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400)
            return value
        with mock.patch.object(Path, "lstat", fake), self.assertRaisesRegex(evaluation.EvaluationError, "not links"):
            self.load()
        # Real symlink coverage is conditional capability, with a portable
        # reparse rejection above on every platform. No successful substitute I/O.
        if hasattr(os, "symlink") and os.name != "nt":
            (self.root / "base.json").rename(self.root / "actual.json")
            (self.root / "base.json").symlink_to("actual.json")
            with self.assertRaisesRegex(evaluation.EvaluationError, "not links"):
                self.load()
            (self.root / "base.json").unlink()
            (self.root / "linked").symlink_to(self.root, target_is_directory=True)
            self.delta["base"]["path"] = "linked/actual.json"
            self.write("delta.json", self.delta)
            with self.assertRaisesRegex(evaluation.EvaluationError, "not links"):
                self.load()

    def test_opened_object_is_checked_before_reading(self):
        import stat
        from types import SimpleNamespace
        with mock.patch.object(evaluation.os, "fstat", return_value=SimpleNamespace(st_mode=stat.S_IFIFO)):
            with self.assertRaisesRegex(evaluation.EvaluationError, "not a regular file"):
                self.load()
        if hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"):
            original_open = os.open
            def replace_with_fifo(path, flags):
                if path.name == "base.json":
                    path.unlink()
                    os.mkfifo(path)
                return original_open(path, flags)
            with mock.patch.object(evaluation.os, "open", replace_with_fifo):
                with self.assertRaisesRegex(evaluation.EvaluationError, "not a regular file"):
                    self.load()

    def test_cycle_and_depth_case_and_byte_limits(self):
        changed = copy.deepcopy(self.delta)
        changed["base"]["path"] = "delta.json"
        self.write("delta.json", changed)
        with self.assertRaisesRegex(evaluation.EvaluationError, "cycle"):
            self.load()
        self.write("delta.json", self.delta)
        for limit, value, message in (("MAX_MANIFEST_DEPTH", 1, "depth limit"),
                                      ("MAX_MANIFEST_BYTES", 16, "byte limit"),
                                      ("MAX_CHAIN_BYTES", 16, "total byte limit"),
                                      ("MAX_COMPOSED_CASES", 1, "case limit")):
            with mock.patch.object(evaluation, limit, value), self.assertRaisesRegex(evaluation.EvaluationError, message):
                self.load()

    def test_duplicate_json_keys_nonfinite_and_invalid_contract_rejected(self):
        for raw in ('{"format":"x","format":"y"}', '{"x":NaN}', '{"x":Infinity}', '{broken'):
            (self.root / "delta.json").write_text(raw)
            with self.assertRaises(evaluation.EvaluationError):
                self.load()
        for field, value in (("base", []), ("base", {"path": "base.json", "sha256": "A" * 64}),
                             ("files", []), ("cases", []), ("format", "unknown-format")):
            changed = copy.deepcopy(self.delta)
            changed[field] = value
            self.write("delta.json", changed)
            with self.subTest(field=field), self.assertRaises(evaluation.EvaluationError):
                self.load()
        changed = {**self.delta, "override": True}
        self.write("delta.json", changed)
        with self.assertRaises(evaluation.EvaluationError):
            self.load()

    def test_actual_additive_dataset_preserves_old_selection_and_complete_payload(self):
        workspace = self.root / "workspace"
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        initialize_workspace(workspace, schema_source_root=evaluation.REPO_ROOT)
        directory = workspace / "knowledge/intake"
        directory.mkdir(parents=True)
        old = fixture()
        new = copy.deepcopy(old)
        for source in new["sources"]:
            source["device"] = "NEW-" + source["device"]
        for name, payload in (("a.json", old), ("b.json", new)):
            (directory / name).write_text(json.dumps(payload), encoding="utf-8")
        self.base["files"] = {"knowledge/intake/a.json": hashlib.sha256((directory / "a.json").read_bytes()).hexdigest()}
        self.base["cases"] = [{"id": "old", "command": "search", "query": "",
            "filters": {"device": "MCP23017"}, "expected": ["knowledge/intake/a.json#gpio-supply"]}]
        self.write("base.json", self.base)
        self.delta["base"]["sha256"] = self.digest("base.json")
        self.delta["files"] = {"knowledge/intake/b.json": hashlib.sha256((directory / "b.json").read_bytes()).hexdigest()}
        self.delta["cases"] = [{"id": "new", "command": "issues", "query": "",
            "filters": {"device": "NEW-MCP23017"}, "expected": ["knowledge/intake/b.json#MCP23017-AMBIGUITY"]}]
        self.write("delta.json", self.delta)
        flattened = self.load()
        report = evaluation.evaluate(workspace, flattened)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["batch_count"], 2)
        self.assertEqual([row["id"] for row in report["cases"]], ["old", "new"])
        (directory / "a.json").write_bytes((directory / "a.json").read_bytes() + b"\n")
        with self.assertRaisesRegex(evaluation.EvaluationError, "dataset bytes"):
            evaluation.evaluate(workspace, flattened)

    def test_cli_uses_real_runner_and_legacy_report_remains_unchanged(self):
        workspace = self.root / "workspace"
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        initialize_workspace(workspace, schema_source_root=evaluation.REPO_ROOT)
        batch = workspace / "knowledge/intake/synthetic.json"
        batch.parent.mkdir(parents=True)
        batch.write_text(json.dumps(fixture()), encoding="utf-8")
        self.base["files"] = {"knowledge/intake/synthetic.json": hashlib.sha256(batch.read_bytes()).hexdigest()}
        self.write("base.json", self.base)
        self.delta["base"]["sha256"] = self.digest("base.json")
        self.delta["files"] = {}
        self.write("delta.json", self.delta)
        for name, count in (("base.json", 1), ("delta.json", 2)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = evaluation.main(["--repo", str(workspace), "--cases", str(self.root / name)])
            report = json.loads(output.getvalue())
            expected = evaluation.evaluate(workspace, evaluation.load_manifest(self.root / name))
            expected["manifest_sha256"] = self.digest(name)
            if name == "delta.json":
                expected["manifest_dependencies"] = {"base.json": self.digest("base.json")}
            self.assertEqual(code, 0)
            self.assertEqual(report, expected)
            self.assertEqual(report["case_count"], count)
        (self.root / "base.json").write_bytes(b"invalid")
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), mock.patch.object(
                evaluation, "evaluate", side_effect=AssertionError("runner must not execute")):
            code = evaluation.main(["--repo", str(workspace), "--cases", str(self.root / "delta.json")])
        self.assertEqual(code, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("SHA-256 mismatch", errors.getvalue())
