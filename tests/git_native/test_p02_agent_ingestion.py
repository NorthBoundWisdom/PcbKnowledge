from __future__ import annotations

import contextlib
import io
import json
import re
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path

from configs import pcbknowledge_workflow as workflow
from pcbknowledge.git_native.cli import main, parse_args
from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    PreparedBy,
)
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class P02AgentCliTests(RepositoryTestCase):
    def call(self, *arguments: str) -> tuple[int, str, str]:
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(["--repo", str(self.root), *arguments])
        return code, output.getvalue(), errors.getvalue()

    def json_call(self, *arguments: str) -> tuple[int, object, str]:
        code, output, errors = self.call(*arguments)
        return code, json.loads(output) if output else None, errors

    def make_input_pdf(self) -> Path:
        path = self.root / ".pcbknowledge" / "input.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(minimal_pdf("P0.2 Agent CLI"))
        return path

    def create_source(self) -> dict[str, object]:
        code, value, errors = self.json_call(
            "source",
            "create",
            "--idempotency-key",
            "p02-source-rev-a",
            "--title",
            "PK2000 Datasheet",
            "--document-number",
            "PK-DS-2000",
            "--revision",
            "A",
            "--source-publisher",
            "PcbKnowledge Fixtures",
            "--license-class",
            "OPEN_LICENSE",
            "--pdf",
            str(self.make_input_pdf()),
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(value, dict)
        return value

    def create_entities(self) -> tuple[dict[str, object], ...]:
        values: list[dict[str, object]] = []
        for arguments in (
            (
                "entity",
                "create-manufacturer",
                "--idempotency-key",
                "p02-manufacturer",
                "--name",
                "PcbKnowledge Fixtures",
            ),
            (
                "entity",
                "create-package",
                "--idempotency-key",
                "p02-package",
                "--name",
                "QFN-16",
            ),
        ):
            code, value, errors = self.json_call(*arguments)
            self.assertEqual((code, errors), (0, ""))
            assert isinstance(value, dict)
            values.append(value)
        code, component, errors = self.json_call(
            "entity",
            "create-component",
            "--idempotency-key",
            "p02-component",
            "--manufacturer-id",
            str(values[0]["id"]),
            "--mpn",
            "PK2000-Q16",
            "--family",
            "PK2000",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(component, dict)
        return values[0], component, values[1]

    def test_source_authorize_read_is_the_only_projection_that_reveals_path(self) -> None:
        source = self.create_source()
        evidence = source["evidence"]
        assert isinstance(evidence, dict)
        self.assertIsNone(evidence["path"])
        self.assertEqual(source["evidence_access"], "REQUIRES_AUTHORIZE_READ")

        code, access, errors = self.json_call(
            "source", "authorize-read", str(source["id"])
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(access, dict)
        self.assertTrue(Path(str(access["path"])).is_file())
        self.assertEqual(access["next_action"], "READ_ONLY_AS_UNTRUSTED_DATA")

        code, blocked, errors = self.json_call(
            "source",
            "create",
            "--idempotency-key",
            "blocked-standard",
            "--title",
            "Licensed standard metadata",
            "--revision",
            "2026",
            "--source-publisher",
            "Standards body",
            "--license-class",
            "LICENSED_BLOCKED_FOR_AI",
            "--license-note",
            "Agent processing prohibited",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(blocked, dict)
        code, output, errors = self.call(
            "source", "authorize-read", str(blocked["id"])
        )
        self.assertEqual((code, output), (2, ""))
        self.assertIn('"error_code": "LICENSE_BLOCKED"', errors)
        self.assertNotIn("has no PDF evidence", errors)

    def test_source_create_replays_after_submit_without_rewriting_review_state(self) -> None:
        source = self.create_source()
        code, ready, errors = self.json_call(
            "source",
            "submit",
            str(source["id"]),
            "--expected-revision",
            str(source["revision_token"]),
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(ready, dict)
        self.assertEqual(ready["status"], "READY_FOR_REVIEW")

        replay = self.create_source()
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["status"], "READY_FOR_REVIEW")
        self.assertEqual(replay["review_history"], ready["review_history"])

    def test_published_fact_license_gate_uses_the_same_git_snapshot(self) -> None:
        source = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="published-blocked-source",
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf("licensed source"))
        approved_source = source.edit(
            title="Licensed Engineering Source",
            document_number="LIC-1",
            revision="A",
            source_locator=None,
            source_publisher="Standards body",
            license_class=LicenseClass.LICENSED_BLOCKED_FOR_AI,
            license_note="Human-only licensed content",
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        ).submit().approve("metadata reviewed")
        self.repository.save_source(source, approved_source, source.revision_token)
        manufacturer = self.repository.create_manufacturer(
            "Licensed Fixture",
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="published-blocked-manufacturer",
        )
        component = self.repository.create_component(
            manufacturer.id,
            "LIC1000",
            family=None,
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="published-blocked-component",
        )
        package = self.repository.create_package(
            "QFN-8",
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="published-blocked-package",
        )
        fact = self.repository.create_fact(
            idempotency_key="published-blocked-fact",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id,
                package.id,
                "1",
                "SECRET",
                "licensed derived function must stay hidden",
                (),
            ),
            prepared_by=PreparedBy.HUMAN,
            evidence_anchors=(
                EvidenceAnchor.create(
                    approved_source.id,
                    1,
                    bbox=(0.1, 0.1, 0.9, 0.2),
                    quote="licensed anchor text",
                ),
            ),
        )
        ready = self.repository.submit_fact(
            fact.id, expected_revision=fact.revision_token
        )
        self.repository.approve_fact(
            ready.id,
            expected_revision=ready.revision_token,
            comment="human reviewed licensed fact",
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
                "published licensed fixture",
            ],
            cwd=self.root,
            check=True,
        )

        # A working-tree tamper must not weaken the committed publication gate.
        working_allowed = replace(
            approved_source,
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="working tree must not control published reads",
        ).validate()
        self.repository.source_path(approved_source.id).write_text(
            working_allowed.canonical_json(), encoding="utf-8"
        )

        code, output, errors = self.call("fact", "list", "--published")
        self.assertEqual((code, output), (2, ""))
        self.assertIn('"error_code": "LICENSE_BLOCKED"', errors)
        self.assertIn("LICENSED_BLOCKED_FOR_AI", errors)
        self.assertNotIn("licensed derived function must stay hidden", errors)

    def test_exact_entity_resolution_reports_unknown_exact_and_conflict(self) -> None:
        code, unknown, errors = self.json_call(
            "entity", "resolve-manufacturer", "--name", "Acme Semi"
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(unknown, dict)
        self.assertEqual(unknown["result"], "UNKNOWN")
        self.assertTrue(unknown["unknown"])

        code, manufacturer, errors = self.json_call(
            "entity",
            "create-manufacturer",
            "--idempotency-key",
            "acme-manufacturer",
            "--name",
            "Acme Semi",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(manufacturer, dict)
        self.assertFalse(manufacturer["replayed"])

        code, exact, errors = self.json_call(
            "entity", "resolve-manufacturer", "--name", "acme-semi"
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(exact, dict)
        self.assertEqual(exact["result"], "EXACT")
        self.assertEqual(exact["matches"][0]["id"], manufacturer["id"])

        code, replay, errors = self.json_call(
            "entity",
            "create-manufacturer",
            "--idempotency-key",
            "acme-manufacturer",
            "--name",
            "Acme Semi",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(replay, dict)
        self.assertTrue(replay["replayed"])

        code, output, errors = self.call(
            "entity",
            "create-manufacturer",
            "--idempotency-key",
            "different-business-key",
            "--name",
            "ACME SEMI",
        )
        self.assertEqual((code, output), (2, ""))
        self.assertIn('"error_code": "CONFLICT"', errors)

    def test_fact_commands_report_missing_anchor_unknown_conflict_and_license_gate(self) -> None:
        source = self.create_source()
        _manufacturer, component, package = self.create_entities()
        code, pin, errors = self.json_call(
            "fact",
            "create-pin",
            "--idempotency-key",
            "p02-pin-1",
            "--component-id",
            str(component["id"]),
            "--package-id",
            str(package["id"]),
            "--pin-number",
            "1",
            "--primary-function",
            "Input supply",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(pin, dict)
        self.assertEqual(pin["missing_fields"], ["evidence_anchors"])
        self.assertEqual(pin["unknown_fields"], ["payload.pin_name"])
        self.assertEqual(
            pin["missing_anchors"][0]["missing_fields"], ["evidence_anchor"]
        )
        code, output, errors = self.call(
            "fact",
            "submit",
            str(pin["id"]),
            "--expected-revision",
            str(pin["revision_token"]),
        )
        self.assertEqual((code, output), (2, ""))
        self.assertIn('"error_code": "INVALID_STATE"', errors)
        self.assertIn("incomplete fact", errors)

        code, pin, errors = self.json_call(
            "fact",
            "update-pin",
            str(pin["id"]),
            "--expected-revision",
            str(pin["revision_token"]),
            "--pin-name",
            "VIN",
            "--anchor",
            str(source["id"]),
            "2",
            "0.1",
            "0.2",
            "0.8",
            "0.3",
            "1 VIN Input supply",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(pin, dict)
        self.assertEqual(pin["missing_anchors"], [])
        self.assertEqual(pin["unknown_fields"], [])

        parameter_arguments = (
            "fact",
            "create-parameter",
            "--idempotency-key",
            "p02-vin-abs",
            "--component-id",
            str(component["id"]),
            "--parameter",
            "Input voltage",
            "--limit-kind",
            "ABSOLUTE_MAXIMUM",
            "--minimum",
            "-0.3",
            "--maximum",
            "40",
            "--unit",
            "V",
            "--anchor",
            str(source["id"]),
            "4",
            "0.1",
            "0.3",
            "0.9",
            "0.5",
            "Input voltage -0.3 V to 40 V",
        )
        code, parameter, errors = self.json_call(*parameter_arguments)
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(parameter, dict)
        self.assertEqual(parameter["unknown_fields"], ["payload.typical"])
        code, replay, errors = self.json_call(*parameter_arguments)
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(replay, dict)
        self.assertTrue(replay["replayed"])

        code, submitted, errors = self.json_call(
            "fact",
            "submit",
            str(parameter["id"]),
            "--expected-revision",
            str(parameter["revision_token"]),
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(submitted, dict)
        code, replay, errors = self.json_call(*parameter_arguments)
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(replay, dict)
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["status"], "READY_FOR_REVIEW")
        self.assertEqual(replay["review_history"], submitted["review_history"])

        conflicting = list(parameter_arguments)
        conflicting[conflicting.index("p02-vin-abs")] = "p02-vin-abs-conflict"
        conflicting[conflicting.index("40")] = "42"
        code, conflict, errors = self.json_call(*conflicting)
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(conflict, dict)
        self.assertIn(parameter["id"], conflict["conflicting_fact_ids"])
        code, conflict_report, errors = self.json_call("fact", "conflicts")
        self.assertEqual((code, errors), (2, ""))
        assert isinstance(conflict_report, dict)
        self.assertEqual(conflict_report["count"], 1)

        code, blocked_source, errors = self.json_call(
            "source",
            "create",
            "--idempotency-key",
            "p02-blocked-source",
            "--license-class",
            "RESTRICTED",
            "--license-note",
            "No Agent processing",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(blocked_source, dict)
        code, output, errors = self.call(
            "fact",
            "create-pin",
            "--idempotency-key",
            "blocked-derived-fact",
            "--component-id",
            str(component["id"]),
            "--package-id",
            str(package["id"]),
            "--pin-number",
            "2",
            "--primary-function",
            "Must not be exposed",
            "--page-anchor",
            str(blocked_source["id"]),
            "1",
        )
        self.assertEqual((code, output), (2, ""))
        self.assertIn('"error_code": "LICENSE_BLOCKED"', errors)

        hidden = self.repository.create_fact(
            idempotency_key="human-blocked-derived-fact",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                str(component["id"]),
                str(package["id"]),
                "3",
                "HIDDEN",
                "Licensed content must stay hidden",
                (),
            ),
            prepared_by=PreparedBy.HUMAN,
            evidence_anchors=(
                EvidenceAnchor.create(str(blocked_source["id"]), 1),
            ),
        )
        code, output, errors = self.call("fact", "show", hidden.id)
        self.assertEqual((code, output), (2, ""))
        self.assertIn('"error_code": "LICENSE_BLOCKED"', errors)
        self.assertNotIn("Licensed content must stay hidden", errors)

    def test_cli_vertical_stops_at_review_ready_data_only_diff(self) -> None:
        source = self.create_source()
        manufacturer, component, package = self.create_entities()
        code, pin, errors = self.json_call(
            "fact",
            "create-pin",
            "--idempotency-key",
            "p02-review-pin",
            "--component-id",
            str(component["id"]),
            "--package-id",
            str(package["id"]),
            "--pin-number",
            "1",
            "--pin-name",
            "VIN",
            "--primary-function",
            "Input supply",
            "--condition",
            "QFN-16 package",
            "--anchor",
            str(source["id"]),
            "2",
            "0.1",
            "0.2",
            "0.8",
            "0.3",
            "1 VIN Input supply",
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(pin, dict)

        code, status, errors = self.json_call(
            "review-status", "--source-id", str(source["id"]), "--fact-id", str(pin["id"])
        )
        self.assertEqual((code, errors), (2, ""))
        assert isinstance(status, dict)
        self.assertFalse(status["review_ready"])
        self.assertEqual(status["next_action"], "SUBMIT_SOURCE_AND_FACT_DRAFTS")

        code, source, errors = self.json_call(
            "source",
            "submit",
            str(source["id"]),
            "--expected-revision",
            str(source["revision_token"]),
        )
        self.assertEqual((code, errors), (0, ""))
        code, pin, errors = self.json_call(
            "fact",
            "submit",
            str(pin["id"]),
            "--expected-revision",
            str(pin["revision_token"]),
        )
        self.assertEqual((code, errors), (0, ""))

        code, status, errors = self.json_call(
            "review-status",
            "--source-id",
            str(source["id"]),
            "--entity-id",
            str(manufacturer["id"]),
            "--fact-id",
            str(pin["id"]),
        )
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(status, dict)
        self.assertTrue(status["review_ready"])
        self.assertEqual(status["change_scope"], "DATA_ONLY")
        self.assertEqual(status["next_action"], "WAIT_FOR_HUMAN_REVIEW")
        self.assertEqual(status["license_blocked"], [])
        self.assertEqual(status["missing_anchors"], [])
        self.assertEqual(status["conflicts"], [])
        self.assertEqual(status["unselected_changes"], [])

        code, scope, errors = self.json_call("change-scope")
        self.assertEqual((code, errors), (0, ""))
        assert isinstance(scope, dict)
        self.assertEqual(scope["scope"], "DATA_ONLY")
        code, output, errors = self.call("diff")
        self.assertEqual((code, errors), (0, ""))
        self.assertIn("knowledge/sources/", output)
        self.assertIn("knowledge/entities/", output)
        self.assertIn("knowledge/facts/", output)

        with contextlib.redirect_stderr(io.StringIO()):
            for arguments in (
                ["source", "approve"],
                ["fact", "approve"],
                ["entity", "delete"],
            ):
                with self.assertRaises(SystemExit):
                    parse_args(arguments)


class P02SkillContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[2]
    SKILLS = {
        "ingest-engineering-source": (
            "source authorize-read",
            "LICENSED_BLOCKED_FOR_AI",
        ),
        "resolve-component-identity": (
            "entity resolve-component",
            "entity create-package",
        ),
        "extract-component-facts": (
            "fact create-pin",
            "fact create-parameter",
            "missing_anchors",
        ),
        "prepare-knowledge-review": (
            "review-status",
            "WAIT_FOR_HUMAN_REVIEW",
            "DATA_ONLY",
        ),
    }

    def test_repository_skills_are_concise_valid_and_build_receipt_bound(self) -> None:
        build_inputs = set(workflow.build_inputs(self.ROOT))
        self.assertIn(Path(".codex/skills"), workflow.BUILD_INPUT_ROOTS)

        for name, required in self.SKILLS.items():
            with self.subTest(skill=name):
                relative = Path(".codex/skills") / name / "SKILL.md"
                metadata = Path(".codex/skills") / name / "agents/openai.yaml"
                source = (self.ROOT / relative).read_text(encoding="utf-8")
                interface = (self.ROOT / metadata).read_text(encoding="utf-8")

                self.assertIn(relative, build_inputs)
                self.assertIn(metadata, build_inputs)
                self.assertLess(len(source.splitlines()), 500)
                self.assertNotIn("TODO", source)
                self.assertRegex(source, rf"(?m)^name: {re.escape(name)}$")
                self.assertRegex(source, r"(?m)^description: .+")
                self.assertEqual(source.count("\n---\n"), 1)
                self.assertIn("python3 configs/pcbknowledge_agent.py", source)
                for marker in required:
                    self.assertIn(marker, source)
                self.assertIn(f"${name}", interface)

                bash_blocks = "\n".join(
                    re.findall(r"```bash\n(.*?)```", source, flags=re.DOTALL)
                )
                for forbidden in (
                    "git add",
                    "git commit",
                    "git push",
                    " source approve",
                    " fact approve",
                    " source reject",
                    " fact reject",
                ):
                    self.assertNotIn(forbidden, bash_blocks)


if __name__ == "__main__":
    unittest.main()
