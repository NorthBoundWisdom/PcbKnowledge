"""Invented NTC metadata preserve conditions, not temperature-system qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticThermistorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = 'knowledge/intake/synthetic-thermistor.json'
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        # All identity, numeric values and test conditions are invented.
        specs = {
            'identity': {'kind': 'identity', 'value': {
                'orderable': 'SYNTH-NTC-7300-J', 'lead_pitch_mm': 2.3,
                'complete_footprint': None, 'coating_insulation_specified': False,
                'potted_application_intended': False, 'preferred_new_design': False,
                'discontinued': None}},
            'resistance': {'kind': 'electrical_characteristic', 'value': {
                'nominal_ohm': 7300, 'initial_tolerance_percent': 7,
                'system_temperature_accuracy_C': None},
                'conditions': {'body_temperature_C': 23,
                    'zero_power': True, 'excitation_current_A': None, 'zero_power_fraction_max': 0.007}},
            'beta': {'kind': 'electrical_characteristic', 'value': {
                'nominal_K': 3701, 'tolerance_percent': 2.3,
                'global_conversion_accuracy_C': None},
                'conditions': {'temperature_pair_C': [23, 81],
                    'resistance_temperature_table_complete': False}},
            'dissipation': {'kind': 'typical_characteristic', 'value': {
                'dissipation_factor_mW_per_K': 6.3,
                'guaranteed_min_mW_per_K': None,
                'application_self_heating_K': None},
                'conditions': {'medium': 'synthetic still air',
                    'mounting': 'synthetic reference mounting',
                    'excitation_power_mW': None}},
            'response': {'kind': 'typical_characteristic', 'value': {
                'thermal_time_constant_s': 13,
                'guaranteed_max_response_s': None,
                'whole_system_settling_s': None},
                'conditions': {'medium': 'synthetic reference fluid',
                    'response_fraction': 0.63, 'flow_rate_known': False}},
            'power': {'kind': 'absolute_maximum', 'value': {
                'maximum_dissipation_mW': 370,
                'precision_measurement_power_mW': None},
                'conditions': {'ambient_C': 43,
                    'temperature_derating_required': True,
                    'board_thermal_path_known': False}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
            'acceptance_status': 'DRAFT',
            'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                'device': 'SYNTH-NTC-7300-J', 'package': 'SYNTH-LEADED-NTC',
                'revision': 'Synthetic R5', 'status': 'DRAFT'}],
            'facts': [{'id': key, 'source_id': 'synthetic', 'parameter': key,
                       'status': 'DRAFT', **spec} for key, spec in specs.items()],
            'source_issues': [
                {'id': 'thermal-warning', 'source_id': 'synthetic',
                    'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                    'missing': ['excitation power', 'medium', 'mounting', 'airflow']},
                {'id': 'accuracy-warning', 'source_id': 'synthetic',
                    'issue_status': 'SOURCE_SCOPE_LIMITATION',
                    'value': {'temperature_system_accuracy_C': None,
                              'sensor_interface_qualified': False}}]}

        self.path.write_text(json.dumps(data), encoding='utf-8')
        self.original_bytes = self.path.read_bytes()
        cases = [{'id': key, 'command': 'search', 'query': '',
            'filters': {'source_id': 'synthetic', 'parameter': key},
            'expected': [self.relative + '#' + key]} for key in specs]
        cases += [{'id': issue['id'], 'command': 'issues', 'query': issue['id'],
            'filters': {'source_id': 'synthetic'},
            'expected': [self.relative + '#' + issue['id']]} for issue in data['source_issues']]
        self.manifest = {'format': evaluation.FORMAT,
            'files': {self.relative: hashlib.sha256(self.original_bytes).hexdigest()},
            'cases': cases}
        # Genuine CLI responses stored immutably, then copied afresh per probe.
        self.baselines = {case['id']: json.dumps(evaluation.run_cli(self.root, case), sort_keys=True)
                          for case in cases}

    def test_full_payload_preserves_conditions_without_authority_upgrade(self):
        self.assertEqual(evaluation.evaluate(self.root, self.manifest)['status'], 'PASS')
        for encoded in self.baselines.values():
            for item in json.loads(encoded):
                self.assertFalse(item['canonical'])
                self.assertEqual(item['evidence_verification'], 'NOT_LOCALLY_VERIFIED')
        self.assertEqual(self.path.read_bytes(), self.original_bytes)

    def test_same_ids_cannot_promote_conditioned_values_or_resolve_unknowns(self):
        mutations = [
            ('identity', ['fact', 'value', 'orderable'], 'SYNTH-NTC-7300-K'),
            ('identity', ['fact', 'value', 'lead_pitch_mm'], 3.2),
            ('identity', ['fact', 'value', 'complete_footprint'], {}),
            ('identity', ['fact', 'value', 'coating_insulation_specified'], True),
            ('identity', ['fact', 'value', 'potted_application_intended'], True),
            ('identity', ['fact', 'value', 'preferred_new_design'], True),
            ('identity', ['fact', 'value', 'discontinued'], True),
            ('resistance', ['fact', 'value', 'nominal_ohm'], 10000),
            ('resistance', ['fact', 'value', 'initial_tolerance_percent'], 1),
            ('resistance', ['fact', 'value', 'system_temperature_accuracy_C'], 0.1),
            ('resistance', ['fact', 'conditions', 'body_temperature_C'], 25),
            ('resistance', ['fact', 'conditions', 'zero_power'], False),
            ('resistance', ['fact', 'conditions', 'excitation_current_A'], 0.001),
            ('resistance', ['fact', 'conditions', 'zero_power_fraction_max'], 1),
            ('beta', ['fact', 'value', 'nominal_K'], 3950),
            ('beta', ['fact', 'value', 'tolerance_percent'], 1),
            ('beta', ['fact', 'value', 'global_conversion_accuracy_C'], 0.1),
            ('beta', ['fact', 'conditions', 'temperature_pair_C'], [0, 100]),
            ('beta', ['fact', 'conditions', 'resistance_temperature_table_complete'], True),
            ('dissipation', ['fact', 'kind'], 'guaranteed_characteristic'),
            ('dissipation', ['fact', 'value', 'guaranteed_min_mW_per_K'], 6.3),
            ('dissipation', ['fact', 'value', 'application_self_heating_K'], 0),
            ('dissipation', ['fact', 'conditions', 'medium'], None),
            ('dissipation', ['fact', 'conditions', 'mounting'], None),
            ('dissipation', ['fact', 'conditions', 'excitation_power_mW'], 0),
            ('response', ['fact', 'kind'], 'guaranteed_maximum'),
            ('response', ['fact', 'value', 'thermal_time_constant_s'], 1),
            ('response', ['fact', 'value', 'guaranteed_max_response_s'], 13),
            ('response', ['fact', 'value', 'whole_system_settling_s'], 13),
            ('response', ['fact', 'conditions', 'medium'], None),
            ('response', ['fact', 'conditions', 'response_fraction'], 1),
            ('response', ['fact', 'conditions', 'flow_rate_known'], True),
            ('power', ['fact', 'kind'], 'recommended_operation'),
            ('power', ['fact', 'value', 'precision_measurement_power_mW'], 370),
            ('power', ['fact', 'conditions', 'ambient_C'], None),
            ('power', ['fact', 'conditions', 'temperature_derating_required'], False),
            ('power', ['fact', 'conditions', 'board_thermal_path_known'], True),
            ('resistance', ['source_issues'], []),
            ('resistance', ['canonical'], True),
            ('resistance', ['evidence_verification'], 'VERIFIED'),
            ('thermal-warning', ['source_issue', 'missing'], []),
            ('accuracy-warning', ['source_issue', 'value', 'temperature_system_accuracy_C'], 0.1),
            ('accuracy-warning', ['source_issue', 'value', 'sensor_interface_qualified'], True),
        ]
        self.assertEqual(len(mutations), 43)
        for target, keys, value in mutations:
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

    def test_wrong_identity_and_absent_guarantees_do_not_select_candidates(self):
        negatives = [
            ('search', {'device': 'SYNTH-NTC-7300-K'}),
            ('search', {'package': 'SYNTH-SMD'}),
            ('issues', {'device': 'SYNTH-NTC-7300-K'}),
            ('issues', {'package': 'SYNTH-SMD'}),
            ('search', {'parameter': 'guaranteed_temperature_accuracy'}),
            ('search', {'parameter': 'qualified_sensor_interface'}),
        ]
        for index, (command, filters) in enumerate(negatives):
            case = {'id': 'negative-' + str(index), 'command': command, 'query': '',
                'filters': {'source_id': 'synthetic', **filters}, 'expected': []}
            with self.subTest(command=command, filters=filters):
                self.assertEqual(evaluation.run_cli(self.root, case), [])
                report = evaluation.evaluate(self.root, {**self.manifest, 'cases': [case]})
                self.assertEqual(report['status'], 'PASS')
        # Missing temperature-system evidence does not become zero error.
        resistance = json.loads(self.baselines['resistance'])[0]['fact']['value']
        self.assertIsNone(resistance['system_temperature_accuracy_C'])
        beta = json.loads(self.baselines['beta'])[0]['fact']['value']
        self.assertIsNone(beta['global_conversion_accuracy_C'])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class ThermistorSuccessorTests(unittest.TestCase):
    def test_compact_successor_preserves_prior_cases_pins_and_full_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / 'evals/intake-retrieval-electrolytic.json'
        old = evaluation.load_manifest(base_path)
        manifest_path = root / 'evals/intake-retrieval-thermistor.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base']['path'], base_path.name)
        self.assertEqual(delta['base']['sha256'],
            '5680163544c970dbc3f1f0db4656a7dd44e7b0645dbc8f86da7c04293b93f021')
        self.assertEqual(len(delta['cases']), 30)
        self.assertEqual(len(delta['files']), 1)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({path: new['files'][path] for path in old['files']}, old['files'])
        relative = 'knowledge/intake/ntcle100-thermistor-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {relative})
        for suffix, digest in {
            '.json': '085793b239cb1a67f455f327c7214fa87b5ffbb3df0161eaee72e34d8d514a5a',
            '-review.md': '2b0b76714d623824e7bea18675475192f6c173790aa7331fe24e646fd6412599',
        }.items():
            pair_path = root / ('knowledge/intake/ntcle100-thermistor-constraints' + suffix)
            self.assertEqual(hashlib.sha256(pair_path.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (7, 3))
        self.assertEqual(new['files'][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 30)
        self.assertEqual(sum(not case['expected'] for case in additions), 20)
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
