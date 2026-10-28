"""Synthetic capacitance qualification and uncertainty preservation."""
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

class SyntheticCapacitanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        initialize_workspace(self.root, schema_source_root=evaluation.REPO_ROOT)
        relative = 'knowledge/intake/synthetic-capacitance.json'
        path = self.root / relative
        path.parent.mkdir(parents=True)
        # Invented devices, values and conditions; not real source specifications.
        specs = {
            'nominal': {'kind': 'electrical_characteristic',
                'value': {'nominal_nf': 73, 'effective_nf': None},
                'conditions': {'frequency_hz': 1700, 'ac_vrms': 0.7,
                    'referee_hours': 37, 'test_is_circuit_guarantee': False}},
            'rating': {'kind': 'rating',
                'value': {'rated_v': 31, 'withstand_v': 77},
                'conditions': {'duration_seconds': 4, 'test_is_continuous': False}},
            'temperature': {'kind': 'electrical_characteristic',
                'value': {'change_pct': 11},
                'conditions': {'dc_v': 0, 'reference_c': 23, 'combined_envelope': False}},
            'aging': {'kind': 'electrical_characteristic',
                'value': {'rate_pct': 2},
                'conditions': {'time_basis': 'decade-hour', 'thermal_history': None}},
            'simulation': {'kind': 'application_constraint',
                'value': {'numeric_samples': None, 'guaranteed_minimum_nf': None},
                'conditions': {'evidence': 'typical simulation', 'circuit_qualified': False}},
            'geometry': {'kind': 'package_dimension',
                'value': {'body_mm': 1.7, 'certified_pad_mm': None},
                'conditions': {'density': None, 'is_footprint': False}}}
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

    def test_equal_identity_cannot_promote_capacitance_or_unknowns(self):
        changes = [
            ('nominal', ['fact', 'value', 'effective_nf'], 73),
            ('nominal', ['fact', 'conditions', 'frequency_hz'], None),
            ('nominal', ['fact', 'conditions', 'ac_vrms'], None),
            ('nominal', ['fact', 'conditions', 'referee_hours'], None),
            ('nominal', ['fact', 'conditions', 'test_is_circuit_guarantee'], True),
            ('rating', ['fact', 'value', 'rated_v'], 77),
            ('rating', ['fact', 'conditions', 'duration_seconds'], None),
            ('rating', ['fact', 'conditions', 'test_is_continuous'], True),
            ('temperature', ['fact', 'conditions', 'dc_v'], 31),
            ('temperature', ['fact', 'conditions', 'reference_c'], None),
            ('temperature', ['fact', 'conditions', 'combined_envelope'], True),
            ('aging', ['fact', 'conditions', 'time_basis'], 'hour'),
            ('aging', ['fact', 'conditions', 'thermal_history'], 'known'),
            ('simulation', ['fact', 'value', 'numeric_samples'], [73, 60]),
            ('simulation', ['fact', 'value', 'guaranteed_minimum_nf'], 60),
            ('simulation', ['fact', 'conditions', 'evidence'], 'guaranteed'),
            ('simulation', ['fact', 'conditions', 'circuit_qualified'], True),
            ('geometry', ['fact', 'value', 'certified_pad_mm'], 1.7),
            ('geometry', ['fact', 'conditions', 'density'], 'selected'),
            ('geometry', ['fact', 'conditions', 'is_footprint'], True),
            ('unknown', ['source_issue', 'answer'], 'SAFE'),
            ('unknown', ['source_issue', 'missing'], []),
            ('nominal', ['source_issues'], []),
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

class MlccSuccessorTests(unittest.TestCase):
    def test_history_exact_handoff_and_complete_case_coverage(self):
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-translation-loadswitch.json').read_bytes())
        new = json.loads((root / 'evals/intake-retrieval-mlcc.json').read_bytes())
        evaluation.validate_manifest(new)
        self.assertEqual(new['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: new['files'][p] for p in old['files']}, old['files'])
        path = 'knowledge/intake/kemet-c0603c104k5ractu-capacitance-constraints.json'
        self.assertEqual(set(new['files']) - set(old['files']), {path})
        for suffix, digest in {
            '.json': 'e4cb0113234ed90ed6f9ef7e2c32cad842d6f9b7648ac017b16b2cbbe9903a1b',
            '-review.md': 'da3bb353c8452ebedc0f7629452cd98d0d09e6a9b2db986e8efacec027f626b4',
        }.items():
            p = root / ('knowledge/intake/kemet-c0603c104k5ractu-capacitance-constraints' + suffix)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)
        data = json.loads((root / path).read_bytes())
        self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
        self.assertFalse(data['canonical'])
        self.assertFalse(data['human_reviewed'])
        selected = {ref for case in new['cases'][len(old['cases']):] for ref in case['expected']}
        self.assertEqual(selected, {path + '#' + rec['id'] for rec in data['facts'] + data['source_issues']})
