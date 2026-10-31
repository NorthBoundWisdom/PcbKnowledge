"""G2 reference power path, physical loads and adversarial acceptance checks."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.audit import audit_catalog
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.intent import validate_intent

ROOT = Path(__file__).resolve().parents[2]


class G2AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/golden-designs/g2.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g2.block-graph.json').read_bytes())

    def expand(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def test_reference_reaches_a2_with_reachable_catalog(self):
        result = self.expand()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        self.assertEqual(result['verification'], 'AGENT_VERIFIED')
        self.assertTrue(result['checks'])
        self.assertTrue(all(row['result'] == 'PASS' for row in result['checks']))
        validate_intent(self.catalog, result, bundle_commit='a' * 40)
        self.assertEqual(audit_catalog(self.catalog)['unreachable'], [])

    def test_missing_buck_or_protection_remains_a_refusal(self):
        for name in ('g2-buck', 'g2-protected-input'):
            with self.subTest(block=name):
                self.setUp()
                del self.catalog.records['block:' + name]
                result = self.expand()
                self.assertEqual(result['status'], 'REFUSED')
                self.assertTrue(any(row['code'] == 'MISSING_RECORD' for row in result['refusals']))

    def test_input_envelope_and_full_input_monitor_are_preserved(self):
        voltage = self.brief['power']['sources'][0]['voltage']
        self.assertEqual((voltage['min'], voltage['max']), (7, 12))
        nets = {n['net']: {(p['instance'], p['port']) for p in n['endpoints']}
                for n in self.graph['connections']}
        self.assertEqual(nets['PROTECTED_INPUT'], {('protection', 'VOUT'), ('monitor', 'SENSE_IN')})
        self.assertTrue({('monitor', 'SENSE_OUT'), ('buck', 'VIN'), ('relay', 'VLOAD'), ('switch', 'VLOAD')}
                        <= nets['MONITORED_LOAD'])
        self.assertIn(('monitor', 'VDD'), nets['LOGIC_3V3'])
        self.assertEqual(self.catalog.get('block:g2-input-monitor')['parameters'], {})
        self.assertEqual(len([i for i in self.graph['instances']
                              if i['block'] == 'block:g2-load-output-header']), 3)

    def test_oversized_input_and_logic_budgets_are_rejected(self):
        for identity in ('protection', 'buck'):
            with self.subTest(instance=identity):
                self.setUp()
                item = next(i for i in self.graph['instances'] if i['id'] == identity)
                item['parameters']['output_current']['value'] *= 2
                result = self.expand()
                self.assertEqual(result['status'], 'REFUSED')
                self.assertTrue(any(row['code'] == 'CHECK_FAILED' for row in result['refusals']))

    def test_missing_load_return_and_ground_short_are_rejected(self):
        net = next(n for n in self.graph['connections'] if n['net'] == 'SWITCH_RETURN')
        self.graph['connections'].remove(net)
        self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        ground = next(n for n in self.graph['connections'] if n['net'] == 'GND')
        ground['endpoints'].append({'instance': 'switch', 'port': 'RETURN'})
        self.assertEqual(self.expand()['status'], 'REFUSED')

    def test_tps_enable_default_is_source_backed_and_required(self):
        result = self.expand()
        default = next(c for c in result['checks'] if c['id'] == 'connection:buck_U1:5')
        self.assertEqual(default['unconnected_state']['state'], 'ENABLED')
        pin = next(p for p in self.catalog.get('part:ti-tps5430dda')['pins'] if p['number'] == '5')
        del pin['unconnected_state']
        self.assertEqual(self.expand()['status'], 'REFUSED')

    def test_gpio_requirement_and_monitor_evidence_survive_handoff(self):
        result = self.expand()
        self.assertEqual({p['pin'] for p in result['pin_configurations']}, {'10', '11', '30'})
        self.assertTrue(all(p['initial_state'] == 'LOW' for p in result['pin_configurations']))
        self.assertIn('source:st-rm0008', result['dependencies'])
        self.assertNotIn('part:rohm-bd14210g-latr', self.catalog.records)
        self.assertNotIn('part:rohm-bd79124muf-ce2', self.catalog.records)
        altered = copy.deepcopy(result)
        altered['pin_configurations'][0]['initial_state'] = 'HIGH'
        bundle = SimpleNamespace(catalog=self.catalog, briefs={'G2': self.brief}, commit='a' * 40)
        with self.assertRaisesRegex(ValueError, 'differs from deterministic'):
            validate_expansion(bundle, altered, self.graph)
        altered['pin_configurations'][0]['initial_state'] = 'UNDECLARED_STATE'
        with self.assertRaisesRegex(ValueError, 'Unknown pin-states'):
            validate_intent(self.catalog, altered, bundle_commit='a' * 40)

    def test_unknown_operating_inputs_still_refuse(self):
        switch = next(i for i in self.graph['instances'] if i['id'] == 'switch')
        switch['parameters']['input_voltage'] = {
            'status': 'UNKNOWN', 'reason': 'Synthetic absent rail limit.', 'blocks': ['Q4', 'Q10']}
        self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        block = self.catalog.get('block:g2-input-monitor')
        block['checks'][0]['inputs']['sense_limit'] = {
            'status': 'UNKNOWN', 'reason': 'Synthetic absent PGA limit.', 'blocks': ['Q4', 'Q10']}
        self.assertEqual(self.expand()['status'], 'REFUSED')

    def test_i2c_cannot_substitute_nominal_voltage_for_actual_rail(self):
        item = next(i for i in self.graph['instances'] if i['id'] == 'i2c')
        item['parameters']['input_voltage'] = {
            'basis': 'ENGINEERING_DEFAULT', 'conditions': {}, 'unit': 'V', 'value': 3.3,
            'note': 'Synthetic stale nominal rail.'}
        result = self.expand()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(r['path'] == 'i2c.parameters.input_voltage' for r in result['refusals']))
