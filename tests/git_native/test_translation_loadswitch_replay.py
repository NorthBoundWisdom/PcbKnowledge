"""Synthetic supply-domain, switch and resistor qualification preservation."""
from __future__ import annotations
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace

class SyntheticDomainSwitchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-domain-switch.json'
        path = self.root / relative
        path.parent.mkdir(parents=True)
        # Invented devices, values and conditions; not real source specifications.
        specs = {
            'translation': {'kind': 'electrical_characteristic',
                'value': {'ioff': 5, 'automatic_direction': False, 'glitch_free': None},
                'conditions': {'rail_state': 'grounded', 'control_domain': 'rail-A',
                    'direction': 'A-to-B', 'rail_pair': [2, 4], 'load_pf': 13,
                    'timing_status': 'typical', 'stress_is_operating': False}},
            'switch': {'kind': 'application_guidance',
                'value': {'rise_us': 17, 'reverse_blocking': None, 'current_limit': None,
                    'qod_is_isolation': False},
                'conditions': {'ct_pf': 11, 'load_uf': 3, 'vin_v': 4,
                    'on_state': 'low', 'total_current_includes_load': True,
                    'rise_is_guaranteed': False}},
            'resistor': {'kind': 'rating',
                'value': {'standard_w': 0.07, 'extended_w': 0.09, 'footprint': None},
                'conditions': {'temperature_c': 61, 'drift_standard_pct': 1,
                    'drift_extended_pct': 2, 'voltage_is_thermal_permission': False}}}
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
                'acceptance_status': 'DRAFT',
                'sources': [{'id': 'synthetic', 'device': 'SYNTH', 'manufacturer': 'Synthetic',
                             'package': 'SYNTH-PKG', 'status': 'DRAFT'}],
                'facts': [{'id': k, 'source_id': 'synthetic', 'parameter': k, 'status': 'DRAFT', **v}
                          for k, v in specs.items()],
                'source_issues': [{'id': 'unknown', 'source_id': 'synthetic',
                                  'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                                  'answer': 'UNKNOWN', 'missing': ['board', 'fault', 'mating-part']}]}
        path.write_text(json.dumps(data), encoding='utf-8')
        cases = [{'id': k, 'command': 'search', 'query': '',
                  'filters': {'source_id': 'synthetic', 'parameter': k},
                  'expected': [relative + '#' + k]} for k in specs]
        cases.append({'id': 'unknown', 'command': 'issues', 'query': '',
                      'filters': {'source_id': 'synthetic'}, 'expected': [relative + '#unknown']})
        self.manifest = {'format': evaluation.FORMAT,
                         'files': {relative: hashlib.sha256(path.read_bytes()).hexdigest()}, 'cases': cases}
        self.outputs = {c['id']: evaluation.run_cli(self.root, c) for c in cases}

    def test_complete_payload_keeps_unknown_and_nonverification(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for items in self.outputs.values():
            for item in items:
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')

    def test_equal_identity_cannot_promote_domain_switch_rating_or_unknowns(self):
        changes = [
            ('translation', ['fact', 'value', 'automatic_direction'], True),
            ('translation', ['fact', 'value', 'glitch_free'], True),
            ('translation', ['fact', 'conditions', 'rail_state'], 'floating'),
            ('translation', ['fact', 'conditions', 'control_domain'], 'rail-B'),
            ('translation', ['fact', 'conditions', 'direction'], 'B-to-A'),
            ('translation', ['fact', 'conditions', 'rail_pair'], [4, 2]),
            ('translation', ['fact', 'conditions', 'load_pf'], None),
            ('translation', ['fact', 'conditions', 'timing_status'], 'guaranteed'),
            ('translation', ['fact', 'conditions', 'stress_is_operating'], True),
            ('switch', ['fact', 'value', 'reverse_blocking'], True),
            ('switch', ['fact', 'value', 'current_limit'], 2),
            ('switch', ['fact', 'value', 'qod_is_isolation'], True),
            ('switch', ['fact', 'conditions', 'ct_pf'], None),
            ('switch', ['fact', 'conditions', 'load_uf'], None),
            ('switch', ['fact', 'conditions', 'vin_v'], None),
            ('switch', ['fact', 'conditions', 'on_state'], 'high'),
            ('switch', ['fact', 'conditions', 'total_current_includes_load'], False),
            ('switch', ['fact', 'conditions', 'rise_is_guaranteed'], True),
            ('resistor', ['fact', 'value', 'standard_w'], 0.09),
            ('resistor', ['fact', 'value', 'footprint'], 'certified'),
            ('resistor', ['fact', 'conditions', 'temperature_c'], None),
            ('resistor', ['fact', 'conditions', 'drift_extended_pct'], 1),
            ('resistor', ['fact', 'conditions', 'voltage_is_thermal_permission'], True),
            ('unknown', ['source_issue', 'answer'], 'SAFE'),
            ('unknown', ['source_issue', 'missing'], []),
            ('translation', ['source_issues'], []),
        ]
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
                self.assertEqual(failed['actual'], next(c['expected'] for c in self.manifest['cases'] if c['id'] == target))

class SuccessorManifestTests(unittest.TestCase):
    def test_historical_cases_and_exact_resistor_pair_preserved(self):
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-tvs-connector.json').read_bytes())
        new = json.loads((root / 'evals/intake-retrieval-translation-loadswitch.json').read_bytes())
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: new['files'][p] for p in old['files']}, old['files'])
        expected_paths = {'knowledge/intake/' + stem + '.json' for stem in (
            'sn74lvc1t45-level-translation-constraints', 'tps22918-load-switch-constraints',
            'vishay-crcw060310k0fkea-rating-constraints')}
        self.assertEqual(set(new['files']) - set(old['files']), expected_paths)
        for suffix, digest in {
            '.json': 'a8bb3d06470509605dee99d5b52f9854eac29a3c406781a7171a005505acb438',
            '-review.md': '9530f7f14ffe1cdae687b7d03926c6c9e9b83e56e1122a59be318574f717035a',
        }.items():
            path = root / ('knowledge/intake/vishay-crcw060310k0fkea-rating-constraints' + suffix)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        selected = {ref for case in new['cases'][len(old['cases']):] for ref in case['expected']}
        for path in expected_paths:
            data = json.loads((root / path).read_bytes())
            self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
            self.assertFalse(data['canonical'])
            self.assertFalse(data['human_reviewed'])
            for record in data['facts'] + data['source_issues']:
                self.assertIn(path + '#' + record['id'], selected)
