"""Invented photodiode metadata preserve optical conditions, not frontend guarantees."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from configs import pcbknowledge_intake_eval as evaluation
from pcbknowledge.git_native.workspace import initialize_workspace


class SyntheticPhotodiodeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        self.relative = 'knowledge/intake/synthetic-photodiode.json'
        self.path = self.root / self.relative
        self.path.parent.mkdir(parents=True)
        # All identity, numeric values and test conditions are invented.
        specs = {'identity': {'kind': 'identity',
                      'value': {'orderable': 'SYNTH-PHOTO-BULK',
                                'package': 'SYNTH-LEADED-OPTICAL',
                                'automotive_qualified': False,
                                'area_tolerance_mm2': None}},
         'light': {'kind': 'electrical_characteristic',
                   'value': {'radiometric': {'irradiance_mW_cm2': 1.7,
                                             'wavelength_nm': 937,
                                             'bias_V': 4.3,
                                             'min_uA': 31,
                                             'typ_uA': 46,
                                             'max_uA': None},
                             'photometric': {'illuminance_klx': 1.3,
                                             'bias_V': 4.3,
                                             'typ_uA': 68,
                                             'max_uA': None,
                                             'illuminant_spectrum': None},
                             'ambient_C': 23,
                             'universal_conversion': None}},
         'dark': {'kind': 'electrical_characteristic',
                  'value': {'typ_nA': 3.7,
                            'max_nA': 27,
                            'bias_V': 8,
                            'illumination': 'dark',
                            'ambient_C': 23,
                            'full_temperature_max_nA': None}},
         'capacitance': {'kind': 'electrical_characteristic',
                         'value': {'zero_bias': {'bias_V': 0, 'typ_pF': 63, 'max_pF': None},
                                   'biased': {'bias_V': 2.7, 'typ_pF': 21, 'max_pF': 36},
                                   'frequency_Hz': 870000,
                                   'illumination': 'dark',
                                   'ambient_C': 23,
                                   'total_TIA_input_pF': None}},
         'response': {'kind': 'electrical_characteristic',
                      'value': {'rise_typ_ns': 83,
                                'fall_typ_ns': 91,
                                'rise_max_ns': None,
                                'fall_max_ns': None,
                                'bias_V': 8,
                                'load_ohm': 1300,
                                'wavelength_nm': 837,
                                'ambient_C': 23,
                                'optical_amplitude': None,
                                'edge_thresholds': None,
                                'installed_bandwidth_Hz': None}},
         'spectral': {'kind': 'optical_characteristic',
                      'value': {'peak_typ_nm': 893,
                                'relative_threshold': 0.13,
                                'band_typ_nm': [417, 1087],
                                'half_angle_typ_deg': [-61, 61],
                                'flat_gain_band_nm': None}},
         'absolute': {'kind': 'absolute_maximum',
                      'value': {'reverse_max_V': 53,
                                'power_max_mW': 197,
                                'ambient_max_C': 23,
                                'thermal_K_W': 371,
                                'connection': 'invented wire condition',
                                'recommended_bias_V': None}}}
        data = {'format': 'pcbknowledge-independent-intake-v1', 'canonical': False,
            'acceptance_status': 'DRAFT',
            'sources': [{'id': 'synthetic', 'manufacturer': 'Synthetic',
                'device': 'SYNTH-PHOTO-BULK', 'package': 'SYNTH-LEADED-OPTICAL',
                'revision': 'Synthetic R5', 'status': 'DRAFT'}],
            'facts': [{'id': key, 'source_id': 'synthetic', 'parameter': key,
                       'status': 'DRAFT', **spec} for key, spec in specs.items()],
            'source_issues': [
                {'id': 'optical-warning', 'source_id': 'synthetic',
                 'issue_status': 'UNRESOLVED_APPLICATION_INPUTS',
                 'missing': ['optical spectrum', 'feedback network', 'noise spectrum', 'temperature']},
                {'id': 'qualification-warning', 'source_id': 'synthetic',
                 'issue_status': 'SOURCE_SCOPE_LIMITATION',
                 'value': {'calibrated_lux_accuracy': None,
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
        mutations = [('identity', ['fact', 'value', 'orderable'], 'SYNTH-PHOTO-TUBE'),
         ('identity', ['fact', 'value', 'package'], 'SYNTH-OTHER'),
         ('identity', ['fact', 'value', 'automotive_qualified'], True),
         ('identity', ['fact', 'value', 'area_tolerance_mm2'], 0),
         ('light', ['fact', 'value', 'radiometric', 'irradiance_mW_cm2'], None),
         ('light', ['fact', 'value', 'radiometric', 'wavelength_nm'], None),
         ('light', ['fact', 'value', 'radiometric', 'bias_V'], 0),
         ('light', ['fact', 'value', 'radiometric', 'min_uA'], 46),
         ('light', ['fact', 'value', 'radiometric', 'max_uA'], 46),
         ('light', ['fact', 'value', 'photometric', 'illuminance_klx'], 1.7),
         ('light', ['fact', 'value', 'photometric', 'illuminant_spectrum'], 'invented daylight spectrum'),
         ('light', ['fact', 'value', 'photometric', 'max_uA'], 68),
         ('light', ['fact', 'value', 'ambient_C'], None),
         ('light', ['fact', 'value', 'universal_conversion'], 1),
         ('dark', ['fact', 'value', 'typ_nA'], 27),
         ('dark', ['fact', 'value', 'max_nA'], 3.7),
         ('dark', ['fact', 'value', 'bias_V'], 4.3),
         ('dark', ['fact', 'value', 'illumination'], 'illuminated'),
         ('dark', ['fact', 'value', 'ambient_C'], None),
         ('dark', ['fact', 'value', 'full_temperature_max_nA'], 27),
         ('capacitance', ['fact', 'value', 'zero_bias', 'max_pF'], 36),
         ('capacitance', ['fact', 'value', 'zero_bias', 'typ_pF'], 21),
         ('capacitance', ['fact', 'value', 'biased', 'bias_V'], 0),
         ('capacitance', ['fact', 'value', 'frequency_Hz'], None),
         ('capacitance', ['fact', 'value', 'illumination'], 'illuminated'),
         ('capacitance', ['fact', 'value', 'total_TIA_input_pF'], 36),
         ('response', ['fact', 'value', 'rise_max_ns'], 83),
         ('response', ['fact', 'value', 'fall_max_ns'], 91),
         ('response', ['fact', 'value', 'bias_V'], 0),
         ('response', ['fact', 'value', 'load_ohm'], None),
         ('response', ['fact', 'value', 'wavelength_nm'], 937),
         ('response', ['fact', 'value', 'optical_amplitude'], 1.7),
         ('response', ['fact', 'value', 'edge_thresholds'], [0.1, 0.9]),
         ('response', ['fact', 'value', 'installed_bandwidth_Hz'], 1000000),
         ('spectral', ['fact', 'value', 'relative_threshold'], 1),
         ('spectral', ['fact', 'value', 'band_typ_nm'], [0, 2000]),
         ('spectral', ['fact', 'value', 'flat_gain_band_nm'], [417, 1087]),
         ('absolute', ['fact', 'value', 'ambient_max_C'], 85),
         ('absolute', ['fact', 'value', 'connection'], None),
         ('absolute', ['fact', 'value', 'recommended_bias_V'], 53),
         ('absolute', ['fact', 'kind'], 'recommended_operation'),
         ('light', ['source_issues'], []),
         ('light', ['canonical'], True),
         ('light', ['evidence_verification'], 'VERIFIED'),
         ('optical-warning', ['source_issue', 'missing'], []),
         ('qualification-warning', ['source_issue', 'value', 'calibrated_lux_accuracy'], 0.01),
         ('qualification-warning', ['source_issue', 'value', 'circuit_qualified'], True)]
        self.assertEqual(len(mutations), 47)
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
            ('search', {'device': 'SYNTH-PHOTO-TUBE'}),
            ('search', {'package': 'SYNTH-OTHER'}),
            ('issues', {'device': 'SYNTH-PHOTO-TUBE'}),
            ('issues', {'package': 'SYNTH-OTHER'}),
            ('search', {'parameter': 'guaranteed_tia_bandwidth'}),
            ('search', {'parameter': 'full_temperature_dark_current_max'}),
        ]
        for index, (command, filters) in enumerate(negatives):
            case = {'id': 'negative-' + str(index), 'command': command, 'query': '',
                'filters': {'source_id': 'synthetic', **filters}, 'expected': []}
            with self.subTest(command=command, filters=filters):
                self.assertEqual(evaluation.run_cli(self.root, case), [])
                report = evaluation.evaluate(self.root, {**self.manifest, 'cases': [case]})
                self.assertEqual(report['status'], 'PASS')
        light = json.loads(self.baselines['light'])[0]['fact']['value']
        self.assertIsNone(light['photometric']['illuminant_spectrum'])
        capacitance = json.loads(self.baselines['capacitance'])[0]['fact']['value']
        self.assertIsNone(capacitance['zero_bias']['max_pF'])
        self.assertEqual(self.path.read_bytes(), self.original_bytes)


class PhotodiodeSuccessorTests(unittest.TestCase):
    def test_compact_successor_preserves_prior_cases_pins_and_full_scope(self):
        root = evaluation.REPO_ROOT
        base_path = root / 'evals/intake-retrieval-zener.json'
        old = evaluation.load_manifest(base_path)
        self.assertEqual(len(old['cases']), 738)
        self.assertEqual(len(old['files']), 34)
        manifest_path = root / 'evals/intake-retrieval-photodiode.json'
        delta = json.loads(manifest_path.read_bytes())
        self.assertEqual(delta['format'], 'pcbknowledge-intake-retrieval-delta-v1')
        self.assertEqual(delta['base']['path'], base_path.name)
        self.assertEqual(delta['base']['sha256'],
            'f384d0944e1679ebdaca37702767137ffb21a31d8c15d08defc966228b00aa3d')
        self.assertEqual(len(delta['cases']), 26)
        self.assertEqual(len(delta['files']), 1)
        new = evaluation.load_manifest(manifest_path)
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({path: new['files'][path] for path in old['files']}, old['files'])
        relative = 'knowledge/intake/bpw34-photodiode-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {relative})
        for suffix, digest in {
            '.json': 'f495129cc4068f6519883de8b3c81d962ee6e727e5476d30efc7efc463dbe6bb',
            '-review.md': 'e87c7ad41b6698d97e8f1a4fb25a5b11815fe2fc971d07d5b650f28eed491d50',
        }.items():
            pair_path = root / ('knowledge/intake/bpw34-photodiode-constraints' + suffix)
            self.assertEqual(hashlib.sha256(pair_path.read_bytes()).hexdigest(), digest)
        data = json.loads((root / relative).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        self.assertEqual((len(data['facts']), len(data['source_issues'])), (7, 3))
        self.assertEqual(new['files'][relative], hashlib.sha256((root / relative).read_bytes()).hexdigest())
        additions = new['cases'][len(old['cases']):]
        self.assertEqual(len(additions), 26)
        self.assertEqual(sum(not case['expected'] for case in additions), 13)
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
