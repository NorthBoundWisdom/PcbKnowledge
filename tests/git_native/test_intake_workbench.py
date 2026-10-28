"""Synthetic selected-workspace intake browsing through actual loopback HTTP."""
from __future__ import annotations

import copy
import html
import http.client
import json
import re
import threading
import urllib.parse
from pathlib import Path
from unittest import mock

from pcbknowledge.git_native.intake import IntakeError, search_intake
from pcbknowledge.git_native.intake_workbench import IntakeBrowseApplication
from pcbknowledge.git_native.intake_views import render_intake
from pcbknowledge.git_native.server import create_server
from pcbknowledge.git_native.workspace import initialize_workspace
from pcbknowledge.git_native.workspace_server import create_server as create_workspace_server
from tests.git_native.support import RepositoryTestCase
from tests.git_native.test_intake import sample


class IntakeWorkbenchTests(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        self.directory = self.root / "knowledge" / "intake"
        self.directory.mkdir(exist_ok=True)
        self.payload = sample()
        self.payload["sources"][0]["package"] = " Exact Package "
        self.payload["source_issues"] = [{"id": "warning-1", "source_id": "source-z",
            "issue_status": "UNRESOLVED_APPLICATION_INPUTS", "description": "Missing thermal inputs"}]
        self.path = self.directory / "synthetic.json"
        self.write()
        self.application = IntakeBrowseApplication(self.root)

    def write(self):
        self.path.write_text(json.dumps(self.payload), encoding="utf-8")

    def test_exact_filters_preserve_whitespace_case_and_complete_payload(self):
        view = self.application.browse({"device": ["SYNTH-42"], "package": [" Exact Package "]})
        self.assertEqual(view.total_count, 2)
        self.assertEqual(list(view.candidates), search_intake(self.root, device="SYNTH-42", package=" Exact Package "))
        for candidate in view.candidates:
            self.assertEqual(candidate["source_issues"], self.payload["source_issues"])
        for package in ("Exact Package", " exact package "):
            self.assertEqual(self.application.browse({"package": [package]}).total_count, 0)
        self.assertEqual(self.application.browse({"device": ["synth-42"]}).total_count, 0)
        self.assertEqual(self.application.browse({"q": ["synth-42 vcc"]}).total_count, 1)

    def test_issue_mode_returns_warning_without_fact_match(self):
        self.assertEqual(self.application.browse({"q": ["thermal"]}).total_count, 0)
        view = self.application.browse({"mode": ["issues"], "q": ["thermal"]})
        self.assertEqual(view.total_count, 1)
        self.assertEqual(view.candidates[0]["source_issue"], self.payload["source_issues"][0])
        self.assertEqual(self.application.browse({"mode": ["issues"], "kind": [""]}).total_count, 1)

    def test_invalid_duplicate_unknown_and_unsupported_parameters_fail(self):
        for parameters in ({"q": ["a", "b"]}, {"q": []}, {"workspace": ["/elsewhere"]},
                           {"mode": ["approve"]}, {"mode": [""]}, {"page": ["0"]},
                           {"page": ["01"]}, {"page": ["2"]}, {"page": ["1e2"]},
                           {"q": ["a" * 513]}, {"q": ["\x00"]},
                           {"mode": ["issues"], "parameter": ["VCC"]}):
            with self.subTest(parameters=parameters), self.assertRaises(IntakeError):
                self.application.browse(parameters)

    def test_pagination_is_explicit_and_does_not_drop_candidates(self):
        self.payload["facts"] = [{**self.payload["facts"][0], "id": f"fact-{n:03}"} for n in range(57)]
        self.write()
        views = [self.application.browse({"page": [str(n)]}) for n in (1, 2, 3)]
        self.assertEqual([len(view.candidates) for view in views], [25, 25, 7])
        self.assertEqual([view.page_count for view in views], [3, 3, 3])
        self.assertEqual([item for view in views for item in view.candidates], search_intake(self.root))
        output = render_intake(views[1], change_count=4)
        self.assertIn("57 candidates", output)
        self.assertIn("Previous", output)
        self.assertIn("Next", output)
        self.assertIn("Changes (4)", output)

    def test_selected_empty_workspace_never_falls_back_to_software(self):
        self.path.unlink()
        view = self.application.browse({})
        self.assertEqual(view.total_count, 0)
        output = render_intake(view, change_count=0)
        self.assertIn(str(self.root), output)
        self.assertIn("No matching candidates", output)
        self.assertIn("No source-checkout fallback", output)
        self.assertNotIn("ADS1115", output)

    def test_html_escapes_entire_payload_filters_and_does_not_link_untrusted_urls(self):
        attack = '<script>alert("x")</script>'
        self.payload["sources"][0]["device"] = attack
        self.payload["sources"][0]["document_url"] = "javascript:alert(1)"
        self.payload["facts"][0]["conditions"] = attack
        self.write()
        output = render_intake(self.application.browse({"device": [attack]}), change_count=0)
        self.assertNotIn(attack, output)
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn('href="javascript:', output)
        blocks = re.findall(r"<pre>(.*?)</pre>", output, re.S)
        self.assertEqual([json.loads(html.unescape(block)) for block in blocks], search_intake(self.root))
        self.assertIn('method="get"', output)
        self.assertNotIn('method="post"', output)
        self.assertIn("NONCANONICAL", output)
        self.assertIn("NOT_LOCALLY_VERIFIED", output)

    def test_full_disposition_and_review_provenance_projection_is_not_reinterpreted(self):
        # Domain loader owns disposition validation; this rendering fixture verifies
        # the application and view preserve rather than summarize its full output.
        candidate = search_intake(self.root)[0]
        candidate["source_issue_dispositions"] = [{"data": {
            "disposition": "HANDLED_CONSERVATIVELY", "manufacturer_confirmed": False,
            "original_status": "UNRESOLVED_SOURCE_WORDING", "details": "<untrusted>"}}]
        candidate["source"]["review"] = {"actor_type": "AGENT", "actor_id": "synthetic-reader"}
        before = copy.deepcopy(candidate)
        with mock.patch("pcbknowledge.git_native.intake_workbench._search_loaded_facts", return_value=[candidate]):
            output = render_intake(self.application.browse({}), change_count=0)
        decoded = json.loads(html.unescape(re.search(r"<pre>(.*?)</pre>", output, re.S)[1]))
        self.assertEqual(decoded, before)
        self.assertEqual(candidate, before)

    def test_documented_workspace_runtime_serves_intake(self):
        initialize_workspace(self.root, schema_source_root=Path(__file__).resolve().parents[2])
        server = create_workspace_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original = self.path.read_bytes()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/intake?device=SYNTH-42")
            response = connection.getresponse()
            body = response.read().decode()
            connection.close()
            self.assertEqual(response.status, 200)
            self.assertEqual(self.root.resolve(), server.repository.root)
            self.assertIn(html.escape(str(self.root.resolve()), quote=True), body)
            self.assertIn("2 candidates", body)
            self.assertIn("1 same-source warnings", body)
            self.assertIn("<details><summary>Complete evidence and warnings</summary>", body)
            self.assertEqual(self.path.read_bytes(), original)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_actual_loopback_get_errors_and_post_have_no_mutation(self):
        server = create_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        before = self.path.read_bytes()
        def request(method, target, body=None, headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request(method, target, body=body, headers=headers or {})
            response = connection.getresponse()
            result = response.status, dict(response.getheaders()), response.read().decode()
            connection.close()
            return result
        try:
            status, headers, body = request("GET", "/intake?device=SYNTH-42")
            self.assertEqual(status, 200)
            self.assertIn("FACT_CANDIDATE", body)
            self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
            self.assertIn('href="/intake"', request("GET", "/review")[2])
            for query in ("device=A&device=B", "unknown=x", "q=%ZZ", "q=%FF", "q", "q=%00",
                          "mode=issues&parameter=VCC", "page=2", "q=" + "x" * 8200):
                self.assertEqual(request("GET", "/intake?" + query)[0], 400, query[:80])
            self.assertEqual(request("GET", "/intake", headers={"Host": "evil.test"})[0], 400)
            form = urllib.parse.urlencode({"csrf_token": server.csrf_token})
            status, _, _ = request("POST", "/intake", form, {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": f"http://127.0.0.1:{server.server_port}"})
            self.assertEqual(status, 404)
            self.assertEqual(self.path.read_bytes(), before)
            self.path.write_bytes(b"{}")
            self.assertEqual(request("GET", "/intake")[0], 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
