"""Derived zones preserve input identity and do not claim filled connectivity."""
from copy import deepcopy
import unittest

from pcbknowledge.v2.boardview import children, field
from pcbknowledge.v2.layout_copper import add_copper


def q(value):
    return {'value': value, 'unit': 'mm'}


class Catalog:
    def get(self, identity, kind):
        return {'clearance_min': q(.15), 'trace_width_min': q(.2)}


class CopperTests(unittest.TestCase):
    def setUp(self):
        self.tree = ['kicad_pcb', ['net', '1', 'ground'], ['net', '2', 'output']]
        self.intent = {'fab_profile': 'fab:test', 'mechanical': {'outline_envelope': {
            'shape': 'RECTANGLE', 'max_width': q(20), 'max_length': q(30)}},
            'nets': [{'name': 'ground', 'class': 'GROUND', 'pins': []},
                     {'name': 'output', 'class': 'POWER', 'pins': [{'ref': 'U1', 'pin': '2'}]}],
            'layout': [{'kind': 'COPPER_AREA', 'target': 'U1.pin:2'}]}

    def test_zones_are_deterministic_unfilled_and_source_is_immutable(self):
        original = deepcopy(self.tree)
        result = add_copper(self.tree, self.intent, Catalog())
        self.assertEqual(result, add_copper(self.tree, self.intent, Catalog()))
        self.assertEqual(self.tree, original)
        zones = children(result, 'zone')
        self.assertEqual([field(row, 'layer') for row in zones], [['B.Cu'], ['F.Cu']])
        self.assertEqual([field(row, 'net_name') for row in zones], [['ground'], ['output']])
        self.assertTrue(all(not children(row, 'filled_polygon') for row in zones))
        self.assertEqual(field(zones[0], 'min_thickness'), ['0.2'])
        with self.assertRaisesRegex(ValueError, 'unzoned'):
            add_copper(result, self.intent, Catalog())

    def test_ambiguous_ground_and_unresolved_thermal_target_fail(self):
        self.intent['nets'][1]['class'] = 'GROUND'
        with self.assertRaisesRegex(ValueError, 'one explicit ground'):
            add_copper(self.tree, self.intent, Catalog())
        self.intent['nets'][1]['class'] = 'POWER'
        self.intent['layout'][0]['target'] = 'U1'
        with self.assertRaisesRegex(ValueError, 'exact target pad'):
            add_copper(self.tree, self.intent, Catalog())
        self.intent['layout'][0]['target'] = 'U1.pin:9'
        with self.assertRaisesRegex(ValueError, 'one net'):
            add_copper(self.tree, self.intent, Catalog())
