"""CH340C joined-supply decoupling retains per-pin distance and electrical checks."""
import copy
import math
from pathlib import Path
import unittest

import pcbknowledge
from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.rules import apply_rules

ROOT = Path(pcbknowledge.__file__).resolve().parents[2]


def resolved_block(catalog, block):
    parts = {'bridge_' + item['ref']: catalog.get(item['select']['part'], 'part') for item in block['components']}
    nets = []
    for net in block['nets']:
        pins = []
        for endpoint in net['connect']:
            if endpoint.startswith('port:'):
                continue
            ref, pin = endpoint.split('.pin:')
            pins.append({'ref': 'bridge_' + ref, 'pin': pin})
        nets.append({'name': net['name'], 'pins': pins})
    constraints = copy.deepcopy(block['layout'])
    for item in constraints:
        for key in ('subject', 'target'):
            item[key] = 'bridge_' + item[key]
    generated, _ = apply_rules(catalog, parts, nets, constraints)
    return parts, nets, constraints + generated


class UsbSupplyDecouplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')
        cls.block = cls.catalog.get('block:usb-uart-bridge', 'block')
        cls.geometry = derive_footprint(cls.catalog.get('package:sop-16-wch-ch340c', 'package'))

    def test_original_shared_capacitor_circles_do_not_intersect(self):
        pads = {p['number']: (p['x'], p['y']) for p in self.geometry['pads']}
        self.assertEqual(pads['4'], (-2.75, -0.635))
        self.assertEqual(pads['16'], (2.75, -4.445))
        separation = math.dist(pads['4'], pads['16'])
        self.assertAlmostEqual(separation, 6.690747342415046)
        self.assertGreater(separation, 3 + 3)
        # Triangle inequality proves no rotation/translation or capacitor origin can meet both bounds.
        legacy = copy.deepcopy(self.block)
        legacy['components'] = [c for c in legacy['components'] if c['ref'] != 'C2']
        legacy['layout'] = [copy.deepcopy(legacy['layout'][0])]
        legacy['layout'][0]['target'] = 'U1.pin:16'
        for net in legacy['nets']:
            net['connect'] = [p for p in net['connect'] if not p.startswith('C2.pin:')]
        _, _, rules = resolved_block(self.catalog, legacy)
        targets = {r['target'] for r in rules if r['subject'] == 'bridge_C1'}
        self.assertEqual(targets, {'bridge_U1.pin:4', 'bridge_U1.pin:16'})

    def test_dedicated_caps_cover_both_source_mapped_supply_pins(self):
        part = self.catalog.get('part:wch-ch340c', 'part')
        pins = {p['number']: (p['name'], p['type']) for p in part['pins']}
        self.assertEqual(pins['4'], ('V3', 'POWER_IN'))
        self.assertEqual(pins['16'], ('VCC', 'POWER_IN'))
        self.assertEqual(pins['1'], ('GND', 'GROUND'))
        parts, nets, rules = resolved_block(self.catalog, self.block)
        expected = {'bridge_C1': 'bridge_U1.pin:4', 'bridge_C2': 'bridge_U1.pin:16'}
        self.assertEqual(len(self.block['layout']), 2)
        for capacitor, target in expected.items():
            self.assertEqual(parts[capacitor]['id'], 'part:kemet-c0603c104k5ractu')
            self.assertEqual(parts[capacitor]['parameters']['capacitance']['typ'], 100e-9)
            matching = [r for r in rules if r['subject'] == capacitor]
            self.assertTrue(matching)
            self.assertEqual({r['target'] for r in matching}, {target})
            self.assertTrue(all(r['max_distance']['value'] == 3 for r in matching))
            self.assertTrue(all(r['max_distance']['unit'] == 'mm' for r in matching))
            by_name = {n['name']: n['pins'] for n in nets}
            self.assertIn({'ref': capacitor, 'pin': '1'}, by_name['PWR3V3'])
            self.assertIn({'ref': capacitor, 'pin': '2'}, by_name['GND'])
        powered = next(n for n in nets if n['name'] == 'PWR3V3')['pins']
        self.assertTrue(all({'ref': 'bridge_U1', 'pin': pin} in powered for pin in ('4', '16')))

    def test_disconnected_second_capacitor_recreates_contradictory_rule_binding(self):
        broken = copy.deepcopy(self.block)
        ground = next(n for n in broken['nets'] if n['name'] == 'GND')
        ground['connect'].remove('C2.pin:2')
        _, _, rules = resolved_block(self.catalog, broken)
        targets = {r['target'] for r in rules if r['subject'] == 'bridge_C1'}
        self.assertEqual(targets, {'bridge_U1.pin:4', 'bridge_U1.pin:16'})
