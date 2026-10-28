"""Immutable handoff integration and invented pulse/geometry payload regressions."""
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

PINS = {
    'vishay-smbj5-0a-tvs-pulse-constraints.json': '54772a9aea101d79612815f88a317c8e2915391fa274eac16ca0d4a590f2a596',
    'vishay-smbj5-0a-tvs-pulse-constraints-review.md': '9c9609faaf7f5a947d03bdf4dcdd5b910e3a14db88eb55be6267cbb9c767dba9',
    'wurth-61300211121-connector-geometry.json': '02f61ef6ec11b5bab48d6bd19461f2d6b1afa1a18cb1c34dde30b81e1370a5e6',
    'wurth-61300211121-connector-geometry-review.md': '53303a6f473f4dc72ffba70cae37b67d4f5fef54736439ad9d6c55a8a8e35ca4',
}


class HandoffManifestTests(unittest.TestCase):
    def test_exact_handoffs_and_historical_cases(self):
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-reset-rs485-discretes.json').read_bytes())
        new = json.loads((root / 'evals/intake-retrieval-tvs-connector.json').read_bytes())
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: new['files'][p] for p in old['files']}, old['files'])
        additions = set(new['files']) - set(old['files'])
        self.assertEqual(additions, {'knowledge/intake/' + n for n in PINS if n.endswith('.json')})
        for name, digest in PINS.items():
            self.assertEqual(hashlib.sha256((root / 'knowledge/intake' / name).read_bytes()).hexdigest(), digest)
        selected = {ref for c in new['cases'][len(old['cases']):] for ref in c['expected']}
        for path in additions:
            data = json.loads((root / path).read_bytes())
            self.assertFalse(data['canonical'])
            self.assertFalse(data['human_reviewed'])
            self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
            for record in data['facts'] + data['source_issues']:
                self.assertIn(path + '#' + record['id'], selected)


class SyntheticPulseGeometryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-pulse-geometry.json'
        path = self.root / relative
        path.parent.mkdir(parents=True)
        # Invented devices, values and conditions; not real source specifications.
        specs = {
            'pulse': {'kind': 'maximum_rating',
                      'value': {'peak_power': 17, 'continuous_power': None, 'joules': None,
                                'marking_unique': False, 'guaranteed_capacitance': None},
                      'conditions': {'waveform': 'synthetic-decay', 'duration_definition': 'half-peak',
                                     'temperature_kind': 'initial-junction', 'thermal_path': 'test-fixture',
                                     'repetition': 'single-event', 'derating': 'typical-not-guaranteed'}},
            'geometry': {'kind': 'mechanical_characteristic',
                         'value': {'pitch': 7, 'footprint_coordinates': None, 'board_side': None,
                                   'pin_map': None, 'power_polarity': None, 'current_test_temperature': None,
                                   'working_voltage': 11, 'withstand_voltage': 29},
                         'conditions': {'dimension_source': 'explicit-callout-only',
                                        'withstand_duration': 3, 'mating_part': 'UNKNOWN'}}}
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

    def test_equal_identity_cannot_promote_pulse_geometry_or_unknowns(self):
        changes = [
            ('pulse', ['fact', 'value', 'continuous_power'], 17),
            ('pulse', ['fact', 'value', 'joules'], 17),
            ('pulse', ['fact', 'value', 'marking_unique'], True),
            ('pulse', ['fact', 'value', 'guaranteed_capacitance'], 7),
            ('pulse', ['fact', 'conditions', 'waveform'], 'rectangle'),
            ('pulse', ['fact', 'conditions', 'duration_definition'], 'full-peak'),
            ('pulse', ['fact', 'conditions', 'temperature_kind'], 'ambient'),
            ('pulse', ['fact', 'conditions', 'thermal_path'], 'any-board'),
            ('pulse', ['fact', 'conditions', 'repetition'], 'unlimited'),
            ('pulse', ['fact', 'conditions', 'derating'], 'guaranteed'),
            ('geometry', ['fact', 'value', 'footprint_coordinates'], [[0, 0], [7, 0]]),
            ('geometry', ['fact', 'value', 'board_side'], 'top'),
            ('geometry', ['fact', 'value', 'pin_map'], {'1': 'left'}),
            ('geometry', ['fact', 'value', 'power_polarity'], 'positive'),
            ('geometry', ['fact', 'value', 'current_test_temperature'], 25),
            ('geometry', ['fact', 'value', 'working_voltage'], 29),
            ('geometry', ['fact', 'conditions', 'dimension_source'], 'image-scale'),
            ('geometry', ['fact', 'conditions', 'withstand_duration'], 'continuous'),
            ('geometry', ['fact', 'conditions', 'mating_part'], 'any-header'),
            ('unknown', ['source_issue', 'answer'], 'SAFE'),
            ('unknown', ['source_issue', 'missing'], []),
            ('pulse', ['source_issues'], []),
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
