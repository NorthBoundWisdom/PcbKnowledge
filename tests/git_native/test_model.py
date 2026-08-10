from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path

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
    RecordTransitionError,
    RecordValidationError,
    ReviewAction,
    SourceRecord,
    SourceType,
    deterministic_entity_id,
    deterministic_fact_id,
    deterministic_source_id,
    normalize_lookup,
)


SOURCE_ID = "pk_0123456789abcdef01234567"
MANUFACTURER_ID = "ent_0123456789abcdef01234567"
COMPONENT_ID = "ent_1123456789abcdef01234567"
PACKAGE_ID = "ent_2123456789abcdef01234567"
FACT_ID = "fact_0123456789abcdef01234567"


def described_evidence() -> Evidence:
    digest = "a" * 64
    return Evidence(
        path=f"evidence/sha256/aa/{digest}.pdf",
        sha256=digest,
        byte_size=42,
        media_type="application/pdf",
    )


def complete_source() -> SourceRecord:
    return SourceRecord.new(SOURCE_ID, prepared_by=PreparedBy.HUMAN).edit(
        title="电源数据手册",
        document_number="DS-1",
        revision="A",
        source_locator="https://example.test/ds.pdf",
        source_publisher="Example",
        license_class=LicenseClass.PUBLIC_REFERENCE,
        license_note=None,
        evidence=described_evidence(),
        preparation_note="synthetic fixture",
        supersedes=None,
    )


def complete_anchor() -> EvidenceAnchor:
    return EvidenceAnchor.create(
        SOURCE_ID,
        3,
        bbox=(0.1, 0.2, 0.8, 0.9),
        quote="Pin 1 is VIN.",
    )


