from __future__ import annotations

import contextlib
import io
import json

from pcbknowledge.git_native.cli import main, parse_args
from tests.git_native.support import RepositoryTestCase


class AgentCliTests(RepositoryTestCase):
    def call(self, *arguments: str) -> tuple[int, str, str]:
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(["--repo", str(self.root), *arguments])
        return code, output.getvalue(), errors.getvalue()

    def test_agent_create_list_update_and_submit_share_repository_files(self) -> None:
        code, output, errors = self.call(
            "create",
            "--idempotency-key",
            "agent-task-1",
            "--title",
            "Agent draft",
        )
        self.assertEqual((code, errors), (0, ""))
        created = json.loads(output)
        self.assertEqual(created["prepared_by"], "AGENT")
        self.assertEqual(created["source_type"], "DATASHEET")
        self.assertFalse(created["replayed"])

        code, output, _ = self.call("list")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)[0]["id"], created["id"])

        code, output, errors = self.call(
            "update",
            created["id"],
            "--expected-revision",
            created["revision_token"],
            "--revision",
            "A",
        )
        self.assertEqual((code, errors), (0, ""))
        updated = json.loads(output)
        self.assertEqual(updated["revision"], "A")

        code, output, errors = self.call(
            "submit",
            created["id"],
            "--expected-revision",
            updated["revision_token"],
        )
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(json.loads(output)["status"], "READY_FOR_REVIEW")

    def test_replayed_create_with_different_content_fails(self) -> None:
        self.assertEqual(
            self.call(
                "create", "--idempotency-key", "same", "--title", "First"
            )[0],
            0,
        )
        code, _, errors = self.call(
            "create", "--idempotency-key", "same", "--title", "Different"
        )
        self.assertEqual(code, 2)
        self.assertIn("different content", errors)

    def test_agent_cli_exposes_no_review_or_commit_command(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["approve"])
            with self.assertRaises(SystemExit):
                parse_args(["commit"])

    def test_invalid_metadata_does_not_leave_record_or_evidence_files(self) -> None:
        pdf = self.root / "source.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        code, _, errors = self.call(
            "create",
            "--idempotency-key",
            "invalid-before-write",
            "--pdf",
            str(pdf),
            "--supersedes",
            "not-a-record-id",
            "--license-class",
            "PUBLIC_REFERENCE",
        )

        self.assertEqual(code, 2)
        self.assertIn("supersedes", errors)
        self.assertEqual(list(self.repository.records_dir.glob("*.json")), [])
        self.assertEqual(list(self.repository.evidence_dir.rglob("*.pdf")), [])

    def test_agent_pdf_processing_fails_closed_for_unknown_or_blocked_license(self) -> None:
        pdf = self.root / "blocked.pdf"
        pdf.write_bytes(b"not even opened as a PDF")
        for license_class in ("UNKNOWN", "LICENSED_BLOCKED_FOR_AI", "RESTRICTED"):
            with self.subTest(license_class=license_class):
                code, _, errors = self.call(
                    "create",
                    "--idempotency-key",
                    f"blocked-{license_class}",
                    "--license-class",
                    license_class,
                    "--pdf",
                    str(pdf),
                )
                self.assertEqual(code, 2)
                self.assertIn("processing is blocked", errors)
        self.assertEqual(list(self.repository.sources_dir.glob("*.json")), [])
        self.assertEqual(list(self.repository.evidence_dir.rglob("*.pdf")), [])


if __name__ == "__main__":
    import unittest

    unittest.main()
