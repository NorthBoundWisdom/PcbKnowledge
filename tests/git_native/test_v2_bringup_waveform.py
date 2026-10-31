"""G2 waveform plans bind real physical pins and catalog limits, not observations."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.bringup import make_bringup, render_bringup
from pcbknowledge.v2.bringup_contract import validate_bringup
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand

ROOT = Path(__file__).resolve().parents[2]
PART = 'part:ti-tps5430dda'


def read(kind):
    return json.loads((ROOT / f'evals/golden-designs/g2.{kind}.json').read_text())


def waveform_row(graph):
    return next(row for row in graph['bringup']['rails'] if 'waveform' in row)


class WaveformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')

    def expanded(self, graph=None, catalog=None):
        graph = read('block-graph') if graph is None else graph
        catalog = self.catalog if catalog is None else catalog
        brief = read('brief')
        intent = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
        return intent, graph, brief, catalog

    def test_real_g2_plan_complete_all_observations_not_run_and_exact_terminals(self):
        args = self.expanded()
        before = deepcopy(args[:3])
        report = make_bringup(*args)
        self.assertEqual(args[:3], before)
        self.assertEqual(report['range_coverage'], 'COMPLETE')
        self.assertEqual(report['unresolved_rail_ranges'], [])
        self.assertEqual(report['a6'], 'NOT_RUN')
        self.assertEqual(report['prerequisites_status'], 'NOT_RUN')
        self.assertEqual(len(report['rails']), 9)
        for group in ('rails', 'programming', 'functional_tests'):
            self.assertTrue(all(row['result'] == 'NOT_RUN' for row in report[group]))
        rail = next(row for row in report['rails'] if row['net'] == 'BUCK_SW')
        self.assertNotIn('expected_voltage', rail)
        self.assertEqual(rail['expected_waveform']['acceptance_type'], 'WAVEFORM_PROTOCOL')
        self.assertEqual(rail['expected_waveform']['conditions_status'], 'NOT_RUN')
        for field, pin, net in (('test', '8', 'BUCK_SW'), ('reference', '6', 'GND'),
                                ('input', '7', 'MONITORED_LOAD')):
            location = rail['declared_' + field + '_location']
            self.assertEqual((location['ref'], location['pin']), ('buck_U1', pin))
            actual_net = next(n['name'] for n in args[0]['nets']
                              if {'ref': 'buck_U1', 'pin': pin} in n['pins'])
            self.assertEqual(actual_net, net)

    def test_source_limits_and_all_protocol_fields_are_visible_in_render(self):
        args = self.expanded()
        report = make_bringup(*args)
        rail = next(row for row in report['rails'] if row['net'] == 'BUCK_SW')
        expected = rail['expected_waveform']
        parameters = self.catalog.get(PART, 'part')['parameters']
        for key, value in expected['source_limits'].items():
            self.assertEqual(value, parameters[key])
            self.assertEqual(value['evidence']['source'], 'source:ti-tps5430')
        rendered = render_bringup(report, schemas=self.catalog.schemas)
        self.assertIn('WAVEFORM_PROTOCOL', rendered)
        self.assertIn('not measured compliance', rendered)
        self.assertNotIn('- [x]', rendered)
        for key, value in expected['protocol'].items():
            self.assertIn(key + ':', rendered)
            if isinstance(value, dict):
                for bound in ('min', 'max'):
                    if bound in value:
                        self.assertIn(f'{bound}={value[bound]}', rendered)
                self.assertIn(value['unit'], rendered)
        self.assertIn('switch_node_negative_transient_duration_limit', rendered)

    def test_removing_waveform_keeps_switch_node_unknown_in_final_report(self):
        graph = read('block-graph')
        graph['bringup']['rails'].remove(waveform_row(graph))
        report = make_bringup(*self.expanded(graph))
        self.assertEqual(report['range_coverage'], 'UNKNOWN')
        self.assertEqual(report['unresolved_rail_ranges'], ['BUCK_SW'])
        self.assertIn('BUCK_SW: UNKNOWN', render_bringup(report, schemas=self.catalog.schemas))

    def assert_graph_refused(self, graph):
        intent = expand(self.catalog, graph, read('brief'), bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'REFUSED', intent)
        self.assertTrue(intent['refusals'])

    def test_every_required_protocol_field_is_required(self):
        for key in waveform_row(read('block-graph'))['waveform']:
            graph = read('block-graph')
            del waveform_row(graph)['waveform'][key]
            with self.subTest(key=key):
                self.assert_graph_refused(graph)

    def test_wrong_units_unsafe_source_bounds_and_incomplete_acquisition_fail(self):
        changes = [('bandwidth', 'unit', 's'), ('negative_excursion_duration', 'max', 1e-8),
                   ('negative_peak', 'min', -1.3), ('low_level', 'min', -.7),
                   ('positive_peak', 'max', 41), ('timing_uncertainty', 'max', 2e-9),
                   ('sample_rate', 'min', 1e6), ('input_voltage', 'min', 4),
                   ('frequency', 'max', 700e3), ('record_duration', 'min', 1e-8),
                   ('probe_range', 'max', 1), ('low_voltage_uncertainty', 'max', -1)]
        for field, key, value in changes:
            graph = read('block-graph')
            waveform_row(graph)['waveform'][field][key] = value
            with self.subTest(field=field, key=key):
                self.assert_graph_refused(graph)

    def test_inadequate_bandwidth_and_inconsistent_peak_envelopes_cannot_complete(self):
        changes = (
            {'bandwidth': {'min': 1}, 'sample_rate': {'min': 5}},
            {'positive_peak': {'max': 1}},
            {'positive_peak_offset': {'max': .01}},
            {'negative_excursion_duration': {'max': 1e-10}, 'timing_uncertainty': {'max': 9.9e-9}},
        )
        for change in changes:
            graph = read('block-graph')
            protocol = waveform_row(graph)['waveform']
            for field, bounds in change.items():
                protocol[field].update(bounds)
            with self.subTest(change=change):
                self.assert_graph_refused(graph)
                intent, _, brief, catalog = self.expanded()
                waveform_row(intent)['waveform'] = deepcopy(protocol)
                with self.assertRaises(ValueError):
                    make_bringup(intent, graph, brief, catalog)

    def test_alias_wrong_reference_input_and_dual_dc_declaration_fail(self):
        for mode in ('alias', 'ground', 'input', 'dc', 'part', 'no_catalog'):
            intent, graph, _, _ = self.expanded()
            row = waveform_row(intent)
            if mode == 'alias':
                row['at'] = 'buck_U1.pin:PH'
            elif mode == 'ground':
                row['reference_at'] = 'buck_U1.pin:7'
            elif mode == 'input':
                row['waveform']['input_at'] = 'buck_U1.pin:8'
            elif mode == 'dc':
                row['expected_voltage'] = deepcopy(graph['bringup']['rails'][0]['expected_voltage'])
            elif mode == 'part':
                next(c for c in intent['components'] if c['ref'] == 'buck_U1')['part'] = 'part:ti-tps562208ddcr'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_bringup(intent, None if mode == 'no_catalog' else self.catalog)

    def test_catalog_source_change_projects_and_stricter_limit_refuses(self):
        catalog = deepcopy(self.catalog)
        parameter = catalog.get(PART, 'part')['parameters']['switch_node_absolute_voltage']
        parameter['max'] = 39
        report = make_bringup(*self.expanded(catalog=catalog))
        waveform = next(r for r in report['rails'] if r['net'] == 'BUCK_SW')['expected_waveform']
        self.assertEqual(waveform['source_limits']['switch_node_absolute_voltage']['max'], 39)
        parameter['max'] = 12
        intent = expand(catalog, read('block-graph'), read('brief'), bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'REFUSED')
        self.assertTrue(intent['refusals'])
        self.assertEqual(self.catalog.get(PART, 'part')['parameters']['switch_node_absolute_voltage']['max'], 40)
