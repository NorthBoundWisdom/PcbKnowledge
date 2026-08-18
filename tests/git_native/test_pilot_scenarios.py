from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest

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
    PilotCaseStatus,
    PilotEvaluationError,
    PilotEvaluationManifest,
)
from pcbknowledge.git_native.pilot_scenarios import (
    PILOT_SCENARIO_FORMAT,
    PilotScenarioReport,
    PilotScenarioSuite,
    apply_scenario_report,
    example_scenario_suite_payload,
    run_pilot_scenarios,
)
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class PilotScenarioRunnerTests(RepositoryTestCase):
    def _source(
        self,
        key: str,
        document: str,
        revision: str,
        *,
        supersedes: str | None = None,
        blocked: bool = False,
        approve: bool = True,
    ):
        source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key=key,
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf(f"{document}-{revision}"))
        edited = source.edit(
            title=f"{document} revision {revision}",
            document_number=document,
            revision=revision,
            source_locator=f"https://example.invalid/{document}-{revision}.pdf",
            source_publisher="PcbKnowledge Scenario Fixtures",
            license_class=(
                LicenseClass.LICENSED_BLOCKED_FOR_AI
                if blocked
                else LicenseClass.OPEN_LICENSE
            ),
            license_note="Synthetic scenario fixture",
            evidence=evidence,
            preparation_note="Synthetic only",
            supersedes=supersedes,
        )
        if approve:
            edited = edited.submit().approve("scenario source reviewed")
        self.repository.save_source(source, edited, source.revision_token)
        return edited

    def _approved_fact(self, *, key: str, fact_type: FactType, payload, source, page: int, quote: str, conditions=()):
        fact = self.repository.create_fact(
            idempotency_key=key,
            fact_type=fact_type,
            payload=payload,
            prepared_by=PreparedBy.AGENT,
            conditions=tuple(conditions),
            applicability=("PK-SCENARIO-Q16",),
            evidence_anchors=(
                EvidenceAnchor.create(
                    source.id,
                    page,
                    bbox=(0.10, 0.20, 0.90, 0.35),
                    quote=quote,
                ),
            ),
        )
        ready = self.repository.submit_fact(fact.id, expected_revision=fact.revision_token)
        return self.repository.approve_fact(
            ready.id,
            expected_revision=ready.revision_token,
            comment="scenario fact reviewed",
        )

    def _fixture(self) -> dict[str, object]:
        old_source = self._source("scenario-source-a", "PK-SCENARIO-1", "A")
        new_source = self._source(
            "scenario-source-b",
            "PK-SCENARIO-1",
            "B",
            supersedes=old_source.id,
        )
        manufacturer = self.repository.create_manufacturer(
            "PcbKnowledge Scenario Fixtures",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="scenario-manufacturer",
        )
        component = self.repository.create_component(
            manufacturer.id,
            "PK-SCENARIO-Q16",
            family="PK-SCENARIO",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="scenario-component",
        )
        package = self.repository.create_package(
            "QFN-16",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="scenario-package",
        )
        other_package = self.repository.create_package(
            "TSSOP-16",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="scenario-other-package",
        )
        pin = self._approved_fact(
            key="scenario-pin",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id, package.id, "1", "VIN", "Input supply", ()
            ),
            source=new_source,
            page=2,
            quote="1 VIN Input supply",
            conditions=("QFN-16 package",),
        )
        absolute = self._approved_fact(
            key="scenario-absolute",
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
            source=new_source,
            page=4,
            quote="Input voltage -0.3 to 40 V",
        )
        recommended = self._approved_fact(
            key="scenario-recommended",
            fact_type=FactType.PARAMETER_LIMIT,
            payload=ParameterLimitPayload(
                component.id,
                "Input voltage",
                ParameterLimitKind.RECOMMENDED_OPERATING,
                4.5,
                12,
                36,
                "V",
            ),
            source=new_source,
            page=5,
            quote="Input voltage 4.5 to 36 V",
        )
        subprocess.run(["git", "add", "knowledge", "evidence"], cwd=self.root, check=True)
        subprocess.run(
            [
                "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "-q", "-m", "published scenario fixture",
            ],
            cwd=self.root,
            check=True,
        )

        blocked = self._source(
            "scenario-blocked",
            "PK-BLOCK",
            "A",
            blocked=True,
            approve=False,
        )
        conflict = self.repository.create_fact(
            idempotency_key="scenario-pin-conflict",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id,
                package.id,
                "1",
                "VIN",
                "Conflicting input function",
                (),
            ),
            prepared_by=PreparedBy.AGENT,
            conditions=("QFN-16 package",),
            applicability=("PK-SCENARIO-Q16",),
            evidence_anchors=(
                EvidenceAnchor.create(
                    new_source.id,
                    2,
                    bbox=(0.10, 0.20, 0.90, 0.35),
                    quote="1 VIN Conflicting input function",
                ),
            ),
        )
        uncommitted = self._source("scenario-uncommitted", "PK-UNCOMMITTED", "A")
        (self.root / "scenario-code-change.txt").write_text("code-side change\n", encoding="utf-8")
        return {
            "old": old_source,
            "new": new_source,
            "manufacturer": manufacturer,
            "component": component,
            "package": package,
            "other_package": other_package,
            "pin": pin,
            "absolute": absolute,
            "recommended": recommended,
            "blocked": blocked,
            "conflict": conflict,
            "uncommitted": uncommitted,
        }

    @staticmethod
    def _scenario(identifier: str, case: str, kind: str, expected: str, parameters: dict[str, object], *, snapshot: str = "WORKING") -> dict[str, object]:
        return {
            "id": identifier,
            "pilot_case_id": case,
            "kind": kind,
            "expected_code": expected,
            "snapshot": snapshot,
            "parameters": parameters,
            "notes": None,
        }

    def _suite(self, f: dict[str, object]) -> PilotScenarioSuite:
        anchor = f["pin"].evidence_anchors[0]
        scenarios = [
            self._scenario("scenario_wrong_mpn", "case_wrong_mpn", "COMPONENT_LOOKUP", "UNKNOWN", {"manufacturer_id": f["manufacturer"].id, "raw_mpn": "DOES-NOT-EXIST"}),
            self._scenario("scenario_wrong_package", "case_wrong_package", "PIN_FACT_LOOKUP", "UNKNOWN", {"component_id": f["component"].id, "package_id": f["other_package"].id, "pin_number": "1"}),
            self._scenario("scenario_wrong_revision", "case_wrong_revision", "SOURCE_REVISION_LOOKUP", "UNKNOWN", {"document_number": "PK-SCENARIO-1", "revision": "Z", "publisher": "PcbKnowledge Scenario Fixtures"}),
            self._scenario("scenario_supersedes", "case_supersede", "SOURCE_SUPERSEDES", "MATCH", {"source_id": f["new"].id, "target_source_id": f["old"].id}),
            self._scenario("scenario_license_block", "case_license_block", "SOURCE_LICENSE_GATE", "BLOCKED", {"source_id": f["blocked"].id}),
            self._scenario("scenario_limit_distinction", "case_abs_max_recommended", "PARAMETER_LIMIT_DISTINCTION", "DISTINCT", {"component_id": f["component"].id, "parameter": "Input voltage"}),
            self._scenario("scenario_conflict", "case_conflict", "FACT_CONFLICT", "CONFLICT", {"fact_id": f["pin"].id}),
            self._scenario("scenario_anchor_integrity", "case_anchor_drift", "ANCHOR_INTEGRITY", "MATCH", {"fact_id": f["pin"].id, "source_id": f["new"].id, "page": anchor.page, "quote_sha256": anchor.quote_sha256}),
            self._scenario("scenario_review_history", "case_review_history", "REVIEW_HISTORY", "MATCH", {"record_id": f["pin"].id, "actions": ["SUBMITTED", "APPROVED"]}),
            self._scenario("scenario_uncommitted", "case_uncommitted_approval", "PUBLICATION_VISIBILITY", "WORKING_ONLY", {"record_id": f["uncommitted"].id}),
            self._scenario("scenario_change_scope", "case_mixed_commit", "CHANGE_SCOPE", "MIXED", {}),
        ]
        return PilotScenarioSuite.from_dict(
            {
                "format": PILOT_SCENARIO_FORMAT,
                "dataset_name": "scenario-runner-test",
                "scenarios": scenarios,
                "notes": "Synthetic executable scenario suite.",
            }
        )

    def _manifest(self) -> PilotEvaluationManifest:
        rows = [
            ("case_wrong_mpn", "WRONG_MPN", "UNKNOWN"),
            ("case_wrong_package", "WRONG_PACKAGE", "UNKNOWN"),
            ("case_wrong_revision", "WRONG_REVISION", "UNKNOWN"),
            ("case_supersede", "SUPERSEDE", "MATCH"),
            ("case_license_block", "LICENSE_BLOCK", "BLOCKED"),
            ("case_abs_max_recommended", "ABS_MAX_VS_RECOMMENDED", "DISTINCT"),
            ("case_conflict", "CONFLICT", "CONFLICT"),
            ("case_anchor_drift", "ANCHOR_DRIFT", "MATCH"),
            ("case_review_history", "REVIEW_HISTORY", "MATCH"),
            ("case_uncommitted_approval", "UNCOMMITTED_APPROVAL", "WORKING_ONLY"),
            ("case_mixed_commit", "MIXED_COMMIT", "MIXED"),
        ]
        return PilotEvaluationManifest.from_dict(
            {
                "format": "pcbknowledge-pilot-eval-v1",
                "dataset_name": "scenario-runner-test",
                "cases": [
                    {"id": i, "category": c, "status": "NOT_RUN", "expected_code": e, "observed_code": None, "related_ids": [], "notes": None}
                    for i, c, e in rows
                ],
                "visual_acceptance": [],
                "notes": None,
            }
        )

    def test_contract_and_runner_cover_exact_negative_policy_and_review_state(self) -> None:
        payload = example_scenario_suite_payload()
        PilotScenarioSuite.from_dict(payload)
        duplicate = json.loads(json.dumps(payload))
        duplicate["scenarios"].append(dict(duplicate["scenarios"][0]))
        with self.assertRaisesRegex(PilotEvaluationError, "scenario ids must be unique"):
            PilotScenarioSuite.from_dict(duplicate)
        extra = json.loads(json.dumps(payload))
        extra["scenarios"][0]["parameters"]["fuzzy"] = True
        with self.assertRaisesRegex(PilotEvaluationError, "unsupported fields"):
            PilotScenarioSuite.from_dict(extra)

        report = run_pilot_scenarios(self.repository, self._suite(self._fixture()))
        self.assertTrue(report.passed)
        observed = {item.scenario_id: item.observed_code for item in report.results}
        self.assertEqual(
            observed,
            {
                "scenario_wrong_mpn": "UNKNOWN",
                "scenario_wrong_package": "UNKNOWN",
                "scenario_wrong_revision": "UNKNOWN",
                "scenario_supersedes": "MATCH",
                "scenario_license_block": "BLOCKED",
                "scenario_limit_distinction": "DISTINCT",
                "scenario_conflict": "CONFLICT",
                "scenario_anchor_integrity": "MATCH",
                "scenario_review_history": "MATCH",
                "scenario_uncommitted": "WORKING_ONLY",
                "scenario_change_scope": "MIXED",
            },
        )

    def test_working_and_published_snapshots_are_explicit(self) -> None:
        f = self._fixture()
        suite = PilotScenarioSuite.from_dict(
            {
                "format": PILOT_SCENARIO_FORMAT,
                "dataset_name": "snapshot-selection",
                "scenarios": [
                    self._scenario("scenario_working_conflict", "case_conflict", "PIN_FACT_LOOKUP", "CONFLICT", {"component_id": f["component"].id, "package_id": f["package"].id, "pin_number": "1"}),
                    self._scenario("scenario_published_exact", "case_table_pin", "PIN_FACT_LOOKUP", "EXACT", {"component_id": f["component"].id, "package_id": f["package"].id, "pin_number": "1"}, snapshot="PUBLISHED"),
                ],
                "notes": None,
            }
        )
        self.assertTrue(run_pilot_scenarios(self.repository, suite).passed)

    def test_overlay_and_stale_working_binding_fail_closed(self) -> None:
        report = run_pilot_scenarios(self.repository, self._suite(self._fixture()))
        manifest = self._manifest()
        effective = apply_scenario_report(manifest, report, self.repository)
        self.assertTrue(all(case.status is PilotCaseStatus.PASS for case in effective.cases))
        wrong = json.loads(manifest.canonical_json())
        wrong["cases"][0]["category"] = "LICENSE_BLOCK"
        with self.assertRaisesRegex(PilotEvaluationError, "not compatible"):
            apply_scenario_report(PilotEvaluationManifest.from_dict(wrong), report, self.repository)
        self.repository.create_package("BGA-64", prepared_by=PreparedBy.AGENT, idempotency_key="stale-working")
        with self.assertRaisesRegex(PilotEvaluationError, "working authority fingerprint"):
            apply_scenario_report(manifest, report, self.repository)

    def test_git_and_published_bindings_are_independent(self) -> None:
        report = run_pilot_scenarios(self.repository, self._suite(self._fixture()))
        manifest = self._manifest()
        subprocess.run(["git", "add", "scenario-code-change.txt"], cwd=self.root, check=True)
        with self.assertRaisesRegex(PilotEvaluationError, "Git working-state fingerprint"):
            apply_scenario_report(manifest, report, self.repository)

        self.tearDown()
        self.setUp()
        report = run_pilot_scenarios(self.repository, self._suite(self._fixture()))
        manifest = self._manifest()
        subprocess.run(
            [
                "git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "--allow-empty", "-q", "-m", "advance published ref only",
            ],
            cwd=self.root,
            check=True,
        )
        with self.assertRaisesRegex(PilotEvaluationError, "published commit changed"):
            apply_scenario_report(manifest, report, self.repository)

    def test_cli_runs_suite_and_overlays_result_without_touching_authority(self) -> None:
        suite = self._suite(self._fixture())
        local = self.root / ".pcbknowledge" / "scenario-tests"
        local.mkdir(parents=True)
        suite_path = local / "suite.json"
        report_path = local / "report.json"
        suite_path.write_text(suite.canonical_json(), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors := io.StringIO()):
            code = pilot_main(["scenario-run", "--workspace", str(self.root), "--suite", str(suite_path), "--output", str(report_path), "--require-pass"])
        self.assertEqual((code, errors.getvalue()), (0, ""))
        self.assertTrue(PilotScenarioReport.from_path(report_path).passed)

        scaffold = local / "template.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pilot_main(["scenario-scaffold", "--output", str(scaffold)]), 0)
            self.assertEqual(pilot_main(["scenario-scaffold", "--output", str(scaffold)]), 0)

        manifest_path = local / "manifest.json"
        manifest_path.write_text(self._manifest().canonical_json(), encoding="utf-8")
        with contextlib.redirect_stdout(output := io.StringIO()), contextlib.redirect_stderr(errors := io.StringIO()):
            code = pilot_main(["report", "--workspace", str(self.root), "--manifest", str(manifest_path), "--scenario-report", str(report_path)])
        self.assertEqual((code, errors.getvalue()), (0, ""))
        self.assertEqual(json.loads(output.getvalue())["evaluation"]["case_pass_count"], 11)


if __name__ == "__main__":
    unittest.main()
