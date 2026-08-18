from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from configs.check_english_repo import check_english_repository


class EnglishRepositoryPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def track(self, relative: str, content: str | bytes) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", relative], cwd=self.root, check=True)

    def test_english_source_tree_passes(self) -> None:
        self.track("README.md", "English documentation only.\n")
        self.track("src/example.py", '# Comment and UI text are English.\nLABEL = "Review"\n')
        self.assertEqual(check_english_repository(self.root), ())

    def test_cjk_text_is_reported_without_storing_cjk_in_this_test_file(self) -> None:
        disallowed = chr(0x4E2D) + chr(0x6587)
        self.track("README.md", f"Unexpected {disallowed} text\n")
        violations = check_english_repository(self.root)
        self.assertEqual(len(violations), 2)
        self.assertTrue(all(item.path == "README.md" for item in violations))
        self.assertTrue(all(item.line == 1 for item in violations))

    def test_kana_and_hangul_are_rejected(self) -> None:
        text = chr(0x30C6) + chr(0xD14C)
        self.track("fixture.txt", text)
        self.assertEqual(len(check_english_repository(self.root)), 2)

    def test_binary_files_are_not_decoded_as_repository_text(self) -> None:
        self.track("fixture.bin", b"\x00\xe4\xb8\xad")
        self.assertEqual(check_english_repository(self.root), ())


if __name__ == "__main__":
    unittest.main()
