from __future__ import annotations

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    PreparedBy,
    RecordStatus,
)
from pcbknowledge.git_native.workbench import WorkbenchApplication
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class TypedWorkbenchApplicationTests(RepositoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.application = WorkbenchApplication(self.repository)

    def make_review_closure(self):
        source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03a-source",
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf("p03a datasheet"))
        draft = source.edit(
            title="PK3000 Synthetic Datasheet",
            document_number="PK-DS-3000",
            revision="A",
            source_locator="https://example.invalid/pk3000-a.pdf",
            source_publisher="PcbKnowledge Fixtures",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic fixture",
            evidence=evidence,
            preparation_note="Prepared for P0.3a review tests",
            supersedes=None,
        )
        self.repository.save_source(source, draft, source.revision_token)
        source = self.repository.submit_source(
            draft.id, expected_revision=draft.revision_token
        )

        manufacturer = self.repository.create_manufacturer(
            "PcbKnowledge Fixtures",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03a-manufacturer",
        )
        component = self.repository.create_component(
            manufacturer.id,
            "PK3000-Q16",
            family="PK3000",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03a-component",
        )
        package = self.repository.create_package(
            "QFN-16",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03a-package",
        )

        facts = []
        for key, function in (
            ("p03a-pin-primary", "Input supply"),
            ("p03a-pin-conflict", "Conflicting input function"),
        ):
            fact = self.repository.create_fact(
                idempotency_key=key,
                fact_type=FactType.COMPONENT_PIN,
                payload=ComponentPinPayload(
                    component.id,
                    package.id,
                    "1",
                    "VIN",
                    function,
                    (),
                ),
                prepared_by=PreparedBy.AGENT,
                conditions=("QFN-16 package",),
                applicability=("PK3000-Q16",),
                evidence_anchors=(
                    EvidenceAnchor.create(
                        source.id,
                        2,
                        bbox=(0.1, 0.2, 0.8, 0.3),
                        quote=f"1 VIN {function}",
                    ),
                ),
            )
            facts.append(
                self.repository.submit_fact(
                    fact.id, expected_revision=fact.revision_token
                )
            )
        return source, manufacturer, component, package, tuple(facts)

    def test_review_queue_surfaces_source_fact_closure_and_conflicts(self) -> None:
        source, _manufacturer, _component, _package, facts = self.make_review_closure()

        overview = self.application.overview()

        self.assertEqual(
            (overview.source_count, overview.entity_count, overview.fact_count),
            (1, 3, 2),
        )
        self.assertEqual(overview.conflict_count, 1)
        self.assertEqual(len(overview.review_items), 3)
        source_item = next(item for item in overview.review_items if item.id == source.id)
        self.assertEqual(source_item.blockers, ())
        fact_item = next(item for item in overview.review_items if item.id == facts[0].id)
        self.assertIn("Semantic conflict is unresolved", fact_item.blockers)
        self.assertIn(
            f"Source {source.id} is READY_FOR_REVIEW, not APPROVED",
            fact_item.blockers,
        )
        self.assertEqual(overview.change_scope, "DATA_ONLY")

    def test_typed_relationship_navigation_is_derived_from_authority(self) -> None:
        source, manufacturer, component, package, facts = self.make_review_closure()

        source_view = self.application.source_detail(source.id)
        manufacturer_view = self.application.entity_detail(manufacturer.id)
        component_view = self.application.entity_detail(component.id)
        package_view = self.application.entity_detail(package.id)
        fact_view = self.application.fact_detail(facts[0].id)

        self.assertEqual({link.id for link in source_view.facts}, {fact.id for fact in facts})
        self.assertEqual(
            {link.id for link in manufacturer_view.related_entities}, {component.id}
        )
        self.assertEqual(component_view.manufacturer.id, manufacturer.id)
        self.assertEqual({link.id for link in component_view.facts}, {fact.id for fact in facts})
        self.assertEqual({link.id for link in package_view.facts}, {fact.id for fact in facts})
        self.assertEqual(
            {(link.role, link.id) for link in fact_view.entities},
            {("component", component.id), ("package", package.id)},
        )
        self.assertEqual({link.id for link in fact_view.sources}, {source.id})
        self.assertEqual({link.id for link in fact_view.conflicts}, {facts[1].id})
        self.assertEqual(len(fact_view.anchors), 1)
        self.assertTrue(fact_view.anchors[0].complete)
        self.assertEqual(fact_view.anchors[0].page, 2)

    def test_typed_list_filters_use_domain_status(self) -> None:
        source, _manufacturer, _component, _package, facts = self.make_review_closure()

        self.assertEqual(
            tuple(item.id for item in self.application.list_sources(status=RecordStatus.READY_FOR_REVIEW)),
            (source.id,),
        )
        self.assertEqual(
            self.application.list_sources(status=RecordStatus.DRAFT),
            (),
        )
        self.assertEqual(
            {item.id for item in self.application.list_facts(status=RecordStatus.READY_FOR_REVIEW)},
            {fact.id for fact in facts},
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
