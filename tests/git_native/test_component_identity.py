"""Synthetic exact-MPN regression coverage; no manufacturer product claims."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from dataclasses import replace

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EntityRecord,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    PreparedBy,
    RecordTransitionError,
    exact_mpn_key,
)
from pcbknowledge.git_native.store import RecordConflictError
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class ExactComponentIdentityTests(RepositoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manufacturer = self.repository.create_manufacturer(
            "Synthetic Identity Fixtures", prepared_by=PreparedBy.AGENT,
            idempotency_key="identity-manufacturer",
        )

    def component(self, mpn: str, key: str, manufacturer_id: str | None = None):
        return self.repository.create_component(
            manufacturer_id or self.manufacturer.id, mpn, family=None,
            prepared_by=PreparedBy.AGENT, idempotency_key=key,
        )

    def call(self, *arguments: str):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(["--repo", str(self.root), *arguments])
        return code, json.loads(output.getvalue()) if output.getvalue() else None, errors.getvalue()

    def test_exact_policy_preserves_case_unicode_internal_space_and_suffix(self) -> None:
        spellings = ("AB-12", "AB12", "AB-12A", "ab-12", "AB 12", "AB\t12", "ＡＢ-１２", "AB-é", "AB-e\u0301")
        records = [self.component(mpn, f"variant-{index}") for index, mpn in enumerate(spellings)]
        self.assertEqual(len({record.identity_key for record in records}), len(spellings))
        self.assertEqual(records[0].normalized_mpn, records[1].normalized_mpn)
        self.assertEqual(records[0].normalized_mpn, records[3].normalized_mpn)
        self.assertEqual(records[0].normalized_mpn, records[6].normalized_mpn)
        for record in records:
            with self.subTest(mpn=record.raw_mpn):
                self.assertEqual(
                    self.repository.find_components_exact(self.manufacturer.id, record.raw_mpn),
                    [record],
                )
                self.assertEqual(EntityRecord.from_json(record.canonical_json()), record)
        self.assertEqual(exact_mpn_key(" \tAB-12\n"), "AB-12")
        self.assertEqual(self.repository.find_components_exact(self.manufacturer.id, " AB-12 "), [records[0]])
        self.assertEqual(self.repository.find_components_exact(self.manufacturer.id, "AB-12B"), [])
        self.repository.validate_all()

    def test_missing_exact_match_does_not_use_single_normalized_candidate(self) -> None:
        self.component("AB-12", "punctuated")
        for query in ("AB12", "ab-12", "ＡＢ-１２", "AB 12"):
            self.assertEqual(self.repository.find_components_exact(self.manufacturer.id, query), [])
            code, value, errors = self.call(
                "entity", "resolve-component", "--manufacturer-id", self.manufacturer.id,
                "--mpn", query,
            )
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(value["result"], "UNKNOWN")
            self.assertEqual(value["matches"], [])

    def test_colliding_candidates_resolve_independently_and_deterministically(self) -> None:
        records = [self.component(mpn, mpn) for mpn in ("AB-12", "AB12")]
        for _ in range(2):
            for record in records:
                code, value, errors = self.call(
                    "entity", "resolve-component", "--manufacturer-id", self.manufacturer.id,
                    "--mpn", record.raw_mpn,
                )
                self.assertEqual((code, errors), (0, ""))
                self.assertEqual(value["result"], "EXACT")
                self.assertEqual([item["id"] for item in value["matches"]], [record.id])
                self.assertEqual(value["query"]["matching_policy"], "MANUFACTURER_ID_AND_OUTER_TRIMMED_MPN")
        self.repository.validate_all()

    def test_manufacturer_boundary_and_idempotent_creation_remain_enforced(self) -> None:
        first = self.component("AB-12", "first")
        other = self.repository.create_manufacturer(
            "Other Synthetic Fixtures", prepared_by=PreparedBy.AGENT,
            idempotency_key="other-manufacturer",
        )
        second = self.component("AB-12", "second", other.id)
        self.assertNotEqual(first.identity_key, second.identity_key)
        self.assertEqual(self.repository.find_components_exact(self.manufacturer.id, "AB-12"), [first])
        self.assertEqual(self.repository.find_components_exact(other.id, "AB-12"), [second])
        self.assertEqual(self.component(" AB-12 ", "first"), first)
        with self.assertRaises(RecordConflictError):
            self.component("AB12", "first")
        with self.assertRaises(RecordConflictError):
            self.component("AB-12", "new-key-same-identity")

    def test_agent_ingestion_creates_distinct_identities_and_replays(self) -> None:
        identifiers = []
        for mpn in ("AB-12", "AB12"):
            args = ("entity", "create-component", "--manufacturer-id", self.manufacturer.id,
                    "--mpn", mpn, "--idempotency-key", mpn)
            code, created, errors = self.call(*args)
            self.assertEqual((code, errors), (0, ""))
            self.assertFalse(created["replayed"])
            identifiers.append(created["id"])
            code, replay, errors = self.call(*args)
            self.assertEqual((code, errors), (0, ""))
            self.assertTrue(replay["replayed"])
            self.assertEqual(replay["id"], created["id"])
        self.assertEqual(len(set(identifiers)), 2)

    def test_existing_records_references_and_approval_bytes_are_not_rewritten(self) -> None:
        component = self.component("AB-12", "legacy-component")
        package = self.repository.create_package(
            "QFN-2", prepared_by=PreparedBy.AGENT, idempotency_key="package",
        )
        source = self.repository.create_source(prepared_by=PreparedBy.AGENT, idempotency_key="source")
        source_ready = source.edit(
            title="Synthetic identity fixture", document_number="SYN-ID", revision="A",
            source_locator=None, source_publisher="Synthetic Fixtures",
            license_class=LicenseClass.OPEN_LICENSE, license_note="Synthetic",
            evidence=self.repository.import_pdf_bytes(minimal_pdf("identity")),
            preparation_note=None, supersedes=None,
        ).submit().approve("Synthetic fixture review")
        self.repository.save_source(source, source_ready, source.revision_token)
        fact = self.repository.create_fact(
            idempotency_key="legacy-fact", fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(component.id, package.id, "1", "IN", "Input", ()),
            prepared_by=PreparedBy.AGENT,
            evidence_anchors=(EvidenceAnchor.create(source.id, 1, bbox=(0.1, 0.1, 0.5, 0.5), quote="1 IN Input"),),
        )
        ready = self.repository.submit_fact(fact.id, expected_revision=fact.revision_token)
        approved = self.repository.approve_fact(ready.id, expected_revision=ready.revision_token, comment="Synthetic fixture review")
        subprocess.run(["git", "add", "knowledge"], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "legacy records"], cwd=self.root, check=True)
        paths = [self.repository.entity_path(component.id), self.repository.source_path(source.id), self.repository.fact_path(fact.id)]
        before = {path: path.read_bytes() for path in paths}
        collision = self.component("AB12", "new-distinct-component")
        self.repository.validate_all()
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        self.assertEqual(self.repository.load_fact(fact.id), approved)
        self.assertEqual(self.repository.load_fact(fact.id).payload.component_id, component.id)
        self.assertNotEqual(collision.id, component.id)
        self.assertEqual(self.repository.load_entity(component.id).revision_token, component.revision_token)
        with self.assertRaises(RecordTransitionError):
            changed = replace(approved, conditions=("rewritten",))
            self.repository.save_fact(approved, changed, approved.revision_token)
