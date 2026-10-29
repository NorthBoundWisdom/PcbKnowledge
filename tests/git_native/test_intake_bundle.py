"""Synthetic scoped handoffs preserve complete data without creating authority."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock

from pcbknowledge.git_native.cli import main
from pcbknowledge.git_native.intake import IntakeError, load_intake, search_intake, search_intake_issues
from pcbknowledge.git_native.intake_bundle import intake_bundle
from pcbknowledge.git_native.intake_reference import candidate_digest, resolve_intake_reference, StaleIntakeItem
from tests.git_native.support import RepositoryTestCase
from tests.git_native.test_intake import sample


class IntakeBundleTests(RepositoryTestCase):
    def setUp(self):
        super().setUp()
        self.path = self.root / 'knowledge/intake/one.json'
        self.path.parent.mkdir()
        self.data = sample()
        self.data['sources'][0].update(package='SYNTH-PKG', revision='R1')
        self.data['facts'][0]['conditions'] = {'unknown': None, 'extra': ['full', 1, False]}
        self.data['limitations'] = ['Synthetic unknown inputs remain unknown.']
        self.data['source_issues'] = [{'id': 'fact-a', 'source_id': 'source-z',
            'issue_status': 'UNRESOLVED_APPLICATION_INPUTS', 'description': 'Do not infer readiness <script>'}]
        self.write()

    def write(self, data=None, path=None):
        (path or self.path).write_text(json.dumps(self.data if data is None else data), encoding='utf-8')

    def bundle(self, **filters):
        return intake_bundle(self.root, device='SYNTH-42', **filters)

    def invoke(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                code = main(['--repo', str(self.root), 'intake', 'bundle', *arguments])
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_complete_candidates_and_individually_resolvable_pins(self):
        result = self.bundle()
        self.assertEqual(result['summary'], {'batch_count': 1, 'source_scope_count': 1,
                                            'fact_count': 2, 'issue_count': 1})
        batch = result['batches'][0]
        self.assertEqual(batch['sources'], self.data['sources'])
        self.assertEqual(batch['batch_context'], {k: v for k, v in self.data.items()
                         if k not in {'sources', 'facts', 'source_issues'}})
        self.assertEqual([r['candidate'] for r in batch['facts']], search_intake(self.root))
        self.assertEqual([r['candidate'] for r in batch['issues']], search_intake_issues(self.root))
        self.assertEqual(batch['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        for record in batch['facts'] + batch['issues']:
            verified = resolve_intake_reference(self.root, {k: [v] for k, v in record['reference'].items()})
            self.assertEqual(verified.candidate, record['candidate'])
            self.assertEqual(verified.selectors(), record['reference'])
            self.assertFalse(record['canonical'])
            self.assertEqual(record['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertFalse(result['canonical'])
        self.assertEqual(result['operation'], 'CAPTURE_CURRENT_METADATA')

    def test_complete_fingerprint_is_deterministic_and_not_self_referential(self):
        result = self.bundle()
        self.assertEqual(result, self.bundle())
        digest = result.pop('bundle_sha256')
        self.assertEqual(digest, candidate_digest(result))
        mutations = [(['summary', 'fact_count'], 3), (['canonical'], True),
                     (['batches', 0, 'batch_context', 'limitations'], ['changed']),
                     (['batches', 0, 'sources', 0, 'revision'], 'R2'),
                     (['batches', 0, 'facts', 0, 'candidate', 'fact', 'value'], 7)]
        for keys, value in mutations:
            changed = copy.deepcopy(result)
            target = changed
            for key in keys[:-1]:
                target = target[key]
            target[keys[-1]] = value
            self.assertNotEqual(digest, candidate_digest(changed))

    def test_exact_conjunctive_filters_and_missing_raw_metadata(self):
        self.assertEqual(self.bundle(source_id='source-z', manufacturer='Synthetic Maker',
                                    package='SYNTH-PKG', revision='R1')['summary']['fact_count'], 2)
        for filters in ({'source_id': 'SOURCE-Z'}, {'manufacturer': 'synthetic maker'},
                        {'package': 'SYNTH-PKG '}, {'revision': 'r1'}, {'revision': ' R1'}):
            self.assertEqual(self.bundle(**filters)['batches'], [])
        for value in (None, 1, ['R1'], {'revision': 'R1'}):
            self.data['sources'][0]['revision'] = value
            self.write()
            self.assertEqual(self.bundle(revision='R1')['batches'], [])
            self.assertEqual(self.bundle()['batches'][0]['sources'][0]['revision'], value)
        del self.data['sources'][0]['revision']
        self.write()
        self.assertEqual(self.bundle(revision='R1')['batches'], [])

    def test_sources_without_facts_or_issues_and_warning_only_sources_remain(self):
        self.data['facts'] = []
        self.write()
        self.assertEqual(self.bundle()['summary'], {'batch_count': 1, 'source_scope_count': 1,
                                                  'fact_count': 0, 'issue_count': 1})
        self.data['source_issues'] = []
        self.write()
        self.assertEqual(self.bundle()['summary']['source_scope_count'], 1)
        self.assertEqual(self.bundle()['batches'][0]['sources'], self.data['sources'])
        self.path.unlink()
        self.assertEqual(self.bundle()['summary'], {'batch_count': 0, 'source_scope_count': 0,
                                                  'fact_count': 0, 'issue_count': 0})

    def test_duplicate_batch_local_ids_remain_distinct(self):
        other = copy.deepcopy(self.data)
        other['facts'][0]['value'] = 99
        self.write(other, self.path.parent / 'two.json')
        result = self.bundle()
        self.assertEqual(result['summary']['fact_count'], 4)
        self.assertEqual([b['path'] for b in result['batches']],
                         ['knowledge/intake/one.json', 'knowledge/intake/two.json'])
        first, second = result['batches']
        self.assertNotEqual(first['facts'][1]['reference'], second['facts'][1]['reference'])
        self.assertEqual(second['facts'][1]['candidate']['fact']['value'], 99)
        self.assertEqual(first['issues'][0]['reference']['type'], 'issue')
        self.assertEqual(first['facts'][0]['reference']['type'], 'fact')

    def test_unselected_sources_not_projected_but_batch_context_retained(self):
        self.data['sources'].append({'id': 'other', 'device': 'OTHER', 'status': 'DRAFT'})
        self.data['facts'].append({'id': 'other-fact', 'source_id': 'other', 'status': 'DRAFT'})
        self.data['source_issues'].append({'id': 'other-issue', 'source_id': 'other'})
        self.data['source_review_receipts'] = {'other': 'Recorded batch context only'}
        self.write()
        batch = self.bundle()['batches'][0]
        self.assertEqual(len(batch['sources']), 1)
        self.assertEqual(len(batch['facts']), 2)
        self.assertEqual(len(batch['issues']), 1)
        self.assertEqual(batch['batch_context']['source_review_receipts'], self.data['source_review_receipts'])

    def test_one_load_no_hidden_reread_and_old_pin_stays_stale(self):
        batches = load_intake(self.root)
        def change_after_load(_):
            self.path.write_bytes(self.path.read_bytes() + b'\n')
            return batches
        with mock.patch('pcbknowledge.git_native.intake_bundle.load_intake', side_effect=change_after_load) as loader:
            result = self.bundle()
        self.assertEqual(loader.call_count, 1)
        batch = result['batches'][0]
        self.assertEqual(batch['sha256'], batches[0]['sha256'])
        for record in batch['facts'] + batch['issues']:
            self.assertEqual(record['reference']['sha256'], batch['sha256'])
            with self.assertRaises(StaleIntakeItem):
                resolve_intake_reference(self.root, {k: [v] for k, v in record['reference'].items()})

    def test_dispositions_preserved_and_changes_alter_pins_and_bundle_digest(self):
        batches = load_intake(self.root)
        receipt = {'path': 'knowledge/dispositions/synthetic.json', 'sha256': 'a' * 64,
                   'data': {'target': {'source_id': 'source-z', 'issue_id': 'fact-a'},
                            'manufacturer_confirmed': False, 'description': 'Unknown outside scope'}}
        batches[0]['source_issue_dispositions'] = [receipt]
        with mock.patch('pcbknowledge.git_native.intake_bundle.load_intake', return_value=batches):
            first = copy.deepcopy(self.bundle())
            self.assertEqual(first['batches'][0]['source_issue_dispositions'], [receipt])
            for record in first['batches'][0]['facts'] + first['batches'][0]['issues']:
                self.assertEqual(record['candidate']['source_issue_dispositions'], [receipt])
            receipt['sha256'] = 'b' * 64
            second = self.bundle()
        self.assertNotEqual(first['bundle_sha256'], second['bundle_sha256'])
        for kind in ('facts', 'issues'):
            self.assertNotEqual(first['batches'][0][kind][0]['reference']['context'],
                                second['batches'][0][kind][0]['reference']['context'])

    def test_real_loader_receipt_roundtrip_and_changed_receipt_refusal(self):
        from tests.git_native.test_intake_dispositions import synthetic_batch, synthetic_disposition
        self.write(synthetic_batch())
        relative = self.path.relative_to(self.root).as_posix()
        receipt = synthetic_disposition(self.path, relative)
        receipt_path = self.root / 'knowledge/intake-dispositions/synthetic.json'
        receipt_path.parent.mkdir()
        receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
        captured = intake_bundle(self.root, device='SYNTH-A')
        batch = captured['batches'][0]
        self.assertEqual(batch['source_issue_dispositions'][0]['data'], receipt)
        records = batch['facts'] + batch['issues']
        for record in records:
            params = {k: [v] for k, v in record['reference'].items()}
            verified = resolve_intake_reference(self.root, params)
            self.assertEqual(verified.candidate, record['candidate'])
            self.assertEqual(verified.candidate['source_issue_dispositions'][0]['data'], receipt)
        receipt['summary'] = 'Changed synthetic context only; original issue remains unresolved.'
        receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
        changed = intake_bundle(self.root, device='SYNTH-A')
        self.assertNotEqual(captured['bundle_sha256'], changed['bundle_sha256'])
        self.assertEqual(batch['sha256'], changed['batches'][0]['sha256'])
        for record in records:
            with self.assertRaises(StaleIntakeItem):
                resolve_intake_reference(self.root, {k: [v] for k, v in record['reference'].items()})
        receipt['target']['batch_sha256'] = '0' * 64
        receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
        code, output, _ = self.invoke('--device', 'SYNTH-A')
        self.assertEqual(code, 2)
        self.assertEqual(output, '')

    def test_no_scope_invalid_filters_and_unsupported_selection_fail_closed(self):
        for filters in ({}, {'manufacturer': 'Synthetic Maker'}, {'device': ''},
                        {'source_id': ' '}, {'device': 1}):
            with self.assertRaises(IntakeError):
                intake_bundle(self.root, **filters)
        for args in ([], ['--manufacturer', 'Synthetic Maker'], ['--device', ''],
                     ['--device', 'SYNTH-42', '--device', 'OTHER'],
                     ['--device', 'SYNTH-42', '--revision', 'R1', '--revision', 'R1'],
                     ['--device', 'SYNTH-42', '--kind', 'anything'],
                     ['--device', 'SYNTH-42', 'lexical'], ['--dev', 'SYNTH-42']):
            code, output, _ = self.invoke(*args)
            self.assertEqual(code, 2, args)
            self.assertEqual(output, '')

    def test_invalid_unselected_batch_prevents_partial_output(self):
        (self.path.parent / 'bad.json').write_text('{"canonical":true}', encoding='utf-8')
        code, output, errors = self.invoke('--device', 'SYNTH-42')
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('invalid intake', errors)

    def test_unreferenceable_record_is_not_returned_as_a_valid_bundle(self):
        self.data['facts'][0]['id'] = 'x' * 513
        self.write()
        code, output, _ = self.invoke('--device', 'SYNTH-42')
        self.assertEqual(code, 2)
        self.assertEqual(output, '')

    def test_public_entrypoint_selected_workspace_and_filesystem_unchanged(self):
        script = Path(__file__).resolve().parents[2] / 'configs/pcbknowledge_agent.py'
        shutil.rmtree(self.root / '.pcbknowledge')
        def snapshot():
            return {str(p.relative_to(self.root)): (p.read_bytes() if p.is_file() else None)
                    for p in self.root.rglob('*')}
        before = snapshot()
        command = [sys.executable, '-B', str(script), '--repo', str(self.root),
                   'intake', 'bundle', '--device', 'SYNTH-42']
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.bundle())
        self.assertNotIn('ADS1115', result.stdout)
        self.assertEqual(snapshot(), before)
        self.path.write_text('invalid', encoding='utf-8')
        before = snapshot()
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(snapshot(), before)
