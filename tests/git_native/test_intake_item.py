"""Exact local links preserve batch-local identity and fail closed when stale."""
from __future__ import annotations

import copy
import hashlib
import html
import http.client
import json
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest import mock

from pcbknowledge.git_native.intake import IntakeError, load_intake
from pcbknowledge.git_native.intake_workbench import IntakeBrowseApplication
from pcbknowledge.git_native.intake_reference import IntakeItemNotFound, StaleIntakeItem
from pcbknowledge.git_native.intake_views import render_intake, render_intake_item
from pcbknowledge.git_native.workspace import initialize_workspace
from pcbknowledge.git_native.workspace_server import create_server
from tests.git_native.support import RepositoryTestCase
from tests.git_native.test_intake import sample


class IntakeItemTests(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        self.directory = self.root / 'knowledge' / 'intake'
        self.directory.mkdir(exist_ok=True)
        self.payload = sample()
        self.payload['source_issues'] = [{'id': 'fact-a', 'source_id': 'source-z',
            'issue_status': 'UNRESOLVED_APPLICATION_INPUTS', 'description': '<unknown>'}]
        self.path = self.directory / 'one.json'
        self.path.write_text(json.dumps(self.payload), encoding='utf-8')
        self.app = IntakeBrowseApplication(self.root)

    def link(self, mode='facts'):
        view = self.app.browse({'mode': [mode]})
        output = render_intake(view, change_count=0)
        url = html.unescape(re.search(r'href="(/intake/item\?[^\"]+)"', output)[1])
        return url, parse_qs(urlsplit(url).query)

    def test_round_trip_exact_identity_full_evidence_and_separate_record_types(self):
        for mode, kind in [('facts', 'fact'), ('issues', 'issue')]:
            _, params = self.link(mode)
            item = self.app.item(params)
            self.assertEqual(item.record_type, kind)
            self.assertEqual(item.candidate, self.app.browse({'mode': [mode]}).candidates[0])
            output = render_intake_item(item, change_count=0)
            decoded = json.loads(html.unescape(re.search(r'<pre>(.*?)</pre>', output, re.S)[1]))
            self.assertEqual(decoded, item.candidate)
            self.assertNotIn('<unknown>', output)
            self.assertIn('NOT_LOCALLY_VERIFIED', output)
            self.assertIn('not a canonical published snapshot', output)
        self.assertEqual(self.app.item(self.link()[1]).candidate['fact']['id'], 'fact-a')
        self.assertEqual(self.app.item(self.link('issues')[1]).candidate['source_issue']['id'], 'fact-a')

    def test_same_id_in_another_batch_never_substitutes(self):
        _, params = self.link()
        duplicate = copy.deepcopy(self.payload)
        duplicate['facts'][1]['value'] = 999
        (self.directory / 'two.json').write_text(json.dumps(duplicate), encoding='utf-8')
        self.assertEqual(self.app.item(params).candidate['fact']['value'], 0)
        params['batch'] = ['knowledge/intake/two.json']
        with self.assertRaises(StaleIntakeItem):
            self.app.item(params)
        self.path.unlink()
        params['batch'] = ['knowledge/intake/one.json']
        with self.assertRaises(IntakeItemNotFound):
            self.app.item(params)

    def test_changed_bytes_stale_even_when_record_values_are_same(self):
        _, params = self.link()
        self.path.write_bytes(self.path.read_bytes() + b'\n')
        with self.assertRaises(StaleIntakeItem):
            self.app.item(params)

    def test_linked_disposition_only_change_expires_context_pin(self):
        batches = load_intake(self.root)
        batches[0]['source_issue_dispositions'] = [{'path': 'knowledge/dispositions/one.json',
            'sha256': 'a' * 64, 'data': {'target': {'source_id': 'source-z', 'issue_id': 'fact-a'},
            'manufacturer_confirmed': False, 'description': 'conservative synthetic receipt'}}]
        original = self.path.read_bytes()
        with mock.patch('pcbknowledge.git_native.intake_workbench.load_intake', return_value=batches), \
                mock.patch('pcbknowledge.git_native.intake_reference.load_intake', return_value=batches):
            _, params = self.link()
            item = self.app.item(params)
            self.assertEqual(item.candidate['source_issue_dispositions'], batches[0]['source_issue_dispositions'])
            batches[0]['source_issue_dispositions'][0]['sha256'] = 'b' * 64
            with self.assertRaisesRegex(StaleIntakeItem, 'context'):
                self.app.item(params)
        self.assertEqual(self.path.read_bytes(), original)

    def test_browse_uses_one_loaded_byte_snapshot_for_display_and_link(self):
        batches = load_intake(self.root)
        expected = batches[0]['sha256']
        def loaded(_):
            self.path.write_bytes(self.path.read_bytes() + b'\n')
            return batches
        with mock.patch('pcbknowledge.git_native.intake_workbench.load_intake', side_effect=loaded) as loader:
            _, params = self.link()
            self.assertEqual(loader.call_count, 1)
            self.assertEqual(params['sha256'], [expected])
        with self.assertRaises(StaleIntakeItem):
            self.app.item(params)

    def test_missing_record_is_not_found_and_bad_parameters_are_invalid(self):
        _, original = self.link()
        wrong_id = {**original, 'id': ['missing']}
        with self.assertRaises(IntakeItemNotFound):
            self.app.item(wrong_id)
        for key, values in [('batch', ['../one.json']), ('batch', ['/knowledge/intake/one.json']),
                            ('batch', ['knowledge/intake/../one.json']),
                            ('batch', ['knowledge/intake//one.json']),
                            ('batch', ['knowledge/intake/./one.json']),
                            ('batch', ['knowledge/intake/a\\b.json']),
                            ('batch', ['knowledge/sources/one.json']),
                            ('sha256', ['A' * 64]), ('context', ['g' * 64]),
                            ('id', ['', 'fact-a']), ('id', ['\x00']), ('type', ['approve'])]:
            with self.subTest(key=key, values=values), self.assertRaises(IntakeError):
                self.app.item({**original, key: values})
        for params in ({}, {**original, 'extra': ['x']}):
            with self.assertRaises(IntakeError):
                self.app.item(params)

    def test_documented_runtime_http_detail_statuses_and_no_mutation(self):
        initialize_workspace(self.root, schema_source_root=Path(__file__).resolve().parents[2])
        server = create_server(self.root, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url, params = self.link()
        original = self.path.read_bytes()
        def request(target, method='GET', data=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                       'Origin': f'http://127.0.0.1:{server.server_port}'} if data else {}
            connection.request(method, target, body=data, headers=headers)
            response = connection.getresponse()
            body = response.read().decode()
            status = response.status
            connection.close()
            return status, body
        try:
            status, body = request(url)
            self.assertEqual(status, 200)
            self.assertEqual(self.root.resolve(), server.repository.root)
            self.assertIn(html.escape(str(self.root.resolve()), quote=True), body)
            self.assertNotIn('ADS1115', body)
            self.assertEqual(request('/intake/item?')[0], 400)
            self.assertEqual(request(url + '&id=duplicate')[0], 400)
            missing = {key: values[0] for key, values in params.items()}
            missing['id'] = 'missing'
            self.assertEqual(request('/intake/item?' + urlencode(missing))[0], 404)
            self.assertEqual(request(url, 'POST', urlencode({'csrf_token': server.csrf_token}))[0], 404)
            self.assertEqual(self.path.read_bytes(), original)
            self.path.write_bytes(original + b'\n')
            self.assertEqual(request(url)[0], 409)
            self.path.unlink()
            self.assertEqual(request(url)[0], 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
