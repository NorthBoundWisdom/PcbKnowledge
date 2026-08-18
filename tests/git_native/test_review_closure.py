from __future__ import annotations

import http.client
import subprocess
import threading
import urllib.parse

from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    PreparedBy,
    RecordStatus,
    RecordTransitionError,
)
from pcbknowledge.git_native.server import create_server as create_base_server
from pcbknowledge.git_native.workbench import WorkbenchApplication
from pcbknowledge.git_native.workspace_server import create_server as create_workspace_server
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class ReviewClosureTests(RepositoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.application = WorkbenchApplication(self.repository)

    def _approved_source(
        self,
        key: str = "review-source",
        *,
        license_class: LicenseClass = LicenseClass.OPEN_LICENSE,
    ):
        source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key=key,
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf(key))
        updated = source.edit(
            title=f"Synthetic {key}",
            document_number="PK-RV-1",
            revision="A",
            source_locator=f"https://example.invalid/{key}.pdf",
            source_publisher="PcbKnowledge Fixtures",
            license_class=license_class,
            license_note=(
                "Synthetic open fixture"
                if license_class is LicenseClass.OPEN_LICENSE
                else "Synthetic fixture deliberately blocked for review testing"
            ),
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )
        self.repository.save_source(source, updated, source.revision_token)
        submitted = self.repository.submit_source(
            updated.id,
            expected_revision=updated.revision_token,
        )
        return self.repository.approve_source(
            submitted.id,
            expected_revision=submitted.revision_token,
            comment="Source checked",
        )

    def _entities(self, suffix: str = "main"):
        manufacturer = self.repository.create_manufacturer(
            f"Fixture Maker {suffix}",
            prepared_by=PreparedBy.AGENT,
            idempotency_key=f"manufacturer-{suffix}",
        )
        component = self.repository.create_component(
            manufacturer.id,
            f"PK-{suffix.upper()}-16",
            family="PK",
            prepared_by=PreparedBy.AGENT,
            idempotency_key=f"component-{suffix}",
        )
        package = self.repository.create_package(
            f"QFN-16-{suffix}",
            prepared_by=PreparedBy.AGENT,
            idempotency_key=f"package-{suffix}",
        )
        return manufacturer, component, package

    def _ready_fact(
        self,
        *,
        key: str,
        source,
        component,
        package,
        pin_number: str = "1",
        complete_anchor: bool = True,
    ):
        anchor = (
            EvidenceAnchor.create(
                source.id,
                1,
                bbox=(0.1, 0.2, 0.8, 0.3),
                quote=f"{pin_number} VIN Input supply",
            )
            if complete_anchor
            else EvidenceAnchor.create(source.id, 1)
        )
        fact = self.repository.create_fact(
            idempotency_key=key,
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id,
                package.id,
                pin_number,
                "VIN",
                "Input supply",
                (),
            ),
            prepared_by=PreparedBy.AGENT,
            evidence_anchors=(anchor,),
        )
        return self.repository.submit_fact(
            fact.id,
            expected_revision=fact.revision_token,
        )

    @staticmethod
    def _commit_all(root, message: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
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

    def test_fact_approval_projects_exact_selected_closure_and_excludes_unrelated_data(self) -> None:
        source = self._approved_source()
        manufacturer, component, package = self._entities()
        fact = self._ready_fact(
            key="selected-fact",
            source=source,
            component=component,
            package=package,
        )
        unrelated = self.repository.create_fact(
            idempotency_key="unrelated-fact",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                component.id,
                package.id,
                "9",
                "NC",
                "No connect",
                (),
            ),
            prepared_by=PreparedBy.AGENT,
        )

        decision = self.application.fact_review_decision(fact.id)

        self.assertTrue(decision.can_approve)
        self.assertTrue(decision.can_reject)
        self.assertEqual(decision.change_scope, "DATA_ONLY")
        self.assertIn(f"knowledge/facts/{fact.id}.json", decision.selected.paths)
        self.assertIn(f"knowledge/entities/{manufacturer.id}.json", decision.selected.paths)
        self.assertIn(f"knowledge/entities/{component.id}.json", decision.selected.paths)
        self.assertIn(f"knowledge/entities/{package.id}.json", decision.selected.paths)
        self.assertIn(f"knowledge/sources/{source.id}.json", decision.selected.paths)
        self.assertIn(source.evidence.path, decision.selected.paths)
        self.assertIn(fact.id, decision.selected.diff_text)
        self.assertNotIn(unrelated.id, decision.selected.diff_text)

    def test_clean_committed_review_candidate_can_approve_and_becomes_data_only(self) -> None:
        source = self._approved_source()
        _manufacturer, component, package = self._entities()
        fact = self._ready_fact(
            key="clean-fact",
            source=source,
            component=component,
            package=package,
        )
        self._commit_all(self.root, "ready review closure")

        decision = self.application.fact_review_decision(fact.id)
        self.assertEqual(decision.change_scope, "CLEAN")
        self.assertTrue(decision.can_approve)

        approved = self.application.approve_fact(
            fact.id,
            expected_revision=fact.revision_token,
            comment="Evidence checked",
        )
        self.assertEqual(approved.status, RecordStatus.APPROVED)
        self.assertEqual(self.repository.git_change_scope().value, "DATA_ONLY")

    def test_missing_anchor_conflict_and_blocked_license_each_fail_closed_for_approval(self) -> None:
        source = self._approved_source()
        _manufacturer, component, package = self._entities()
        incomplete = self._ready_fact(
            key="incomplete-anchor",
            source=source,
            component=component,
            package=package,
            complete_anchor=False,
        )
        decision = self.application.fact_review_decision(incomplete.id)
        self.assertFalse(decision.can_approve)
        self.assertTrue(decision.can_reject)
        self.assertTrue(any("Missing" in item for item in decision.approval_blockers))
        with self.assertRaisesRegex(RecordTransitionError, "review approval is blocked"):
            self.application.approve_fact(
                incomplete.id,
                expected_revision=incomplete.revision_token,
                comment=None,
            )
        self.assertEqual(
            self.repository.load_fact(incomplete.id).status,
            RecordStatus.READY_FOR_REVIEW,
        )

        first = self._ready_fact(
            key="conflict-a",
            source=source,
            component=component,
            package=package,
            pin_number="7",
        )
        second = self._ready_fact(
            key="conflict-b",
            source=source,
            component=component,
            package=package,
            pin_number="7",
        )
        for fact in (first, second):
            conflict_decision = self.application.fact_review_decision(fact.id)
            self.assertFalse(conflict_decision.can_approve)
            self.assertTrue(
                any("Semantic conflict" in item for item in conflict_decision.approval_blockers)
            )

        blocked_source = self._approved_source(
            "restricted-source",
            license_class=LicenseClass.RESTRICTED,
        )
        blocked = self._ready_fact(
            key="license-blocked-fact",
            source=blocked_source,
            component=component,
            package=package,
            pin_number="8",
        )
        blocked_decision = self.application.fact_review_decision(blocked.id)
        self.assertFalse(blocked_decision.can_approve)
        self.assertTrue(
            any("blocks evidence review" in item for item in blocked_decision.approval_blockers)
        )

    def test_mixed_scope_blocks_both_approval_and_rejection_without_mutation(self) -> None:
        source = self._approved_source()
        _manufacturer, component, package = self._entities()
        fact = self._ready_fact(
            key="mixed-fact",
            source=source,
            component=component,
            package=package,
        )
        (self.root / "workspace-note.txt").write_text("code-side change\n", encoding="utf-8")

        decision = self.application.fact_review_decision(fact.id)
        self.assertEqual(decision.change_scope, "MIXED")
        self.assertFalse(decision.can_approve)
        self.assertFalse(decision.can_reject)
        before = self.repository.load_fact(fact.id)

        with self.assertRaisesRegex(RecordTransitionError, "review rejection is blocked"):
            self.application.reject_fact(
                fact.id,
                expected_revision=fact.revision_token,
                comment="Reject",
            )
        self.assertEqual(self.repository.load_fact(fact.id), before)

    def test_source_decision_uses_same_scope_gate(self) -> None:
        source = self.repository.create_source(
            prepared_by=PreparedBy.HUMAN,
            idempotency_key="source-scope",
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf("source scope"))
        updated = source.edit(
            title="Scope source",
            document_number="PK-SCOPE",
            revision="A",
            source_locator="https://example.invalid/scope.pdf",
            source_publisher="Fixtures",
            license_class=LicenseClass.OPEN_LICENSE,
            license_note="Synthetic",
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )
        self.repository.save_source(source, updated, source.revision_token)
        ready = self.repository.submit_source(
            updated.id,
            expected_revision=updated.revision_token,
        )
        (self.root / "workspace-note.txt").write_text("code-side change\n", encoding="utf-8")

        decision = self.application.source_review_decision(ready.id)
        self.assertEqual(decision.change_scope, "MIXED")
        self.assertFalse(decision.can_approve)
        self.assertFalse(decision.can_reject)
        with self.assertRaisesRegex(RecordTransitionError, "review approval is blocked"):
            self.application.approve_source(
                ready.id,
                expected_revision=ready.revision_token,
                comment=None,
            )

    def test_reject_edit_resubmit_approve_preserves_append_only_fact_review_history(self) -> None:
        source = self._approved_source()
        _manufacturer, component, package = self._entities()
        ready = self._ready_fact(
            key="history-fact",
            source=source,
            component=component,
            package=package,
        )
        rejected = self.application.reject_fact(
            ready.id,
            expected_revision=ready.revision_token,
            comment="Clarify condition",
        )
        edited = rejected.edit(conditions=("Updated condition",))
        self.repository.save_fact(rejected, edited, rejected.revision_token)
        resubmitted = self.repository.submit_fact(
            edited.id,
            expected_revision=edited.revision_token,
        )
        approved = self.application.approve_fact(
            resubmitted.id,
            expected_revision=resubmitted.revision_token,
            comment="Condition verified",
        )

        self.assertEqual(
            tuple(event.action.value for event in approved.review_history),
            ("SUBMITTED", "REJECTED", "SUBMITTED", "APPROVED"),
        )
        self.assertEqual(approved.review_history[1].comment, "Clarify condition")
        self.assertEqual(approved.review_history[3].comment, "Condition verified")

    def test_http_fact_decision_uses_visual_evidence_before_actions_and_never_stages_git(self) -> None:
        source = self._approved_source()
        _manufacturer, component, package = self._entities()
        fact = self._ready_fact(
            key="http-review-fact",
            source=source,
            component=component,
            package=package,
        )
        server = create_workspace_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _headers, payload = self._request(server.server_port, "GET", f"/facts/{fact.id}")
            self.assertEqual(status, 200)
            text = payload.decode("utf-8")
            self.assertIn("Visual evidence review", text)
            self.assertIn("Human decision closure", text)
            self.assertLess(text.index("Visual evidence review"), text.index("Human decision closure"))
            self.assertIn(f'/facts/{fact.id}/approve', text)
            self.assertIn("Selected diff", text)

            body = urllib.parse.urlencode(
                {
                    "csrf_token": server.csrf_token,
                    "expected_revision": fact.revision_token,
                    "review_comment": "Browser review complete",
                }
            ).encode("utf-8")
            status, headers, _payload = self._request(
                server.server_port,
                "POST",
                f"/facts/{fact.id}/approve",
                body=body,
                content_type="application/x-www-form-urlencoded",
            )
            self.assertEqual(status, 303)
            self.assertEqual(headers.get("location"), f"/facts/{fact.id}")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        approved = self.repository.load_fact(fact.id)
        self.assertEqual(approved.status, RecordStatus.APPROVED)
        cached = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=self.root, check=False
        )
        self.assertEqual(cached.returncode, 0, "GUI review must not stage Git")

    def test_http_blocked_decision_returns_conflict_and_approved_fact_has_no_mutation_form(self) -> None:
        source = self._approved_source()
        _manufacturer, component, package = self._entities()
        fact = self._ready_fact(
            key="http-blocked-fact",
            source=source,
            component=component,
            package=package,
            complete_anchor=False,
        )
        server = create_base_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            body = urllib.parse.urlencode(
                {
                    "csrf_token": server.csrf_token,
                    "expected_revision": fact.revision_token,
                    "review_comment": "Should not approve",
                }
            ).encode("utf-8")
            status, _headers, payload = self._request(
                server.server_port,
                "POST",
                f"/facts/{fact.id}/approve",
                body=body,
                content_type="application/x-www-form-urlencoded",
            )
            self.assertEqual(status, 409)
            self.assertIn(b"review approval is blocked", payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(self.repository.load_fact(fact.id).status, RecordStatus.READY_FOR_REVIEW)

        complete = self._ready_fact(
            key="immutable-fact",
            source=source,
            component=component,
            package=package,
            pin_number="2",
        )
        approved = self.application.approve_fact(
            complete.id,
            expected_revision=complete.revision_token,
            comment=None,
        )
        server = create_base_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _headers, payload = self._request(server.server_port, "GET", f"/facts/{approved.id}")
            self.assertEqual(status, 200)
            text = payload.decode("utf-8")
            self.assertIn("approved and immutable in place", text)
            self.assertNotIn(f'/facts/{approved.id}/approve', text)
            self.assertNotIn(f'/facts/{approved.id}/reject', text)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    @staticmethod
    def _request(
        port: int,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
    ):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {}
        if content_type is not None:
            headers["Content-Type"] = content_type
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        status = response.status
        connection.close()
        return status, response_headers, payload


if __name__ == "__main__":
    import unittest

    unittest.main()
