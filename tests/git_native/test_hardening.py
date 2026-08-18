from __future__ import annotations

import contextlib
import io
import json
import subprocess
import threading

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.model import (
    Evidence,
    LicenseClass,
    PreparedBy,
    SourceRecord,
    deterministic_record_id,
)
from pcbknowledge.git_native.store import (
    ChangeScope,
    EvidenceError,
    KnowledgeRepository,
    RepositoryError,
)
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class GitNativeHardeningTests(RepositoryTestCase):
    def _complete(self, record, evidence):
        return record.edit(
            title="Datasheet",
            document_number="DS-1",
            revision="A",
            source_locator="https://example.test/d.pdf",
            source_publisher="Example",
            license_class=LicenseClass.PUBLIC_REFERENCE,
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

    def test_published_view_requires_evidence_in_the_same_git_snapshot(self) -> None:
        record = self.repository.create(prepared_by=PreparedBy.HUMAN)
        evidence = self.repository.import_pdf_bytes(minimal_pdf("not committed"))
        approved = self._complete(record, evidence).submit().approve("reviewed")
        self.repository.save(record, approved, record.revision_token)
        subprocess.run(["git", "add", "knowledge"], cwd=self.root, check=True)
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
                "record without evidence",
            ],
            cwd=self.root,
            check=True,
        )

        with self.assertRaisesRegex(EvidenceError, "missing from HEAD"):
            self.repository.list_published()

    def test_published_view_rejects_record_filename_identity_mismatch(self) -> None:
        record = SourceRecord.new(
            "pk_aaaaaaaaaaaaaaaaaaaaaaaa", prepared_by=PreparedBy.HUMAN
        )
        wrong_path = self.root / "knowledge/sources/pk_bbbbbbbbbbbbbbbbbbbbbbbb.json"
        wrong_path.write_text(record.canonical_json(), encoding="utf-8")
        subprocess.run(["git", "add", "knowledge"], cwd=self.root, check=True)
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
                "mismatched record",
            ],
            cwd=self.root,
            check=True,
        )

        with self.assertRaisesRegex(ValueError, "does not match filename"):
            self.repository.list_published()

    def test_published_view_rejects_git_symlinks(self) -> None:
        record = SourceRecord.new(
            "pk_aaaaaaaaaaaaaaaaaaaaaaaa", prepared_by=PreparedBy.HUMAN
        )
        relative = f"knowledge/sources/{record.id}.json"
        # Build the symlink directly in the Git index. This tests the published
        # tree mode itself and does not depend on OS symlink privileges.
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=self.root,
            input=record.canonical_json().encode("utf-8"),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.decode("ascii").strip()
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"120000,{blob},{relative}"],
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
                "symlink record",
            ],
            cwd=self.root,
            check=True,
        )

        with self.assertRaisesRegex(RepositoryError, "not a regular"):
            self.repository.list_published()

    def test_published_view_rejects_retired_legacy_authority(self) -> None:
        legacy = self.root / "knowledge/records/pk_aaaaaaaaaaaaaaaaaaaaaaaa.json"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("{}\n", encoding="utf-8")
        subprocess.run(["git", "add", "knowledge"], cwd=self.root, check=True)
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
                "retired legacy authority",
            ],
            cwd=self.root,
            check=True,
        )

        with self.assertRaisesRegex(ValueError, "retired knowledge/records"):
            self.repository.list_published()

    def test_change_scope_rejects_mixed_candidate(self) -> None:
        self.repository.create(prepared_by=PreparedBy.HUMAN)
        (self.root / "README.md").write_text("code-side change\n", encoding="utf-8")
        self.assertEqual(self.repository.git_change_scope(), ChangeScope.MIXED)
        with self.assertRaisesRegex(RepositoryError, "mixed knowledge/evidence"):
            self.repository.validate_change_scope()

    def test_change_scope_counts_both_sides_of_a_staged_rename(self) -> None:
        readme = self.root / "README.md"
        readme.write_text("policy\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
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
                "base",
            ],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            ["git", "mv", "README.md", "knowledge/README.md"],
            cwd=self.root,
            check=True,
        )

        self.assertEqual(self.repository.git_change_scope(), ChangeScope.MIXED)

    def test_change_scope_uses_staged_candidate_before_unstaged_workspace(self) -> None:
        readme = self.root / "README.md"
        readme.write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.root, check=True)
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
                "base",
            ],
            cwd=self.root,
            check=True,
        )
        data = self.root / "knowledge/sources/staged-note.txt"
        data.write_text("data candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", data.relative_to(self.root)], cwd=self.root, check=True)
        readme.write_text("unstaged code change\n", encoding="utf-8")

        self.assertEqual(self.repository.git_change_scope(), ChangeScope.DATA_ONLY)

    def test_evidence_pruning_is_serialized_against_new_references(self) -> None:
        prune_entered = threading.Event()
        allow_prune = threading.Event()

        class PausingRepository(KnowledgeRepository):
            pause = False

            def _prune_replaced_evidence(self, previous, updated):
                if self.pause:
                    prune_entered.set()
                    if not allow_prune.wait(3):
                        raise AssertionError("test did not release evidence pruning")
                return super()._prune_replaced_evidence(previous, updated)

        writer = PausingRepository(self.root)
        first = writer.create(prepared_by=PreparedBy.HUMAN)
        old = writer.import_pdf_bytes(minimal_pdf("old concurrent evidence"))
        initial = self._complete(first, old)
        writer.save(first, initial, first.revision_token)
        replacement = writer.import_pdf_bytes(minimal_pdf("replacement evidence"))
        updated = initial.edit(
            title=initial.title,
            document_number=initial.document_number,
            revision=initial.revision,
            source_locator=initial.source.locator,
            source_publisher=initial.source.publisher,
            license_class=initial.license_class,
            license_note=initial.license_note,
            evidence=replacement,
            preparation_note=initial.preparation_note,
            supersedes=initial.supersedes,
        )
        concurrent = SourceRecord.new(
            deterministic_record_id("concurrent-reference"),
            prepared_by=PreparedBy.AGENT,
        ).edit(
            title="Concurrent",
            document_number=None,
            revision="A",
            source_locator=None,
            source_publisher="Example",
            license_class=LicenseClass.PUBLIC_REFERENCE,
            license_note=None,
            evidence=old,
            preparation_note=None,
            supersedes=None,
        )
        save_errors: list[BaseException] = []
        insert_errors: list[BaseException] = []
        insert_done = threading.Event()

        def replace_evidence() -> None:
            try:
                writer.pause = True
                writer.save(initial, updated, initial.revision_token)
            except BaseException as error:
                save_errors.append(error)

        def insert_reference() -> None:
            try:
                KnowledgeRepository(self.root).insert(concurrent)
            except BaseException as error:
                insert_errors.append(error)
            finally:
                insert_done.set()

        save_thread = threading.Thread(target=replace_evidence)
        save_thread.start()
        self.assertTrue(prune_entered.wait(3))
        insert_thread = threading.Thread(target=insert_reference)
        insert_thread.start()
        self.assertFalse(insert_done.wait(0.1), "insert did not wait for repository write lock")
        allow_prune.set()
        save_thread.join(3)
        insert_thread.join(3)

        self.assertFalse(save_thread.is_alive())
        self.assertFalse(insert_thread.is_alive())
        self.assertEqual(save_errors, [])
        self.assertEqual(len(insert_errors), 1)
        self.assertIsInstance(insert_errors[0], EvidenceError)
        self.assertFalse(writer.record_path(concurrent.id).exists())
        writer.validate_all()

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
