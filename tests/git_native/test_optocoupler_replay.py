"""Invented optocoupler records exercise complete-condition preservation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticOptocouplerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-opto.json'
        self.path = self.root / relative
        self.path.parent.mkdir(parents=True)
        # Deliberately invented values, not manufacturer ratings or design advice.
        specs = {
            'identity': {'kind': 'pin', 'value': {'orderable': 'SYNTH-OPTO-B',
                'bin': 'B', 'pins': {'1': 'anode', '2': 'cathode',
                '3': 'emitter', '4': 'collector'}, 'complete_footprint': None}},
            'stress': {'kind': 'absolute_maximum', 'value': {'IF_max_mA': 47},
                'conditions': {'Tamb_C': 23, 'recommended_drive': False}},
            'led': {'kind': 'electrical_characteristic',
                'value': {'min_V': 1.1, 'typ_V': 1.4, 'max_V': 1.7,
                          'max_at_other_current_V': None},
                'conditions': {'IF_mA': 47, 'Tamb_C': 23}},
            'ctr': {'kind': 'electrical_characteristic',
                'value': {'min_percent': 90, 'max_percent': 170, 'typ_percent': None,
                          'guaranteed_saturated_percent': None},
                'conditions': {'bin': 'B', 'IF_mA': 4, 'VCE_V': 4.5, 'Tamb_C': 23,
                               'lifetime_minimum': None}},
            'saturation': {'kind': 'electrical_characteristic',
                'value': {'typ_V': 0.21, 'max_V': 0.36, 'max_at_other_load_V': None},
                'conditions': {'IF_mA': 4, 'IC_mA': 0.8, 'Tamb_C': 23}},
            'leakage': {'kind': 'electrical_characteristic',
                'value': {'typ_nA': 7, 'max_nA': 91, 'hot_max_nA': None},
                'conditions': {'bin': 'B', 'VCE_V': 9, 'Tamb_C': 23}},
            'switching': {'kind': 'electrical_characteristic',
                'value': {'typ_us': 2.8, 'max_us': None, 'qualified_bit_rate': None},
                'conditions': {'saturated': False, 'IF_mA': 4, 'VCC_V': 4.5,
                    'RL_ohm': 82, 'Tamb_C': 23, 'pulse_us': 43, 'duty_ratio': 0.02,
                    'generator_ohm': 48, 'scope_ohm': 900000, 'scope_pF': 17}},
            'conflict': {'kind': 'electrical_characteristic',
                'value': {'table_IF_mA': 4, 'figure_IF_mA': 9,
                          'resolved_IF_mA': None, 'qualified_delay_us': None},
                'conditions': {'figure_supply_V': 4.5, 'figure_load_ohm': 1200,
                               'manufacturer_correction': None}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
                'acceptance_status': 'DRAFT',
                'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                    'device': 'SYNTH-OPTO-B', 'package': 'SYNTH-DIP',
                    'revision': 'Synthetic R3', 'status': 'DRAFT'}],
                'facts': [{'id': k, 'source_id': 'synthetic', 'parameter': k,
                           'status': 'DRAFT', **v} for k, v in specs.items()],
                'source_issues': [
                    {'id': 'conflict-warning', 'source_id': 'synthetic',
                     'issue_status': 'UNRESOLVED_SOURCE_CONFLICT',
                     'description': 'Invented table and figure disagree; qualified delay unknown.'},
                    {'id': 'isolation-warning', 'source_id': 'synthetic',
                     'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                     'description': 'Exact option and insulation system not qualified.'},
                    {'id': 'logic-warning', 'source_id': 'synthetic',
                     'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                     'missing': ['driver', 'pull-up', 'receiver', 'temperature', 'aging']}]}
        self.path.write_text(json.dumps(data), encoding='utf-8')
        self.original_bytes = self.path.read_bytes()
        cases = [{'id': k, 'command': 'search', 'query': '',
                  'filters': {'source_id': 'synthetic', 'parameter': k},
                  'expected': [relative + '#' + k]} for k in specs]
        for issue in data['source_issues']:
            cases.append({'id': issue['id'], 'command': 'issues', 'query': issue['id'],
                          'filters': {'source_id': 'synthetic'},
                          'expected': [relative + '#' + issue['id']]})
        self.manifest = {'format': evaluation.FORMAT,
                         'files': {relative: hashlib.sha256(self.original_bytes).hexdigest()},
                         'cases': cases}
        self.baselines = {c['id']: json.dumps(evaluation.run_cli(self.root, c), sort_keys=True)
                          for c in cases}

    def test_complete_conditions_and_unknowns_replay_without_authority_upgrade(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for encoded in self.baselines.values():
            for item in json.loads(encoded):
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_same_ids_cannot_conflate_bins_conditions_or_resolve_conflicts(self):
        changes = [
            ('identity', ['fact', 'value', 'bin'], 'A'),
            ('identity', ['fact', 'value', 'orderable'], 'SYNTH-OPTO-B-SMD'),
            ('identity', ['fact', 'value', 'pins', '3'], 'collector'),
            ('identity', ['fact', 'value', 'complete_footprint'], {}),
            ('stress', ['fact', 'kind'], 'recommended_operating'),
            ('stress', ['fact', 'conditions', 'recommended_drive'], True),
            ('led', ['fact', 'value', 'max_V'], 1.4),
            ('led', ['fact', 'value', 'max_at_other_current_V'], 1.7),
            ('led', ['fact', 'conditions', 'IF_mA'], 4),
            ('led', ['fact', 'conditions', 'Tamb_C'], None),
            ('ctr', ['fact', 'value', 'typ_percent'], 130),
            ('ctr', ['fact', 'value', 'guaranteed_saturated_percent'], 90),
            ('ctr', ['fact', 'conditions', 'bin'], 'A'),
            ('ctr', ['fact', 'conditions', 'IF_mA'], None),
            ('ctr', ['fact', 'conditions', 'VCE_V'], 0.36),
            ('ctr', ['fact', 'conditions', 'Tamb_C'], None),
            ('ctr', ['fact', 'conditions', 'lifetime_minimum'], 90),
            ('saturation', ['fact', 'value', 'max_V'], 0.21),
            ('saturation', ['fact', 'value', 'max_at_other_load_V'], 0.36),
            ('saturation', ['fact', 'conditions', 'IF_mA'], None),
            ('saturation', ['fact', 'conditions', 'IC_mA'], 4),
            ('saturation', ['fact', 'conditions', 'Tamb_C'], None),
            ('leakage', ['fact', 'value', 'max_nA'], 7),
            ('leakage', ['fact', 'value', 'hot_max_nA'], 91),
            ('leakage', ['fact', 'conditions', 'bin'], 'A'),
            ('leakage', ['fact', 'conditions', 'VCE_V'], None),
            ('leakage', ['fact', 'conditions', 'Tamb_C'], None),
            ('switching', ['fact', 'value', 'max_us'], 2.8),
            ('switching', ['fact', 'value', 'qualified_bit_rate'], 100000),
            ('switching', ['fact', 'conditions', 'saturated'], True),
            ('switching', ['fact', 'conditions', 'IF_mA'], 9),
            ('switching', ['fact', 'conditions', 'VCC_V'], None),
            ('switching', ['fact', 'conditions', 'RL_ohm'], 900000),
            ('switching', ['fact', 'conditions', 'Tamb_C'], None),
            ('switching', ['fact', 'conditions', 'pulse_us'], None),
            ('switching', ['fact', 'conditions', 'duty_ratio'], None),
            ('switching', ['fact', 'conditions', 'generator_ohm'], None),
            ('switching', ['fact', 'conditions', 'scope_ohm'], 82),
            ('switching', ['fact', 'conditions', 'scope_pF'], None),
            ('conflict', ['fact', 'value', 'table_IF_mA'], 9),
            ('conflict', ['fact', 'value', 'figure_IF_mA'], 4),
            ('conflict', ['fact', 'value', 'resolved_IF_mA'], 4),
            ('conflict', ['fact', 'value', 'resolved_IF_mA'], 9),
            ('conflict', ['fact', 'value', 'qualified_delay_us'], 2.8),
            ('conflict', ['fact', 'conditions', 'figure_supply_V'], None),
            ('conflict', ['fact', 'conditions', 'figure_load_ohm'], None),
            ('conflict', ['fact', 'conditions', 'manufacturer_correction'], 'table wins'),
            ('conflict', ['source_issues'], []),
            ('conflict', ['canonical'], True),
            ('conflict', ['evidence_verification'], 'VERIFIED'),
            ('conflict-warning', ['source_issue', 'issue_status'], 'RESOLVED'),
            ('isolation-warning', ['source_issue', 'description'], 'Safety qualified.'),
            ('logic-warning', ['source_issue', 'missing'], []),
        ]
        self.assertEqual(len(changes), 53)
        for target, keys, value in changes:
            with self.subTest(target=target, keys=keys, value=value):
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
        self.assertEqual(evaluation.evaluate(self.root, self.manifest,
            runner=lambda root, case: json.loads(self.baselines[case['id']]))['status'], 'PASS')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class OptocouplerSuccessorTests(unittest.TestCase):
    def test_accepted_handoff_and_historical_recipes_are_exact(self):
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-low-voltage-mosfet.json').read_bytes())
        manifest_path = root / 'evals/intake-retrieval-optocoupler.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base'], {
            'path': 'intake-retrieval-low-voltage-mosfet.json',
            'sha256': '1417b54784e5aa739c71b9d5272d45b0ddebd48fbc36706f1b0b7696e57209f4'})
        self.assertEqual(len(delta['cases']), 30)
        self.assertEqual(len(delta['files']), 1)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: new['files'][p] for p in old['files']}, old['files'])
        path = 'knowledge/intake/vo617a-3-optocoupler-logic-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {path})
        for suffix, digest in {
            '.json': 'adc2ce86339add3ad91ee96225abdc2bc4343dd6e994afc0e4e50f35ae60e64c',
            '-review.md': '60d562758d2dea912416a199fe6fe9fe4b37fb5d36c4fc5452b502d26fd72da3',
        }.items():
            p = root / ('knowledge/intake/vo617a-3-optocoupler-logic-constraints' + suffix)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)
        data = json.loads((root / path).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (8, 3))
        self.assertEqual(data['sources'][0]['pdf_sha256'],
                         '145893b5422f68cc3f2016e2dddfc33f6ee26f0d2444fe8889d0dc0388f805a1')
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 30)
        selected = {ref for case in additions for ref in case['expected']}
        self.assertEqual(selected, {path + '#' + rec['id']
                                    for rec in data['facts'] + data['source_issues']})
        for fact in data['facts']:
            self.assertTrue(any(case['command'] == 'search' and case['query'] == ''
                and case['filters'] == {'source_id': fact['source_id'], 'parameter': fact['parameter']}
                and case['expected'] == [path + '#' + fact['id']] for case in additions))
        self.assertEqual(sum(not case['expected'] for case in additions), 18)
