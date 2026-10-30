"""G2 retained work is reachable and explicitly refused, never promoted to A2."""
import copy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.audit import audit_catalog
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.calculators import evaluate_check

ROOT = Path(__file__).resolve().parents[2]


class G2PartialTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/golden-designs/g2.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g2.block-graph.json').read_bytes())

    def test_unavailable_blocks_are_refused_not_fabricated(self):
        result = expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)
        self.assertEqual(result['status'], 'REFUSED')
        reasons = {(row['code'], row['path']) for row in result['refusals']}
        self.assertIn(('MISSING_RECORD', 'buck.block'), reasons)
        self.assertIn(('MISSING_RECORD', 'protection.block'), reasons)
        self.assertFalse(any(code == 'INVALID_REFERENCE' for code, _ in reasons))
        self.assertNotIn('block:g2-buck', self.catalog.records)
        self.assertNotIn('block:g2-protected-input', self.catalog.records)
        self.assertTrue(all(row['status'] == 'NOT_RUN' for row in self.brief['acceptance']))
        self.assertEqual(audit_catalog(self.catalog)['unreachable'], [])

    def test_source_unknowns_and_full_input_envelope_are_not_replaced(self):
        self.assertEqual(self.brief['power']['sources'][0]['voltage']['min'], 7)
        self.assertEqual(self.brief['power']['sources'][0]['voltage']['max'], 12)
        instances = {item['id']: item for item in self.graph['instances']}
        for identity in ('relay', 'switch'):
            for key in ('gate_voltage', 'on_resistance'):
                self.assertEqual(instances[identity]['parameters'][key]['status'], 'UNKNOWN')
        self.assertEqual(instances['monitor']['parameters']['sense_limit']['status'], 'UNKNOWN')
        endpoints = {tuple(sorted(endpoint.items())) for net in self.graph['connections']
                     for endpoint in net['endpoints']}
        self.assertNotIn(tuple(sorted({'instance': 'switch', 'port': 'GATE'}.items())), endpoints)
        load = next(net for net in self.graph['connections'] if net['net'] == 'MONITORED_LOAD')
        self.assertEqual({(e['instance'], e['port']) for e in load['endpoints']},
                         {('monitor', 'SENSE_OUT'), ('relay', 'VLOAD'), ('switch', 'VLOAD')})

    def test_conditional_loss_diagnostic_cannot_supply_unknown_operating_bound(self):
        for name in ('g2-low-side-switch', 'g2-relay-channels'):
            block = self.catalog.get('block:' + name)
            parts = {row['ref']: self.catalog.get(row['select']['part']) for row in block['components']}
            instance = next(row for row in self.graph['instances'] if row['block'] == block['id'])
            results = [evaluate_check(check, instance['parameters'], parts) for check in block['checks']]
            self.assertEqual([row['result'] for row in results], ['PASS', 'REFUSED'] * (len(results) // 2))
            self.assertTrue(all('on_resistance' in row['reason'] for row in results[1::2]))

    def test_monitor_has_no_invented_3v3_transfer_limit(self):
        block = self.catalog.get('block:g2-input-monitor')
        parts = {row['ref']: self.catalog.get(row['select']['part']) for row in block['components']}
        instance = next(row for row in self.graph['instances'] if row['id'] == 'monitor')
        result = evaluate_check(block['checks'][0], instance['parameters'], parts)
        self.assertEqual(result['result'], 'REFUSED')
        self.assertIn('sense_limit', result['reason'])
