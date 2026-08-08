from __future__ import annotations

import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

from pcbknowledge.git_native.store import KnowledgeRepository


class RepositoryTestCase(unittest.TestCase):
    temporary: tempfile.TemporaryDirectory[str]
    root: Path
    repository: KnowledgeRepository

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        repository_root = Path(__file__).resolve().parents[2]
        shutil.copytree(repository_root / "schemas", self.root / "schemas")
        shutil.copy2(repository_root / ".gitignore", self.root / ".gitignore")
        subprocess.run(["git", "add", "schemas", ".gitignore"], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-q",
                "-m",
                "typed schema fixture",
            ],
            cwd=self.root,
            check=True,
        )
        self.repository = KnowledgeRepository(self.root)
        self.repository.ensure_layout()

    def tearDown(self) -> None:
        self.temporary.cleanup()


def minimal_pdf(label: str = "test") -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog>>endobj\n"
        + f"% {label}\n".encode()
        + b"%%EOF\n"
    )
