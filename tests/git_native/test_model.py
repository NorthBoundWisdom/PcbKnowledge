from __future__ import annotations

import json
import unittest
from pathlib import Path

from pcbknowledge.git_native.model import (
    Evidence,
    KnowledgeRecord,
    LicenseClass,
    PreparedBy,
    RecordStatus,
    RecordTransitionError,
    RecordValidationError,
    ReviewAction,
    deterministic_record_id,
)


class KnowledgeRecordTests(unittest.TestCase):
    def test_canonical_round_trip_is_stable_unicode_json(self) -> None:
        record = KnowledgeRecord.new("pk_0123456789abcdef01234567", prepared_by=PreparedBy.HUMAN)
        edited = record.edit(
            title="电源数据手册",
            document_number="DS-1",
            revision="A",
            source_locator="https://example.test/ds.pdf",
            source_publisher="Example",
            license_class=LicenseClass.OPEN,
            license_note=None,
            evidence=Evidence(),
            preparation_note="待补原件",
            supersedes=None,
        )

        payload = edited.canonical_json()

        self.assertEqual(KnowledgeRecord.from_json(payload), edited)
        self.assertTrue(payload.endswith("\n"))
        self.assertIn("电源数据手册", payload)
        self.assertEqual(json.loads(payload)["schema_version"], 2)
        self.assertEqual(json.loads(payload)["review_history"], [])

    def test_extra_fields_and_invalid_evidence_paths_fail_closed(self) -> None:
        record = KnowledgeRecord.new("pk_0123456789abcdef01234567", prepared_by=PreparedBy.AGENT)
        value = record.to_dict()
        value["unexpected"] = True
        with self.assertRaisesRegex(RecordValidationError, "unsupported fields"):
            KnowledgeRecord.from_dict(value)

        value = record.to_dict()
        value["evidence"] = {
            "path": "../../outside.pdf",
            "sha256": "a" * 64,
            "byte_size": 10,
            "media_type": "application/pdf",
        }
        with self.assertRaisesRegex(RecordValidationError, "derived"):
            KnowledgeRecord.from_dict(value)

    def test_approval_requires_complete_evidence_and_metadata(self) -> None:
        record = KnowledgeRecord.new("pk_0123456789abcdef01234567", prepared_by=PreparedBy.AGENT)
        ready = record.submit()

        with self.assertRaisesRegex(RecordTransitionError, "fields are missing"):
            ready.approve("looks good")

    def test_rejection_history_survives_edit_and_resubmit(self) -> None:
        record = KnowledgeRecord.new("pk_0123456789abcdef01234567", prepared_by=PreparedBy.AGENT)
        ready = record.submit()
        with self.assertRaisesRegex(RecordTransitionError, "requires a review comment"):
            ready.reject(None)

        rejected = ready.reject("请补版本")
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
        )
        self.assertEqual(edited.status, RecordStatus.DRAFT)
        self.assertIsNone(edited.review.decision)
        self.assertEqual(
            [event.action for event in edited.review_history],
            [ReviewAction.SUBMITTED, ReviewAction.REJECTED],
        )
        self.assertEqual(edited.review_history[-1].comment, "请补版本")

        resubmitted = edited.submit()
        self.assertEqual(
            [event.action for event in resubmitted.review_history],
            [ReviewAction.SUBMITTED, ReviewAction.REJECTED, ReviewAction.SUBMITTED],
        )

    def test_restricted_license_blocks_agent_processing(self) -> None:
        restricted = KnowledgeRecord.new(
            "pk_0123456789abcdef01234567", prepared_by=PreparedBy.HUMAN
        ).edit(
            title="Licensed standard",
            document_number=None,
            revision="A",
            source_locator=None,
            source_publisher="Publisher",
            license_class=LicenseClass.RESTRICTED,
            license_note="No AI/TDM",
            evidence=Evidence(),
            preparation_note=None,
            supersedes=None,
        )
        self.assertFalse(restricted.agent_processing_allowed)
        self.assertTrue(LicenseClass.OPEN.agent_processing_allowed)
        self.assertTrue(LicenseClass.INTERNAL.agent_processing_allowed)
        self.assertFalse(LicenseClass.UNKNOWN.agent_processing_allowed)

    def test_review_history_tampering_fails_closed(self) -> None:
        record = KnowledgeRecord.new("pk_0123456789abcdef01234567", prepared_by=PreparedBy.AGENT)
        value = record.to_dict()
        value["status"] = "READY_FOR_REVIEW"
        with self.assertRaisesRegex(RecordValidationError, "trailing SUBMITTED"):
            KnowledgeRecord.from_dict(value)

        value = record.to_dict()
        value["review_history"] = [
            {"action": "REJECTED", "comment": "impossible without submission"}
        ]
        with self.assertRaisesRegex(RecordValidationError, "start or resume with SUBMITTED"):
            KnowledgeRecord.from_dict(value)

        value = record.submit().to_dict()
        value["review_history"].append({"action": "SUBMITTED", "comment": None})
        with self.assertRaisesRegex(RecordValidationError, "requires APPROVED or REJECTED"):
            KnowledgeRecord.from_dict(value)

        rejected = record.submit().reject("original reason")
        value = rejected.to_dict()
        value["review"]["comment"] = "contradictory current reason"
        with self.assertRaisesRegex(RecordValidationError, "must match"):
            KnowledgeRecord.from_dict(value)

    def test_deterministic_id_is_stable_and_bounded(self) -> None:
        first = deterministic_record_id("agent-task-42")
        self.assertEqual(first, deterministic_record_id("agent-task-42"))
        self.assertNotEqual(first, deterministic_record_id("agent-task-43"))
        self.assertRegex(first, r"^pk_[0-9a-f]{24}$")

    def test_documented_schema_tracks_executable_enums_and_required_keys(self) -> None:
        schema_path = Path(__file__).resolve().parents[2] / "schemas/knowledge-record.schema.json"
        schema = json.loads(schema_path.read_text("utf-8"))
        record = KnowledgeRecord.new(
            "pk_0123456789abcdef01234567", prepared_by=PreparedBy.HUMAN
        )

        self.assertEqual(set(schema["required"]), set(record.to_dict()))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 2)
        self.assertEqual(
            set(schema["properties"]["status"]["enum"]),
            {item.value for item in RecordStatus},
        )
        self.assertEqual(
            set(schema["properties"]["license"]["properties"]["class"]["enum"]),
            {item.value for item in LicenseClass},
        )


if __name__ == "__main__":
    unittest.main()
