"""Differential geometry rule export is not an impedance or routing certification."""
import copy
from types import SimpleNamespace
import unittest

from pcbknowledge.v2.handoff_rules import export_rules, project_settings


def fixture():
    def mm(value):
        return {'value': value, 'unit': 'mm'}
    fab = {key: mm(value) for key, value in [('trace_width_min', .15), ('clearance_min', .15),
                                            ('drill_min', .3), ('annular_ring_min', .125)]}
    intent = {'fab_profile': 'fab_profile:synthetic', 'components': [], 'mechanical': {'mounting': []},
              'nets': [{'name': 'USB_P'}, {'name': 'USB_N'}], 'layout': [
                  {'kind': 'DIFFERENTIAL_PAIR', 'nets': ['USB_P', 'USB_N'],
                   'min_width': mm(.2), 'gap': mm(.18), 'max_skew': mm(.5)}]}
    return intent, SimpleNamespace(get=lambda *_: fab)


class DifferentialRulesTests(unittest.TestCase):
    def test_exact_pair_geometry_rules_and_netclasses_are_deterministic(self):
        intent, catalog = fixture()
        rules = export_rules(intent, catalog)
        self.assertIn('constraint diff_pair_gap (min 0.180000mm) (opt 0.180000mm) (max 0.180000mm)', rules)
        self.assertIn('constraint skew (max 0.500000mm) (within_diff_pairs)', rules)
        self.assertEqual(rules.count('track_width (min 0.200000mm)'), 2)
        project = project_settings(intent, catalog)
        pair = next(item for item in project['net_settings']['classes'] if item['name'] == 'Differential_1')
        self.assertEqual((pair['diff_pair_width'], pair['diff_pair_gap']), (.2, .18))
        self.assertEqual({p['netclass'] for p in project['net_settings']['netclass_patterns']}, {'Differential_1'})
        reversed_intent = copy.deepcopy(intent)
        reversed_intent['layout'][0]['nets'].reverse()
        self.assertEqual(export_rules(reversed_intent, catalog), rules)

    def test_ambiguous_pair_names_and_reused_nets_are_refused(self):
        intent, catalog = fixture()
        intent['layout'].append(copy.deepcopy(intent['layout'][0]))
        with self.assertRaises(ValueError):
            export_rules(intent, catalog)
        intent, catalog = fixture()
        intent['nets'][1]['name'] = 'USB_M'
        intent['layout'][0]['nets'][1] = 'USB_M'
        with self.assertRaisesRegex(ValueError, 'matching stems'):
            export_rules(intent, catalog)
