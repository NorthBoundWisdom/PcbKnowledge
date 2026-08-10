from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace

from pcbknowledge.git_native.model import Evidence, LicenseClass, PreparedBy, RecordStatus
from pcbknowledge.git_native.store import (
    EvidenceError,
    RecordConflictError,
)
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class KnowledgeRepositoryTests(RepositoryTestCase):
    def test_create_is_idempotent_and_stale_save_is_rejected(self) -> None:
        record = self.repository.create(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="supplier-datasheet-1",
        )
        replay = self.repository.create(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="supplier-datasheet-1",
        )
        self.assertEqual(replay, record)

        updated = record.edit(
            title="Datasheet",
            document_number=None,
            revision=None,
            source_locator=None,
            source_publisher=None,
            license_class=LicenseClass.UNKNOWN,
            license_note=None,
            evidence=Evidence(),
            preparation_note=None,
            supersedes=None,
        )
        self.repository.save(record, updated, record.revision_token)
        with self.assertRaisesRegex(RecordConflictError, "changed since"):
            self.repository.save(record, updated, record.revision_token)

    def test_pdf_is_content_addressed_deduplicated_and_verified(self) -> None:
        payload = minimal_pdf("same bytes")
        evidence = self.repository.import_pdf_bytes(payload)
        replay = self.repository.import_pdf_bytes(payload)

        self.assertEqual(replay, evidence)
        self.assertEqual(evidence.sha256, hashlib.sha256(payload).hexdigest())
        self.assertTrue((self.root / (evidence.path or "missing")).is_file())
        self.repository.verify_evidence(evidence)

    def test_invalid_or_mutated_pdf_fails_closed(self) -> None:
        with self.assertRaisesRegex(EvidenceError, "not a PDF"):
            self.repository.import_pdf_bytes(b"not a PDF")

        evidence = self.repository.import_pdf_bytes(minimal_pdf())
        assert evidence.path is not None
        (self.root / evidence.path).write_bytes(minimal_pdf("tampered"))
        with self.assertRaisesRegex(EvidenceError, "size|hash"):
            self.repository.verify_evidence(evidence)

    def test_approved_record_is_immutable(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        evidence = self.repository.import_pdf_bytes(minimal_pdf())
        complete = record.edit(
            title="Datasheet",
            document_number="D-1",
            revision="A",
            source_locator="https://example.test/d.pdf",
            source_publisher="Example",
            license_class=LicenseClass.OPEN,
            license_note=None,
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )
        ready = complete.submit()
        approved = ready.approve("reviewed")
        self.repository.save(record, approved, record.revision_token)

        with self.assertRaisesRegex(Exception, "immutable|READY_FOR_REVIEW"):
            self.repository.save(
                approved,
                replace(approved, title="silently changed"),
                approved.revision_token,
            )

    def test_validate_all_checks_supersedes_and_evidence(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        invalid = record.edit(
            title=None,
            document_number=None,
            revision=None,
            source_locator=None,
            source_publisher=None,
            license_class=LicenseClass.UNKNOWN,
            license_note=None,
            evidence=Evidence(),
            preparation_note=None,
            supersedes="pk_aaaaaaaaaaaaaaaaaaaaaaaa",
        )
        self.repository.save(record, invalid, record.revision_token)
        with self.assertRaisesRegex(ValueError, "supersedes missing"):
            self.repository.validate_all()

    def test_git_changes_include_untracked_json_and_binary_receipt(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        evidence = self.repository.import_pdf_bytes(minimal_pdf())
        changes = self.repository.git_changes()

        self.assertGreaterEqual(changes.count, 2)
        self.assertIn(record.id, changes.untracked_preview)
        self.assertIn(evidence.sha256 or "missing", changes.untracked_preview)
        self.assertIn("new binary evidence", changes.untracked_preview)

    def test_status_filter_is_deterministic(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        ready = record.submit()
        self.repository.save(record, ready, record.revision_token)
        self.assertEqual(self.repository.list(status=RecordStatus.READY_FOR_REVIEW), [ready])
        self.assertEqual(self.repository.list(status=RecordStatus.APPROVED), [])

    def test_validator_rejects_unknown_layout_and_orphaned_evidence(self) -> None:
        unexpected = self.repository.records_dir / "notes.json"
        unexpected.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected record layout"):
            self.repository.validate_all()
        unexpected.unlink()

        evidence = self.repository.import_pdf_bytes(minimal_pdf("orphan"))
        with self.assertRaisesRegex(EvidenceError, "unreferenced evidence"):
            self.repository.validate_all()
        assert evidence.path is not None
        (self.root / evidence.path).unlink()
        self.repository.validate_all()

    def test_committed_approved_record_cannot_be_rewritten_or_deleted(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        evidence = self.repository.import_pdf_bytes(minimal_pdf("committed"))
        approved = record.edit(
            title="Committed evidence",
            document_number="DS-1",
            revision="A",
            source_locator=None,
            source_publisher="Publisher",
            license_class=LicenseClass.OPEN,
            license_note=None,
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        ).submit().approve("reviewed")
        self.repository.save(record, approved, record.revision_token)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "add", "knowledge", "evidence"],
            cwd=self.root,
            check=True,
        )
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
                "approved fixture",
            ],
            cwd=self.root,
            check=True,
        )

        path = self.repository.record_path(record.id)
        path.write_text(replace(approved, title="Silently rewritten").canonical_json(), "utf-8")
        with self.assertRaisesRegex(ValueError, "committed approved record is immutable"):
            self.repository.validate_all()

        path.write_text(approved.canonical_json(), "utf-8")
        path.unlink()
        with self.assertRaisesRegex(ValueError, "committed approved record cannot be deleted"):
            self.repository.validate_all()
