from __future__ import annotations

import unittest

from pcbknowledge.git_native.public_repo import (
    ALLOWED_AUTHORITY_PLACEHOLDERS,
    public_distribution_violations,
)


class PublicRepositoryPolicyTests(unittest.TestCase):
    def test_only_expected_placeholders_are_allowed(self) -> None:
        self.assertEqual(
            public_distribution_violations(ALLOWED_AUTHORITY_PLACEHOLDERS),
            (),
        )

    def test_real_knowledge_records_are_rejected(self) -> None:
        self.assertEqual(
            public_distribution_violations(
                [
                    "knowledge/sources/source-1.json",
                    "knowledge/entities/component-1.json",
                    "knowledge/facts/fact-1.json",
                ]
            ),
            (
                "knowledge/entities/component-1.json",
                "knowledge/facts/fact-1.json",
                "knowledge/sources/source-1.json",
            ),
        )

    def test_real_evidence_is_rejected(self) -> None:
        self.assertEqual(
            public_distribution_violations(
                ["evidence/sha256/ab/abcdef.pdf", "evidence/sha256/.gitkeep"]
            ),
            ("evidence/sha256/ab/abcdef.pdf",),
        )

    def test_legacy_record_root_is_rejected(self) -> None:
        self.assertEqual(
            public_distribution_violations(["knowledge/records/.gitkeep"]),
            ("knowledge/records/.gitkeep",),
        )

    def test_unrelated_code_and_synthetic_tests_are_ignored(self) -> None:
        self.assertEqual(
            public_distribution_violations(
                [
                    "src/pcbknowledge/git_native/model.py",
                    "tests/git_native/fixtures/synthetic-source.json",
                    "docs/architecture.md",
                ]
            ),
            (),
        )

    def test_windows_and_dot_prefixes_are_normalized(self) -> None:
        self.assertEqual(
            public_distribution_violations(
                [r".\knowledge\sources\source-1.json"]
            ),
            ("knowledge/sources/source-1.json",),
        )


if __name__ == "__main__":
    unittest.main()
