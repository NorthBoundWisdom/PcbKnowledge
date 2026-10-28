"""Invented Zener metadata preserve test conditions, not circuit regulation guarantees."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticZenerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = 'knowledge/intake/synthetic-zener.json'
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        # All identity, numeric values and test conditions are invented.
        specs = {'identity': {'kind': 'identity',
                      'value': {'orderable': 'SYNTH-ZENER-6V2-C',
                                'package': 'SYNTH-SMALL-DIODE',
                                'automotive_qualified': False,
                                'complete_footprint': None}},
         'voltage': {'kind': 'electrical_characteristic',
                     'value': {'min_V': 5.9, 'max_V': 6.5, 'all_current_regulation_V': None},
                     'conditions': {'test_current_mA': 7,
                                    'ambient_C': 23,
                                    'pulse_duration_ms': None,
                                    'temperature_compensated': False}},
         'dynamic': {'kind': 'electrical_characteristic',
                     'value': {'upper_current_resistance_ohm': 47,
                               'knee_resistance_ohm': 731,
                               'static_DC_resistance_ohm': None},
                     'conditions': {'AC_test_frequency_Hz': 870,
                                    'upper_current_mA': 7,
                                    'knee_current_mA': 0.7,
                                    'arbitrary_frequency_guarantee': False}},
         'leakage': {'kind': 'tabulated_characteristic',
                     'value': {'tabulated_current_uA': 2.7,
                               'guaranteed_max_current_uA': None,
                               'limit_type_explicit': False},
                     'conditions': {'reverse_voltage_V': 3.1,
                                    'ambient_C': 23,
                                    'hot_leakage_uA': None}},
         'tempco': {'kind': 'electrical_characteristic',
                    'value': {'min_percent_per_K': -0.037,
                              'max_percent_per_K': 0.043,
                              'system_reference_accuracy_V': None},
                    'conditions': {'test_current_mA': 7,
                                   'temperature_range_C': None,
                                   'ambient_equals_junction': False}},
         'power': {'kind': 'absolute_maximum',
                   'value': {'power_mW': 317,
                             'junction_to_ambient_K_per_W': 417,
                             'board_continuous_power_mW': None},
                   'conditions': {'ambient_C': 23,
                                  'mounting': 'invented copper reference',
                                  'alternate_rating_same_condition': False,
                                  'voltage_is_continuous_board_guarantee': False}}}
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
            'acceptance_status': 'DRAFT',
            'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                'device': 'SYNTH-ZENER-6V2-C', 'package': 'SYNTH-SMALL-DIODE',
                'revision': 'Synthetic R5', 'status': 'DRAFT'}],
            'facts': [{'id': key, 'source_id': 'synthetic', 'parameter': key,
                       'status': 'DRAFT', **spec} for key, spec in specs.items()],
            'source_issues': [
                {'id': 'drive-warning', 'source_id': 'synthetic',
                 'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                 'missing': ['bias current', 'source impedance', 'load waveform', 'temperature']},
                {'id': 'qualification-warning', 'source_id': 'synthetic',
                 'issue_status': 'SOURCE_SCOPE_LIMITATION',
                 'value': {'precision_reference_accuracy_V': None,
                           'circuit_qualified': False}}]}


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
        mutations = [('identity', ['fact', 'value', 'orderable'], 'SYNTH-ZENER-6V2-B'),
         ('identity', ['fact', 'value', 'package'], 'SYNTH-OTHER'),
         ('identity', ['fact', 'value', 'automotive_qualified'], True),
         ('identity', ['fact', 'value', 'complete_footprint'], {}),
         ('voltage', ['fact', 'value', 'min_V'], 6.2),
         ('voltage', ['fact', 'value', 'max_V'], 6.2),
         ('voltage', ['fact', 'value', 'all_current_regulation_V'], 6.2),
         ('dynamic', ['fact', 'value', 'upper_current_resistance_ohm'], 731),
         ('dynamic', ['fact', 'value', 'knee_resistance_ohm'], 47),
         ('dynamic', ['fact', 'value', 'static_DC_resistance_ohm'], 47),
         ('leakage', ['fact', 'value', 'guaranteed_max_current_uA'], 2.7),
         ('leakage', ['fact', 'value', 'limit_type_explicit'], True),
         ('leakage', ['fact', 'value', 'tabulated_current_uA'], 0),
         ('tempco', ['fact', 'value', 'min_percent_per_K'], 0),
         ('tempco', ['fact', 'value', 'max_percent_per_K'], 0),
         ('tempco', ['fact', 'value', 'system_reference_accuracy_V'], 0.01),
         ('power', ['fact', 'value', 'board_continuous_power_mW'], 317),
         ('power', ['fact', 'value', 'junction_to_ambient_K_per_W'], 0),
         ('voltage', ['fact', 'conditions', 'test_current_mA'], 0.7),
         ('voltage', ['fact', 'conditions', 'ambient_C'], None),
         ('voltage', ['fact', 'conditions', 'pulse_duration_ms'], 3.7),
         ('voltage', ['fact', 'conditions', 'temperature_compensated'], True),
         ('dynamic', ['fact', 'conditions', 'AC_test_frequency_Hz'], None),
         ('dynamic', ['fact', 'conditions', 'upper_current_mA'], 0.7),
         ('dynamic', ['fact', 'conditions', 'knee_current_mA'], 7),
         ('dynamic', ['fact', 'conditions', 'arbitrary_frequency_guarantee'], True),
         ('leakage', ['fact', 'conditions', 'reverse_voltage_V'], 6.2),
         ('leakage', ['fact', 'conditions', 'ambient_C'], None),
         ('leakage', ['fact', 'conditions', 'hot_leakage_uA'], 2.7),
         ('tempco', ['fact', 'conditions', 'test_current_mA'], None),
         ('tempco', ['fact', 'conditions', 'temperature_range_C'], [23, 143]),
         ('tempco', ['fact', 'conditions', 'ambient_equals_junction'], True),
         ('power', ['fact', 'conditions', 'ambient_C'], None),
         ('power', ['fact', 'conditions', 'mounting'], None),
         ('power', ['fact', 'conditions', 'alternate_rating_same_condition'], True),
         ('power', ['fact', 'conditions', 'voltage_is_continuous_board_guarantee'], True),
         ('power', ['fact', 'kind'], 'recommended_operation'),
         ('voltage', ['source_issues'], []),
         ('voltage', ['canonical'], True),
         ('voltage', ['evidence_verification'], 'VERIFIED'),
         ('drive-warning', ['source_issue', 'missing'], []),
         ('qualification-warning', ['source_issue', 'value', 'precision_reference_accuracy_V'], 0.01),
         ('qualification-warning', ['source_issue', 'value', 'circuit_qualified'], True)]
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
            ('search', {'device': 'SYNTH-ZENER-6V2-B'}),
            ('search', {'package': 'SYNTH-OTHER'}),
            ('issues', {'device': 'SYNTH-ZENER-6V2-B'}),
            ('issues', {'package': 'SYNTH-OTHER'}),
            ('search', {'parameter': 'qualified_precision_reference'}),
            ('search', {'parameter': 'guaranteed_hot_leakage'}),
        ]
        for index, (command, filters) in enumerate(negatives):
            case = {'id': 'negative-' + str(index), 'command': command, 'query': '',
                'filters': {'source_id': 'synthetic', **filters}, 'expected': []}
            with self.subTest(command=command, filters=filters):
                self.assertEqual(evaluation.run_cli(self.root, case), [])
                report = evaluation.evaluate(self.root, {**self.manifest, 'cases': [case]})
                self.assertEqual(report['status'], 'PASS')
        voltage = json.loads(self.baselines['voltage'])[0]['fact']['value']
        self.assertIsNone(voltage['all_current_regulation_V'])
        leakage = json.loads(self.baselines['leakage'])[0]['fact']['value']
        self.assertIsNone(leakage['guaranteed_max_current_uA'])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class ZenerSuccessorTests(unittest.TestCase):
    def test_compact_successor_preserves_prior_cases_pins_and_full_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / 'evals/intake-retrieval-thermistor.json'
        old = evaluation.load_manifest(base_path)
        manifest_path = root / 'evals/intake-retrieval-zener.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base']['path'], base_path.name)
        self.assertEqual(delta['base']['sha256'],
            '1b58e5a4409a22d40c94d1baabe07203555f377098f9e24cc75b9c49873cc758')
        self.assertEqual(len(delta['cases']), 30)
        self.assertEqual(len(delta['files']), 1)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({path: new['files'][path] for path in old['files']}, old['files'])
        relative = 'knowledge/intake/bzx84c5v1-zener-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {relative})
        for suffix, digest in {
            '.json': '6cedd7a538975b627d609bdfd0fa1fdaeae3ecc9386250c84732e4a6b78352a1',
            '-review.md': '26ad207f16003b89ffd2f442d41502d6dd58667fd2e94ab619901f5e1e2474d1',
        }.items():
            pair_path = root / ('knowledge/intake/bzx84c5v1-zener-constraints' + suffix)
            self.assertEqual(hashlib.sha256(pair_path.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (6, 3))
        self.assertEqual(new['files'][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 30)
        self.assertEqual(sum(not case['expected'] for case in additions), 19)
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
