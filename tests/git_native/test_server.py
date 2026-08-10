from __future__ import annotations

import http.client
import re
import threading
import urllib.parse
from http import HTTPStatus

from pcbknowledge.git_native.model import PreparedBy, RecordStatus
from pcbknowledge.git_native.server import EditorHTTPServer, create_server
from tests.git_native.support import RepositoryTestCase, minimal_pdf


def _multipart(
    fields: dict[str, str],
    *,
    filename: str | None = None,
    payload: bytes | None = None,
) -> tuple[str, bytes]:
    boundary = "pcbknowledge-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            )
        )
    if filename is not None and payload is not None:
        chunks.extend(
            (
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="pdf"; filename="',
                filename.encode("utf-8"),
                b'"\r\nContent-Type: application/pdf\r\n\r\n',
                payload,
                b"\r\n",
            )
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


class LocalEditorServerTests(RepositoryTestCase):
    server: EditorHTTPServer
    thread: threading.Thread

    def setUp(self) -> None:
        super().setUp()
        self.server = create_server(self.root, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(
        self,
        method: str,
        target: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        request_headers = dict(headers or {})
        if content_type is not None:
            request_headers["Content-Type"] = content_type
        connection.request(method, target, body=body, headers=request_headers)
        response = connection.getresponse()
        response_body = response.read()
        response_headers = {name.lower(): value for name, value in response.getheaders()}
        connection.close()
        return response.status, response_headers, response_body

    def post_urlencoded(
        self,
        target: str,
        fields: dict[str, str],
        *,
        origin: str | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        body = urllib.parse.urlencode(fields).encode()
        headers = {} if origin is None else {"Origin": origin}
        return self.request(
            "POST",
            target,
            body=body,
            content_type="application/x-www-form-urlencoded",
            headers=headers,
        )

    def create_complete_record(self) -> str:
        content_type, body = _multipart(
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": "",
                "title": "TPS5430 数据手册",
                "document_number": "SLVS632",
                "revision": "G",
                "source_publisher": "Texas Instruments",
                "source_locator": "https://example.test/tps5430.pdf",
                "license_class": "PUBLIC_REFERENCE",
                "license_note": "公开资料",
                "preparation_note": "人工核对版本",
                "supersedes": "",
            },
            filename="datasheet.pdf",
            payload=minimal_pdf("TPS5430"),
        )
        status, headers, _ = self.request(
            "POST", "/records/new", body=body, content_type=content_type
        )
        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        match = re.fullmatch(r"/records/(pk_[0-9a-f]+)", headers["location"])
        self.assertIsNotNone(match)
        assert match is not None
        return match.group(1)

    def test_dashboard_is_immediately_available_without_login(self) -> None:
        status, headers, body = self.request("GET", "/")

        text = body.decode("utf-8")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("资料工作台", text)
        self.assertIn("没有账号和数据库", text)
        self.assertNotIn("登录", text)
        self.assertEqual(headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'none'", headers["content-security-policy"])

    def test_agent_prepared_draft_appears_in_the_same_gui(self) -> None:
        record = self.repository.create(
            prepared_by=PreparedBy.AGENT, idempotency_key="agent-visible-draft"
        )
        updated = record.edit(
            title="Agent prepared TPS5430 draft",
            document_number=None,
            revision=None,
            source_locator=None,
            source_publisher=None,
            license_class=record.license_class,
            license_note=None,
            evidence=record.evidence,
            preparation_note="等待工程师补充",
            supersedes=None,
        )
        self.repository.save(record, updated, record.revision_token)

        status, _, body = self.request("GET", "/")
        text = body.decode("utf-8")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Agent prepared TPS5430 draft", text)
        self.assertIn("AI 准备", text)

    def test_create_submit_approve_diff_and_evidence_vertical_flow(self) -> None:
        index_before = self.root.joinpath(".git", "index").read_bytes()
        record_id = self.create_complete_record()
        draft = self.repository.load(record_id)
        self.assertEqual(draft.status, RecordStatus.DRAFT)
        self.assertEqual(draft.missing_fields, ())

        status, headers, _ = self.post_urlencoded(
            f"/records/{record_id}/submit",
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": draft.revision_token,
            },
        )
        self.assertEqual((status, headers["location"]), (HTTPStatus.SEE_OTHER, f"/records/{record_id}"))

        ready = self.repository.load(record_id)
        self.assertEqual(ready.status, RecordStatus.READY_FOR_REVIEW)
        status, _, _ = self.post_urlencoded(
            f"/records/{record_id}/approve",
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": ready.revision_token,
                "review_comment": "来源与原件一致",
            },
        )
        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        approved = self.repository.load(record_id)
        self.assertEqual(approved.status, RecordStatus.APPROVED)

        status, headers, evidence = self.request("GET", f"/records/{record_id}/evidence")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(headers["content-type"], "application/pdf")
        self.assertEqual(evidence, minimal_pdf("TPS5430"))

        status, _, diff = self.request("GET", "/diff")
        self.assertEqual(status, HTTPStatus.OK)
        diff_text = diff.decode("utf-8")
        self.assertIn(record_id, diff_text)
        self.assertIn("new binary evidence", diff_text)
        self.assertEqual(
            self.root.joinpath(".git", "index").read_bytes(),
            index_before,
            "the GUI must not stage files",
        )

    def test_reject_then_edit_returns_record_to_draft(self) -> None:
        record_id = self.create_complete_record()
        draft = self.repository.load(record_id)
        self.post_urlencoded(
            f"/records/{record_id}/submit",
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": draft.revision_token,
            },
        )
        ready = self.repository.load(record_id)
        status, _, _ = self.post_urlencoded(
            f"/records/{record_id}/reject",
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": ready.revision_token,
                "review_comment": "请补充资料编号",
            },
        )
        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        rejected = self.repository.load(record_id)
        self.assertEqual(rejected.status, RecordStatus.REJECTED)

        content_type, body = _multipart(
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": rejected.revision_token,
                "title": rejected.title or "",
                "document_number": "SLVS632G",
                "revision": rejected.revision or "",
                "source_publisher": rejected.source.publisher or "",
                "source_locator": rejected.source.locator or "",
                "license_class": rejected.license_class.value,
                "license_note": rejected.license_note or "",
                "preparation_note": rejected.preparation_note or "",
                "supersedes": rejected.supersedes or "",
            }
        )
        status, _, _ = self.request(
            "POST",
            f"/records/{record_id}/save",
            body=body,
            content_type=content_type,
        )
        self.assertEqual(status, HTTPStatus.SEE_OTHER)
        edited = self.repository.load(record_id)
        self.assertEqual(edited.status, RecordStatus.DRAFT)
        self.assertEqual(edited.document_number, "SLVS632G")
        self.assertIsNone(edited.review.decision)

    def test_stale_revision_and_invalid_csrf_fail_closed(self) -> None:
        record_id = self.create_complete_record()
        status, _, _ = self.post_urlencoded(
            f"/records/{record_id}/submit",
            {"csrf_token": self.server.csrf_token, "expected_revision": "0" * 64},
        )
        self.assertEqual(status, HTTPStatus.CONFLICT)
        self.assertEqual(self.repository.load(record_id).status, RecordStatus.DRAFT)

        status, _, _ = self.post_urlencoded(
            f"/records/{record_id}/submit",
            {"csrf_token": "wrong", "expected_revision": self.repository.load(record_id).revision_token},
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertEqual(self.repository.load(record_id).status, RecordStatus.DRAFT)

    def test_non_loopback_host_and_cross_origin_mutation_are_rejected(self) -> None:
        status, _, _ = self.request("GET", "/", headers={"Host": "evil.example"})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

        record_id = self.create_complete_record()
        record = self.repository.load(record_id)
        status, _, _ = self.post_urlencoded(
            f"/records/{record_id}/submit",
            {
                "csrf_token": self.server.csrf_token,
                "expected_revision": record.revision_token,
            },
            origin="http://evil.example",
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertEqual(self.repository.load(record_id).status, RecordStatus.DRAFT)


if __name__ == "__main__":
    import unittest

    unittest.main()
