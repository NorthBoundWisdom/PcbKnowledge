"""Synthetic low-drive MOSFET condition and unknown-state preservation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticLowVoltageMosfetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-low-drive.json'
        path = self.root / relative
        path.parent.mkdir(parents=True)
        # Invented values and identities, never a manufacturer ratings fixture.
        specs = {
            'identity': {'kind': 'pin', 'value': {'orderable': 'SYNTH-FET-R2',
                'view': 'top', 'pins': {'A': 'G', 'B': 'S', 'C': 'D'},
                'complete_cad_footprint': None}},
            'stress': {'kind': 'absolute_maximum', 'value': {'VDS_max_V': 9,
                'VGS_min_V': -4, 'VGS_max_V': 4},
                'conditions': {'recommended_operating': False, 'safe_replacement': False}},
            'threshold': {'kind': 'electrical_characteristic',
                'value': {'min_V': 0.41, 'max_V': 0.83, 'typ_V': None},
                'conditions': {'ID_uA': 210, 'VDS_equals_VGS': True, 'TJ_C': 24,
                               'useful_load_enhancement': False}},
            'resistance': {'kind': 'electrical_characteristic',
                'value': {'VGS_V': 1.6, 'ID_A': 2.7, 'typ_ohm': 0.029,
                          'max_ohm': 0.041, 'hot_max_ohm': None},
                'conditions': {'TJ_C': 24, 'pulse_max_us': 250, 'duty_max_percent': 1.7,
                               'test_current_is_board_rating': False}},
            'thermal': {'kind': 'thermal_characteristic',
                'value': {'short_ambient_typ_C_W': 61, 'short_ambient_max_C_W': 88,
                          'steady_ambient_max_C_W': 141, 'steady_foot_max_C_W': 39},
                'conditions': {'duration_max_s': 4, 'foot_reference': 'drain',
                               'board_inch': [1.2, 1.2], 'board_material': 'SYNTH-FR',
                               'qualified_continuous_current_A': None}},
            'charge': {'kind': 'electrical_characteristic',
                'value': {'typ_nC': 4.7, 'max_nC': 8.3, 'charge_at_other_gate_nC': None,
                          'qualified_pwm_Hz': None},
                'conditions': {'VGS_V': 2.2, 'VDS_V': 3.7, 'ID_A': 6.1, 'TJ_C': 24,
                               'guaranteed_by_design': True, 'production_tested': False}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
                'acceptance_status': 'DRAFT',
                'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                             'device': 'SYNTH-FET-R2', 'package': 'SYNTH-PKG',
                             'revision': 'Synthetic R2', 'status': 'DRAFT'}],
                'facts': [{'id': k, 'source_id': 'synthetic', 'parameter': k,
                           'status': 'DRAFT', **v} for k, v in specs.items()],
                'source_issues': [
                    {'id': 'application', 'source_id': 'synthetic',
                     'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                     'missing': ['loaded-driver', 'waveform', 'board', 'loss']},
                    {'id': 'container', 'source_id': 'synthetic',
                     'issue_status': 'SOURCE_PROCESSING_LIMITATION',
                     'description': 'Synthetic source required parser recovery; full validity unknown.'}]}
        path.write_text(json.dumps(data), encoding='utf-8')
        self.original_bytes = path.read_bytes()
        self.path = path
        cases = [{'id': k, 'command': 'search', 'query': '',
                  'filters': {'source_id': 'synthetic', 'parameter': k},
                  'expected': [relative + '#' + k]} for k in specs]
        cases.append({'id': 'warnings', 'command': 'issues', 'query': '',
                      'filters': {'source_id': 'synthetic'},
                      'expected': [relative + '#' + k for k in ('application', 'container')]})
        self.manifest = {'format': evaluation.FORMAT,
                         'files': {relative: hashlib.sha256(path.read_bytes()).hexdigest()},
                         'cases': cases}
        self.baselines = {c['id']: json.dumps(evaluation.run_cli(self.root, c), sort_keys=True)
                          for c in cases}

    def test_complete_payload_preserves_noncanonical_unknown_and_conditions(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for encoded in self.baselines.values():
            for item in json.loads(encoded):
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_equal_identity_cannot_promote_low_drive_or_drop_conditions(self):
        changes = [
            ('identity', ['fact', 'value', 'orderable'], 'SYNTH-FET'),
            ('identity', ['fact', 'value', 'view'], 'bottom'),
            ('identity', ['fact', 'value', 'pins', 'A'], 'S'),
            ('identity', ['fact', 'value', 'complete_cad_footprint'], {}),
            ('stress', ['fact', 'kind'], 'recommended_operating'),
            ('stress', ['fact', 'value', 'VDS_max_V'], 90),
            ('stress', ['fact', 'conditions', 'safe_replacement'], True),
            ('threshold', ['fact', 'value', 'typ_V'], 0.6),
            ('threshold', ['fact', 'conditions', 'ID_uA'], 210000),
            ('threshold', ['fact', 'conditions', 'VDS_equals_VGS'], False),
            ('threshold', ['fact', 'conditions', 'useful_load_enhancement'], True),
            ('resistance', ['fact', 'value', 'max_ohm'], 0.029),
            ('resistance', ['fact', 'value', 'VGS_V'], 1.2),
            ('resistance', ['fact', 'value', 'ID_A'], None),
            ('resistance', ['fact', 'value', 'hot_max_ohm'], 0.041),
            ('resistance', ['fact', 'conditions', 'TJ_C'], None),
            ('resistance', ['fact', 'conditions', 'pulse_max_us'], None),
            ('resistance', ['fact', 'conditions', 'duty_max_percent'], None),
            ('resistance', ['fact', 'conditions', 'test_current_is_board_rating'], True),
            ('thermal', ['fact', 'value', 'steady_ambient_max_C_W'], 88),
            ('thermal', ['fact', 'value', 'short_ambient_max_C_W'], 61),
            ('thermal', ['fact', 'conditions', 'duration_max_s'], None),
            ('thermal', ['fact', 'conditions', 'foot_reference'], 'ambient'),
            ('thermal', ['fact', 'conditions', 'board_inch'], None),
            ('thermal', ['fact', 'conditions', 'board_material'], None),
            ('thermal', ['fact', 'conditions', 'qualified_continuous_current_A'], 2.7),
            ('charge', ['fact', 'value', 'max_nC'], 4.7),
            ('charge', ['fact', 'value', 'charge_at_other_gate_nC'], 4.7),
            ('charge', ['fact', 'value', 'qualified_pwm_Hz'], 20000),
            ('charge', ['fact', 'conditions', 'VGS_V'], 1.6),
            ('charge', ['fact', 'conditions', 'VDS_V'], None),
            ('charge', ['fact', 'conditions', 'ID_A'], None),
            ('charge', ['fact', 'conditions', 'TJ_C'], None),
            ('charge', ['fact', 'conditions', 'production_tested'], True),
            ('charge', ['source_issues'], []),
            ('charge', ['canonical'], True),
            ('charge', ['evidence_verification'], 'VERIFIED'),
            ('warnings', ['source_issue', 'issue_status'], 'RESOLVED'),
            ('warnings', ['source_issue', 'missing'], []),
        ]
        self.assertEqual(len(changes), 39)
        for target, keys, value in changes:
            with self.subTest(target=target, keys=keys):
                def runner(root, case):
                    items = json.loads(self.baselines[case['id']])
                    if case['id'] == target:
                        node = items[0]
                        for key in keys[:-1]:
                            node = node[key]
                        node[keys[-1]] = value
                    return items
                result = evaluation.evaluate(self.root, self.manifest, runner=runner)
                self.assertEqual(result['status'], 'FAIL')
                failed = next(c for c in result['cases'] if c['id'] == target)
                self.assertFalse(failed['passed'])
                self.assertEqual(failed['actual'], next(c['expected'] for c in self.manifest['cases']
                                                       if c['id'] == target))
                pristine = evaluation.evaluate(self.root, self.manifest,
                    runner=lambda root, case: json.loads(self.baselines[case['id']]))
                self.assertEqual(pristine['status'], 'PASS')
                self.assertEqual(self.path.read_bytes(), self.original_bytes)


class LowVoltageMosfetSuccessorTests(unittest.TestCase):
    def test_exact_reviewed_pair_and_historical_cases_are_preserved(self):
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-inductor.json').read_bytes())
        new = json.loads((root / 'evals/intake-retrieval-low-voltage-mosfet.json').read_bytes())
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: new['files'][p] for p in old['files']}, old['files'])
        path = 'knowledge/intake/si2342ds-low-voltage-drive-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {path})
        for suffix, digest in {
            '.json': '7dee5cb9349c408a9dc01b39edd6b65bfe6f93f5429b17f13146dd0ae3b1664a',
            '-review.md': 'fa098769edd9833674a2cb8f4b76fc2c3c2331c2638079726c7cc10a8a1dbc60',
        }.items():
            p = root / ('knowledge/intake/si2342ds-low-voltage-drive-constraints' + suffix)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)
        data = json.loads((root / path).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (6, 3))
        self.assertEqual(data['sources'][0]['pdf_sha256'],
                         'eba3913f3b9856077dd8ba9b1e81d691fbe958c759075b89ff7fcb605f0e0a03')
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 26)
        selected = {ref for case in additions for ref in case['expected']}
        self.assertEqual(selected, {path + '#' + rec['id']
                                    for rec in data['facts'] + data['source_issues']})
        for fact in data['facts']:
            self.assertTrue(any(case['command'] == 'search' and case['query'] == ''
                and case['filters'] == {'source_id': fact['source_id'], 'parameter': fact['parameter']}
                and case['expected'] == [path + '#' + fact['id']] for case in additions))
        self.assertEqual(sum(not case['expected'] for case in additions), 16)
