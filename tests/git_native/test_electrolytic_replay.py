"""Invented electrolytic metadata preserve conditions, not application approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticElectrolyticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = 'knowledge/intake/synthetic-electrolytic.json'
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        # All identity, numeric values and test conditions are invented.
        specs = {
            'identity': {'kind': 'identity', 'value': {
                'orderable': 'SYNTH-AL-150-X', 'case_mm': [7.3, 13.2],
                'lead_pitch_mm': 3.1, 'complete_footprint': None}},
            'capacitance': {'kind': 'electrical_characteristic', 'value': {
                'nominal_uF': 150, 'initial_tolerance_percent': [-17, 23],
                'effective_capacitance_at_application_uF': None},
                'conditions': {'test_frequency_Hz': 97, 'ambient_C': 23}},
            'impedance': {'kind': 'electrical_characteristic', 'value': {
                'impedance_max_ohm': 0.19, 'ESR_max_ohm': None},
                'conditions': {'test_frequency_Hz': 87000, 'ambient_C': 23}},
            'ripple': {'kind': 'electrical_characteristic', 'value': {
                'rated_ripple_A_rms': 0.63, 'qualified_board_ripple_A_rms': None},
                'conditions': {'frequency_Hz': 87000, 'ambient_C': 99,
                    'low_frequency_factor': {'frequency_Hz': 97, 'factor': 0.61},
                    'spectrum_known': False, 'internal_temperature_C': None}},
            'voltage': {'kind': 'electrical_characteristic', 'value': {
                'rated_DC_V': 23, 'surge_V': 28, 'reverse_voltage_permission_V': None},
                'conditions': {'surge_is_continuous_rating': False,
                    'surge_duration_s': 17, 'surge_recovery_s': 281,
                    'surge_cycles': 713}},
            'endurance': {'kind': 'qualification_test', 'value': {
                'duration_h': 1700, 'field_lifetime_h': None,
                'acceptance': {'capacitance_change_percent': 19,
                               'ESR_multiplier': 1.8}},
                'conditions': {'ambient_C': 99, 'applied_DC_V': 23,
                    'ripple_A_rms': 0.63, 'board_hotspot_C': None,
                    'temperature_life_multiplier': None}},
        }
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
            'acceptance_status': 'DRAFT',
            'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                'device': 'SYNTH-AL-150-X', 'package': 'SYNTH-RADIAL',
                'revision': 'Synthetic R5', 'status': 'DRAFT'}],
            'facts': [{'id': key, 'source_id': 'synthetic', 'parameter': key,
                       'status': 'DRAFT', **spec} for key, spec in specs.items()],
            'source_issues': [
                {'id': 'thermal-warning', 'source_id': 'synthetic',
                    'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                    'missing': ['ripple spectrum', 'ambient', 'internal heating', 'airflow']},
                {'id': 'life-warning', 'source_id': 'synthetic',
                    'issue_status': 'SOURCE_SCOPE_LIMITATION',
                    'value': {'application_life_h': None, 'replacement_qualified': False}}]}
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
            ('identity', ['fact', 'value', 'orderable'], 'SYNTH-AL-150-Y'),
            ('identity', ['fact', 'value', 'case_mm'], [13.2, 7.3]),
            ('identity', ['fact', 'value', 'complete_footprint'], {}),
            ('capacitance', ['fact', 'value', 'initial_tolerance_percent'], [-23, 23]),
            ('capacitance', ['fact', 'value', 'effective_capacitance_at_application_uF'], 150),
            ('capacitance', ['fact', 'conditions', 'test_frequency_Hz'], 87000),
            ('capacitance', ['fact', 'conditions', 'ambient_C'], None),
            ('impedance', ['fact', 'value', 'ESR_max_ohm'], 0.19),
            ('impedance', ['fact', 'conditions', 'test_frequency_Hz'], 97),
            ('impedance', ['fact', 'conditions', 'ambient_C'], None),
            ('ripple', ['fact', 'value', 'rated_ripple_A_rms'], 0.89),
            ('ripple', ['fact', 'value', 'qualified_board_ripple_A_rms'], 0.63),
            ('ripple', ['fact', 'conditions', 'frequency_Hz'], None),
            ('ripple', ['fact', 'conditions', 'ambient_C'], None),
            ('ripple', ['fact', 'conditions', 'low_frequency_factor', 'factor'], 1),
            ('ripple', ['fact', 'conditions', 'spectrum_known'], True),
            ('ripple', ['fact', 'conditions', 'internal_temperature_C'], 99),
            ('voltage', ['fact', 'value', 'rated_DC_V'], 28),
            ('voltage', ['fact', 'value', 'reverse_voltage_permission_V'], 1),
            ('voltage', ['fact', 'conditions', 'surge_is_continuous_rating'], True),
            ('voltage', ['fact', 'conditions', 'surge_duration_s'], None),
            ('voltage', ['fact', 'conditions', 'surge_recovery_s'], 0),
            ('voltage', ['fact', 'conditions', 'surge_cycles'], None),
            ('endurance', ['fact', 'kind'], 'guaranteed_lifetime'),
            ('endurance', ['fact', 'value', 'field_lifetime_h'], 1700),
            ('endurance', ['fact', 'value', 'acceptance', 'ESR_multiplier'], 1),
            ('endurance', ['fact', 'conditions', 'ambient_C'], None),
            ('endurance', ['fact', 'conditions', 'applied_DC_V'], None),
            ('endurance', ['fact', 'conditions', 'ripple_A_rms'], None),
            ('endurance', ['fact', 'conditions', 'temperature_life_multiplier'], 2),
            ('endurance', ['source_issues'], []),
            ('endurance', ['canonical'], True),
            ('endurance', ['evidence_verification'], 'VERIFIED'),
            ('thermal-warning', ['source_issue', 'missing'], []),
            ('life-warning', ['source_issue', 'value', 'application_life_h'], 1700),
            ('life-warning', ['source_issue', 'value', 'replacement_qualified'], True),
        ]
        self.assertEqual(len(mutations), 36)
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
            ('search', {'device': 'SYNTH-AL-150-Y'}),
            ('search', {'package': 'SYNTH-SMD'}),
            ('issues', {'device': 'SYNTH-AL-150-Y'}),
            ('issues', {'package': 'SYNTH-SMD'}),
            ('search', {'parameter': 'guaranteed_application_lifetime'}),
            ('search', {'parameter': 'qualified_board_ripple'}),
        ]
        for index, (command, filters) in enumerate(negatives):
            case = {'id': 'negative-' + str(index), 'command': command, 'query': '',
                'filters': {'source_id': 'synthetic', **filters}, 'expected': []}
            with self.subTest(command=command, filters=filters):
                self.assertEqual(evaluation.run_cli(self.root, case), [])
                report = evaluation.evaluate(self.root, {**self.manifest, 'cases': [case]})
                self.assertEqual(report['status'], 'PASS')
        # Empty selections above do not turn absent field-lifetime evidence into zero.
        lifetime = json.loads(self.baselines['endurance'])[0]['fact']['value']
        self.assertIsNone(lifetime['field_lifetime_h'])
        impedance = json.loads(self.baselines['impedance'])[0]['fact']['value']
        self.assertIsNone(impedance['ESR_max_ohm'])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class ElectrolyticSuccessorTests(unittest.TestCase):
    def test_compact_successor_preserves_prior_cases_pins_and_full_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / 'evals/intake-retrieval-ptc.json'
        old = evaluation.load_manifest(base_path)
        manifest_path = root / 'evals/intake-retrieval-electrolytic.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base']['path'], base_path.name)
        self.assertEqual(delta['base']['sha256'],
            'd2ecfe62dca2b2583511a50debeabe4ea91c285eac4dda37f3584b33984bfb49')
        self.assertEqual(len(delta['cases']), 30)
        self.assertEqual(len(delta['files']), 1)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({path: new['files'][path] for path in old['files']}, old['files'])
        relative = 'knowledge/intake/146rti-bulk-capacitor-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {relative})
        for suffix, digest in {
            '.json': '823234d25f9b7881e072abfc3621d928c7df57f724e698a58394aeddf1e9a23b',
            '-review.md': '80e6400736e9566c88cabb4cf131f458d1a99aa1c8e86382e7a2a25d4ddc79da',
        }.items():
            pair_path = root / ('knowledge/intake/146rti-bulk-capacitor-constraints' + suffix)
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
