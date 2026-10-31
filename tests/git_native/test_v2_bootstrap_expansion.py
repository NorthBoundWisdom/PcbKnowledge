"""Synthetic topology traverses the real catalog and full graph expansion pipeline."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, dependency_closure
from pcbknowledge.v2.intent import validate_intent
from tests.git_native.test_v2_record_contracts import fixtures, quantity
from tests.git_native import test_v2_bootstrap as bootstrap_tests

ROOT = Path(__file__).resolve().parents[2]


class BootstrapExpansionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())
        synthetic = fixtures()
        for kind in ('source', 'package', 'part'):
            synthetic[kind]['verification'] = 'AGENT_VERIFIED'
            synthetic[kind]['provenance']['verified_by'] = ['agent:independent-fixture']
        source = synthetic['source']
        source['license_class'] = 'PUBLIC_REFERENCE'
        package = synthetic['package']
        template = deepcopy(package['explicit_pads'][0])
        package['explicit_pads'] = []
        for index, number in enumerate(('1', '2', '3', '6')):
            pad = deepcopy(template)
            pad['number'] = number
            pad['x'] = quantity(index * 2, 'mm')
            package['explicit_pads'].append(pad)
        fixture = bootstrap_tests.BootstrapTests()
        fixture.setUp()
        part = synthetic['part']
        part['roles'] = ['regulator.switching.buck']
        part['pins'] = [dict(p, name=p['number']) for p in fixture.parts['IC']['pins']]
        part['bootstrap_supplies'] = [deepcopy(fixture.descriptor)]
        self.part = part
        for record in (source, package, part):
            self.catalog.records[record['id']] = record
        self.catalog.structure(part, 'part.schema.json')
        self.catalog._anchors(part)
        self.catalog._part(part)
        block = self.catalog.get('block:usb-c-5v-sink')
        block['components'] += [{'ref': 'BOOTIC', 'select': {'part': part['id']}},
                                {'ref': 'BOOTCAP', 'select': {'part': 'part:kemet-c0603c104k5ractu'}},
                                {'ref': 'INPUTCAP', 'select': {'part': 'part:kemet-c0603c104k5ractu'}}]
        next(n for n in block['nets'] if n['name'] == 'VBUS')['connect'].extend(['BOOTIC.pin:3', 'INPUTCAP.pin:1'])
        next(n for n in block['nets'] if n['name'] == 'GND')['connect'].extend(['BOOTIC.pin:1', 'INPUTCAP.pin:2'])
        block['nets'] += [{'name': 'BOOTSTRAP', 'connect': ['BOOTIC.pin:6', 'BOOTCAP.pin:1']},
                          {'name': 'SWITCHING', 'connect': ['BOOTIC.pin:2', 'BOOTCAP.pin:2']}]
        self.block = block

    def run_expansion(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def test_full_expansion_accepts_exact_bootstrap_pin_and_preserves_types(self):
        result = self.run_expansion()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        checks = {c['id']: c for c in result['checks']}
        self.assertEqual(checks['bootstrap:usb_BOOTIC:6']['result'], 'PASS')
        self.assertEqual(checks['source:usb_BOOTIC:6']['result'], 'PASS')
        self.assertIn('floating bootstrap', checks['source:usb_BOOTIC:6']['reason'])
        self.assertEqual(next(p for p in self.part['pins'] if p['number'] == '6')['type'], 'POWER_IN')
        self.assertIn('source:synthetic', dependency_closure(self.catalog, {'part:synthetic'}))
        self.assertIn({'source': 'source:synthetic', 'page': 1}, result['evidence'])
        validate_intent(self.catalog, result, bundle_commit='a' * 40)
        rules = [r for r in result['layout'] if r.get('subject') == 'usb_BOOTCAP'
                 and r.get('target') == 'usb_BOOTIC.pin:6' and r['kind'] == 'PLACE_NEAR']
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]['max_distance']['value'], 3)

    def test_missing_descriptor_retains_ordinary_power_input_failure(self):
        self.part.pop('bootstrap_supplies')
        result = self.run_expansion()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(r['path'] == 'source:usb_BOOTIC:6' for r in result['refusals']))

    def test_wrong_switch_reference_refuses_full_expansion(self):
        next(n for n in self.block['nets'] if n['name'] == 'SWITCHING')['connect'].remove('BOOTCAP.pin:2')
        next(n for n in self.block['nets'] if n['name'] == 'GND')['connect'].append('BOOTCAP.pin:2')
        result = self.run_expansion()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(r['path'] == 'bootstrap:topology' for r in result['refusals']))

    def test_unrelated_input_is_not_powered_by_bootstrap_net(self):
        next(n for n in self.block['nets'] if n['name'] == 'VBUS')['connect'].remove('BOOTIC.pin:3')
        next(n for n in self.block['nets'] if n['name'] == 'BOOTSTRAP')['connect'].append('BOOTIC.pin:3')
        result = self.run_expansion()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(r['path'] == 'source:usb_BOOTIC:3' for r in result['refusals']))

    def test_catalog_rejects_wrong_pin_duplicate_and_dangling_source(self):
        original = deepcopy(self.part['bootstrap_supplies'])
        for mutation in ('wrong-pin', 'duplicate', 'bad-source'):
            self.part['bootstrap_supplies'] = deepcopy(original)
            if mutation == 'wrong-pin':
                self.part['bootstrap_supplies'][0]['bootstrap_pin'] = '99'
            if mutation == 'duplicate':
                self.part['bootstrap_supplies'] *= 2
            if mutation == 'bad-source':
                self.part['bootstrap_supplies'][0]['evidence'][0]['source'] = 'source:missing'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.catalog._part(self.part)

    def test_schema_rejects_malformed_descriptor(self):
        for bad in (None, {'kind': 'FLOATING_BOOTSTRAP_SUPPLY'}):
            self.part['bootstrap_supplies'] = [bad]
            with self.assertRaises(ValueError):
                self.catalog.structure(self.part, 'part.schema.json')

    def test_ordinary_supply_still_requires_ground_decoupling(self):
        next(n for n in self.block['nets'] if n['name'] == 'GND')['connect'].remove('INPUTCAP.pin:2')
        result = self.run_expansion()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(r['path'] == 'decoupling:usb_BOOTIC:3' for r in result['refusals']))

    def test_revalidated_intent_rejects_capacitor_wrong_reference(self):
        result = self.run_expansion()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        endpoint = {'ref': 'usb_BOOTCAP', 'pin': '2'}
        for net in result['nets']:
            if endpoint in net['pins']:
                net['pins'].remove(endpoint)
        next(n for n in result['nets'] if n['name'] == 'GND')['pins'].append(endpoint)
        with self.assertRaises(ValueError):
            validate_intent(self.catalog, result, bundle_commit='a' * 40)

    def test_wrong_nominal_capacitor_fails_real_expansion(self):
        capacitor = self.catalog.get('part:kemet-c0603c104k5ractu')
        capacitor['parameters']['capacitance']['typ'] = 1.01e-7
        result = self.run_expansion()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(r['path'] == 'bootstrap:topology' for r in result['refusals']))

    def test_layout_binding_rejects_grounded_substitute_capacitor(self):
        from pcbknowledge.v2.rules import apply_rules
        result = self.run_expansion()
        parts = {ref: self.catalog.get(row['part']) for row in result['bom'] for ref in row['refs']}
        endpoint = {'ref': 'usb_BOOTCAP', 'pin': '2'}
        for net in result['nets']:
            if endpoint in net['pins']:
                net['pins'].remove(endpoint)
        next(n for n in result['nets'] if n['name'] == 'GND')['pins'].append(endpoint)
        with self.assertRaises(ValueError):
            apply_rules(self.catalog, parts, result['nets'])


if __name__ == '__main__':
    unittest.main()
