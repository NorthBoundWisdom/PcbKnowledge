"""Synthetic cross-interface metadata pins; verification never refreshes a pin."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import shutil
import sys
from unittest import mock

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import load_intake, search_intake
from pcbknowledge.git_native.intake_workbench import IntakeBrowseApplication
from tests.git_native.support import RepositoryTestCase
from tests.git_native.test_intake import sample


class IntakeReferenceCliTests(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.root / 'knowledge/intake/one.json'
        self.path.parent.mkdir()
        self.payload = sample()
        self.payload['source_issues'] = [{'id': 'fact-a', 'source_id': 'source-z',
            'issue_status': 'UNRESOLVED_APPLICATION_INPUTS', 'description': 'Unknown <thermal>'}]
        self.path.write_text(json.dumps(self.payload), encoding='utf-8')
        self.selectors = {'batch': 'knowledge/intake/one.json', 'id': 'fact-a', 'type': 'fact'}

    def invoke(self, action, selectors, extra=()):
        arguments = ['--repo', str(self.root), 'intake', action]
        for key, value in selectors.items():
            arguments.extend(['--' + key, value])
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                result = main(arguments + list(extra))
            except SystemExit as error:
                result = error.code
        return result, output.getvalue(), errors.getvalue()

    def pin(self, **changes):
        code, output, errors = self.invoke('pin', {**self.selectors, **changes})
        self.assertEqual(code, 0, errors)
        return json.loads(output)

    def test_pin_then_item_keeps_full_payload_and_does_not_claim_approval(self):
        captured = self.pin()
        self.assertEqual(captured['operation'], 'CAPTURE_CURRENT_METADATA')
        self.assertFalse(captured['canonical'])
        self.assertEqual(captured['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(captured['candidate'], search_intake(self.root)[0])
        self.assertEqual(captured['reference']['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        code, output, errors = self.invoke('item', captured['reference'])
        self.assertEqual(code, 0, errors)
        verified = json.loads(output)
        self.assertEqual(verified['operation'], 'VERIFY_PINNED_METADATA')
        self.assertEqual(verified['reference'], captured['reference'])
        self.assertEqual(verified['candidate'], captured['candidate'])
        self.assertEqual(verified['candidate']['source_issues'], self.payload['source_issues'])

    def test_gui_and_cli_use_identical_pins_and_candidate(self):
        app = IntakeBrowseApplication(self.root)
        for kind, mode in [('fact', 'facts'), ('issue', 'issues')]:
            captured = self.pin(type=kind)
            params = {key: [value] for key, value in captured['reference'].items()}
            item = app.item(params)
            self.assertEqual(item.candidate, captured['candidate'])
            browse = app.browse({'mode': [mode]})
            self.assertEqual(item.candidate, browse.candidates[0])
            self.assertEqual(item.context_sha256, browse.candidate_digests[0])
            self.assertEqual(item.batch_sha256, browse.batch_digests[self.selectors['batch']])

    def test_duplicate_id_cannot_cross_batch_or_record_type(self):
        original = self.pin()['reference']
        duplicate = copy.deepcopy(self.payload)
        duplicate['facts'][1]['value'] = 77
        (self.path.parent / 'two.json').write_text(json.dumps(duplicate), encoding='utf-8')
        second = self.pin(batch='knowledge/intake/two.json')
        self.assertEqual(second['candidate']['fact']['value'], 77)
        for changed in ({'batch': 'knowledge/intake/two.json'}, {'type': 'issue'}):
            code, output, errors = self.invoke('item', {**original, **changed})
            self.assertEqual(code, 2)
            self.assertEqual(output, '')
            self.assertIn('STALE_INTAKE_REFERENCE', errors)
        self.path.unlink()
        code, output, errors = self.invoke('item', original)
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('INTAKE_ITEM_NOT_FOUND', errors)

    def test_byte_only_change_rejected_not_silently_recaptured(self):
        captured = self.pin()['reference']
        self.path.write_bytes(self.path.read_bytes() + b'\n')
        code, output, errors = self.invoke('item', captured)
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('STALE_INTAKE_REFERENCE', errors)
        self.assertNotEqual(self.pin()['reference']['sha256'], captured['sha256'])

    def test_context_and_digest_tampering_rejected(self):
        captured = self.pin()['reference']
        for key in ('sha256', 'context'):
            code, output, errors = self.invoke('item', {**captured, key: '0' * 64})
            self.assertEqual(code, 2)
            self.assertEqual(output, '')
            self.assertIn('STALE_INTAKE_REFERENCE', errors)

    def test_disposition_only_change_invalidates_reference(self):
        batches = load_intake(self.root)
        batches[0]['source_issue_dispositions'] = [{'path': 'knowledge/dispositions/one.json',
            'sha256': 'a' * 64, 'data': {'target': {'source_id': 'source-z', 'issue_id': 'fact-a'},
            'manufacturer_confirmed': False, 'description': 'Synthetic conservative handling'}}]
        with mock.patch('pcbknowledge.git_native.intake_reference.load_intake', return_value=batches):
            captured = self.pin()
            self.assertEqual(captured['candidate']['source_issue_dispositions'], batches[0]['source_issue_dispositions'])
            batches[0]['source_issue_dispositions'][0]['sha256'] = 'b' * 64
            code, output, errors = self.invoke('item', captured['reference'])
            self.assertEqual(code, 2)
            self.assertEqual(output, '')
            self.assertIn('STALE_INTAKE_REFERENCE', errors)

    def test_missing_pins_duplicate_unknown_and_malformed_selectors_fail(self):
        captured = self.pin()['reference']
        for key in captured:
            code, output, _ = self.invoke('item', {k: v for k, v in captured.items() if k != key})
            self.assertEqual(code, 2)
            self.assertEqual(output, '')
            for action, selectors in [('pin', self.selectors), ('item', captured)]:
                if key in selectors:
                    code, output, _ = self.invoke(action, selectors, ['--' + key, selectors[key]])
                    self.assertEqual(code, 2)
                    self.assertEqual(output, '')
        for changes in ({'batch': '../one.json'}, {'batch': 'knowledge/intake//one.json'},
                        {'type': 'approve'}, {'id': ''}, {'id': '\x00'},
                        {'context': 'A' * 64}, {'sha256': 'x'}, {'id': 'a' * 513}):
            code, output, _ = self.invoke('item', {**captured, **changes})
            self.assertEqual(code, 2)
            self.assertEqual(output, '')
        self.assertEqual(self.invoke('pin', self.selectors, ['--sha256', '0' * 64])[0], 2)
        self.assertEqual(self.invoke('pin', self.selectors, ['--unknown', 'x'])[0], 2)
        self.assertEqual(self.invoke('pin', {**self.selectors, 'id': 'missing'})[0], 2)

    def test_capture_loads_once_and_digests_the_displayed_snapshot(self):
        batches = load_intake(self.root)
        expected = batches[0]['sha256']
        def loaded(_):
            self.path.write_bytes(self.path.read_bytes() + b'\n')
            return batches
        with mock.patch('pcbknowledge.git_native.intake_reference.load_intake', side_effect=loaded) as loader:
            captured = self.pin()
            self.assertEqual(loader.call_count, 1)
        self.assertEqual(captured['reference']['sha256'], expected)
        self.assertEqual(self.invoke('item', captured['reference'])[0], 2)

    def test_actual_entrypoint_is_readonly_and_selected_workspace_bound(self):
        script = Path(__file__).resolve().parents[2] / 'configs/pcbknowledge_agent.py'
        def snapshot():
            return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        # Required authority directories remain for the workspace contract; the
        # optional original-cache layout must not be initialized by these reads.
        shutil.rmtree(self.root / '.pcbknowledge')
        directories_before = {str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_dir()}
        before = snapshot()
        command = [sys.executable, '-B', str(script), '--repo', str(self.root), 'intake', 'pin']
        for key, value in self.selectors.items():
            command += ['--' + key, value]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        captured = json.loads(result.stdout)
        self.assertEqual(captured['candidate']['source']['device'], 'SYNTH-42')
        self.assertNotIn('ADS1115', result.stdout)
        command = [sys.executable, '-B', str(script), '--repo', str(self.root), 'intake', 'item']
        for key, value in captured['reference'].items():
            command += ['--' + key, value]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot(), before)
        self.assertEqual({str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_dir()}, directories_before)
        self.path.unlink()
        empty_before = snapshot()
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('INTAKE_ITEM_NOT_FOUND', result.stderr)
        self.assertEqual(snapshot(), empty_before)