class TypedAuthorityModelTests(unittest.TestCase):
    def test_source_canonical_round_trip_is_stable_unicode_json(self) -> None:
        source = complete_source()
        payload = source.canonical_json()

        self.assertEqual(SourceRecord.from_json(payload), source)
        self.assertTrue(payload.endswith("\n"))
        self.assertIn("电源数据手册", payload)
        self.assertEqual(json.loads(payload)["schema_version"], 1)
        self.assertEqual(json.loads(payload)["source_type"], "DATASHEET")
        self.assertEqual(json.loads(payload)["review_history"], [])

    def test_source_extra_fields_and_invalid_evidence_fail_closed(self) -> None:
        source = SourceRecord.new(SOURCE_ID, prepared_by=PreparedBy.AGENT)
        value = source.to_dict()
        value["unexpected"] = True
        with self.assertRaisesRegex(RecordValidationError, "unsupported fields"):
            SourceRecord.from_dict(value)

        value = source.to_dict()
        value["evidence"] = {
            "path": "../../outside.pdf",
            "sha256": "a" * 64,
            "byte_size": 10,
            "media_type": "application/pdf",
        }
        with self.assertRaisesRegex(RecordValidationError, "derived"):
            SourceRecord.from_dict(value)

    def test_source_approval_and_review_history_fail_closed(self) -> None:
        source = SourceRecord.new(SOURCE_ID, prepared_by=PreparedBy.AGENT)
        with self.assertRaisesRegex(RecordTransitionError, "fields are missing"):
            source.submit().approve("looks good")

        rejected = source.submit().reject("请补版本")
        edited = rejected.edit(
            title="Title",
            document_number=None,
            revision="A",
            source_locator=None,
            source_publisher=None,
            license_class=LicenseClass.UNKNOWN,
            license_note=None,
            evidence=Evidence(),
            preparation_note=None,
            supersedes=None,
            source_type=SourceType.APPLICATION_NOTE,
        )
        self.assertEqual(edited.status, RecordStatus.DRAFT)
        self.assertEqual(
            [event.action for event in edited.review_history],
            [ReviewAction.SUBMITTED, ReviewAction.REJECTED],
        )
        self.assertEqual(edited.review_history[-1].comment, "请补版本")
        self.assertEqual(edited.submit().review_history[-1].action, ReviewAction.SUBMITTED)

        tampered = edited.to_dict()
        tampered["review_history"] = [
            {"action": "REJECTED", "comment": "impossible"}
        ]
        with self.assertRaisesRegex(RecordValidationError, "start or resume"):
            SourceRecord.from_dict(tampered)

    def test_license_taxonomy_and_agent_gate_are_explicit(self) -> None:
        allowed = {
            LicenseClass.PUBLIC_REFERENCE,
            LicenseClass.OPEN_LICENSE,
            LicenseClass.INTERNAL,
        }
        self.assertEqual(
            {item for item in LicenseClass if item.agent_processing_allowed}, allowed
        )
        self.assertFalse(LicenseClass.UNKNOWN.agent_processing_allowed)
        self.assertFalse(LicenseClass.RESTRICTED.agent_processing_allowed)
        self.assertFalse(LicenseClass.LICENSED_BLOCKED_FOR_AI.agent_processing_allowed)

        blocked = replace(
            complete_source(),
            license_class=LicenseClass.LICENSED_BLOCKED_FOR_AI,
            license_note=None,
        )
        self.assertIn("license_note", blocked.missing_fields)
        with self.assertRaisesRegex(RecordTransitionError, "license_note"):
            blocked.submit().approve(None)

    def test_entity_models_preserve_raw_and_validate_normalized_keys(self) -> None:
        manufacturer = EntityRecord.manufacturer(
            MANUFACTURER_ID, "Texas Instruments, Inc.", prepared_by=PreparedBy.AGENT
        )
        component = EntityRecord.component(
            COMPONENT_ID,
            MANUFACTURER_ID,
            " TPS5430DDA ",
            family="TPS54xx",
            prepared_by=PreparedBy.AGENT,
        )
        package = EntityRecord.package(
            PACKAGE_ID, "SO-PowerPAD-8", prepared_by=PreparedBy.HUMAN
        )

        self.assertEqual(manufacturer.raw_name, "Texas Instruments, Inc.")
        self.assertEqual(manufacturer.normalized_key, "TEXASINSTRUMENTSINC")
        self.assertEqual(component.raw_mpn, "TPS5430DDA")
        self.assertEqual(component.normalized_mpn, "TPS5430DDA")
        self.assertEqual(package.normalized_key, "SOPOWERPAD8")
        self.assertEqual(normalize_lookup("村田 製作所"), "村田製作所")
        self.assertEqual(EntityRecord.from_json(component.canonical_json()), component)

        value = component.to_dict()
        value["normalized_mpn"] = "TPS5430"
        with self.assertRaisesRegex(RecordValidationError, "does not match"):
            EntityRecord.from_dict(value)

        value = package.to_dict()
        value["unexpected"] = "guess"
        with self.assertRaisesRegex(RecordValidationError, "unsupported"):
            EntityRecord.from_dict(value)

    def test_evidence_anchor_page_bbox_and_quote_hash_are_strict(self) -> None:
        anchor = complete_anchor()
        self.assertTrue(anchor.complete)
        self.assertEqual(
            anchor.quote_sha256,
            hashlib.sha256(b"Pin 1 is VIN.").hexdigest(),
        )
        self.assertEqual(EvidenceAnchor.from_dict(anchor.to_dict()), anchor)

        page_only = EvidenceAnchor.create(SOURCE_ID, 1)
        self.assertFalse(page_only.complete)

        for bbox in (
            (-0.1, 0.1, 0.5, 0.5),
            (0.5, 0.1, 0.5, 0.5),
            (0.1, 0.8, 0.5, 0.7),
            (0.1, 0.1, float("inf"), 0.5),
        ):
            with self.subTest(bbox=bbox):
                with self.assertRaises(RecordValidationError):
                    EvidenceAnchor.create(SOURCE_ID, 1, bbox=bbox)
        with self.assertRaisesRegex(RecordValidationError, "1-based"):
            EvidenceAnchor.create(SOURCE_ID, 0)

        value = anchor.to_dict()
        value["quote_sha256"] = "0" * 64
        with self.assertRaisesRegex(RecordValidationError, "does not match"):
            EvidenceAnchor.from_dict(value)

    def test_typed_fact_payloads_round_trip_and_reject_free_text_numbers(self) -> None:
        pin_payload = ComponentPinPayload(
            component_id=COMPONENT_ID,
            package_id=PACKAGE_ID,
            pin_number="1",
            pin_name="VIN",
            primary_function="Input supply",
            alternate_functions=("BOOTSTRAP SENSE",),
        ).validate()
        pin = FactRecord.new(
            FACT_ID,
            fact_type=FactType.COMPONENT_PIN,
            payload=pin_payload,
            prepared_by=PreparedBy.AGENT,
            conditions=("DDA package",),
            applicability=("TPS5430",),
            evidence_anchors=(complete_anchor(),),
        )
        self.assertEqual(FactRecord.from_json(pin.canonical_json()), pin)
        self.assertEqual(pin.submit().approve("verified").status, RecordStatus.APPROVED)

        limit = ParameterLimitPayload(
            component_id=COMPONENT_ID,
            parameter="Input voltage",
            limit_kind=ParameterLimitKind.ABSOLUTE_MAXIMUM,
            minimum=None,
            typical=None,
            maximum=40,
            unit="V",
        ).validate()
        fact = FactRecord.new(
            deterministic_fact_id("limit"),
            fact_type=FactType.PARAMETER_LIMIT,
            payload=limit,
            prepared_by=PreparedBy.AGENT,
        )
        self.assertEqual(FactRecord.from_json(fact.canonical_json()), fact)

        value = limit.to_dict()
        value["maximum"] = "40 V"
        with self.assertRaisesRegex(RecordValidationError, "JSON number"):
            ParameterLimitPayload.from_dict(value)
        value = limit.to_dict()
        value.update({"minimum": None, "typical": None, "maximum": None})
        with self.assertRaisesRegex(RecordValidationError, "at least one"):
            ParameterLimitPayload.from_dict(value)

        with self.assertRaisesRegex(RecordValidationError, "requires ComponentPinPayload"):
            replace(pin, payload=limit).validate()

        successor = replace(
            pin, supersedes="fact_aaaaaaaaaaaaaaaaaaaaaaaa"
        ).validate()
        rejected = successor.submit().reject("revise conditions")
        edited = rejected.edit(conditions=("updated condition",))
        self.assertEqual(edited.supersedes, successor.supersedes)
        self.assertIsNone(rejected.edit(supersedes=None).supersedes)

    def test_deterministic_ids_are_namespaced_stable_and_bounded(self) -> None:
        self.assertEqual(
            deterministic_source_id("agent-task-42"),
            deterministic_source_id("agent-task-42"),
        )
        self.assertNotEqual(
            deterministic_source_id("same"),
            deterministic_entity_id(EntityKind.MANUFACTURER, "same"),
        )
        self.assertRegex(deterministic_source_id("x"), r"^pk_[0-9a-f]{24}$")
        self.assertRegex(
            deterministic_entity_id(EntityKind.PACKAGE, "x"),
            r"^ent_[0-9a-f]{24}$",
        )
        self.assertRegex(deterministic_fact_id("x"), r"^fact_[0-9a-f]{24}$")

    def test_three_documented_schemas_track_executable_contract(self) -> None:
        root = Path(__file__).resolve().parents[2]
        source_schema = json.loads(
            (root / "schemas/source-record.schema.json").read_text("utf-8")
        )
        entity_schema = json.loads(
            (root / "schemas/entity-record.schema.json").read_text("utf-8")
        )
        fact_schema = json.loads(
            (root / "schemas/fact-record.schema.json").read_text("utf-8")
        )

        self.assertEqual(set(source_schema["required"]), set(complete_source().to_dict()))
        self.assertEqual(
            set(entity_schema["required"]),
            set(
                EntityRecord.package(
                    PACKAGE_ID, "QFN", prepared_by=PreparedBy.HUMAN
                ).to_dict()
            ),
        )
        self.assertEqual(
            set(fact_schema["required"]),
            set(
                FactRecord.new(
                    FACT_ID,
                    fact_type=FactType.COMPONENT_PIN,
                    payload=ComponentPinPayload(
                        COMPONENT_ID, PACKAGE_ID, "1", None, "VIN"
                    ),
                    prepared_by=PreparedBy.HUMAN,
                ).to_dict()
            ),
        )
        self.assertEqual(
            set(source_schema["properties"]["source_type"]["enum"]),
            {item.value for item in SourceType},
        )
        self.assertEqual(
            set(source_schema["$defs"]["license"]["properties"]["class"]["enum"]),
            {item.value for item in LicenseClass},
        )
        self.assertEqual(
            set(entity_schema["properties"]["kind"]["enum"]),
            {item.value for item in EntityKind},
        )
        self.assertEqual(
            set(fact_schema["properties"]["fact_type"]["enum"]),
            {item.value for item in FactType},
        )
        self.assertEqual(
            set(
                fact_schema["$defs"]["parameterLimitPayload"]["properties"]
                ["limit_kind"]["enum"]
            ),
            {item.value for item in ParameterLimitKind},
        )


if __name__ == "__main__":
    unittest.main()
