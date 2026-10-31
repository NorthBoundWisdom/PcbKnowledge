"""Conditional variant rail windows and missing waveform coverage."""
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.bringup import make_bringup, render_bringup
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand

ROOT = Path(__file__).resolve().parents[2]


def read(name, kind):
    return json.loads((ROOT / f'evals/golden-designs/{name}.{kind}.json').read_text())


class Stage14BringupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')

    def report(self, name, graph=None):
        graph = graph if graph is not None else read(name, 'block-graph')
        brief = read(name, 'brief')
        intent = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
        return make_bringup(intent, graph, brief, self.catalog)

    def test_variant_windows_remain_unobserved_and_resolve_exact_terminals(self):
        for name, count in (('g1v1', 4), ('g1v2', 5), ('g5', 3)):
            with self.subTest(name=name):
                report = self.report(name)
                self.assertEqual(report['range_coverage'], 'COMPLETE')
                self.assertEqual(len(report['rails']), count)
                self.assertEqual(report['a6'], 'NOT_RUN')
                self.assertEqual(report['prerequisites_status'], 'NOT_RUN')
                for rail in report['rails']:
                    self.assertEqual(rail['result'], 'NOT_RUN')
                    if rail['expected_voltage'].get('acceptance_type') == 'ENGINEERING_TEST_WINDOW':
                        self.assertEqual(rail['expected_voltage']['conditions_status'], 'NOT_RUN')
                        self.assertIn(rail['declared_test_location'], rail['test_locations'])

    def test_no_shunt_variant_and_bridge_variant_use_their_actual_topology(self):
        first = {row['net']: row for row in self.report('g1v1')['rails']}
        second = {row['net']: row for row in self.report('g1v2')['rails']}
        self.assertNotIn('REGULATED_3V3', first)
        self.assertEqual(first['LOGGER_3V3']['declared_test_location']['ref'], 'ldo_U1')
        self.assertEqual(first['LOGGER_3V3']['expected_voltage']['min'], 3.18)
        self.assertEqual(first['MCU_VDDA']['expected_voltage']['min'], 3.06)
        self.assertEqual(second['LOGGER_3V3']['declared_test_location']['ref'], 'monitor_R1')
        self.assertEqual(second['LOGGER_3V3']['expected_voltage']['min'], 3.16)
        self.assertEqual(second['MCU_VDDA']['expected_voltage']['min'], 3.04)
        self.assertEqual(second['REGULATED_3V3']['expected_voltage']['conditions']['regulator_load_max']['value'], .15)

    def test_missing_required_window_reaches_final_report_as_unknown(self):
        for name, endpoint, net in (('g1v1', 'mcu_C5.pin:1', 'MCU_VDDA'),
                                    ('g1v2', 'monitor_R1.pin:2', 'LOGGER_3V3'),
                                    ('g2', 'relay_U1.pin:16', 'RELAY1_RETURN'),
                                    ('g5', 'reference_U1.pin:1', 'VREF')):
            graph = read(name, 'block-graph')
            graph['bringup']['rails'] = [row for row in graph['bringup']['rails'] if row['at'] != endpoint]
            if not graph['bringup']['rails']:
                del graph['bringup']
            report = self.report(name, graph)
            self.assertEqual(report['range_coverage'], 'UNKNOWN')
            self.assertIn(net, report['unresolved_rail_ranges'])
            self.assertIn(net + ': UNKNOWN', render_bringup(report))

    def test_g2_dc_windows_do_not_claim_switch_waveform_coverage(self):
        graph = read('g2', 'block-graph')
        graph['bringup']['rails'] = [row for row in graph['bringup']['rails'] if 'waveform' not in row]
        report = self.report('g2', graph)
        self.assertEqual(report['range_coverage'], 'UNKNOWN')
        self.assertEqual(report['unresolved_rail_ranges'], ['BUCK_SW'])
        rails = {row['net']: row for row in report['rails']}
        self.assertEqual(len(rails), 9)
        self.assertEqual(rails['PROTECTED_INPUT']['expected_voltage']['min'], 6.332)
        self.assertEqual(rails['PROTECTED_INPUT']['expected_voltage']['contextual_expectation']['min'], 7)
        self.assertEqual(rails['MONITORED_LOAD']['expected_voltage']['min'], 6.2715)
        self.assertAlmostEqual(7.02 - .6 - .5 * .156 - .01,
                               rails['PROTECTED_INPUT']['expected_voltage']['min'])
        self.assertAlmostEqual(6.332 - .5 * .101 - .01,
                               rails['MONITORED_LOAD']['expected_voltage']['min'])
        for name, maximum in (('RELAY1_RETURN', 2), ('RELAY2_RETURN', 2), ('SWITCH_RETURN', .02)):
            value = rails[name]['expected_voltage']
            self.assertEqual(value['max'], maximum)
            self.assertEqual(value['conditions_status'], 'NOT_RUN')
            self.assertTrue(value['prerequisites'])
        self.assertIn('BUCK_SW: UNKNOWN', render_bringup(report))
        self.assertTrue(all(row['result'] == 'NOT_RUN' for row in rails.values()))

    def test_g5_reference_uses_matching_circuit_and_combined_load_budget(self):
        old, new = read('g3', 'block-graph'), read('g5', 'block-graph')
        reference = lambda graph: next(row for row in graph['instances'] if row['id'] == 'reference')
        self.assertEqual(reference(old), reference(new))
        row = next(row for row in self.report('g5')['rails'] if row['net'] == 'VREF')
        self.assertEqual((row['expected_voltage']['min'], row['expected_voltage']['max']), (2.35, 2.65))
        self.assertEqual(row['expected_voltage']['conditions']['regulator_load_max']['value'], .0005)
        self.assertEqual(row['declared_reference_location']['pin'], '3')

    def test_g2_new_conditions_keep_electrical_dimensions(self):
        graph = read('g2', 'block-graph')
        row = next(row for row in graph['bringup']['rails'] if row['at'] == 'protection_D1.pin:1')
        row['expected_voltage']['conditions']['diode_drop_max']['unit'] = 'A'
        intent = expand(self.catalog, graph, read('g2', 'brief'), bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'REFUSED')
        self.assertTrue(intent['refusals'])
