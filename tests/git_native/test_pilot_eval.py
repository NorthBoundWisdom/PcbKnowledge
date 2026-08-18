from __future__ import annotations

import contextlib
import io
import json
import subprocess
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
from pcbknowledge.git_native.pilot_eval import (
    PilotCase,
    PilotCaseCategory,
    PilotCaseStatus,
    PilotEvaluationError,
    PilotEvaluationManifest,
    VisualAcceptance,
    VisualCharacteristic,
    build_pilot_report,
    write_example_manifest,
)
from pcbknowledge.git_native.store import KnowledgeRepository
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class PilotEvaluationHarnessTests(RepositoryTestCase):
    @staticmethod
    def _commit_all(root: Path, message: str) -> None:
        subprocess.run(["git", "add", "knowledge", "evidence"], cwd=root, check=True)
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
                message,
            ],
            cwd=root,
            check=True,
        )

    def _approved_source(
        self,
        key: str,
        *,
        revision: str,
        supersedes: str | None = None,
    ):
        source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key=key,
        )
        evidence = self.repository.import_pdf_bytes(
            minimal_pdf(f"pilot source {revision}")
        )
        approved = source.edit(
            title="PK-PILOT Synthetic Datasheet",
            document_number="PK-PILOT-DS",
            revision=revision,
            source_locator=f"https://example.invalid/pilot-{revision}.pdf",
            source_publisher="PcbKnowledge Pilot Fixtures",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic test material",
            evidence=evidence,
            preparation_note="Synthetic pilot fixture",
            supersedes=supersedes,
        ).submit().approve(f"source revision {revision} reviewed")
        self.repository.save_source(source, approved, source.revision_token)
        return approved

    def _approved_fact(
        self,
        key: str,
        *,
        fact_type: FactType,
        payload,
        source_id: str,
        page: int,
        quote: str,
        conditions: tuple[str, ...],
        applicability: tuple[str, ...],
        second_anchor: bool = False,
    ):
        anchors = [
            EvidenceAnchor.create(
                source_id,
                page,
                bbox=(0.10, 0.15, 0.88, 0.30),
                quote=quote,
            )
        ]
        if second_anchor:
            anchors.append(
                EvidenceAnchor.create(
                    source_id,
                    page + 1,
                    bbox=(0.12, 0.34, 0.90, 0.48),
                    quote=quote + " continued",
                )
            )
        fact = self.repository.create_fact(
            idempotency_key=key,
            fact_type=fact_type,
            payload=payload,
            prepared_by=PreparedBy.AGENT,
            conditions=conditions,
            applicability=applicability,
            evidence_anchors=tuple(anchors),
        )
        ready = self.repository.submit_fact(
            fact.id, expected_revision=fact.revision_token
        )
        return self.repository.approve_fact(
            ready.id,
            expected_revision=ready.revision_token,
            comment="pilot synthetic fact reviewed",
        )

    def _build_passing_pilot(self):
        source_a = self._approved_source("pilot-source-a", revision="A")
        source_b = self._approved_source(
            "pilot-source-b",
            revision="B",
            supersedes=source_a.id,
        )
        manufacturer = self.repository.create_manufacturer(
            "PcbKnowledge Pilot Fixtures",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="pilot-manufacturer",
        )
        components = [
            self.repository.create_component(
                manufacturer.id,
                f"PKP{index + 1}000",
                family=f"PKP{index + 1}",
                prepared_by=PreparedBy.AGENT,
                idempotency_key=f"pilot-component-{index + 1}",
            )
            for index in range(3)
        ]
        packages = [
            self.repository.create_package(
                name,
                prepared_by=PreparedBy.AGENT,
                idempotency_key=f"pilot-package-{index + 1}",
            )
            for index, name in enumerate(("QFN-16", "TSSOP-16"))
        ]

        facts = []
        pin_index = 0
        for component_index, component in enumerate(components):
            package_sequence = (
                (packages[0], packages[1])
                if component_index == 0
                else (packages[0],)
            )
            pins_per_package = 4
            for package in package_sequence:
                for pin_number in range(1, pins_per_package + 1):
                    pin_index += 1
                    facts.append(
                        self._approved_fact(
                            f"pilot-pin-{pin_index}",
                            fact_type=FactType.COMPONENT_PIN,
                            payload=ComponentPinPayload(
                                component.id,
                                package.id,
                                str(pin_number),
                                f"PIN{pin_number}",
                                f"Synthetic function {pin_number}",
                                (),
                            ),
                            source_id=source_b.id,
                            page=2,
                            quote=(
                                f"{component.raw_mpn} {package.raw_name} "
                                f"pin {pin_number} synthetic function"
                            ),
                            conditions=(f"{package.raw_name} package",),
                            applicability=(component.raw_mpn or component.id,),
                            second_anchor=pin_index == 1,
                        )
                    )

        parameter_specs = (
            (components[0], "Input voltage", -0.3, None, 40, "V"),
            (components[0], "Operating voltage", 4.5, 12, 36, "V"),
            (components[1], "Junction temperature", -40, None, 150, "°C"),
            (components[2], "Output current", 0, 2, 3, "A"),
        )
        for index, (component, parameter, minimum, typical, maximum, unit) in enumerate(
            parameter_specs,
            start=1,
        ):
            kind = (
                ParameterLimitKind.RECOMMENDED_OPERATING
                if parameter == "Operating voltage"
                else ParameterLimitKind.ABSOLUTE_MAXIMUM
            )
            facts.append(
                self._approved_fact(
                    f"pilot-limit-{index}",
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
                    source_id=source_b.id,
                    page=5,
                    quote=(
                        f"{parameter}: {minimum}, {typical}, {maximum} {unit}; "
                        "see synthetic footnote 1"
                    ),
                    conditions=("Synthetic footnote 1 applies",),
                    applicability=(component.raw_mpn or component.id,),
                )
            )

        self.assertEqual(len(facts), 20)
        self._commit_all(self.root, "publish synthetic pilot authority")
        manifest = self._passing_manifest(
            source_id=source_b.id,
            table_fact_id=facts[0].id,
            footnote_fact_id=facts[-1].id,
            component_id=components[0].id,
            package_id=packages[0].id,
        )
        return manifest, source_b, facts

    @staticmethod
    def _passing_manifest(
        *,
        source_id: str,
        table_fact_id: str,
        footnote_fact_id: str,
        component_id: str,
        package_id: str,
    ) -> PilotEvaluationManifest:
        cases = (
            PilotCase(
                "case_wrong_mpn",
                PilotCaseCategory.WRONG_MPN,
                PilotCaseStatus.PASS,
                "UNKNOWN",
                "UNKNOWN",
                (component_id,),
                "Wrong MPN remained unresolved.",
            ),
            PilotCase(
                "case_wrong_package",
                PilotCaseCategory.WRONG_PACKAGE,
                PilotCaseStatus.PASS,
                "UNKNOWN",
                "UNKNOWN",
                (component_id, package_id),
                "Package was not inferred from a similar suffix.",
            ),
            PilotCase(
                "case_wrong_revision",
                PilotCaseCategory.WRONG_REVISION,
                PilotCaseStatus.PASS,
                "UNKNOWN",
                "UNKNOWN",
                (source_id,),
                "Unknown revision remained unknown.",
            ),
            PilotCase(
                "case_unknown_preserved",
                PilotCaseCategory.UNKNOWN,
                PilotCaseStatus.PASS,
                "UNKNOWN",
                "UNKNOWN",
                (component_id,),
                "Unstated value was not guessed.",
            ),
            PilotCase(
                "case_license_block",
                PilotCaseCategory.LICENSE_BLOCK,
                PilotCaseStatus.PASS,
                "BLOCKED",
                "BLOCKED",
                (),
                "Synthetic policy-path receipt.",
            ),
            PilotCase(
                "case_table_pin",
                PilotCaseCategory.TABLE_PIN,
                PilotCaseStatus.PASS,
                "EXACT",
                "EXACT",
                (table_fact_id,),
                "Pin Fact reviewed from table-like region.",
            ),
            PilotCase(
                "case_footnote_limit",
                PilotCaseCategory.FOOTNOTE_LIMIT,
                PilotCaseStatus.PASS,
                "EXACT",
                "EXACT",
                (footnote_fact_id,),
                "Parameter Fact retained footnote condition.",
            ),
        )
        visual = (
            VisualAcceptance(
                "visual_primary_anchor",
                source_id,
                table_fact_id,
                2,
                (
                    VisualCharacteristic.TABLE,
                    VisualCharacteristic.RESIZE_ZOOM,
                    VisualCharacteristic.ROTATED_OR_CROPPED,
                ),
                PilotCaseStatus.PASS,
                "Synthetic receipt standing in for a real-browser private pilot.",
            ),
        )
        return PilotEvaluationManifest(
            dataset_name="synthetic-pilot",
            cases=cases,
            visual_acceptance=visual,
            notes="Public synthetic coverage only.",
        ).validate()

    def test_full_pilot_report_passes_structural_scenario_visual_and_publication_gates(self) -> None:
        manifest, _source, _facts = self._build_passing_pilot()
        report = build_pilot_report(self.repository, manifest)

        self.assertTrue(report.passed)
        self.assertEqual(report.working.component_count, 3)
        self.assertEqual(report.working.fact_count, 20)
        self.assertEqual(report.working.component_pin_fact_count, 16)
        self.assertEqual(report.working.parameter_limit_fact_count, 4)
        self.assertEqual(report.working.multi_package_component_count, 1)
        self.assertEqual(report.working.source_supersedes_count, 1)
        self.assertEqual(report.working.multi_anchor_fact_count, 1)
        self.assertEqual(report.negative_case_count, 5)
        self.assertEqual(report.published.fact_count, 20)
        self.assertEqual(report.case_fail_count, 0)
        self.assertEqual(report.case_not_run_count, 0)
        self.assertTrue(all(gate.passed for gate in report.gates))

    def test_uncommitted_reviewed_authority_keeps_publication_gate_open(self) -> None:
        manifest, _source, _facts = self._build_passing_pilot()
        draft = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key="pilot-unpublished-draft",
        )
        report = build_pilot_report(self.repository, manifest)
        gates = {gate.name: gate for gate in report.gates}

        self.assertFalse(report.passed)
        self.assertFalse(gates["working-authority-reviewed"].passed)
        self.assertFalse(gates["published-matches-working"].passed)
        self.assertEqual(report.working.source_count, report.published.source_count + 1)
        self.assertTrue(self.repository.source_path(draft.id).is_file())

    def test_manifest_validation_rejects_false_pass_duplicate_ids_and_bad_visual_anchor(self) -> None:
        with self.assertRaisesRegex(PilotEvaluationError, "observed_code must match"):
            PilotCase(
                "case_false_pass",
                PilotCaseCategory.WRONG_MPN,
                PilotCaseStatus.PASS,
                "UNKNOWN",
                "EXACT",
            ).validate()

        duplicate = {
            "format": "pcbknowledge-pilot-eval-v1",
            "dataset_name": "duplicate",
            "cases": [
                {
                    "id": "case_duplicate",
                    "category": "UNKNOWN",
                    "status": "NOT_RUN",
                    "expected_code": "UNKNOWN",
                    "observed_code": None,
                    "related_ids": [],
                    "notes": None,
                },
                {
                    "id": "case_duplicate",
                    "category": "WRONG_MPN",
                    "status": "NOT_RUN",
                    "expected_code": "UNKNOWN",
                    "observed_code": None,
                    "related_ids": [],
                    "notes": None,
                },
            ],
            "visual_acceptance": [],
            "notes": None,
        }
        with self.assertRaisesRegex(PilotEvaluationError, "case ids must be unique"):
            PilotEvaluationManifest.from_dict(duplicate)

        manifest, source, facts = self._build_passing_pilot()
        broken = PilotEvaluationManifest(
            dataset_name=manifest.dataset_name,
            cases=manifest.cases,
            visual_acceptance=(
                VisualAcceptance(
                    "visual_wrong_page",
                    source.id,
                    facts[0].id,
                    99,
                    (VisualCharacteristic.RESIZE_ZOOM,),
                    PilotCaseStatus.PASS,
                    "No matching anchor exists.",
                ),
            ),
        ).validate()
        with self.assertRaisesRegex(PilotEvaluationError, "does not match a Fact anchor"):
            build_pilot_report(self.repository, broken)

    def test_not_run_and_failed_cases_keep_completion_gate_open(self) -> None:
        manifest, source, facts = self._build_passing_pilot()
        not_run = PilotCase(
            "case_extra_conflict",
            PilotCaseCategory.CONFLICT,
            PilotCaseStatus.NOT_RUN,
            "CONFLICT",
            None,
            (facts[0].id,),
            "Pending conflict exercise.",
        ).validate()
        failed = PilotCase(
            "case_extra_anchor_drift",
            PilotCaseCategory.ANCHOR_DRIFT,
            PilotCaseStatus.FAIL,
            "BLOCKED",
            "EXACT",
            (source.id, facts[0].id),
            "Unexpectedly accepted drift.",
        ).validate()
        changed = PilotEvaluationManifest(
            dataset_name=manifest.dataset_name,
            cases=(*manifest.cases, not_run, failed),
            visual_acceptance=manifest.visual_acceptance,
        ).validate()
        report = build_pilot_report(self.repository, changed)
        gates = {gate.name: gate for gate in report.gates}

        self.assertFalse(report.passed)
        self.assertEqual(report.case_not_run_count, 1)
        self.assertEqual(report.case_fail_count, 1)
        self.assertFalse(gates["all-evaluation-cases-run"].passed)
        self.assertFalse(gates["no-failed-evaluation-cases"].passed)

    def test_cli_metrics_report_require_pass_and_scaffold(self) -> None:
        manifest, _source, _facts = self._build_passing_pilot()
        manifest_path = self.root / "pilot-evaluation.json"
        manifest_path.write_text(manifest.canonical_json(), encoding="utf-8")

        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = pilot_main(
                ["metrics", "--workspace", str(self.root), "--ref", "HEAD"]
            )
        self.assertEqual((code, errors.getvalue()), (0, ""))
        metrics = json.loads(output.getvalue())
        self.assertEqual(metrics["working"]["fact_count"], 20)
        self.assertEqual(metrics["published"]["fact_count"], 20)

        report_path = self.root.parent / "pilot-report.json"
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = pilot_main(
                [
                    "report",
                    "--workspace",
                    str(self.root),
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(report_path),
                    "--require-pass",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "PASS")
        self.assertEqual(json.loads(report_path.read_text("utf-8"))["status"], "PASS")

        scaffold_path = self.root.parent / "pilot-scaffold.json"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = pilot_main(["scaffold", "--output", str(scaffold_path)])
        self.assertEqual(code, 0)
        self.assertTrue(scaffold_path.is_file())
        self.assertEqual(
            json.loads(scaffold_path.read_text("utf-8"))["format"],
            "pcbknowledge-pilot-eval-v1",
        )
        with self.assertRaisesRegex(PilotEvaluationError, "refusing to overwrite"):
            write_example_manifest(scaffold_path)
