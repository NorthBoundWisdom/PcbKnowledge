"""Synthetic source-revision selection; no electrical or revision-order inference."""
from __future__ import annotations

import contextlib
import copy
import html
import http.client
import io
import json
import threading
import urllib.parse
from unittest import mock

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError, search_intake, search_intake_issues
from pcbknowledge.git_native.intake_reference import capture_intake_reference
from pcbknowledge.git_native.intake_report import intake_report
from pcbknowledge.git_native.intake_workbench import IntakeBrowseApplication
from pcbknowledge.git_native.workspace_server import create_server
from tests.git_native.support import RepositoryTestCase
from tests.git_native.test_intake_filters import fixture


class IntakeRevisionTests(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        self.directory = self.root / "knowledge/intake"
        self.directory.mkdir(exist_ok=True)
        self.data = fixture()
        # Both batches reuse exact source, fact and issue IDs. Only the source's
        # revision is an identity selector, not evidence or explanatory prose.
        for source in self.data["sources"]:
            source["revision"] = "Rev A"
            source["description"] = "Rev B mentioned as a comparison only"
        for fact in self.data["facts"]:
            fact["evidence"]["revision"] = "Rev B"
        self.other = copy.deepcopy(self.data)
        for source in self.other["sources"]:
            source["revision"] = "Rev B"
        self.write()
        self.application = IntakeBrowseApplication(self.root)

    def write(self):
        for name, payload in (("a.json", self.data), ("b.json", self.other)):
            (self.directory / name).write_text(json.dumps(payload), encoding="utf-8")

    def invoke(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["--repo", str(self.root), "intake", *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exact_revision_separates_same_ids_and_preserves_complete_payloads(self):
        for search in (search_intake, search_intake_issues):
            all_candidates = search(self.root)
            selected = search(self.root, revision="Rev A")
            self.assertEqual(selected, [c for c in all_candidates if c["path"].endswith("/a.json")])
            self.assertTrue(selected)
            self.assertTrue(all(c["source"]["revision"] == "Rev A" for c in selected))
            self.assertFalse(any(c["canonical"] for c in selected))
            self.assertTrue(all(c["evidence_verification"] == "NOT_LOCALLY_VERIFIED" for c in selected))
        self.assertEqual(len(search_intake(self.root, "Rev B", revision="Rev A")), 10)
        self.assertEqual(len(search_intake(self.root, revision="Rev B")), 10)
        self.assertEqual(search_intake(self.root, revision="revision not recorded"), [])

    def test_revision_is_conjunctive_and_not_fact_evidence(self):
        result = search_intake(self.root, revision="Rev A", source_id="ti-lm1117-q",
                               manufacturer="TI", device="LM1117", kind="recommended_operating",
                               parameter="VIN_to_GND")
        self.assertEqual([c["fact"]["id"] for c in result], ["ti-operating"])
        self.assertEqual(result[0]["fact"]["evidence"]["revision"], "Rev B")
        self.assertEqual(search_intake(self.root, revision="Rev A", source_id="ti-lm1117-q", manufacturer="ST"), [])
        warning = search_intake_issues(self.root, revision="Rev A", device="MCP23017")
        self.assertEqual([c["source_issue"] for c in warning], self.data["source_issues"])

    def test_missing_null_and_nonstring_source_revision_never_fall_back(self):
        for value in (None, 123, ["Rev A"], {"revision": "Rev A"}, False):
            for source in self.data["sources"]:
                source["revision"] = value
            self.write()
            for search in (search_intake, search_intake_issues):
                self.assertEqual(search(self.root, revision="Rev A"), [])
            self.assertIn("No matching recorded source", intake_report(self.root, device="LM1117", revision="Rev A"))
        for source in self.data["sources"]:
            del source["revision"]
        self.write()
        self.assertEqual(search_intake(self.root, revision="Rev A"), [])
        self.assertEqual(search_intake_issues(self.root, revision="Rev A"), [])

    def test_revision_preserves_case_whitespace_and_unicode(self):
        for revision in ("rev a", " Rev A ", "Ｒｅｖ A", "Re\u0301v A"):
            for source in self.data["sources"]:
                source["revision"] = revision
            self.write()
            for search in (search_intake, search_intake_issues):
                self.assertTrue(search(self.root, revision=revision))
                self.assertEqual(search(self.root, revision="Rev A"), [])
                self.assertEqual(search(self.root, revision="Rév A"), [])
        for value in ("", " ", [], 1):
            for search in (search_intake, search_intake_issues):
                with self.assertRaises(IntakeError):
                    search(self.root, revision=value)

    def test_cli_search_issues_report_and_audit_dispatch(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        for action, search in (("search", search_intake), ("issues", search_intake_issues)):
            code, stdout, stderr = self.invoke(action, "--revision", "Rev A", "--device", "MCP23017")
            self.assertEqual((code, stderr), (0, ""))
            self.assertEqual(json.loads(stdout), search(self.root, revision="Rev A", device="MCP23017"))
        code, stdout, stderr = self.invoke("report", "--device", "LM1117", "--revision", "Rev A")
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(stdout, intake_report(self.root, device="LM1117", revision="Rev A"))
        self.assertIn("Matched batches: 1.", stdout)
        with mock.patch("pcbknowledge.git_native.intake_evidence_audit.intake_evidence_audit", return_value={}) as audit:
            code, stdout, stderr = self.invoke("evidence-audit", "--cache-root", str(self.root),
                                             "--cache-file", "synthetic.bin", "--revision", "Rev A")
            self.assertEqual((code, stdout.strip(), stderr), (0, "{}", ""))
            self.assertEqual(audit.call_args.kwargs["revision"], "Rev A")
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.iterdir()}, before)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke("search", "--rev", "Rev A")

    def test_no_filter_keeps_original_candidates_and_reference_pins(self):
        before = search_intake(self.root)
        parameters = {"batch": ["knowledge/intake/a.json"], "id": ["ti-operating"], "type": ["fact"]}
        pin = capture_intake_reference(self.root, parameters).projection(captured=True)
        self.assertEqual(search_intake(self.root, revision=None), before)
        self.assertEqual(capture_intake_reference(self.root, parameters).projection(captured=True), pin)
        self.assertEqual(list(self.application.browse({}).candidates), before)
        self.assertEqual(list(self.application.browse({"revision": [""]}).candidates), before)
        with self.assertRaises(IntakeError):
            self.application.browse({"revision": ["Rev A", "Rev B"]})

    def test_actual_workspace_http_filter_and_pagination_preserve_revision(self):
        self.data["facts"] = [{**self.data["facts"][0], "id": f"f-{n:02}"} for n in range(26)]
        self.write()
        server = create_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        try:
            for query, expected in (({"revision": "Rev A"}, "26 candidates"),
                                    ({"revision": "Rev B", "mode": "issues"}, "1 candidates"),
                                    ({"revision": "rev a"}, "0 candidates")):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                connection.request("GET", "/intake?" + urllib.parse.urlencode(query))
                response = connection.getresponse()
                body = response.read().decode()
                connection.close()
                self.assertEqual(response.status, 200)
                self.assertIn(expected, body)
                self.assertIn('name="revision"', body)
                if expected == "26 candidates":
                    self.assertIn("revision=Rev+A", html.unescape(body))
                    self.assertIn("page=2", html.unescape(body))
            self.assertEqual({p.name: p.read_bytes() for p in self.directory.iterdir()}, before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
