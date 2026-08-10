from __future__ import annotations

import contextlib
import io
import json
import subprocess

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.model import Evidence, LicenseClass, PreparedBy
from pcbknowledge.git_native.store import ChangeScope, RepositoryError
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class GitNativeHardeningTests(RepositoryTestCase):
    def _complete(self, record, evidence):
        return record.edit(
            title="Datasheet",
            document_number="DS-1",
            revision="A",
            source_locator="https://example.test/d.pdf",
            source_publisher="Example",
            license_class=LicenseClass.OPEN,
            license_note=None,
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )

    def test_replacing_draft_evidence_prunes_unreferenced_bytes(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        old = self.repository.import_pdf_bytes(minimal_pdf("old"))
        first = self._complete(record, old)
        self.repository.save(record, first, record.revision_token)
        new = self.repository.import_pdf_bytes(minimal_pdf("new"))
        second = first.edit(
            title=first.title, document_number=first.document_number, revision=first.revision,
            source_locator=first.source.locator, source_publisher=first.source.publisher,
            license_class=first.license_class, license_note=first.license_note,
            evidence=new, preparation_note=first.preparation_note, supersedes=first.supersedes,
        )
        self.repository.save(first, second, first.revision_token)
        assert old.path is not None
        self.assertFalse((self.root / old.path).exists())
        self.repository.validate_all()

    def test_shared_evidence_is_not_pruned(self) -> None:
        first = self.repository.create(prepared_by=PreparedBy.HUMAN)
        shared = self.repository.import_pdf_bytes(minimal_pdf("shared"))
        first_ready = self._complete(first, shared)
        self.repository.save(first, first_ready, first.revision_token)
        second = self.repository.create(prepared_by=PreparedBy.HUMAN)
        second_ready = self._complete(second, shared)
        self.repository.save(second, second_ready, second.revision_token)
        replacement = self.repository.import_pdf_bytes(minimal_pdf("replacement"))
        updated = first_ready.edit(
            title=first_ready.title, document_number=first_ready.document_number, revision=first_ready.revision,
            source_locator=first_ready.source.locator, source_publisher=first_ready.source.publisher,
            license_class=first_ready.license_class, license_note=first_ready.license_note,
            evidence=replacement, preparation_note=first_ready.preparation_note, supersedes=first_ready.supersedes,
        )
        self.repository.save(first_ready, updated, first_ready.revision_token)
        assert shared.path is not None
        self.assertTrue((self.root / shared.path).is_file())

    def test_published_view_requires_committed_approval(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        evidence = self.repository.import_pdf_bytes(minimal_pdf("published"))
        approved = self._complete(record, evidence).submit().approve("reviewed")
        self.repository.save(record, approved, record.revision_token)
        self.assertEqual(self.repository.list_published(), [])
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "add", "knowledge", "evidence"], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "-q", "-m", "publish fixture"], cwd=self.root, check=True)
        self.assertEqual(self.repository.list_published(), [approved])

    def test_change_scope_rejects_mixed_candidate(self) -> None:
        self.repository.create(prepared_by=PreparedBy.HUMAN)
        (self.root / "README.md").write_text("code-side change\n", encoding="utf-8")
        self.assertEqual(self.repository.git_change_scope(), ChangeScope.MIXED)
        with self.assertRaisesRegex(RepositoryError, "mixed knowledge/evidence"):
            self.repository.validate_change_scope()

    def test_agent_cli_published_and_change_scope_contract(self) -> None:
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(["--repo", str(self.root), "list", "--published"])
        self.assertEqual((code, errors.getvalue()), (0, ""))
        self.assertEqual(json.loads(output.getvalue()), [])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--repo", str(self.root), "change-scope"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["scope"], "CLEAN")


if __name__ == "__main__":
    import unittest
    unittest.main()
