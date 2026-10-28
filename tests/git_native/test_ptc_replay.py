"""Synthetic PTC conditions are preserved without creating safety guarantees."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticPtcTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-ptc.json'
        self.path = self.root / relative
        self.path.parent.mkdir(parents=True)
        # Invented identity and numbers only, not manufacturer ratings.
        specs = {
            'identity': {'kind': 'identity', 'value': {
                'orderable': 'SYNTH-PTC-A-R', 'packaging': 'R',
                'new_design_warning': True, 'qualified_replacement': None}},
            'hold': {'kind': 'electrical_characteristic', 'value': {
                'hold_A': 0.43, 'trip_A': 0.91, 'trip_time_at_trip_A_s': None},
                'conditions': {'ambient_C': 21, 'hold_minutes': 27,
                    'medium': 'still air', 'hold_acceptance': 'no trip'}},
            'timing': {'kind': 'electrical_characteristic', 'value': {
                'max_time_s': 0.19, 'lower_overcurrent_time_s': None},
                'conditions': {'test_current_A': 7.3, 'test_voltage_V': 13,
                    'ambient_C': 21, 'medium': 'still air'}},
            'ratings': {'kind': 'electrical_characteristic', 'value': {
                'Vmax_V': 13, 'Imax_A': 93, 'AC_DC_designation': None,
                'continuous_load_A': None, 'open_circuit_isolation': None},
                'conditions': {'source_labels': ['Vmax', 'Imax']}},
            'derating': {'kind': 'electrical_characteristic', 'value': {
                'hold_at_21C_A': 0.43, 'hold_at_67C_A': 0.31,
                'hold_at_83C_A': 0.26, 'interpolated_hold_A': None},
                'conditions': {'model': 'SYNTH-PTC-A', 'board_hotspot_known': False}},
            'tripped': {'kind': 'electrical_characteristic', 'value': {
                'typical_power_W': 0.73, 'max_power_W': None,
                'residual_A': None, 'recovery_s': None, 'recovered_ohm': None},
                'conditions': {'ambient_C': 21}},
            'application': {'kind': 'application_constraint', 'value': {
                'temporary_fault_only': True, 'repeated_fault_qualified': False,
                'expansion_clearance_mm': None, 'potting_qualified': None}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
            'acceptance_status': 'DRAFT',
            'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                'device': 'SYNTH-PTC-A-R', 'package': 'SYNTH-SMD',
                'revision': 'Synthetic R4', 'status': 'DRAFT'}],
            'facts': [{'id': key, 'source_id': 'synthetic', 'parameter': key,
                       'status': 'DRAFT', **spec} for key, spec in specs.items()],
            'source_issues': [
                {'id': 'fault-warning', 'source_id': 'synthetic',
                    'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                    'missing': ['prospective fault', 'transients', 'inrush', 'temperature']},
                {'id': 'reset-warning', 'source_id': 'synthetic',
                    'issue_status': 'SOURCE_SCOPE_LIMITATION',
                    'value': {'residual_A': None, 'reset_s': None, 'isolation': None}},
                {'id': 'legacy-warning', 'source_id': 'synthetic',
                    'issue_status': 'SOURCE_SCOPE_LIMITATION',
                    'value': {'legacy_only': True, 'new_design_recommended': False}}]}
        self.path.write_text(json.dumps(data), encoding='utf-8')
        self.original_bytes = self.path.read_bytes()
        cases = [{'id': key, 'command': 'search', 'query': '',
            'filters': {'source_id': 'synthetic', 'parameter': key},
            'expected': [relative + '#' + key]} for key in specs]
        cases += [{'id': issue['id'], 'command': 'issues', 'query': issue['id'],
            'filters': {'source_id': 'synthetic'},
            'expected': [relative + '#' + issue['id']]} for issue in data['source_issues']]
        self.manifest = {'format': evaluation.FORMAT,
            'files': {relative: hashlib.sha256(self.original_bytes).hexdigest()}, 'cases': cases}
        self.baselines = {case['id']: json.dumps(evaluation.run_cli(self.root, case), sort_keys=True)
                          for case in cases}

    def test_full_conditions_replay_without_authority_upgrade(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for encoded in self.baselines.values():
            for item in json.loads(encoded):
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_same_ids_do_not_erase_conditions_or_invent_protection(self):
        changes = [
            ('identity', ['fact', 'value', 'orderable'], 'SYNTH-PTC-A/25X-R'),
            ('identity', ['fact', 'value', 'packaging'], 'bulk'),
            ('identity', ['fact', 'value', 'new_design_warning'], False),
            ('identity', ['fact', 'value', 'qualified_replacement'], 'SYNTH-PTC-B'),
            ('hold', ['fact', 'value', 'hold_A'], 0.91),
            ('hold', ['fact', 'value', 'trip_A'], 0.43),
            ('hold', ['fact', 'value', 'trip_time_at_trip_A_s'], 0.19),
            ('hold', ['fact', 'conditions', 'ambient_C'], None),
            ('hold', ['fact', 'conditions', 'hold_minutes'], None),
            ('hold', ['fact', 'conditions', 'medium'], 'any mounting'),
            ('hold', ['fact', 'conditions', 'hold_acceptance'], 'trip required'),
            ('timing', ['fact', 'value', 'max_time_s'], 0),
            ('timing', ['fact', 'value', 'lower_overcurrent_time_s'], 0.19),
            ('timing', ['fact', 'conditions', 'test_current_A'], 0.91),
            ('timing', ['fact', 'conditions', 'test_voltage_V'], None),
            ('timing', ['fact', 'conditions', 'ambient_C'], None),
            ('timing', ['fact', 'conditions', 'medium'], None),
            ('ratings', ['fact', 'value', 'Vmax_V'], 25),
            ('ratings', ['fact', 'value', 'Imax_A'], 0.43),
            ('ratings', ['fact', 'value', 'AC_DC_designation'], 'AC'),
            ('ratings', ['fact', 'value', 'AC_DC_designation'], 'DC'),
            ('ratings', ['fact', 'value', 'continuous_load_A'], 93),
            ('ratings', ['fact', 'value', 'open_circuit_isolation'], True),
            ('ratings', ['fact', 'conditions', 'source_labels'], ['recommended voltage', 'hold current']),
            ('derating', ['fact', 'value', 'hold_at_67C_A'], 0.43),
            ('derating', ['fact', 'value', 'hold_at_83C_A'], 0.43),
            ('derating', ['fact', 'value', 'interpolated_hold_A'], 0.35),
            ('derating', ['fact', 'conditions', 'model'], 'SYNTH-PTC-A/25X'),
            ('derating', ['fact', 'conditions', 'board_hotspot_known'], True),
            ('tripped', ['fact', 'kind'], 'absolute_maximum'),
            ('tripped', ['fact', 'value', 'typical_power_W'], 0),
            ('tripped', ['fact', 'value', 'max_power_W'], 0.73),
            ('tripped', ['fact', 'value', 'residual_A'], 0),
            ('tripped', ['fact', 'value', 'recovery_s'], 0.19),
            ('tripped', ['fact', 'value', 'recovered_ohm'], 0.1),
            ('tripped', ['fact', 'conditions', 'ambient_C'], None),
            ('application', ['fact', 'value', 'temporary_fault_only'], False),
            ('application', ['fact', 'value', 'repeated_fault_qualified'], True),
            ('application', ['fact', 'value', 'expansion_clearance_mm'], 0),
            ('application', ['fact', 'value', 'potting_qualified'], True),
            ('hold', ['source_issues'], []),
            ('hold', ['canonical'], True),
            ('hold', ['evidence_verification'], 'VERIFIED'),
            ('fault-warning', ['source_issue', 'missing'], []),
            ('reset-warning', ['source_issue', 'issue_status'], 'RESOLVED'),
            ('reset-warning', ['source_issue', 'value', 'residual_A'], 0),
            ('reset-warning', ['source_issue', 'value', 'reset_s'], 0.19),
            ('reset-warning', ['source_issue', 'value', 'isolation'], True),
            ('legacy-warning', ['source_issue', 'value', 'legacy_only'], False),
            ('legacy-warning', ['source_issue', 'value', 'new_design_recommended'], True),
        ]
        self.assertEqual(len(changes), 50)
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
                failed = next(case for case in result['cases'] if case['id'] == target)
                self.assertFalse(failed['passed'])
                self.assertEqual(failed['actual'], next(case['expected']
                    for case in self.manifest['cases'] if case['id'] == target))
                self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.assertEqual(evaluation.evaluate(self.root, self.manifest,
            runner=lambda root, case: json.loads(self.baselines[case['id']]))['status'], 'PASS')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class PtcSuccessorTests(unittest.TestCase):
    def test_compact_successor_preserves_prior_cases_pins_and_full_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / 'evals/intake-retrieval-current-sense.json'
        old = evaluation.load_manifest(base_path)
        manifest_path = root / 'evals/intake-retrieval-ptc.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base']['path'], base_path.name)
        self.assertEqual(delta['base']['sha256'],
            '711527ab4629d1523ce4d5fc1d6bcc105f210e3dae1d442dbc833094e074e49e')
        self.assertEqual(len(delta['cases']), 30)
        self.assertEqual(len(delta['files']), 1)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({path: new['files'][path] for path in old['files']}, old['files'])
        relative = 'knowledge/intake/bourns-mf-msmf050-ptc-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {relative})
        for suffix, digest in {
            '.json': 'e9f8629bc2504c1999be2512248a51ffabeeb37ec2c4d99b8ec62c405ce48835',
            '-review.md': '5dda5a7f2a4cf1c32b8553df32297780e14a7401bbd44a46e55a16097742c726',
        }.items():
            pair_path = root / ('knowledge/intake/bourns-mf-msmf050-ptc-constraints' + suffix)
            self.assertEqual(hashlib.sha256(pair_path.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (7, 3))
        self.assertEqual(new['files'][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 30)
        self.assertEqual(sum(not case['expected'] for case in additions), 18)
        selected = {ref for case in additions for ref in case['expected']}
        self.assertEqual(selected, {relative + '#' + rec['id']
            for rec in data['facts'] + data['source_issues']})
        for fact in data['facts']:
            self.assertTrue(any(case['command'] == 'search' and case['query'] == ''
                and case['filters'] == {'source_id': fact['source_id'], 'parameter': fact['parameter']}
                and case['expected'] == [relative + '#' + fact['id']] for case in additions))
        self.assertTrue(any(case['command'] == 'issues' and not case['expected']
                            for case in additions))
        self.assertTrue(any(case['command'] == 'search' and not case['expected']
                            for case in additions))
