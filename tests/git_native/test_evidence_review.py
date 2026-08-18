from __future__ import annotations

import http.client
import shutil
import tempfile
import threading
from pathlib import Path

from pcbknowledge.git_native.evidence_review import EvidenceReviewApplication
from pcbknowledge.git_native.evidence_review_views import render_fact_evidence_review
from pcbknowledge.git_native.model import (
    ComponentPinPayload,
    EvidenceAnchor,
    FactType,
    LicenseClass,
    PreparedBy,
)
from pcbknowledge.git_native.pdfjs_vendor import (
    PDFJS_VERSION,
    PdfJsVendorError,
    default_pdfjs_vendor_root,
    validate_pdfjs_vendor,
)
from pcbknowledge.git_native.workspace_server import create_server
from tests.git_native.support import RepositoryTestCase, minimal_pdf


class EvidenceReviewTests(RepositoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.allowed_source = self._source(
            key="allowed-source",
            revision="A",
            license_class=LicenseClass.OPEN_LICENSE,
            label="allowed evidence",
        )
        self.blocked_source = self._source(
            key="blocked-source",
            revision="B",
            license_class=LicenseClass.RESTRICTED,
            label="blocked evidence",
        )
        manufacturer = self.repository.create_manufacturer(
            "PcbKnowledge Fixtures",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03b-manufacturer",
        )
        self.component = self.repository.create_component(
            manufacturer.id,
            "PK6200-Q16",
            family="PK6200",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03b-component",
        )
        self.package = self.repository.create_package(
            "QFN-16",
            prepared_by=PreparedBy.AGENT,
            idempotency_key="p03b-package",
        )
        self.fact = self.repository.create_fact(
            idempotency_key="p03b-two-anchor-fact",
            fact_type=FactType.COMPONENT_PIN,
            payload=ComponentPinPayload(
                self.component.id,
                self.package.id,
                "1",
                "VIN",
                "Input supply",
                (),
            ),
            prepared_by=PreparedBy.AGENT,
            conditions=("Nominal operating condition",),
            applicability=("PK6200-Q16",),
            evidence_anchors=(
                EvidenceAnchor.create(
                    self.allowed_source.id,
                    1,
                    bbox=(0.1, 0.2, 0.8, 0.3),
                    quote="1 VIN Input supply",
                ),
                EvidenceAnchor.create(
                    self.blocked_source.id,
                    1,
                    bbox=(0.2, 0.4, 0.7, 0.6),
                    quote="Restricted comparison anchor",
                ),
            ),
        )

    def _source(
        self,
        *,
        key: str,
        revision: str,
        license_class: LicenseClass,
        label: str,
    ):
        source = self.repository.create_source(
            prepared_by=PreparedBy.AGENT,
            idempotency_key=key,
        )
        evidence = self.repository.import_pdf_bytes(minimal_pdf(label))
        updated = source.edit(
            title=f"PK6200 Synthetic Datasheet Rev {revision}",
            document_number="PK-DS-6200",
            revision=revision,
            source_locator=f"https://example.invalid/pk6200-{revision.lower()}.pdf",
            source_publisher="PcbKnowledge Fixtures",
            license_class=license_class,
            license_note=(
                "Synthetic public fixture"
                if license_class is LicenseClass.OPEN_LICENSE
                else "Synthetic fixture marked restricted for policy testing"
            ),
            evidence=evidence,
            preparation_note=None,
            supersedes=None,
        )
        self.repository.save_source(source, updated, source.revision_token)
        return updated

    def test_projection_preserves_source_revision_bbox_quote_and_policy_gate(self) -> None:
        view = EvidenceReviewApplication(self.repository).fact_review(self.fact.id)

        self.assertEqual(view.subject_context, ("Component: PK6200-Q16", "Package: QFN-16"))
        self.assertEqual(view.applicability, ("PK6200-Q16",))
        self.assertEqual(len(view.anchors), 2)
        allowed, blocked = view.anchors
        self.assertEqual(
            (allowed.source_revision, allowed.page, allowed.coordinate_space),
            ("A", 1, "PDF_NORMALIZED_V1"),
        )
        self.assertEqual(allowed.bbox, (0.1, 0.2, 0.8, 0.3))
        self.assertEqual(
            allowed.evidence_url,
            f"/sources/{self.allowed_source.id}/evidence",
        )
        self.assertIsNone(allowed.blocked_reason)
        self.assertIsNone(blocked.evidence_url)
        self.assertIn("RESTRICTED", blocked.blocked_reason or "")

    def test_renderer_emits_multi_anchor_navigation_and_normalized_svg_overlay(self) -> None:
        view = EvidenceReviewApplication(self.repository).fact_review(self.fact.id)
        payload = render_fact_evidence_review(view)

        self.assertIn('href="#evidence-anchor-1"', payload)
        self.assertIn('href="#evidence-anchor-2"', payload)
        self.assertIn('viewBox="0 0 1 1"', payload)
        self.assertIn('x="0.1" y="0.2" width="0.7" height="0.1"', payload)
        self.assertIn("quote_sha256", payload)
        self.assertIn("revision A", payload)
        self.assertIn("revision B", payload)
        self.assertIn(f'data-pdf-url="/sources/{self.allowed_source.id}/evidence"', payload)
        self.assertNotIn(f'data-pdf-url="/sources/{self.blocked_source.id}/evidence"', payload)

    def test_loopback_fact_page_loads_only_local_viewer_assets_and_blocks_restricted_pdf(self) -> None:
        server = create_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, headers, payload = self._get(server.server_port, f"/facts/{self.fact.id}")
            self.assertEqual(status, 200)
            text = payload.decode("utf-8")
            self.assertIn("Visual evidence review", text)
            self.assertIn('/static/evidence-review.mjs', text)
            self.assertIn('/static/evidence-review.css', text)
            self.assertIn("Selected knowledge workspace", text)
            csp = headers.get("content-security-policy", "")
            self.assertIn("script-src 'self'", csp)
            self.assertIn("worker-src 'self'", csp)
            self.assertIn("connect-src 'self'", csp)
            self.assertNotIn("'unsafe-inline'", csp)

            status, headers, payload = self._get(
                server.server_port, f"/sources/{self.allowed_source.id}/evidence"
            )
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("content-type"), "application/pdf")
            self.assertTrue(payload.startswith(b"%PDF-"))

            status, _headers, payload = self._get(
                server.server_port, f"/sources/{self.blocked_source.id}/evidence"
            )
            self.assertEqual(status, 403)
            self.assertIn(b"blocked by Source license policy", payload)
            self.assertNotIn(minimal_pdf("blocked evidence"), payload)

            status, headers, payload = self._get(server.server_port, "/static/evidence-review.mjs")
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("content-type"), "text/javascript; charset=utf-8")
            script = payload.decode("utf-8")
            self.assertIn("./vendor/pdfjs/6.2.108/pdf.min.mjs", script)
            self.assertNotIn("https://", script)
            self.assertNotIn("http://", script)

            status, _headers, _payload = self._get(
                server.server_port,
                "/static/vendor/pdfjs/6.2.108/vendor-manifest.json",
            )
            self.assertEqual(status, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    @staticmethod
    def _get(port: int, path: str):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", path)
        response = connection.getresponse()
        payload = response.read()
        headers = {key.lower(): value for key, value in response.getheaders()}
        status = response.status
        connection.close()
        return status, headers, payload


class PdfJsVendorTests(RepositoryTestCase):
    def test_committed_pdfjs_distribution_is_exactly_pinned(self) -> None:
        receipt = validate_pdfjs_vendor()
        self.assertEqual(receipt.version, PDFJS_VERSION)
        self.assertEqual(receipt.build, "legacy")
        self.assertEqual(receipt.file_count, 3)

    def test_vendor_validation_rejects_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "pdfjs"
            shutil.copytree(default_pdfjs_vendor_root(), root)
            target = root / "pdf.min.mjs"
            payload = bytearray(target.read_bytes())
            payload[len(payload) // 2] ^= 1
            target.write_bytes(payload)
            with self.assertRaisesRegex(PdfJsVendorError, "SHA-256"):
                validate_pdfjs_vendor(root)


if __name__ == "__main__":
    import unittest

    unittest.main()
