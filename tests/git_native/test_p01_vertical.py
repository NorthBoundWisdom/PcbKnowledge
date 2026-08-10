from __future__ import annotations

import json
import subprocess
import zipfile

from configs import pcbknowledge_workflow as workflow
from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    ParameterLimitKind,
    ParameterLimitPayload,
    PreparedBy,
    RecordStatus,
    ReviewAction,
)
from pcbknowledge.git_native.store import KnowledgeRepository
from tests.git_native.support import minimal_pdf
from tests.git_native.test_workflow import WorkflowTestCase


class P01SyntheticVerticalTests(WorkflowTestCase):
    def test_complete_typed_authority_publication_and_package_gate(self) -> None:
        repository = KnowledgeRepository(self.root)
        repository.ensure_layout()

        # Schemas are software contract and are committed separately from data.
        subprocess.run(["git", "add", "schemas"], cwd=self.root, check=True)
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
                "typed schemas",
            ],
            cwd=self.root,
            check=True,
        )

        source = repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="synthetic-p01-datasheet-rev-a",
        )
        evidence = repository.import_pdf_bytes(minimal_pdf("P0.1 synthetic datasheet"))
        approved_source = source.edit(
            title="PK1000 Synthetic Datasheet",
            document_number="PK-DS-1000",
            revision="A",
            source_locator="https://example.invalid/pk1000-a.pdf",
            source_publisher="PcbKnowledge Test Fixtures",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic fixture generated for repository tests",
            evidence=evidence,
            preparation_note="No real manufacturer material",
            supersedes=None,
        ).submit().approve("synthetic source reviewed")
        repository.save_source(source, approved_source, source.revision_token)

        manufacturer = repository.create_manufacturer(
            "PcbKnowledge Test Fixtures",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="synthetic-manufacturer",
        )
        component = repository.create_component(
            manufacturer.id,
            "PK1000-Q16",
            family="PK1000",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="synthetic-component",
        )
        package = repository.create_package(
            "QFN-16",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="synthetic-package",
        )

        facts = []
        for pin_number, pin_name, function in (
            ("1", "VIN", "Input supply"),
            ("2", "GND", "Ground"),
            ("3", "EN", "Enable input"),
            ("4", "SW", "Switch node"),
            ("5", "FB", "Feedback input"),
        ):
            fact = repository.create_fact(
                idempotency_key=f"synthetic-pin-{pin_number}",
                fact_type=FactType.COMPONENT_PIN,
                payload=ComponentPinPayload(
                    component.id,
                    package.id,
                    pin_number,
                    pin_name,
                    function,
                    (),
                ),
                prepared_by=PreparedBy.AGENT,
                conditions=("QFN-16 package",),
                applicability=("PK1000-Q16",),
                evidence_anchors=(
                    EvidenceAnchor.create(
                        approved_source.id,
                        2,
                        bbox=(0.1, 0.1, 0.8, 0.2),
                        quote=f"{pin_number} {pin_name} {function}",
                    ),
                ),
            )
            ready = repository.submit_fact(
                fact.id, expected_revision=fact.revision_token
            )
            if pin_number == "1":
                rejected = repository.reject_fact(
                    ready.id,
                    expected_revision=ready.revision_token,
                    comment="Confirm package applicability",
                )
                edited = rejected.edit(
                    applicability=("PK1000-Q16 orderable component",)
                )
                repository.save_fact(rejected, edited, rejected.revision_token)
                ready = repository.submit_fact(
                    edited.id, expected_revision=edited.revision_token
                )
            approved = repository.approve_fact(
                ready.id,
                expected_revision=ready.revision_token,
                comment="anchor and typed payload verified",
            )
            facts.append(approved)

        for key, parameter, kind, minimum, typical, maximum, unit in (
            (
                "vin-abs",
                "Input voltage",
                ParameterLimitKind.ABSOLUTE_MAXIMUM,
                -0.3,
                None,
                40,
                "V",
            ),
            (
                "vin-rec",
                "Input voltage",
                ParameterLimitKind.RECOMMENDED_OPERATING,
                4.5,
                12,
                36,
                "V",
            ),
            (
                "junction",
                "Junction temperature",
                ParameterLimitKind.ABSOLUTE_MAXIMUM,
                -40,
                None,
                150,
                "°C",
            ),
        ):
            fact = repository.create_fact(
                idempotency_key=f"synthetic-limit-{key}",
                fact_type=FactType.PARAMETER_LIMIT,
                payload=ParameterLimitPayload(
                    component.id,
                    parameter,
                    kind,
                    minimum,
                    typical,
                    maximum,
                    unit,
                ),
                prepared_by=PreparedBy.AGENT,
                conditions=("Unless otherwise noted",),
                applicability=("PK1000-Q16",),
                evidence_anchors=(
                    EvidenceAnchor.create(
                        approved_source.id,
                        4,
                        bbox=(0.1, 0.3, 0.9, 0.5),
                        quote=f"{parameter}: {minimum}, {typical}, {maximum} {unit}",
                    ),
                ),
            )
            ready = repository.submit_fact(
                fact.id, expected_revision=fact.revision_token
            )
            facts.append(
                repository.approve_fact(
                    ready.id,
                    expected_revision=ready.revision_token,
                    comment="numeric limit verified",
                )
            )

        snapshot = repository.validate_all(require_canonical=True)
        self.assertEqual(
            (len(snapshot.sources), len(snapshot.entities), len(snapshot.facts)),
            (1, 3, 8),
        )
        self.assertEqual(snapshot.conflicts, ())
        self.assertTrue(all(fact.status is RecordStatus.APPROVED for fact in facts))
        self.assertTrue(
            all(
                anchor.complete
                for fact in snapshot.facts
                for anchor in fact.evidence_anchors
            )
        )
        self.assertEqual(
            [event.action for event in facts[0].review_history],
            [
                ReviewAction.SUBMITTED,
                ReviewAction.REJECTED,
                ReviewAction.SUBMITTED,
                ReviewAction.APPROVED,
            ],
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
                "synthetic typed authority",
            ],
            cwd=self.root,
            check=True,
        )

        published = repository.read_published_snapshot()
        self.assertEqual(
            (len(published.sources), len(published.entities), len(published.facts)),
            (1, 3, 8),
        )
        self.assertEqual(published.commit, repository._resolve_git_ref("HEAD"))

        self.prepare_receipts()
        first_package = workflow.create_package(self.root)
        first_bytes = first_package.read_bytes()
        second_package = workflow.create_package(self.root)
        self.assertEqual(first_package, second_package)
        self.assertEqual(first_bytes, second_package.read_bytes())
        with zipfile.ZipFile(first_package) as archive:
            names = set(archive.namelist())
            self.assertIn("schemas/source-record.schema.json", names)
            self.assertIn("schemas/entity-record.schema.json", names)
            self.assertIn("schemas/fact-record.schema.json", names)
            self.assertIn(f"knowledge/sources/{approved_source.id}.json", names)
            self.assertIn(f"knowledge/entities/{component.id}.json", names)
            self.assertIn(f"knowledge/facts/{facts[0].id}.json", names)
            self.assertIn(evidence.path, names)
            manifest = json.loads(archive.read("MANIFEST.json"))
            self.assertEqual(manifest["format"], workflow.PACKAGE_FORMAT)

        worktree_only = repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="uncommitted-working-tree-source",
        )
        republished = repository.read_published_snapshot()
        self.assertNotIn(worktree_only, republished.sources)
        self.assertEqual(republished, published)


if __name__ == "__main__":
    import unittest

    unittest.main()
