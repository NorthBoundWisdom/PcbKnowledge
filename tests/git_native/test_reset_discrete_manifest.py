"""Successor pins preserve historical records and reviewed conditional payloads."""
from __future__ import annotations

import hashlib
import json
import unittest

from configs import pcbknowledge_intake_eval as evaluation


class ResetDiscreteManifestTests(unittest.TestCase):
    def test_successor_keeps_historical_cases_and_pins(self) -> None:
        root = evaluation.REPO_ROOT
        old = json.loads((root / 'evals/intake-retrieval-measurement-timing-operational.json').read_bytes())
        current = json.loads((root / 'evals/intake-retrieval-reset-rs485-discretes.json').read_bytes())
        evaluation.validate_manifest(current)
        self.assertEqual(current['cases'][:len(old['cases'])], old['cases'])
        self.assertEqual({p: current['files'][p] for p in old['files']}, old['files'])
        added = set(current['files']) - set(old['files'])
        self.assertEqual(added, {
            'knowledge/intake/tps3808-reset-supervisor-constraints.json',
            'knowledge/intake/sn65hvd75-rs485-interface-constraints.json',
            'knowledge/intake/ao3400a-gate-drive-constraints.json',
            'knowledge/intake/vishay-ss14-rectifier-constraints.json',
        })
        cases = current['cases'][len(old['cases']):]
        selections = {ref for case in cases for ref in case['expected']}
        for path in added:
            data = json.loads((root / path).read_bytes())
            self.assertEqual(current['files'][path], hashlib.sha256((root / path).read_bytes()).hexdigest())
            self.assertEqual(data['acceptance_status'], 'AGENT_REVIEWED_UNDER_OWNER_DELEGATION')
            self.assertFalse(data['canonical'])
            self.assertFalse(data['human_reviewed'])
            for record in data['facts'] + data['source_issues']:
                self.assertIn(path + '#' + record['id'], selections)
            for fact in data['facts']:
                self.assertTrue(any(case['command'] == 'search'
                    and case['filters'] == {'source_id': fact['source_id'], 'parameter': fact['parameter']}
                    and case['expected'] == [path + '#' + fact['id']] for case in cases))

    def test_immutable_maintainer_handoffs_are_exact(self) -> None:
        root = evaluation.REPO_ROOT
        pins = {
            'ao3400a-gate-drive-constraints.json': '2352020939f6f1c88dd714c31fb491672c6f5da300a76a41c5a5e1f7ec05b0ce',
            'ao3400a-gate-drive-constraints-review.md': '0e7d7ce3173426bf430e3248c6946ebdd75a6058d03f8a6a25dcb251d63772a7',
            'vishay-ss14-rectifier-constraints.json': '6537e3323bd556482167c9a268c799f1d8527e8f4d23d610ccfc88b0f2654407',
            'vishay-ss14-rectifier-constraints-review.md': '39c76cb35adada5a8856d0968eb264fafff136507f8b381cc4ee9c4f4aa387bb',
        }
        for name, digest in pins.items():
            self.assertEqual(hashlib.sha256((root / 'knowledge/intake' / name).read_bytes()).hexdigest(), digest)
