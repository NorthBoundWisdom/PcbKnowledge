"""Invented shunt data exercise complete conditions, never circuit qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticCurrentSenseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-current-sense.json'
        self.path = self.root / relative
        self.path.parent.mkdir(parents=True)
        # Deliberately invented values and identity; not manufacturer specifications.
        specs = {
            'identity': {'kind': 'electrical_characteristic',
                'value': {'orderable': 'SYNTH-SHUNT-015-B', 'nominal_ohm': 0.015,
                    'initial_tolerance_percent': 1.3, 'total_operating_error_percent': None},
                'conditions': {'package': 'SYNTH-2PAD', 'special_suffix': None}},
            'power': {'kind': 'electrical_characteristic',
                'value': {'reference_power_W': 2.4, 'qualified_board_power_W': None,
                    'continuous_current_A': None},
                'conditions': {'reference_ambient_C': 63, 'zero_power_ambient_C': 162,
                    'rating_test_pcb': None, 'terminal_temperature_is_ambient': False}},
            'tcr': {'kind': 'electrical_characteristic',
                'value': {'component_max_abs_ppm_per_C': 81,
                    'element_less_than_ppm_per_C': 17, 'component_includes_terminals': True,
                    'system_accuracy_percent': None},
                'conditions': {'measurement_range_C': [-43, 143],
                    'resistance_row_ohm': [0.008, 0.42]}},
            'voltage': {'kind': 'electrical_characteristic',
                'value': {'source_relation': 'sqrt(P * R)', 'fixed_voltage_limit_V': None,
                    'qualified_pulse_current_A': None},
                'conditions': {'power_basis': 'actual allowable power and energy required'}},
            'geometry': {'kind': 'mechanical',
                'value': {'terminal_T_mm': 0.83, 'terminal_tolerance_mm': 0.21,
                    'pad_mm': {'a': 1.71, 'b': 3.92, 'l': 4.31},
                    'four_terminal_part': False, 'complete_footprint': None,
                    'guaranteed_trace_error_ohm': None},
                'conditions': {'resistance_row_ohm': [0.008, 0.015],
                    'sensing_sketch': 'typical only'}},
            'life': {'kind': 'qualification_test',
                'value': {'duration_h': 850, 'change_limit': {'percent': 1.4,
                    'additive_ohm': 0.0007, 'combination': 'plus/minus sum'},
                    'total_service_accuracy_percent': None},
                'conditions': {'ambient_C': 63, 'on_h': 1.3, 'off_h': 0.7,
                    'test_power_W': None, 'typical_drift': False}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
            'acceptance_status': 'DRAFT',
            'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                'device': 'SYNTH-SHUNT-015-B', 'package': 'SYNTH-2PAD',
                'revision': 'Synthetic R9', 'status': 'DRAFT'}],
            'facts': [{'id': key, 'source_id': 'synthetic', 'parameter': key,
                       'status': 'DRAFT', **spec} for key, spec in specs.items()],
            'source_issues': [
                {'id': 'thermal-warning', 'source_id': 'synthetic',
                    'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                    'missing': ['copper', 'stackup', 'airflow', 'actual current']},
                {'id': 'accuracy-warning', 'source_id': 'synthetic',
                    'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                    'missing': ['takeoff', 'contacts', 'amplifier', 'error budget']},
                {'id': 'pulse-warning', 'source_id': 'synthetic',
                    'issue_status': 'SOURCE_SCOPE_LIMITATION',
                    'value': {'graphic': 'illustrative only', 'pulse_envelope': None,
                              'linked_calculator_evaluated': False}}]}
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
        # Genuine CLI once per case; immutable bytes and fresh objects per mutation.
        self.baselines = {case['id']: json.dumps(evaluation.run_cli(self.root, case), sort_keys=True)
                          for case in cases}

    def test_complete_conditions_remain_noncanonical_and_unverified(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for encoded in self.baselines.values():
            for item in json.loads(encoded):
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_same_id_mutations_cannot_upgrade_conditioned_ratings(self):
        changes = [
            ('identity', ['fact', 'value', 'orderable'], 'SYNTH-SHUNT-015-A'),
            ('identity', ['fact', 'value', 'nominal_ohm'], 15),
            ('identity', ['fact', 'value', 'total_operating_error_percent'], 1.3),
            ('identity', ['fact', 'conditions', 'package'], 'SYNTH-4PAD'),
            ('identity', ['fact', 'conditions', 'special_suffix'], 'P'),
            ('power', ['fact', 'kind'], 'absolute_maximum'),
            ('power', ['fact', 'value', 'qualified_board_power_W'], 2.4),
            ('power', ['fact', 'value', 'continuous_current_A'], 12),
            ('power', ['fact', 'conditions', 'reference_ambient_C'], None),
            ('power', ['fact', 'conditions', 'zero_power_ambient_C'], 200),
            ('power', ['fact', 'conditions', 'rating_test_pcb'], 'any PCB'),
            ('power', ['fact', 'conditions', 'terminal_temperature_is_ambient'], True),
            ('tcr', ['fact', 'value', 'component_max_abs_ppm_per_C'], 17),
            ('tcr', ['fact', 'value', 'component_includes_terminals'], False),
            ('tcr', ['fact', 'value', 'element_less_than_ppm_per_C'], 81),
            ('tcr', ['fact', 'value', 'system_accuracy_percent'], 1.3),
            ('tcr', ['fact', 'conditions', 'measurement_range_C'], None),
            ('tcr', ['fact', 'conditions', 'resistance_row_ohm'], [0, 1]),
            ('voltage', ['fact', 'value', 'source_relation'], 'P * R'),
            ('voltage', ['fact', 'value', 'fixed_voltage_limit_V'], 0.2),
            ('voltage', ['fact', 'value', 'qualified_pulse_current_A'], 12),
            ('voltage', ['fact', 'conditions', 'power_basis'], 'nominal rating always'),
            ('geometry', ['fact', 'value', 'terminal_T_mm'], 1.5),
            ('geometry', ['fact', 'value', 'terminal_tolerance_mm'], 0),
            ('geometry', ['fact', 'value', 'pad_mm', 'a'], 4.31),
            ('geometry', ['fact', 'value', 'four_terminal_part'], True),
            ('geometry', ['fact', 'value', 'complete_footprint'], {}),
            ('geometry', ['fact', 'value', 'guaranteed_trace_error_ohm'], 0),
            ('geometry', ['fact', 'conditions', 'resistance_row_ohm'], [0, 0.008]),
            ('geometry', ['fact', 'conditions', 'sensing_sketch'], 'qualified layout'),
            ('life', ['fact', 'kind'], 'electrical_characteristic'),
            ('life', ['fact', 'value', 'duration_h'], None),
            ('life', ['fact', 'value', 'change_limit', 'additive_ohm'], 0),
            ('life', ['fact', 'value', 'change_limit', 'percent'], 0.0007),
            ('life', ['fact', 'value', 'change_limit', 'combination'], 'percent only'),
            ('life', ['fact', 'value', 'total_service_accuracy_percent'], 1.4),
            ('life', ['fact', 'conditions', 'ambient_C'], None),
            ('life', ['fact', 'conditions', 'on_h'], None),
            ('life', ['fact', 'conditions', 'off_h'], None),
            ('life', ['fact', 'conditions', 'test_power_W'], 2.4),
            ('life', ['fact', 'conditions', 'typical_drift'], True),
            ('power', ['source_issues'], []),
            ('power', ['canonical'], True),
            ('power', ['evidence_verification'], 'VERIFIED'),
            ('thermal-warning', ['source_issue', 'missing'], []),
            ('accuracy-warning', ['source_issue', 'issue_status'], 'RESOLVED'),
            ('pulse-warning', ['source_issue', 'value', 'graphic'], 'guaranteed curve'),
            ('pulse-warning', ['source_issue', 'value', 'pulse_envelope'], {'A': 12}),
            ('pulse-warning', ['source_issue', 'value', 'linked_calculator_evaluated'], True),
        ]
        self.assertEqual(len(changes), 49)
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
                failed = next(case for case in result['cases'] if case['id'] == target)
                self.assertFalse(failed['passed'])
                self.assertEqual(failed['actual'], next(case['expected']
                    for case in self.manifest['cases'] if case['id'] == target))
                self.assertEqual(self.path.read_bytes(), self.original_bytes)
        self.assertEqual(evaluation.evaluate(self.root, self.manifest,
            runner=lambda root, case: json.loads(self.baselines[case['id']]))['status'], 'PASS')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class CurrentSenseSuccessorTests(unittest.TestCase):
    def test_compact_successor_preserves_every_prior_recipe_and_pin(self):
        root = evaluation.REPO_ROOT
        base_path = root / 'evals/intake-retrieval-optocoupler.json'
        old = evaluation.load_manifest(base_path)
        manifest_path = root / 'evals/intake-retrieval-current-sense.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base'], {
            'path': base_path.name,
            'sha256': 'a6191cadb9eb2ce6ba4704e3aaa8e013e9ad5a39dce67bf79b582ccb61ecf2c3'})
        self.assertEqual(len(delta['files']), 1)
        self.assertEqual(len(delta['cases']), 29)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({path: new['files'][path] for path in old['files']}, old['files'])
        relative = 'knowledge/intake/wslp2512-current-sense-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {relative})
        for suffix, digest in {
            '.json': '91abaf2e01f2cbd092e2e4e33f194a59bacf1eebcb33aeb07ff28b1ef775414b',
            '-review.md': 'b634a27fc8cf901ac3c55ecb9d125bc28171d902189f0c8856aec44bc1eaa262',
        }.items():
            pair_path = root / ('knowledge/intake/wslp2512-current-sense-constraints' + suffix)
            self.assertEqual(hashlib.sha256(pair_path.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (6, 3))
        self.assertEqual(data['sources'][0]['pdf_sha256'],
            'd3dd7b4f590e713c84303e32530e8c8c6fd025617896e11d25599521771e4c13')
        self.assertEqual(new['files'][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 29)
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
