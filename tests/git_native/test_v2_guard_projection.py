"""Exact guard-pair clearance projection without changing unrelated nets or widths."""
import copy
import unittest
from unittest.mock import patch

from pcbknowledge.v2.boardview import children, field
from pcbknowledge.v2.specctra import configure_dsn, read_specctra
from tests.git_native.test_v2_specctra import DSN


class Catalog:
    def get(self, identity, kind):
        return {'clearance_min': {'unit': 'mm', 'value': .15},
                'trace_width_min': {'unit': 'mm', 'value': .15}}


def guard(left='GND', right='VCC', clearance=.2):
    return {'kind': 'GUARD_RING', 'net': left, 'guard_net': right,
            'min_clearance': {'unit': 'mm', 'value': clearance}}


def project(rules, text=None):
    intent = {'fab_profile': 'fab:test', 'nets': [{'name': name} for name in ('GND', 'VCC', 'OTHER')],
              'layout': rules}
    text = text or DSN.replace('(net VCC', '(net OTHER (pins U1-3)) (net VCC')
    with patch('pcbknowledge.v2.specctra.net_widths', return_value={'GND': .15, 'VCC': .25, 'OTHER': .15}):
        return configure_dsn(text, intent, Catalog())


class GuardProjectionTests(unittest.TestCase):
    def test_exact_pair_scope_and_all_original_widths(self):
        rules = [guard()]
        original = copy.deepcopy(rules)
        network = children(read_specctra(project(rules)), 'network')[0]
        classes = children(network, 'class')
        mapping = {net: row[1] for row in classes for net in row[2:] if isinstance(net, str)}
        widths = {net: float(field(children(row, 'rule')[0], 'width')[0])
                  for row in classes for net in row[2:] if isinstance(net, str)}
        self.assertEqual(widths, {'GND': .15, 'VCC': .25, 'OTHER': .15})
        pairs = children(network, 'class_class')
        self.assertEqual(len(pairs), 1)
        self.assertEqual(set(field(pairs[0], 'classes')), {mapping['GND'], mapping['VCC']})
        self.assertNotIn(mapping['OTHER'], field(pairs[0], 'classes'))
        self.assertEqual(float(field(children(pairs[0], 'rule')[0], 'clearance')[0]), .2)
        self.assertTrue(all(float(field(children(row, 'rule')[0], 'clearance')[0]) == .15 for row in classes))
        self.assertEqual(rules, original)

    def test_unit_conversion_duplicate_direction_and_fab_floor(self):
        text = DSN.replace('(net VCC', '(net OTHER (pins U1-3)) (net VCC').replace('(unit mm)', '(unit um)')
        rules = [guard(clearance=.1), guard('VCC', 'GND', .2), guard(clearance=.18)]
        tree = read_specctra(project(rules, text))
        pair = children(children(tree, 'network')[0], 'class_class')[0]
        self.assertEqual(float(field(children(pair, 'rule')[0], 'clearance')[0]), 200.0)
        tree = read_specctra(project([guard(clearance=.1)]))
        pair = children(children(tree, 'network')[0], 'class_class')[0]
        self.assertEqual(float(field(children(pair, 'rule')[0], 'clearance')[0]), .15)

    def test_projection_is_idempotent_and_unguarded_has_no_pairs(self):
        output = project([guard()])
        self.assertEqual(project([guard()], output), output)
        network = children(read_specctra(project([])), 'network')[0]
        self.assertEqual(children(network, 'class_class'), [])

    def test_unknown_self_nonfinite_or_wrong_unit_fails_closed(self):
        cases = [guard('BAD', 'VCC'), guard('GND', 'GND'), guard(clearance=float('nan')),
                 guard(clearance=float('inf')), guard(clearance=-1)]
        wrong = guard()
        wrong['min_clearance']['unit'] = 'um'
        for rule in cases + [wrong]:
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                project([rule])
