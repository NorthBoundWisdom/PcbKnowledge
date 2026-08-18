from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from configs.pcbknowledge_pilot import main as pilot_main
from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    ParameterLimitKind,
    ParameterLimitPayload,
    PreparedBy,
)
from pcbknowledge.git_native.pilot_session import (
    PILOT_EVALUATION_FILE,
    PILOT_RUNBOOK_FILE,
    PILOT_SCENARIO_FILE,
    PILOT_SESSION_FILE,
    PilotSessionError,
    PilotSessionManifest,
    bootstrap_pilot_session,
    load_pilot_session,
)
from pcbknowledge.git_native.pilot_session_status import (
    PilotPhase,
    pilot_session_status,
)
from pcbknowledge.git_native.store import KnowledgeRepository
from pcbknowledge.git_native.workspace import validate_workspace
from tests.git_native.support import minimal_pdf


class PilotSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.source_root = Path(__file__).resolve().parents[2]
        self.workspace = self.parent / "PcbKnowledgeData"
        self.state_root = self.parent / "PcbKnowledgePilot"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def _commit_all(self, root: Path, message: str) -> None:
        self._git(root, "add", "-A")
        self._git(
            root,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            message,
        )

    def _bootstrap(self):
        return bootstrap_pilot_session(
            workspace=self.workspace,
            state_root=self.state_root,
            schema_source_root=self.source_root,
            software_root=self.source_root,
            dataset_name="P0.4a Session Fixture",
            init_git=True,
        )

    def _status(self, session):
        return pilot_session_status(session, software_root=self.source_root)

    def _draft_source(
        self,
        repository: KnowledgeRepository,
        key: str,
        *,
        revision: str,
        supersedes: str | None = None,
    ):
        source = repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key=key,
        )
        evidence = repository.import_pdf_bytes(minimal_pdf(f"session-{revision}"))
        updated = source.edit(
            title="Pilot Session Synthetic Datasheet",
            document_number="PK-SESSION-DS",
            revision=revision,
            source_locator=f"https://example.invalid/session-{revision}.pdf",
            source_publisher="PcbKnowledge Session Fixtures",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic test material",
            evidence=evidence,
            preparation_note="Synthetic session fixture",
            supersedes=supersedes,
        )
        repository.save_source(source, updated, source.revision_token)
        return updated

    def _populate_structural_pilot(self, repository: KnowledgeRepository):
        source_a = self._draft_source(repository, "session-source-a", revision="A")
        source_b = self._draft_source(
            repository,
            "session-source-b",
            revision="B",
            supersedes=source_a.id,
        )
        manufacturer = repository.create_manufacturer(
            "PcbKnowledge Session Fixtures",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="session-manufacturer",
        )
        components = [
            repository.create_component(
                manufacturer.id,
                f"PKS{index + 1}000",
                family=f"PKS{index + 1}",
                prepared_by=PreparedBy.AGENT,
                idempotency_key=f"session-component-{index + 1}",
            )
            for index in range(3)
        ]
        packages = [
            repository.create_package(
                name,
                prepared_by=PreparedBy.AGENT,
                idempotency_key=f"session-package-{index + 1}",
            )
            for index, name in enumerate(("QFN-16", "TSSOP-16"))
        ]

        facts = []
        pin_counter = 0
        package_sets = (
            (packages[0], packages[1]),
            (packages[0],),
            (packages[0],),
        )
        for component, component_packages in zip(components, package_sets):
            for package in component_packages:
                for pin_number in range(1, 5):
                    pin_counter += 1
                    quote = f"{pin_number} PIN{pin_counter} synthetic function"
                    facts.append(
                        repository.create_fact(
                            idempotency_key=f"session-pin-{pin_counter}",
                            fact_type=FactType.COMPONENT_PIN,
                            payload=ComponentPinPayload(
                                component.id,
                                package.id,
                                str(pin_number),
                                f"PIN{pin_counter}",
                                "Synthetic function",
                                (),
                            ),
                            prepared_by=PreparedBy.AGENT,
                            conditions=(f"{package.raw_name} package",),
                            applicability=(component.raw_mpn or component.id,),
                            evidence_anchors=(
                                EvidenceAnchor.create(
                                    source_b.id,
                                    2,
                                    bbox=(0.10, 0.15, 0.88, 0.30),
                                    quote=quote,
                                ),
                            ),
                        )
                    )

        for index, (parameter, kind, minimum, typical, maximum, unit) in enumerate(
            (
                (
                    "Input voltage",
                    ParameterLimitKind.ABSOLUTE_MAXIMUM,
                    -0.3,
                    None,
                    40,
                    "V",
                ),
                (
                    "Input voltage",
                    ParameterLimitKind.RECOMMENDED_OPERATING,
                    4.5,
                    12,
                    36,
                    "V",
                ),
                (
                    "Junction temperature",
                    ParameterLimitKind.ABSOLUTE_MAXIMUM,
                    -40,
                    None,
                    150,
                    "degC",
                ),
                (
                    "Switch current",
                    ParameterLimitKind.ABSOLUTE_MAXIMUM,
                    None,
                    None,
                    5,
                    "A",
                ),
            ),
            start=1,
        ):
            facts.append(
                repository.create_fact(
                    idempotency_key=f"session-parameter-{index}",
                    fact_type=FactType.PARAMETER_LIMIT,
                    payload=ParameterLimitPayload(
                        components[0].id,
                        parameter,
                        kind,
                        minimum,
                        typical,
                        maximum,
                        unit,
                    ),
                    prepared_by=PreparedBy.AGENT,
                    conditions=("Unless otherwise noted",),
                    applicability=(components[0].raw_mpn or components[0].id,),
                    evidence_anchors=(
                        EvidenceAnchor.create(
                            source_b.id,
                            4 + index,
                            bbox=(0.12, 0.30, 0.90, 0.46),
                            quote=(
                                f"{parameter} {kind.value} {minimum} {typical} "
                                f"{maximum} {unit}"
                            ),
                        ),
                    ),
                )
            )

        self.assertEqual(len(facts), 20)
        return source_a, source_b, components, packages, facts

    def _approve_everything(
        self,
        repository: KnowledgeRepository,
        source_ids: tuple[str, ...],
        fact_ids: tuple[str, ...],
    ) -> None:
        for source_id in source_ids:
            source = repository.load_source(source_id)
            ready = repository.submit_source(
                source_id,
                expected_revision=source.revision_token,
            )
            repository.approve_source(
                source_id,
                expected_revision=ready.revision_token,
                comment="session source reviewed",
            )
        for fact_id in fact_ids:
            fact = repository.load_fact(fact_id)
            ready = repository.submit_fact(
                fact_id,
                expected_revision=fact.revision_token,
            )
            repository.approve_fact(
                fact_id,
                expected_revision=ready.revision_token,
                comment="session fact reviewed",
            )

    def test_bootstrap_creates_isolated_state_without_staging_or_committing(self) -> None:
        result = self._bootstrap()
        self.assertFalse(result.workspace_replayed)
        self.assertFalse(result.session_replayed)
        self.assertEqual(result.session.root, self.state_root.resolve())
        self.assertEqual(result.session.workspace, self.workspace.resolve())
        self.assertTrue((self.state_root / PILOT_SESSION_FILE).is_file())
        self.assertTrue((self.state_root / PILOT_EVALUATION_FILE).is_file())
        self.assertTrue((self.state_root / PILOT_SCENARIO_FILE).is_file())
        self.assertTrue((self.state_root / PILOT_RUNBOOK_FILE).is_file())
        validate_workspace(self.workspace)

        cached = self._git(self.workspace, "diff", "--cached", "--quiet", check=False)
        self.assertEqual(cached.returncode, 0)
        self.assertNotEqual(self._git(self.workspace, "status", "--porcelain").stdout, "")
        self.assertFalse((self.source_root / "pilot-session.json").exists())

        status = self._status(result.session)
        self.assertEqual(status.phase, PilotPhase.WORKSPACE_CONTRACT)
        self.assertFalse(status.workspace_contract_committed)
        self.assertEqual(status.evaluation_state, "TEMPLATE")
        self.assertEqual(status.scenario_state, "TEMPLATE")
        self.assertEqual(status.actions[0].code, "STAGE_WORKSPACE_CONTRACT")

    def test_bootstrap_replays_without_overwriting_private_evaluation_edits(self) -> None:
        first = self._bootstrap()
        evaluation = first.session.path(first.session.manifest.evaluation_manifest)
        payload = json.loads(evaluation.read_text(encoding="utf-8"))
        payload["notes"] = "private operator edit"
        evaluation.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        second = self._bootstrap()
        self.assertTrue(second.workspace_replayed)
        self.assertTrue(second.session_replayed)
        self.assertEqual(
            json.loads(evaluation.read_text(encoding="utf-8"))["notes"],
            "private operator edit",
        )

    def test_bootstrap_rejects_unsafe_or_overlapping_roots(self) -> None:
        with self.assertRaisesRegex(PilotSessionError, "public software checkout"):
            bootstrap_pilot_session(
                workspace=self.source_root,
                state_root=self.parent / "state-a",
                schema_source_root=self.source_root,
                software_root=self.source_root,
                dataset_name="bad workspace",
            )
        with self.assertRaisesRegex(PilotSessionError, "public software checkout"):
            bootstrap_pilot_session(
                workspace=self.parent / "workspace-b",
                state_root=self.source_root / "build/private-pilot",
                schema_source_root=self.source_root,
                software_root=self.source_root,
                dataset_name="bad state",
                init_git=True,
            )
        with self.assertRaisesRegex(PilotSessionError, "separate roots"):
            bootstrap_pilot_session(
                workspace=self.parent / "workspace-c",
                state_root=self.parent / "workspace-c/pilot-state",
                schema_source_root=self.source_root,
                software_root=self.source_root,
                dataset_name="nested state",
                init_git=True,
            )

    def test_manifest_rejects_noncanonical_or_escaping_session_paths(self) -> None:
        with self.assertRaisesRegex(PilotSessionError, "relative POSIX path|unsafe path"):
            PilotSessionManifest(
                dataset_name="fixture",
                workspace=str(self.workspace.resolve()),
                evaluation_manifest="../pilot.json",
            ).validate()

        result = self._bootstrap()
        manifest_path = result.session.manifest_path
        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_path.write_text(json.dumps(parsed) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(PilotSessionError, "canonical JSON"):
            load_pilot_session(manifest_path)

    def test_status_moves_from_contract_to_ingestion_after_human_git_commit(self) -> None:
        result = self._bootstrap()
        self._commit_all(self.workspace, "workspace contract")

        status = self._status(result.session)
        self.assertEqual(status.phase, PilotPhase.INGESTION)
        self.assertTrue(status.workspace_contract_committed)
        self.assertIsNotNone(status.published_commit)
        self.assertEqual(status.working_metrics["component_count"], 0)
        self.assertEqual(status.actions[0].code, "VALIDATE_WORKSPACE")

    def test_structural_coverage_advances_to_human_review_without_auto_review(self) -> None:
        result = self._bootstrap()
        self._commit_all(self.workspace, "workspace contract")
        repository = KnowledgeRepository(self.workspace)
        source_a, source_b, components, packages, facts = self._populate_structural_pilot(
            repository
        )

        status = self._status(result.session)
        self.assertEqual(status.phase, PilotPhase.HUMAN_REVIEW)
        self.assertEqual(status.working_metrics["component_count"], 3)
        self.assertEqual(status.working_metrics["fact_count"], 20)
        self.assertEqual(status.working_metrics["multi_package_component_count"], 1)
        self.assertEqual(status.working_metrics["source_supersedes_count"], 1)
        self.assertEqual(status.working_metrics["approved_fact_count"], 0)
        self.assertEqual(status.actions[0].code, "OPEN_WORKBENCH")
        self.assertTrue(status.actions[0].human_required)

        before = self._git(self.workspace, "status", "--porcelain=v1").stdout
        self._status(result.session)
        after = self._git(self.workspace, "status", "--porcelain=v1").stdout
        self.assertEqual(before, after)
        self.assertEqual(
            {item.id for item in components},
            {item.id for item in repository.list_entities() if item in components},
        )
        self.assertEqual(len(packages), 2)
        self.assertEqual({source_a.id, source_b.id}, {item.id for item in repository.list_sources()})
        self.assertEqual(len(facts), len(repository.list_facts()))

    def test_reviewed_working_authority_requires_explicit_publication(self) -> None:
        result = self._bootstrap()
        self._commit_all(self.workspace, "workspace contract")
        repository = KnowledgeRepository(self.workspace)
        source_a, source_b, _components, _packages, facts = self._populate_structural_pilot(
            repository
        )
        self._approve_everything(
            repository,
            (source_a.id, source_b.id),
            tuple(fact.id for fact in facts),
        )

        status = self._status(result.session)
        self.assertEqual(status.phase, PilotPhase.PUBLICATION)
        self.assertEqual(status.working_metrics["approved_source_count"], 2)
        self.assertEqual(status.working_metrics["approved_fact_count"], 20)
        assert status.published_metrics is not None
        self.assertEqual(status.published_metrics["fact_count"], 0)
        self.assertEqual(status.actions[0].code, "CHECK_CHANGE_SCOPE")
        self.assertEqual(repository.git_change_scope().value, "DATA_ONLY")

    def test_committed_reviewed_authority_advances_to_scenario_binding(self) -> None:
        result = self._bootstrap()
        self._commit_all(self.workspace, "workspace contract")
        repository = KnowledgeRepository(self.workspace)
        source_a, source_b, _components, _packages, facts = self._populate_structural_pilot(
            repository
        )
        self._approve_everything(
            repository,
            (source_a.id, source_b.id),
            tuple(fact.id for fact in facts),
        )
        self._commit_all(self.workspace, "reviewed pilot authority")

        status = self._status(result.session)
        self.assertEqual(status.phase, PilotPhase.SCENARIOS)
        assert status.published_metrics is not None
        self.assertEqual(status.published_metrics["fact_count"], 20)
        self.assertEqual(status.scenario_state, "TEMPLATE")
        self.assertEqual(status.actions[-1].code, "RUN_SCENARIOS")
        self.assertEqual(repository.git_change_scope().value, "CLEAN")

    def test_cli_bootstrap_and_status_expose_machine_readable_session_state(self) -> None:
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = pilot_main(
                [
                    "bootstrap",
                    "--workspace",
                    str(self.workspace),
                    "--state-dir",
                    str(self.state_root),
                    "--dataset-name",
                    "CLI Pilot Fixture",
                    "--init-git",
                ]
            )
        self.assertEqual((code, errors.getvalue()), (0, ""))
        bootstrap_payload = json.loads(output.getvalue())
        self.assertEqual(bootstrap_payload["status"], "OK")
        self.assertFalse(bootstrap_payload["authority"])
        self.assertEqual(bootstrap_payload["git_mutation"], "NONE")

        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = pilot_main(
                [
                    "status",
                    "--session",
                    str(self.state_root / PILOT_SESSION_FILE),
                ]
            )
        self.assertEqual((code, errors.getvalue()), (0, ""))
        status_payload = json.loads(output.getvalue())
        self.assertEqual(status_payload["phase"], "WORKSPACE_CONTRACT")
        self.assertEqual(status_payload["evaluation_state"], "TEMPLATE")
        self.assertEqual(status_payload["scenario_state"], "TEMPLATE")


if __name__ == "__main__":
    unittest.main()
