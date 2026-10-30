from __future__ import annotations

import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pcbknowledge.public_repo import (
    ALLOWED_AUTHORITY_PLACEHOLDERS,
    ALLOWED_REGISTRY_PATHS,
    _native_link_target_bytes,
    MAX_METADATA_BYTES,
    PINNED_RUNTIME_FILES,
    check_public_distribution,
    public_distribution_violations,
)


class PublicRepositoryPolicyTests(unittest.TestCase):
    def test_placeholders_and_processed_metadata_are_allowed(self) -> None:
        self.assertEqual(public_distribution_violations([
            *ALLOWED_AUTHORITY_PLACEHOLDERS,
            "knowledge/sources/source-1.json",
            "knowledge/parts/component-1.json",
            "knowledge/packages/package-1.json",
            "knowledge/blocks/summary.json",
            "knowledge/rules/candidates.json",
        ]), ())

    def test_only_declared_registry_json_paths_are_allowed(self) -> None:
        self.assertEqual(public_distribution_violations(ALLOWED_REGISTRY_PATHS), ())
        forbidden = ["knowledge/registry/extra.json", "knowledge/registry/roles.md",
                     "knowledge/registry/nested/roles.json", "knowledge/registry/roles.pdf",
                     "knowledge/arbitrary/part.json"]
        self.assertEqual(public_distribution_violations(forbidden), tuple(sorted(forbidden)))

    def test_every_repository_registry_has_an_explicit_public_path(self) -> None:
        root = Path(__file__).resolve().parents[2]
        paths = [p.relative_to(root).as_posix() for p in (root / 'knowledge/registry').glob('*.json')]
        self.assertTrue(paths)
        self.assertEqual(public_distribution_violations(paths), ())

    def test_originals_caches_and_retired_authority_are_rejected(self) -> None:
        paths = [
            "evidence/sha256/ab/abcdef.pdf", "knowledge/records/.gitkeep",
            ".pcbknowledge/evidence/sha256/ab/abcdef.pdf",
            "knowledge/parts/original.pdf", "knowledge/parts/original.zip",
            "knowledge/intake/retired.json", "knowledge/entities/retired.json", "knowledge/facts/retired.json",
            "knowledge/sources/nested/source.json",
        ]
        self.assertEqual(public_distribution_violations(paths), tuple(sorted(paths)))

    def test_software_paths_are_allowed_subject_to_content_checks(self) -> None:
        self.assertEqual(public_distribution_violations([
            "src/pcbknowledge/v2/catalog.py",
            "tests/git_native/fixtures/synthetic-source.json",
            "docs/architecture.md", "vendor/pdfjs/pdf.mjs",
        ]), ())

    def test_windows_and_dot_prefixes_are_normalized(self) -> None:
        self.assertEqual(public_distribution_violations([
            r".\knowledge\parts\original.pdf"
        ]), ("knowledge/parts/original.pdf",))


class IndexedMetadataBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q")

    def git(self, *args: str) -> bytes:
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def stage(self, path: str, payload: bytes) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        self.git("add", "-f", "--", path)
        return target

    def test_small_paraphrased_metadata_is_allowed(self) -> None:
        self.stage("knowledge/parts/pilot.json", b'{"status":"DRAFT"}\n')
        self.stage("knowledge/parts/pilot-note.json", "# Review draft\n\u5f85\u9a8c\u6536\n".encode())
        self.stage("knowledge/sources/source-1.json", b"{}\n")
        self.assertEqual(check_public_distribution(self.root), ())

    def test_registry_allowlist_does_not_bypass_content_or_index_checks(self) -> None:
        path = "knowledge/registry/roles.json"
        target = self.stage(path, b'{"schema":"pcbknowledge.registry.v2"}\n')
        self.assertEqual(check_public_distribution(self.root), ())
        target.write_bytes(b"%PDF-1.4\noriginal")
        self.assertEqual(check_public_distribution(self.root), (path,))
        self.git("add", "--", path)
        target.write_bytes(b"{}\n")
        self.assertEqual(check_public_distribution(self.root), (path,))

    def test_pin_registry_names_keep_binary_and_unknown_path_guards(self) -> None:
        paths = [f'knowledge/registry/{name}.json'
                 for name in ('pin-functions', 'pin-states', 'unconnected-states')]
        for path in paths:
            self.stage(path, b'{"schema":"pcbknowledge.registry.v2"}\n')
        self.assertEqual(check_public_distribution(self.root), ())
        for path in paths:
            self.stage(path, b'\x00\xff')
        unknown = 'knowledge/registry/unknown-pin-states.json'
        self.stage(unknown, b'{}\n')
        self.assertEqual(check_public_distribution(self.root), tuple(sorted([*paths, unknown])))

    def test_index_bytes_cannot_be_hidden_by_clean_worktree(self) -> None:
        path = "knowledge/parts/disguised.json"
        target = self.stage(path, b"%PDF-1.4\noriginal bytes")
        target.write_text('{}\n', encoding="utf-8")
        self.assertEqual(check_public_distribution(self.root), (path,))

    def test_worktree_tamper_is_also_rejected(self) -> None:
        path = "knowledge/parts/pilot-note.json"
        target = self.stage(path, b"summary\n")
        target.write_bytes(b"summary\0binary\xff")
        self.assertEqual(check_public_distribution(self.root), (path,))

    def test_binary_large_and_nonempty_placeholder_rejected(self) -> None:
        paths = ["knowledge/parts/binary.json", "knowledge/parts/large.json",
                 "knowledge/sources/.gitkeep"]
        self.stage(paths[0], b"\xff\xfe\x00")
        self.stage(paths[1], b"a" * (MAX_METADATA_BYTES + 1))
        self.stage(paths[2], b"%PDF-1.4")
        self.assertEqual(check_public_distribution(self.root), tuple(sorted(paths)))

    def test_ignored_cache_force_add_is_rejected_but_untracked_cache_is_not_read(self) -> None:
        (self.root / ".gitignore").write_text("/.pcbknowledge/\n", encoding="utf-8")
        path = ".pcbknowledge/evidence/sha256/ab/original.pdf"
        target = self.root / path
        target.parent.mkdir(parents=True)
        target.write_bytes(b"%PDF-1.4\n")
        self.assertEqual(check_public_distribution(self.root), ())
        self.git("add", "-f", "--", path)
        self.assertEqual(check_public_distribution(self.root), (path,))

    def test_originals_binary_and_large_files_rejected_repo_wide(self) -> None:
        paths = ["downloads/original.pdf", "arbitraryfolder/payload.dat", "notes/huge.txt"]
        self.stage(paths[0], b"%PDF-1.4\n")
        binary = self.stage(paths[1], b"\xff\0binary")
        binary.write_text("clean worktree", encoding="utf-8")
        self.stage(paths[2], b"a" * (MAX_METADATA_BYTES + 1))
        self.assertEqual(check_public_distribution(self.root), tuple(sorted(paths)))

    def test_renamed_pdf_with_preamble_is_rejected(self) -> None:
        path = "misc/prefixed.txt"
        self.stage(path, b"junk preamble\n%PDF-1.7\noriginal bytes")
        self.assertEqual(check_public_distribution(self.root), (path,))

    def test_pdf_literal_in_software_source_is_not_an_original(self) -> None:
        self.stage("src/example.py", b'PDF_HEADER = b"%PDF-1.4"\n')
        self.stage("src/short.py", b"HEADER=b'%PDF-'\n")
        self.assertEqual(check_public_distribution(self.root), ())

    def test_only_exact_pinned_vendor_bytes_are_exempt(self) -> None:
        software_root = Path(__file__).resolve().parents[2]
        for path in PINNED_RUNTIME_FILES:
            self.stage(path, (software_root / path).read_bytes())
        self.assertEqual(check_public_distribution(self.root), ())
        path = next(path for path in PINNED_RUNTIME_FILES if "worker" in path)
        original = (self.root / path).read_bytes()
        # Same size, altered hash, staged payload cannot be hidden by clean disk.
        target = self.stage(path, b"X" + original[1:])
        target.write_bytes(original)
        self.assertEqual(check_public_distribution(self.root), (path,))
        self.stage(path, original)
        target.write_bytes(b"X" + original[1:])
        self.assertEqual(check_public_distribution(self.root), (path,))
        # Arbitrary file in the vendor directory is not exempt.
        extra = "src/pcbknowledge/static/vendor/pdfjs/6.2.108/new.mjs"
        self.stage(extra, b"a" * (MAX_METADATA_BYTES + 1))
        self.assertEqual(check_public_distribution(self.root), tuple(sorted((path, extra))))

    def test_existing_software_link_accepts_only_pinned_target_text(self) -> None:
        target = self.stage(".grok/skills", b"../.codex/skills")
        object_id = self.git("rev-parse", ":.grok/skills").decode().strip()
        self.git("update-index", "--cacheinfo", f"120000,{object_id},.grok/skills")
        # Windows checkouts can represent Git symlinks as regular target text.
        self.assertEqual(check_public_distribution(self.root), ())
        target.write_bytes(b"../../outside")
        self.assertEqual(check_public_distribution(self.root), (".grok/skills",))

    def test_native_windows_link_separators_preserve_exact_target_boundary(self) -> None:
        with patch("pcbknowledge.public_repo.os.sep", "\\"):
            self.assertEqual(_native_link_target_bytes(r"..\.codex\skills"), b"../.codex/skills")
            self.assertNotEqual(_native_link_target_bytes(r"..\outside\skills"), b"../.codex/skills")
        with patch("pcbknowledge.public_repo.os.sep", "/"):
            # Backslashes remain literal on POSIX, not path separators.
            self.assertNotEqual(_native_link_target_bytes(r"..\.codex\skills"), b"../.codex/skills")

    def test_pinned_actual_symlink_checks_normalized_native_target(self) -> None:
        target = self.stage(".grok/skills", b"../.codex/skills")
        object_id = self.git("rev-parse", ":.grok/skills").decode().strip()
        self.git("update-index", "--cacheinfo", f"120000,{object_id},.grok/skills")
        target.unlink()
        try:
            target.symlink_to("../.codex/skills", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable on this platform")
        self.assertEqual(check_public_distribution(self.root), ())
        with patch("pcbknowledge.public_repo.os.sep", "\\"):
            with patch("pcbknowledge.public_repo.os.readlink", return_value=r"..\.codex\skills"):
                self.assertEqual(check_public_distribution(self.root), ())
            with patch("pcbknowledge.public_repo.os.readlink", return_value=r"..\outside\skills"):
                self.assertEqual(check_public_distribution(self.root), (".grok/skills",))

    def test_symlink_index_mode_is_rejected_without_following_target(self) -> None:
        self.stage("knowledge/parts/safe.json", b"summary\n")
        object_id = self.git("rev-parse", ":knowledge/parts/safe.json").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"120000,{object_id},knowledge/parts/link.json")
        self.assertEqual(check_public_distribution(self.root), ("knowledge/parts/link.json",))


if __name__ == "__main__":
    unittest.main()
