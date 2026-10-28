"""Synthetic current-criterion and unresolved-condition payload protection."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticInductorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-inductor.json'
        path = self.root / relative
        path.parent.mkdir(parents=True)
        # Invented fixture values and identities, not copied manufacturer data.
        specs = {
            'inductance': {'kind': 'electrical_characteristic',
                'value': {'nominal_uh': 8.2, 'effective_uh': None},
                'conditions': {'frequency_khz': 73, 'ac_v': 0.6,
                               'table_temperature_c': 23}},
            'saturation': {'kind': 'electrical_characteristic',
                'value': {'isat_a': 4.1, 'inductance_drop_percent': 17},
                'conditions': {'criterion': 'inductance drop',
                               'table_temperature_c': 23,
                               'universal_safe_current': False}},
            'thermal': {'kind': 'thermal_characteristic',
                'value': {'irms_a': 1.9, 'temperature_rise_c': 33,
                          'higher_graph_rating_a': None},
                'conditions': {'criterion': 'temperature rise',
                               'table_temperature_c': 23,
                               'plot_sample': None, 'plot_mounting': None,
                               'plot_test_setup': None,
                               'manufacturer_error_established': False}},
            'resistance': {'kind': 'electrical_characteristic',
                'value': {'dcr_max_mohm': 131, 'hot_dcr_max_mohm': None},
                'conditions': {'table_temperature_c': 23, 'unit': 'milliohm'}},
            'temperature': {'kind': 'operating_constraint',
                'value': {'maximum_c': 137, 'qualified_board_current_a': None},
                'conditions': {'includes_self_heating': True}},
            'geometry': {'kind': 'package_geometry',
                'value': {'land_span_mm': 6.1, 'complete_footprint': None},
                'conditions': {'span_is_pad_pitch': False}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1',
                'canonical': False, 'acceptance_status': 'DRAFT',
                'sources': [{'id': 'synthetic', 'device': 'SYNTH-IND',
                             'manufacturer': 'Synthetic', 'package': 'SYNTH-PKG',
                             'status': 'DRAFT'}],
                'facts': [{'id': k, 'source_id': 'synthetic', 'parameter': k,
                           'status': 'DRAFT', **v} for k, v in specs.items()],
                'source_issues': [{'id': 'unknown', 'source_id': 'synthetic',
                                  'issue_status': 'UNRESOLVED_SOURCE_CONDITIONS',
                                  'answer': 'UNKNOWN',
                                  'missing': ['sample', 'mounting', 'test-setup']}]}
        path.write_text(json.dumps(data), encoding='utf-8')
        cases = [{'id': k, 'command': 'search', 'query': '',
                  'filters': {'source_id': 'synthetic', 'parameter': k},
                  'expected': [relative + '#' + k]} for k in specs]
        cases.append({'id': 'unknown', 'command': 'issues', 'query': '',
                      'filters': {'source_id': 'synthetic'},
                      'expected': [relative + '#unknown']})
        self.manifest = {'format': evaluation.FORMAT,
                         'files': {relative: hashlib.sha256(path.read_bytes()).hexdigest()},
                         'cases': cases}
        self.outputs = {c['id']: evaluation.run_cli(self.root, c) for c in cases}

    def test_complete_payload_keeps_conditions_unknown_and_nonverification(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for items in self.outputs.values():
            for item in items:
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')

    def test_equal_identity_cannot_merge_current_criteria_or_erase_unknowns(self):
        changes = [
            ('inductance', ['fact', 'value', 'effective_uh'], 8.2),
            ('inductance', ['fact', 'conditions', 'frequency_khz'], None),
            ('inductance', ['fact', 'conditions', 'ac_v'], None),
            ('inductance', ['fact', 'conditions', 'table_temperature_c'], None),
            ('saturation', ['fact', 'value', 'isat_a'], 1.9),
            ('saturation', ['fact', 'value', 'inductance_drop_percent'], None),
            ('saturation', ['fact', 'conditions', 'criterion'], 'temperature rise'),
            ('saturation', ['fact', 'conditions', 'table_temperature_c'], None),
            ('saturation', ['fact', 'conditions', 'universal_safe_current'], True),
            ('thermal', ['fact', 'value', 'irms_a'], 4.1),
            ('thermal', ['fact', 'value', 'temperature_rise_c'], None),
            ('thermal', ['fact', 'value', 'higher_graph_rating_a'], 4.8),
            ('thermal', ['fact', 'conditions', 'criterion'], 'inductance drop'),
            ('thermal', ['fact', 'conditions', 'table_temperature_c'], None),
            ('thermal', ['fact', 'conditions', 'plot_sample'], 'matched'),
            ('thermal', ['fact', 'conditions', 'plot_mounting'], 'matched'),
            ('thermal', ['fact', 'conditions', 'plot_test_setup'], 'matched'),
            ('thermal', ['fact', 'conditions', 'manufacturer_error_established'], True),
            ('resistance', ['fact', 'value', 'hot_dcr_max_mohm'], 131),
            ('resistance', ['fact', 'conditions', 'unit'], 'ohm'),
            ('resistance', ['fact', 'conditions', 'table_temperature_c'], None),
            ('temperature', ['fact', 'value', 'qualified_board_current_a'], 1.9),
            ('temperature', ['fact', 'conditions', 'includes_self_heating'], False),
            ('geometry', ['fact', 'value', 'complete_footprint'], {'pad_mm': 6.1}),
            ('geometry', ['fact', 'conditions', 'span_is_pad_pitch'], True),
            ('unknown', ['source_issue', 'answer'], 'SAFE'),
            ('unknown', ['source_issue', 'missing'], []),
            ('unknown', ['source_issue', 'issue_status'], 'MANUFACTURER_ERROR'),
            ('thermal', ['source_issues'], []),
            ('thermal', ['canonical'], True),
            ('thermal', ['evidence_verification'], 'VERIFIED'),
        ]
        self.assertEqual(len(changes), 31)
        for target, keys, value in changes:
            with self.subTest(target=target, keys=keys):
                def runner(root, case):
                    items = copy.deepcopy(self.outputs[case['id']])
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
                self.assertEqual(failed['actual'], next(
                    c['expected'] for c in self.manifest['cases'] if c['id'] == target))


class InductorSuccessorTests(unittest.TestCase):
    def test_history_exact_handoff_and_complete_case_coverage(self):
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-mlcc.json').read_bytes())
        new = json.loads((root / 'evals/intake-retrieval-inductor.json').read_bytes())
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: new['files'][p] for p in old['files']}, old['files'])
        path = 'knowledge/intake/bourns-srp4020ta-4r7m-current-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {path})
        for suffix, digest in {
            '.json': 'e81420e76cbf4665ba891979d6c3e3b5c082970144225d3cae15473d2e368303',
            '-review.md': '7938e1d53a628e51263f45bd79a9bec023a5d98f9f3fc81d94025e9931e5f706',
        }.items():
            p = root / ('knowledge/intake/bourns-srp4020ta-4r7m-current-constraints' + suffix)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)
        data = json.loads((root / path).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (6, 3))
        self.assertEqual(data['sources'][0]['pdf_sha256'],
                         '601b2bd60f01531d3dd98df00eab15635fa971ebc03cf7ae4ccb5679faf03485')
        additions = new['cases'][len(old['cases']):]
        selected = {ref for case in additions for ref in case['expected']}
        self.assertEqual(selected, {path + '#' + rec['id']
                                    for rec in data['facts'] + data['source_issues']})
        for fact in data['facts']:
            self.assertTrue(any(case['command'] == 'search' and case['query'] == ''
                and case['filters'] == {'source_id': fact['source_id'], 'parameter': fact['parameter']}
                and case['expected'] == [path + '#' + fact['id']] for case in additions))
        self.assertGreaterEqual(sum(not case['expected'] for case in additions), 16)
