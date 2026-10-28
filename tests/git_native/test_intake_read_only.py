"""CLI intake reads never initialize or modify the selected workspace."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from configs import pcbknowledge_agent
from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import load_intake, search_intake, search_intake_issues
from pcbknowledge.git_native.store import KnowledgeRepository
from pcbknowledge.git_native.workspace import initialize_workspace
from tests.git_native.test_intake_dispositions import synthetic_batch, synthetic_disposition


READERS = {"list": load_intake, "search": search_intake, "issues": search_intake_issues}
ENTRYPOINTS = (main, pcbknowledge_agent.main)


class IntakeReadOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tree(self) -> dict:
        # Include empty directories, cache/index bytes, modes and modification
        # times. Read access times are intentionally not part of this contract.
        return {
            path.relative_to(self.root).as_posix(): (
                path.stat().st_mode, path.stat().st_mtime_ns,
                None if path.is_dir() else path.read_bytes())
            for path in (self.root, *self.root.rglob("*"))
        }

    @contextlib.contextmanager
    def read_only(self):
        modes = {path: stat.S_IMODE(path.stat().st_mode)
                 for path in (self.root, *self.root.rglob("*"))}
        try:
            for path, mode in modes.items():
                path.chmod(mode & ~0o222)
            yield
        finally:
            for path, mode in modes.items():
                path.chmod(mode)

    def write_batch(self) -> Path:
        path = self.root / "knowledge/intake/synthetic.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(synthetic_batch()), encoding="utf-8")
        return path

    def invoke(self, entrypoint, action: str, *arguments: str) -> tuple[int, str, str]:
        before = self.tree()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = entrypoint(["--repo", str(self.root), "intake", action, *arguments])
        self.assertEqual(self.tree(), before)
        return result, stdout.getvalue(), stderr.getvalue()

    def assert_error(self, entrypoint, action: str, fragment: str, *arguments: str) -> None:
        result, stdout, stderr = self.invoke(entrypoint, action, *arguments)
        self.assertEqual(result, 2)
        self.assertEqual(stdout, "")
        self.assertIn(fragment, stderr)
        self.assertEqual(json.loads(stderr.removeprefix("pcbknowledge: "))["status"], "ERROR")

    def test_empty_git_repository_reads_do_not_create_any_paths(self) -> None:
        for action in READERS:
            with self.subTest(action=action):
                result, stdout, stderr = self.invoke(main, action)
                self.assertEqual((result, json.loads(stdout), stderr), (0, [], ""))
        self.assertFalse((self.root / "knowledge").exists())
        self.assertFalse((self.root / ".pcbknowledge").exists())

    def test_empty_read_only_git_repository_does_not_require_layout_writes(self) -> None:
        with self.read_only():
            for action in READERS:
                with self.subTest(action=action):
                    result, stdout, stderr = self.invoke(main, action)
                    self.assertEqual((result, stdout.strip(), stderr), (0, "[]", ""))

    def test_empty_read_only_workspace_supports_both_entrypoints(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        with self.read_only():
            for entrypoint in ENTRYPOINTS:
                for action in READERS:
                    with self.subTest(entrypoint=entrypoint.__module__, action=action):
                        result, stdout, stderr = self.invoke(entrypoint, action)
                        self.assertEqual((result, json.loads(stdout), stderr), (0, [], ""))
        self.assertFalse((self.root / ".pcbknowledge").exists())

    def test_existing_metadata_cache_and_git_index_remain_unchanged(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        self.write_batch()
        sentinel = self.root / ".pcbknowledge/evidence/sha256/synthetic/sentinel"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_bytes(b"Synthetic local cache marker; not source evidence.")
        subprocess.run(["git", "-C", str(self.root), "add", "knowledge"], check=True)
        self.assertTrue((self.root / ".git/index").is_file())
        with self.read_only():
            for entrypoint in ENTRYPOINTS:
                for action, reader in READERS.items():
                    with self.subTest(entrypoint=entrypoint.__module__, action=action):
                        result, stdout, stderr = self.invoke(entrypoint, action)
                        self.assertEqual((result, stderr), (0, ""))
                        self.assertEqual(json.loads(stdout), reader(self.root))

    def test_read_handlers_never_call_layout_initializer(self) -> None:
        with mock.patch.object(KnowledgeRepository, "ensure_layout",
                               side_effect=AssertionError("intake must not initialize layout")):
            for action in READERS:
                with self.subTest(action=action):
                    self.assertEqual(self.invoke(main, action)[0], 0)

    def test_malformed_batches_fail_whole_read_without_mutation(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        valid = self.write_batch()
        invalid = valid.with_name("z-invalid.json")
        broken_link = synthetic_batch()
        broken_link["facts"][0]["source_id"] = "missing-source"
        for payload in (b"{", b"\xff", b'{"canonical":false,"canonical":true}',
                        b'{"canonical":true}', json.dumps(broken_link).encode("utf-8")):
            invalid.write_bytes(payload)
            with self.read_only():
                for entrypoint in ENTRYPOINTS:
                    for action in READERS:
                        with self.subTest(payload=payload, entrypoint=entrypoint.__module__, action=action):
                            self.assert_error(entrypoint, action, "invalid intake")

    def test_stale_and_orphan_dispositions_fail_closed_without_mutation(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        batch = self.write_batch()
        receipt = synthetic_disposition(batch, batch.relative_to(self.root).as_posix())
        path = self.root / "knowledge/intake-dispositions/synthetic.json"
        path.parent.mkdir()
        for field, value in (("batch_sha256", "f" * 64),
                             ("batch_path", "knowledge/intake/missing.json")):
            changed = copy.deepcopy(receipt)
            changed["target"][field] = value
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.read_only():
                for entrypoint in ENTRYPOINTS:
                    for action in READERS:
                        with self.subTest(field=field, entrypoint=entrypoint.__module__, action=action):
                            self.assert_error(entrypoint, action, "disposition")

    def test_invalid_filters_fail_closed_without_mutation(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        with self.read_only():
            for entrypoint in ENTRYPOINTS:
                for action in ("search", "issues"):
                    with self.subTest(entrypoint=entrypoint.__module__, action=action):
                        self.assert_error(entrypoint, action, "nonempty string", "--device", " ")

    def test_unknown_subcommands_and_options_do_not_initialize_layout(self) -> None:
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        for entrypoint in ENTRYPOINTS:
            for arguments in (("unknown",), ("list", "--unknown"),
                              ("search", "--dev", "SYNTH-A"), ("issues", "--unknown")):
                with self.subTest(entrypoint=entrypoint.__module__, arguments=arguments):
                    before = self.tree()
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        with self.assertRaises(SystemExit) as raised:
                            entrypoint(["--repo", str(self.root), "intake", *arguments])
                    self.assertEqual(raised.exception.code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn("error:", stderr.getvalue())
                    self.assertEqual(self.tree(), before)

    def test_public_wrapper_still_rejects_invalid_workspace_without_mutation(self) -> None:
        for action in READERS:
            with self.subTest(action=action):
                self.assert_error(pcbknowledge_agent.main, action, "INVALID_WORKSPACE")


if __name__ == "__main__":
    unittest.main()
