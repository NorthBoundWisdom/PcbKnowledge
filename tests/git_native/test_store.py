from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityKind,
    EntityRecord,
    Evidence,
    EvidenceAnchor,
    FactRecord,
    FactType,
    LicenseClass,
    ParameterLimitKind,
    ParameterLimitPayload,
    PreparedBy,
    RecordStatus,
    RecordValidationError,
)
from pcbknowledge.git_native.store import (
    EvidenceError,
    RecordConflictError,
)
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class TypedKnowledgeRepositoryTests(RepositoryTestCase):
    def create_approved_source(self, key: str = "datasheet"):
        source = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN, idempotency_key=key
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf(key))
        complete = source.edit(
            title=f"Synthetic {key}",
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
        approved = complete.submit().approve("reviewed")
        self.repository.save_source(source, approved, source.revision_token)
        return approved

    def create_entities(self):
        manufacturer = self.repository.create_manufacturer(
            "Example Semiconductor",
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="manufacturer",
        )
        component = self.repository.create_component(
            manufacturer.id,
            "PK1000-A",
            family="PK1000",
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="component",
        )
        package = self.repository.create_package(
            "QFN-16",
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="package",
        )
        return manufacturer, component, package

    def create_pin_fact(self, source, component, package, key: str = "pin-1"):
        return self.repository.create_fact(
            idempotency_key=key,
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id,
                package.id,
                "1",
                "VIN",
                "Input supply",
                (),
            ),
            prepared_by=PreparedBy.AGENT,
            conditions=("QFN-16",),
            evidence_anchors=(
                EvidenceAnchor.create(
                    source.id,
                    2,
                    bbox=(0.1, 0.1, 0.5, 0.2),
                    quote="1 VIN Input supply",
                ),
            ),
        )

    def test_source_create_is_idempotent_and_stale_save_is_rejected(self) -> None:
        source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="supplier-datasheet-1",
        )
        replay = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="supplier-datasheet-1",
        )
        self.assertEqual(replay, source)

        updated = source.edit(
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
        self.repository.save_source(source, updated, source.revision_token)
        with self.assertRaisesRegex(RecordConflictError, "changed since"):
            self.repository.save_source(source, updated, source.revision_token)

    def test_invalid_schema_cannot_produce_approved_authority(self) -> None:
        source = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN, idempotency_key="schema-gate"
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf("schema gate"))
        ready = source.edit(
            title="Schema gate",
            document_number="DS-GATE",
            revision="A",
            source_locator=None,
            source_publisher="Fixture",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic",
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        ).submit()
        self.repository.save_source(source, ready, source.revision_token)

        schema_path = self.root / "schemas/source-record.schema.json"
        original = schema_path.read_text("utf-8")
        try:
            schema_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RecordValidationError, "schema"):
                self.repository.approve_source(
                    ready.id,
                    expected_revision=ready.revision_token,
                    comment="must not persist",
                )
            self.assertEqual(self.repository.load_source(ready.id), ready)
        finally:
            schema_path.write_text(original, encoding="utf-8")

    def test_pdf_is_content_addressed_deduplicated_and_verified(self) -> None:
        payload = minimal_pdf("same bytes")
        evidence = self.repository.import_pdf_bytes(payload)
        replay = self.repository.import_pdf_bytes(payload)

        self.assertEqual(replay, evidence)
        self.assertEqual(evidence.sha256, hashlib.sha256(payload).hexdigest())
        self.assertTrue((self.root / (evidence.path or "missing")).is_file())
        self.repository.verify_evidence(evidence)

        assert evidence.path is not None
        (self.root / evidence.path).write_bytes(minimal_pdf("tampered"))
        with self.assertRaisesRegex(EvidenceError, "size|hash"):
            self.repository.verify_evidence(evidence)

    def test_entities_are_idempotent_unique_and_referentially_closed(self) -> None:
        manufacturer, component, package = self.create_entities()
        self.assertEqual(
            self.repository.create_manufacturer(
                "Example Semiconductor",
                prepared_by=PreparedBy.HUMAN,
                idempotency_key="manufacturer",
            ),
            manufacturer,
        )
        self.assertEqual(
            self.repository.list_entities(kind=EntityKind.COMPONENT), [component]
        )
        self.assertIn(package, self.repository.list_entities())

        with self.assertRaisesRegex(RecordConflictError, "identity already exists"):
            self.repository.insert_entity(
                EntityRecord.manufacturer(
                    "ent_aaaaaaaaaaaaaaaaaaaaaaaa",
                    "Example Semiconductor",
                    prepared_by=PreparedBy.AGENT,
                )
            )
        with self.assertRaisesRegex(RecordValidationError, "missing entity"):
            self.repository.insert_entity(
                EntityRecord.component(
                    "ent_bbbbbbbbbbbbbbbbbbbbbbbb",
                    "ent_cccccccccccccccccccccccc",
                    "BROKEN",
                    prepared_by=PreparedBy.AGENT,
                )
            )

    def test_fact_approval_requires_correct_entity_source_and_anchor_closure(self) -> None:
        source = self.create_approved_source()
        _manufacturer, component, package = self.create_entities()
        fact = self.create_pin_fact(source, component, package)
        approved = self.repository.approve_fact(
            fact.id,
            expected_revision=self.repository.submit_fact(
                fact.id, expected_revision=fact.revision_token
            ).revision_token,
            comment="verified",
        )
        self.assertEqual(approved.status, RecordStatus.APPROVED)
        snapshot = self.repository.validate_all()
        self.assertEqual(snapshot.facts, (approved,))

        wrong_package = replace(
            approved,
            id="fact_aaaaaaaaaaaaaaaaaaaaaaaa",
            status=RecordStatus.DRAFT,
            payload=replace(approved.payload, package_id=component.id),
            review_history=(),
            review=type(approved.review)(),
        )
        with self.assertRaisesRegex(RecordValidationError, "must reference PACKAGE"):
            self.repository.insert_fact(wrong_package)

        missing_source = replace(
            wrong_package,
            id="fact_bbbbbbbbbbbbbbbbbbbbbbbb",
            payload=replace(approved.payload, pin_number="2"),
            evidence_anchors=(
                EvidenceAnchor.create("pk_aaaaaaaaaaaaaaaaaaaaaaaa", 1),
            ),
        )
        with self.assertRaisesRegex(RecordValidationError, "missing source"):
            self.repository.insert_fact(missing_source)

    def test_approved_fact_rejects_nonapproved_source_and_incomplete_anchor(self) -> None:
        source = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN, idempotency_key="draft-source"
        )
        _manufacturer, component, package = self.create_entities()
        draft = self.repository.create_fact(
            idempotency_key="incomplete-pin",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id, package.id, "1", None, "Ground", ()
            ),
            prepared_by=PreparedBy.AGENT,
            evidence_anchors=(EvidenceAnchor.create(source.id, 1),),
        )
        ready = self.repository.submit_fact(
            draft.id, expected_revision=draft.revision_token
        )
        with self.assertRaisesRegex(Exception, "complete_evidence_anchor"):
            self.repository.approve_fact(
                ready.id, expected_revision=ready.revision_token, comment=None
            )

        complete = ready.reject("anchor incomplete").edit(
            evidence_anchors=(
                EvidenceAnchor.create(
                    source.id,
                    1,
                    bbox=(0.1, 0.1, 0.2, 0.2),
                    quote="1 GND",
                ),
            )
        ).submit().approve(None)
        with self.assertRaisesRegex(RecordValidationError, "non-approved source"):
            self.repository.save_fact(ready, complete, ready.revision_token)

    def test_parameter_limit_fact_uses_numeric_payload(self) -> None:
        source = self.create_approved_source()
        _manufacturer, component, _package = self.create_entities()
        fact = self.repository.create_fact(
            idempotency_key="vin-abs-max",
            fact_type=FactType.PARAMETER_LIMIT,
            payload=ParameterLimitPayload(
                component.id,
                "Input voltage",
                ParameterLimitKind.ABSOLUTE_MAXIMUM,
                -0.3,
                None,
                40,
                "V",
            ),
            prepared_by=PreparedBy.AGENT,
            conditions=("TA = 25 °C",),
            evidence_anchors=(
                EvidenceAnchor.create(
                    source.id,
                    4,
                    bbox=(0.2, 0.2, 0.7, 0.3),
                    quote="Input voltage -0.3 to 40 V",
                ),
            ),
        )
        self.assertEqual(self.repository.load_fact(fact.id), fact)
        self.assertEqual(
            self.repository.list_facts(status=RecordStatus.DRAFT), [fact]
        )

    def test_unresolved_approved_semantic_conflict_is_blocked(self) -> None:
        source = self.create_approved_source()
        _manufacturer, component, package = self.create_entities()
        first = self.create_pin_fact(source, component, package, "first")
        first = self.repository.submit_fact(
            first.id, expected_revision=first.revision_token
        )
        first = self.repository.approve_fact(
            first.id, expected_revision=first.revision_token, comment=None
        )

        second = FactRecord.new(
            "fact_aaaaaaaaaaaaaaaaaaaaaaaa",
            fact_type=FactType.COMPONENT_PIN,
            payload=replace(first.payload, primary_function="Conflicting function"),
            prepared_by=PreparedBy.AGENT,
            conditions=first.conditions,
            applicability=first.applicability,
            evidence_anchors=first.evidence_anchors,
        )
        self.repository.insert_fact(second)
        second = self.repository.submit_fact(
            second.id, expected_revision=second.revision_token
        )
        with self.assertRaisesRegex(RecordValidationError, "second active APPROVED"):
            self.repository.approve_fact(
                second.id, expected_revision=second.revision_token, comment=None
            )

    def test_validate_all_rejects_layout_orphan_and_missing_supersedes(self) -> None:
        unexpected = self.repository.facts_dir / "notes.json"
        unexpected.write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected fact layout"):
            self.repository.validate_all()
        unexpected.unlink()

        evidence = self.repository.import_pdf_bytes(minimal_pdf("orphan"))
        with self.assertRaisesRegex(EvidenceError, "unreferenced evidence"):
            self.repository.validate_all()
        assert evidence.path is not None
        (self.root / evidence.path).unlink()

        source = self.repository.create_source(prepared_by=PreparedBy.HUMAN)
        invalid = source.edit(
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
        self.repository.source_path(source.id).write_text(
            invalid.canonical_json(), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "supersedes missing"):
            self.repository.validate_all()

    def test_supersedes_self_missing_and_cycle_fail_closed(self) -> None:
        first = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN, idempotency_key="cycle-first"
        )
        second = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN, idempotency_key="cycle-second"
        )
        with self.assertRaisesRegex(RecordValidationError, "cannot supersede itself"):
            replace(first, supersedes=first.id).validate()

        first_cycle = replace(first, supersedes=second.id).validate()
        second_cycle = replace(second, supersedes=first.id).validate()
        self.repository.source_path(first.id).write_text(
            first_cycle.canonical_json(), encoding="utf-8"
        )
        self.repository.source_path(second.id).write_text(
            second_cycle.canonical_json(), encoding="utf-8"
        )
        with self.assertRaisesRegex(RecordValidationError, "supersedes cycle"):
            self.repository.validate_all()

    def test_committed_source_fact_and_referenced_entity_are_immutable(self) -> None:
        source = self.create_approved_source("immutable")
        _manufacturer, component, package = self.create_entities()
        fact = self.create_pin_fact(source, component, package, "immutable-pin")
        fact = self.repository.submit_fact(
            fact.id, expected_revision=fact.revision_token
        )
        fact = self.repository.approve_fact(
            fact.id, expected_revision=fact.revision_token, comment="reviewed"
        )
        subprocess.run(
            ["git", "add", "knowledge", "evidence"], cwd=self.root, check=True
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
                "immutable authority",
            ],
            cwd=self.root,
            check=True,
        )

        source_path = self.repository.source_path(source.id)
        source_path.write_text(
            replace(source, title="silently changed").canonical_json(), encoding="utf-8"
        )
        with self.assertRaisesRegex(RecordValidationError, "source is immutable"):
            self.repository.validate_all()
        source_path.write_text(source.canonical_json(), encoding="utf-8")

        fact_path = self.repository.fact_path(fact.id)
        assert isinstance(fact.payload, ComponentPinPayload)
        fact_path.write_text(
            replace(
                fact,
                payload=replace(fact.payload, primary_function="silently changed"),
            ).canonical_json(),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(RecordValidationError, "fact is immutable"):
            self.repository.validate_all()
        fact_path.write_text(fact.canonical_json(), encoding="utf-8")

        component_path = self.repository.entity_path(component.id)
        component_path.unlink()
        with self.assertRaisesRegex(RecordValidationError, "must reference COMPONENT"):
            self.repository.validate_all()
        component_path.write_text(component.canonical_json(), encoding="utf-8")

        source_path.unlink()
        with self.assertRaisesRegex(RecordValidationError, "missing source"):
            self.repository.validate_all()
        source_path.write_text(source.canonical_json(), encoding="utf-8")

        fact_path.unlink()
        with self.assertRaisesRegex(RecordValidationError, "cannot be deleted"):
            self.repository.validate_all()

    def test_published_reader_uses_one_commit_and_ignores_worktree_draft(self) -> None:
        source = self.create_approved_source()
        _manufacturer, component, package = self.create_entities()
        fact = self.create_pin_fact(source, component, package)
        fact = self.repository.submit_fact(
            fact.id, expected_revision=fact.revision_token
        )
        fact = self.repository.approve_fact(
            fact.id, expected_revision=fact.revision_token, comment="reviewed"
        )
        subprocess.run(
            ["git", "add", "knowledge", "evidence"], cwd=self.root, check=True
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
                "approved typed fixture",
            ],
            cwd=self.root,
            check=True,
        )

        worktree_source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT, idempotency_key="worktree-only"
        )
        published = self.repository.read_published_snapshot()
        self.assertEqual(published.sources, (source,))
        self.assertEqual(published.facts, (fact,))
        self.assertNotIn(worktree_source, published.sources)
        self.assertEqual(len(published.entities), 3)


if __name__ == "__main__":
    import unittest

    unittest.main()
