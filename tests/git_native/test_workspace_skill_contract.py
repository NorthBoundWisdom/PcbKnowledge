from __future__ import annotations

import unittest
from pathlib import Path


class WorkspaceSkillContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]
    SKILLS = (
        "ingest-engineering-source",
        "resolve-component-identity",
        "extract-component-facts",
        "prepare-knowledge-review",
    )

    def test_agent_skills_require_one_explicit_workspace(self) -> None:
        for name in self.SKILLS:
            with self.subTest(skill=name):
                source = (
                    self.ROOT / ".codex/skills" / name / "SKILL.md"
                ).read_text(encoding="utf-8")
                self.assertIn(
                    "python3 configs/pcbknowledge_workspace.py validate '<workspace>'",
                    source,
                )
                self.assertIn("--repo '<workspace>'", source)
                self.assertIn("INVALID_WORKSPACE", source)
                self.assertNotIn("--repo .", source)


if __name__ == "__main__":
    unittest.main()
