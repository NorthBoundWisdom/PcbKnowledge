"""Synthetic explicit-cache audit tests; fixtures are not original documents."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from configs import pcbknowledge_agent
from pcbknowledge.git_native import intake_evidence_audit as audit
from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError
from pcbknowledge.git_native.store import KnowledgeRepository
from pcbknowledge.git_native.workspace import initialize_workspace
from tests.git_native.test_intake_dispositions import synthetic_batch


PAYLOAD = b"Invented opaque bytes, deliberately not a PDF.\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
ENTRYPOINTS = (main, pcbknowledge_agent.main)


class IntakeEvidenceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.root = self.directory / "workspace"
        self.cache = self.directory / "private-cache"
        self.cache.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
        self.batch = synthetic_batch()
        self.batch["sources"][0].update(pdf_sha256=DIGEST, pdf_byte_size=len(PAYLOAD))
        self.path = self.root / "knowledge/intake/synthetic.json"
        self.path.parent.mkdir(parents=True)
        self.write_batch()
        self.candidate = self.cache / "invented.bin"
        self.candidate.write_bytes(PAYLOAD)

    def write_batch(self) -> None:
        self.path.write_text(json.dumps(self.batch), encoding="utf-8")

    def run_audit(self, files=None, **kwargs) -> dict:
        return audit.intake_evidence_audit(self.root, cache_root=self.cache,
                                           cache_files=["invented.bin"] if files is None else files, **kwargs)

    def source(self, result: dict, index: int = 0) -> dict:
        return result["sources"][index]

    def tree(self) -> dict:
        return {path.relative_to(self.directory).as_posix():
                (path.stat().st_mode, path.stat().st_mtime_ns,
                 None if path.is_dir() else path.read_bytes())
                for path in (self.directory, *self.directory.rglob("*"))}

    def invoke(self, entrypoint, *arguments: str) -> tuple[int, str, str]:
        before = self.tree()
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = entrypoint(["--repo", str(self.root), "intake", "evidence-audit",
                                 "--cache-root", str(self.cache), *arguments])
        self.assertEqual(self.tree(), before)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_hash_and_byte_count_from_opaque_bytes_without_pdf_review(self) -> None:
        with mock.patch.object(KnowledgeRepository, "verify_evidence", side_effect=AssertionError("canonical verifier")), \
                mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            result = self.run_audit()
        source = self.source(result)
        self.assertEqual(source["local_byte_check"], "FOUND_MATCH")
        self.assertEqual(source["matching_copy_count"], 1)
        self.assertEqual(source["recorded_sha256"], DIGEST)
        self.assertEqual(source["recorded_byte_size"], len(PAYLOAD))
        self.assertEqual(result["candidates"][0]["actual_sha256"], DIGEST)
        self.assertEqual(result["candidates"][0]["actual_byte_size"], len(PAYLOAD))
        self.assertEqual(source["batch_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(source["batch_path"], "knowledge/intake/synthetic.json")
        self.assertFalse(result["canonical"])
        self.assertFalse(result["metadata_modified"])
        self.assertNotIn("VERIFIED", json.dumps(result))
        self.assertEqual(json.loads(self.path.read_text()), self.batch)

    def test_unknown_and_incomplete_pins_stay_unpinned(self) -> None:
        for digest, size in ((None, None), (None, len(PAYLOAD)), (DIGEST, None)):
            self.batch["sources"][0].update(pdf_sha256=digest, pdf_byte_size=size)
            self.write_batch()
            with self.subTest(digest=digest, size=size):
                source = self.source(self.run_audit())
                self.assertEqual(source["local_byte_check"], "UNPINNED")
                self.assertEqual(source["matching_copy_count"], 0)
                self.assertEqual(source["associated_candidates"], [])

    def test_malformed_pins_fail_closed_even_for_nonmatching_source(self) -> None:
        baseline = copy.deepcopy(self.batch)
        for key, values in {"pdf_sha256": ("", "ABC" * 22, "f" * 63, 1, [], True),
                            "pdf_byte_size": (0, -1, True, "45", 1.5, [])}.items():
            for value in values:
                self.batch = copy.deepcopy(baseline)
                self.batch["sources"][1][key] = value
                self.write_batch()
                with self.subTest(key=key, value=value), mock.patch.object(
                        audit, "_read_candidate", side_effect=AssertionError("must validate first")):
                    with self.assertRaisesRegex(IntakeError, key):
                        self.run_audit(source_id="no-match")

    def test_duplicate_identical_candidates_are_matches_not_ambiguity(self) -> None:
        (self.cache / "duplicate.bin").write_bytes(PAYLOAD)
        result = self.run_audit(["invented.bin", "duplicate.bin"])
        source = self.source(result)
        self.assertEqual(source["local_byte_check"], "FOUND_MATCH")
        self.assertEqual(source["matching_copy_count"], 2)
        self.assertEqual(source["associated_candidates"], [1, 2])

    def test_missing_is_limited_to_list_and_never_guesses_filenames(self) -> None:
        (self.cache / "source-a.pdf").write_bytes(b"Different synthetic bytes")
        result = self.run_audit(["missing.pdf", "missing-parent/file.pdf", "source-a.pdf"])
        self.assertEqual(self.source(result)["local_byte_check"], "MISSING")
        self.assertEqual(self.source(result)["associated_candidates"], [])
        self.assertEqual(result["summary"]["read_candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["read_status"], "MISSING")
        self.assertTrue(self.candidate.exists())  # An unlisted matching file is irrelevant.

    def test_hash_named_candidate_or_exact_recorded_path_can_report_mismatch(self) -> None:
        mismatch = DIGEST + ".pdf"
        (self.cache / mismatch).write_bytes(b"Different synthetic bytes")
        self.assertEqual(self.source(self.run_audit([mismatch]))["local_byte_check"], "HASH_MISMATCH")
        self.batch["sources"][0]["pdf_local_path"] = "wrong.bin"
        self.write_batch()
        (self.cache / "wrong.bin").write_bytes(b"Different synthetic bytes")
        result = self.run_audit(["wrong.bin"])
        self.assertEqual(self.source(result)["local_byte_check"], "HASH_MISMATCH")
        self.assertEqual(self.source(result)["associated_candidates"], [1])

    def test_byte_count_conflict_never_returns_match(self) -> None:
        self.batch["sources"][0]["pdf_byte_size"] += 1
        self.write_batch()
        source = self.source(self.run_audit())
        self.assertEqual(source["local_byte_check"], "HASH_MISMATCH")
        self.assertEqual(source["matching_copy_count"], 0)

    def test_conflicting_claimed_locators_preserve_ambiguity(self) -> None:
        self.batch["sources"][0].update(pdf_local_path="wrong.bin", evidence_cache_path="other.bin")
        self.write_batch()
        (self.cache / "wrong.bin").write_bytes(b"Wrong synthetic bytes")
        (self.cache / "other.bin").write_bytes(b"Other synthetic bytes")
        for paths in (["invented.bin", "wrong.bin"], ["wrong.bin", "other.bin"]):
            with self.subTest(paths=paths):
                self.assertEqual(self.source(self.run_audit(paths))["local_byte_check"], "AMBIGUOUS")
        (self.cache / "other.bin").write_bytes(b"Wrong synthetic bytes")
        self.assertEqual(self.source(self.run_audit(["wrong.bin", "other.bin"]))["local_byte_check"], "HASH_MISMATCH")

    def test_metadata_paths_never_authorize_reads_or_discovery(self) -> None:
        for value in ("../private.pdf", "/tmp/private.pdf", "C:\\private.pdf", {"path": "invented.bin"}):
            self.batch["sources"][0].update(pdf_local_path=value, evidence_cache_path=value)
            self.write_batch()
            with self.subTest(value=value), mock.patch.object(Path, "rglob", side_effect=AssertionError("cache crawl")):
                # Intake's existing reader owns metadata enumeration; patch only its input.
                with mock.patch.object(audit, "load_intake", return_value=[{
                        "path": "knowledge/intake/synthetic.json", "sha256": "f" * 64, "data": self.batch}]):
                    self.assertEqual(self.source(self.run_audit())["local_byte_check"], "FOUND_MATCH")

    def test_batch_local_ids_and_filters_preserve_scope_without_merging(self) -> None:
        other = self.path.with_name("other.json")
        other.write_bytes(self.path.read_bytes())
        result = self.run_audit(source_id="source-a")
        self.assertEqual(len(result["sources"]), 2)
        self.assertNotEqual(result["sources"][0]["batch_path"], result["sources"][1]["batch_path"])
        for value in ("SOURCE-A", "source-a "):
            self.assertEqual(self.run_audit(source_id=value)["sources"], [])
        self.assertEqual(self.run_audit(source_id="source-a", device="SYNTH-B")["sources"], [])
        with self.assertRaisesRegex(IntakeError, "nonempty string"):
            self.run_audit(device=" ")

    def test_private_paths_hidden_by_default_and_only_relative_paths_opt_in(self) -> None:
        result = self.run_audit()
        self.assertNotIn("relative_path", result["candidates"][0])
        self.assertNotIn(str(self.cache), json.dumps(result))
        result = self.run_audit(include_paths=True)
        self.assertEqual(result["candidates"][0]["relative_path"], "invented.bin")
        self.assertNotIn(str(self.cache), json.dumps(result))
        self.assertEqual(result, self.run_audit(include_paths=True))

    def test_candidate_path_syntax_rejected_before_any_payload_open(self) -> None:
        values = ("", "/absolute.pdf", "../outside.pdf", "a/../b", "./a", "a//b", "a/", "C:/a", "a:stream",
                  "a\\b", "\\\\server\\share", "bad\x00name", "bad\nname", "a" * 1025, "/".join(["a"] * 17), None, 1)
        for value in values:
            with self.subTest(value=value), mock.patch.object(audit, "_read_candidate", side_effect=AssertionError("read")):
                with self.assertRaises(IntakeError):
                    self.run_audit([value])
        for files in ([], "invented.bin", ["invented.bin"] * 129, ["invented.bin"] * 2):
            with self.subTest(files=str(files)[:30]), self.assertRaises(IntakeError):
                self.run_audit(files)

    def test_root_must_exist_and_be_nonroot_directory_without_traversal(self) -> None:
        for root in (Path(self.cache.anchor), self.cache / "missing", self.candidate, self.cache / ".." / "private-cache"):
            with self.subTest(root=root), self.assertRaises(IntakeError):
                audit.intake_evidence_audit(self.root, cache_root=root, cache_files=["invented.bin"])

    def test_network_and_device_roots_are_rejected_without_cache_access(self) -> None:
        for root in ("//server/share", r"\\server\share", r"\\?\C:\cache", r"\\.\device", "https://example.invalid/cache"):
            with self.subTest(root=root), mock.patch.object(audit, "_root_chain", side_effect=AssertionError("cache access")):
                with self.assertRaisesRegex(IntakeError, "must be local"):
                    audit.intake_evidence_audit(self.root, cache_root=root, cache_files=["invented.bin"])

    def test_directory_special_files_symlinks_and_reparse_points_fail_before_open(self) -> None:
        (self.cache / "folder").mkdir()
        with self.assertRaisesRegex(IntakeError, "regular files"):
            self.run_audit(["folder"])
        original = os.stat
        for target in (self.cache.parent, self.cache, self.candidate):
            for mode, attributes in ((stat.S_IFLNK | 0o777, 0), (stat.S_IFREG | 0o644, 0x400)):
                def fake_stat(path, *args, target=target, mode=mode, attributes=attributes, **kwargs):
                    if path == target.name and kwargs.get("dir_fd") is not None:
                        return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                    return original(path, *args, **kwargs)
                with self.subTest(target=target.name, mode=mode), mock.patch.object(audit.os, "stat", fake_stat):
                    with self.assertRaisesRegex(IntakeError, "symlinks or reparse"):
                        self.run_audit()
        for mode in (stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR, stat.S_IFBLK):
            with self.subTest(mode=mode), self.assertRaisesRegex(IntakeError, "regular files"):
                audit._check_kind(SimpleNamespace(st_mode=mode, st_file_attributes=0), directory=False)

    def test_nested_explicit_files_work_without_enumeration(self) -> None:
        (self.cache / "nested").mkdir()
        (self.cache / "nested/opaque.data").write_bytes(PAYLOAD)
        self.assertEqual(self.source(self.run_audit(["nested/opaque.data"]))["local_byte_check"], "FOUND_MATCH")

    def test_file_and_total_limits_fail_without_partial_success(self) -> None:
        with mock.patch.object(audit, "MAX_FILE_BYTES", len(PAYLOAD) - 1), self.assertRaisesRegex(IntakeError, "byte limit"):
            self.run_audit()
        (self.cache / "copy.bin").write_bytes(PAYLOAD)
        with mock.patch.object(audit, "MAX_TOTAL_BYTES", len(PAYLOAD)), self.assertRaisesRegex(IntakeError, "byte limit"):
            self.run_audit(["invented.bin", "copy.bin"])
        with mock.patch.object(audit, "MAX_FILE_BYTES", len(PAYLOAD)), mock.patch.object(audit, "MAX_TOTAL_BYTES", len(PAYLOAD)):
            self.assertEqual(self.source(self.run_audit())["local_byte_check"], "FOUND_MATCH")

    def test_growth_is_bounded_and_detected_during_streaming(self) -> None:
        original = os.read
        calls = []
        def grow(descriptor, length):
            calls.append(length)
            if len(calls) == 1:
                with self.candidate.open("ab") as stream:
                    stream.write(b"extra")
            return original(descriptor, length)
        with mock.patch.object(audit.os, "read", grow), mock.patch.object(audit, "MAX_FILE_BYTES", len(PAYLOAD)), \
                self.assertRaisesRegex(IntakeError, "grew beyond"):
            self.run_audit()
        self.assertEqual(calls, [len(PAYLOAD) + 1])

    def test_file_replacement_before_open_is_rejected_without_read(self) -> None:
        original = os.open
        def replace(path, flags, **kwargs):
            if path == "invented.bin":
                self.candidate.unlink()
                self.candidate.write_bytes(PAYLOAD + b"replacement")
            return original(path, flags, **kwargs)
        with mock.patch.object(audit.os, "open", replace), mock.patch.object(audit.os, "read", side_effect=AssertionError("read")), \
                self.assertRaisesRegex(IntakeError, "identity changed"):
            self.run_audit()

    def test_same_size_change_during_read_is_rejected(self) -> None:
        original = os.read
        def mutate(descriptor, length):
            chunk = original(descriptor, length)
            if chunk:
                self.candidate.write_bytes(b"X" * len(PAYLOAD))
            return chunk
        with mock.patch.object(audit.os, "read", mutate), self.assertRaisesRegex(IntakeError, "changed during"):
            self.run_audit()

    def test_opened_special_descriptor_is_rejected_and_closed(self) -> None:
        real_fstat = os.fstat
        calls = []
        def changed(descriptor):
            current = real_fstat(descriptor)
            if stat.S_ISREG(current.st_mode):
                calls.append(descriptor)
                return SimpleNamespace(st_mode=stat.S_IFIFO, st_file_attributes=0)
            return current
        with mock.patch.object(audit.os, "fstat", changed), self.assertRaisesRegex(IntakeError, "regular files"):
            self.run_audit()
        with self.assertRaises(OSError):
            real_fstat(calls[0])

    def test_both_cli_entrypoints_are_read_only_including_index_modes_and_mtimes(self) -> None:
        subprocess.run(["git", "-C", str(self.root), "add", "knowledge"], check=True)
        modes = {path: stat.S_IMODE(path.stat().st_mode) for path in (self.directory, *self.directory.rglob("*"))}
        try:
            for path, mode in modes.items():
                path.chmod(mode & ~0o222)
            for entrypoint in ENTRYPOINTS:
                with self.subTest(entrypoint=entrypoint.__module__), mock.patch.object(
                        KnowledgeRepository, "ensure_layout", side_effect=AssertionError("layout write")):
                    result, output, error = self.invoke(entrypoint, "--cache-file", "invented.bin", "--source-id", "source-a")
                    self.assertEqual((result, error), (0, ""))
                    self.assertEqual(self.source(json.loads(output))["local_byte_check"], "FOUND_MATCH")
        finally:
            for path, mode in modes.items():
                path.chmod(mode)
        self.assertFalse((self.root / ".pcbknowledge").exists())

    def test_cli_failures_have_no_partial_output_writes_or_absolute_cache_path(self) -> None:
        for entrypoint in ENTRYPOINTS:
            for arguments in (("--cache-file", "../outside"), ("--cache-file", "invented.bin", "--device", " "),
                              ("--cache-file", "invented.bin", "--cache-file", "invented.bin")):
                with self.subTest(entrypoint=entrypoint.__module__, arguments=arguments):
                    result, output, error = self.invoke(entrypoint, *arguments)
                    self.assertEqual((result, output), (2, ""))
                    self.assertNotIn(str(self.cache), error)
            for arguments in ((), ("--cache-file", "invented.bin", "--output", "audit.json"),
                              ("--cache-file", "invented.bin", "--dev", "SYNTH-A")):
                with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as raised:
                    self.invoke(entrypoint, *arguments)
                self.assertEqual(raised.exception.code, 2)

    def test_invalid_unselected_intake_fails_before_payload_read_or_stdout(self) -> None:
        self.path.with_name("invalid.json").write_text("{", encoding="utf-8")
        for entrypoint in ENTRYPOINTS:
            with mock.patch.object(audit, "_read_candidate", side_effect=AssertionError("payload read")):
                result, output, error = self.invoke(entrypoint, "--cache-file", "invented.bin", "--source-id", "no-match")
                self.assertEqual((result, output), (2, ""))
                self.assertIn("invalid intake", error)

    def test_ancestor_swap_cannot_redirect_open_to_outside_bytes(self) -> None:
        outside = self.directory / "outside"
        outside.mkdir()
        outside_payload = b"Outside-root synthetic bytes"
        (outside / "invented.bin").write_bytes(outside_payload)
        held = self.directory / "held-cache"
        original_stat, original_open, original_read = os.stat, os.open, os.read
        calls, payloads = [], []
        def swap():
            self.cache.rename(held)
            self.cache.symlink_to(outside, target_is_directory=True)
        def restore():
            self.cache.unlink()
            held.rename(self.cache)
        def attacked_stat(path, *args, **kwargs):
            if path == "invented.bin" and kwargs.get("dir_fd") is not None:
                calls.append(path)
                swap()
                value = original_stat(path, *args, **kwargs)
                if len(calls) > 1:
                    restore()
                return value
            return original_stat(path, *args, **kwargs)
        def attacked_open(path, *args, **kwargs):
            descriptor = original_open(path, *args, **kwargs)
            if path == "invented.bin":
                restore()
            return descriptor
        def observed_read(descriptor, size):
            value = original_read(descriptor, size)
            payloads.append(value)
            return value
        with mock.patch.object(audit.os, "stat", attacked_stat), mock.patch.object(audit.os, "open", attacked_open), \
                mock.patch.object(audit.os, "read", observed_read):
            result = self.run_audit()
        self.assertEqual(self.source(result)["local_byte_check"], "FOUND_MATCH")
        self.assertEqual(b"".join(payloads), PAYLOAD)
        self.assertNotIn(outside_payload, payloads)

    def test_directory_swap_before_descent_fails_without_payload_read(self) -> None:
        nested = self.cache / "nested"
        nested.mkdir()
        (nested / "invented.bin").write_bytes(PAYLOAD)
        outside = self.directory / "outside"
        outside.mkdir()
        (outside / "invented.bin").write_bytes(b"Outside-root synthetic bytes")
        held = self.cache / "held"
        original_open = os.open
        def swapped(path, *args, **kwargs):
            if path == "nested":
                nested.rename(held)
                nested.symlink_to(outside, target_is_directory=True)
            return original_open(path, *args, **kwargs)
        try:
            with mock.patch.object(audit.os, "open", swapped), mock.patch.object(audit.os, "read", side_effect=AssertionError("read")), \
                    self.assertRaisesRegex(IntakeError, "cannot safely read"):
                self.run_audit(["nested/invented.bin"])
        finally:
            if nested.is_symlink():
                nested.unlink()
                held.rename(nested)

    def test_directory_descriptors_close_on_success_missing_and_error(self) -> None:
        original_open, original_close = os.open, os.close
        active = set()
        def tracked_open(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            active.add(descriptor)
            return descriptor
        def tracked_close(descriptor):
            active.remove(descriptor)
            return original_close(descriptor)
        with mock.patch.object(audit.os, "open", tracked_open), mock.patch.object(audit.os, "close", tracked_close):
            self.run_audit()
            self.assertFalse(active)
            self.run_audit(["missing-parent/file"])
            self.assertFalse(active)
            with mock.patch.object(audit, "MAX_FILE_BYTES", 1), self.assertRaises(IntakeError):
                self.run_audit()
            self.assertFalse(active)

    def test_root_depth_and_spelling_limits_precede_cache_access(self) -> None:
        for root in ("/" + "/".join(["part"] * 129), "/" + "a" * 4097):
            with mock.patch.object(audit, "_root_chain", side_effect=AssertionError("cache access")), \
                    self.assertRaisesRegex(IntakeError, "bounded explicit"):
                audit.intake_evidence_audit(self.root, cache_root=Path(root), cache_files=["invented.bin"])

    def test_missing_invalid_workspace_is_not_replaced_or_initialized(self) -> None:
        (self.root / "pcbknowledge.workspace.json").unlink()
        result, output, error = self.invoke(pcbknowledge_agent.main, "--cache-file", "invented.bin")
        self.assertEqual((result, output), (2, ""))
        self.assertIn("INVALID_WORKSPACE", error)


class IntakeEvidenceAuditPortableTests(unittest.TestCase):
    """Platform-independent semantics and explicit unsupported behavior."""

    def test_source_outcomes_use_only_complete_pins_and_explicit_associations(self) -> None:
        source = {"id": "synthetic", "pdf_sha256": DIGEST, "pdf_byte_size": len(PAYLOAD)}
        candidate = {"candidate": 1, "relative_path": "invented.bin", "read_status": "READ",
                     "actual_sha256": DIGEST, "actual_byte_size": len(PAYLOAD)}
        self.assertEqual(audit._source_check(source, [candidate])["local_byte_check"], "FOUND_MATCH")
        self.assertEqual(audit._source_check(source, [candidate, {**candidate, "candidate": 2}])["matching_copy_count"], 2)
        self.assertEqual(audit._source_check(source, [])["local_byte_check"], "MISSING")
        self.assertEqual(audit._source_check({**source, "pdf_sha256": None}, [candidate])["local_byte_check"], "UNPINNED")
        self.assertEqual(audit._source_check({**source, "pdf_byte_size": 1}, [candidate])["local_byte_check"], "HASH_MISMATCH")
        conflict = {**candidate, "candidate": 2, "relative_path": DIGEST + ".pdf", "actual_sha256": "a" * 64}
        self.assertEqual(audit._source_check(source, [candidate, conflict])["local_byte_check"], "AMBIGUOUS")

    def test_pin_validation_does_not_coerce_values(self) -> None:
        for source in ({"pdf_sha256": "A" * 64}, {"pdf_sha256": []}, {"pdf_byte_size": True},
                       {"pdf_byte_size": 0}, {"pdf_byte_size": "45"}):
            with self.subTest(source=source), self.assertRaises(IntakeError):
                audit._pin(source)
        self.assertEqual(audit._pin({}), (None, None))

    def test_portable_paths_reject_escape_and_unsafe_hints(self) -> None:
        for value in ("../a", "/a", "a\\b", "C:/a", "a:stream", "//server/share", "a//b", None):
            with self.subTest(value=value), self.assertRaises(IntakeError):
                audit._relative_path(value)
            self.assertIsNone(audit._safe_hint(value))
        self.assertEqual(audit._relative_path("nested/file.bin"), "nested/file.bin")

    def test_kind_checks_reject_symlinks_reparse_points_and_devices(self) -> None:
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFREG, 0x400), (stat.S_IFIFO, 0),
                                 (stat.S_IFSOCK, 0), (stat.S_IFCHR, 0), (stat.S_IFBLK, 0)):
            with self.subTest(mode=mode), self.assertRaises(IntakeError):
                audit._check_kind(SimpleNamespace(st_mode=mode, st_file_attributes=attributes), directory=False)

    def test_unsupported_api_fails_before_metadata_or_cache_access(self) -> None:
        with mock.patch.object(audit, "SECURE_PATHS_SUPPORTED", False), \
                mock.patch.object(audit, "load_intake", side_effect=AssertionError("metadata access")), \
                mock.patch.object(audit, "_root_chain", side_effect=AssertionError("cache access")):
            with self.assertRaisesRegex(IntakeError, "unsupported: requires POSIX"):
                audit.intake_evidence_audit(Path("missing-workspace"), cache_root=Path("missing-cache"), cache_files=["file"])

    def test_unsupported_cli_emits_no_success_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            initialize_workspace(root, schema_source_root=pcbknowledge_agent.REPO_ROOT)
            def snapshot():
                return {path.relative_to(root).as_posix(): (path.stat().st_mode, path.stat().st_mtime_ns,
                        None if path.is_dir() else path.read_bytes()) for path in (root, *root.rglob("*"))}
            before = snapshot()
            for entrypoint in ENTRYPOINTS:
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch.object(audit, "SECURE_PATHS_SUPPORTED", False), \
                        mock.patch.object(audit, "_root_chain", side_effect=AssertionError("cache access")), \
                        contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    result = entrypoint(["--repo", str(root), "intake", "evidence-audit", "--cache-root", "missing-cache",
                                         "--cache-file", "missing-file"])
                self.assertEqual((result, stdout.getvalue()), (2, ""))
                self.assertIn("unsupported: requires POSIX", stderr.getvalue())
                self.assertEqual(snapshot(), before)


def load_tests(loader, tests, pattern):
    # Unsupported platforms exercise rejection and portable semantics, not a fake
    # successful byte-audit backend. POSIX descriptor I/O coverage is separate.
    suite = loader.loadTestsFromTestCase(IntakeEvidenceAuditPortableTests)
    if audit.SECURE_PATHS_SUPPORTED:
        suite.addTests(loader.loadTestsFromTestCase(IntakeEvidenceAuditTests))
    return suite


if __name__ == "__main__":
    unittest.main()
