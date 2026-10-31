"""Bring-up projections use exact synthetic bindings, never rail-name heuristics."""
from copy import deepcopy
import unittest

from pcbknowledge.v2.bringup import make_bringup, render_bringup


class Catalog:
    def __init__(self):
        self.records = {
            'part:reg': {'id': 'part:reg', 'pins': [{'name': 'OUT', 'number': '7', 'type': 'POWER_OUT'}],
                         'parameters': {'output_voltage': {'unit': 'V', 'value': 2.5, 'min': 2.4, 'max': 2.6,
                                                          'basis': 'DATASHEET', 'evidence': {'page': 3}}}},
            'part:debug': {'id': 'part:debug', 'pins': [{'name': 'CLK', 'number': '2', 'type': 'OUTPUT'}]},
            'block:reg': {'id': 'block:reg', 'category': 'power.linear',
                          'ports': [{'name': 'V', 'kind': 'POWER_OUT'}],
                          'nets': [{'connect': ['port:V', 'U.pin:OUT']}]},
            'block:debug': {'id': 'block:debug', 'category': 'digital.debug',
                            'ports': [{'name': 'CLOCK', 'kind': 'OUTPUT'}],
                            'nets': [{'connect': ['port:CLOCK', 'J.pin:2']}]}}

    def get(self, identity, kind):
        return self.records[identity]


def inputs():
    intent = {'status': 'EXPANDED', 'brief_id': 'B', 'bundle_commit': 'abc',
              'components': [{'ref': 'x_U', 'part': 'part:reg'}, {'ref': 'y_J', 'part': 'part:debug'}],
              'nets': [{'name': 'renamed_supply', 'class': 'POWER', 'pins': [{'ref': 'x_U', 'pin': '7'}]},
                       {'name': 'clock', 'class': 'SIGNAL', 'pins': [{'ref': 'y_J', 'pin': '2'}]}]}
    graph = {'brief': 'B', 'instances': [
        {'id': 'x', 'block': 'block:reg', 'requirements': ['power'],
         'parameters': {'output_voltage': {'unit': 'V', 'value': 2.5, 'basis': 'ENGINEERING_DEFAULT'}}},
        {'id': 'y', 'block': 'block:debug', 'requirements': ['debug'], 'parameters': {}}]}
    brief = {'id': 'B', 'functions': [{'id': 'debug', 'description': 'Read identity', 'count': 1,
                                     'requirements': ['Programming link works'], 'parameters': {}}]}
    return intent, graph, brief, Catalog()


class BringupTests(unittest.TestCase):
    def test_source_range_exact_pinout_requirements_and_immutable_inputs(self):
        args = inputs()
        before = deepcopy(args[:3]), deepcopy(args[3].records)
        report = make_bringup(*args)
        self.assertEqual(report['range_coverage'], 'COMPLETE')
        self.assertEqual(report['rails'][0]['expected_voltage']['min'], 2.4)
        self.assertEqual(report['programming'][0]['pinout'][0]['pin'], '2')
        self.assertEqual(report['programming'][0]['pinout'][0]['signal'], 'CLOCK')
        self.assertEqual(report['functional_tests'][0]['result'], 'NOT_RUN')
        self.assertEqual(before, (args[:3], args[3].records))

    def test_nominal_does_not_invent_tolerance_or_propagate_to_other_rails(self):
        intent, graph, brief, catalog = inputs()
        catalog.records['part:reg']['parameters']['output_voltage'] = {'unit': 'V', 'value': 2.5}
        intent['nets'].append({'name': 'AFTER_UNKNOWN_ELEMENT_2V5', 'class': 'POWER', 'pins': []})
        report = make_bringup(intent, graph, brief, catalog)
        self.assertEqual(set(report['unresolved_rail_ranges']), {'renamed_supply', 'AFTER_UNKNOWN_ELEMENT_2V5'})
        self.assertTrue(all(row['expected_voltage']['status'] == 'UNKNOWN' for row in report['rails']))

    def test_conflicting_nominal_and_ambiguous_output_do_not_produce_pass(self):
        intent, graph, brief, catalog = inputs()
        graph['instances'][0]['parameters']['output_voltage']['value'] = 5
        report = make_bringup(intent, graph, brief, catalog)
        self.assertIn('Conflicting', report['rails'][0]['expected_voltage']['reason'])

    def test_brief_bound_function_range_is_explicit_engineering_not_guessed(self):
        intent, graph, brief, catalog = inputs()
        catalog.records['part:reg']['parameters'] = {}
        brief['power'] = {'sources': [], 'rails': [{'id': 'supply', 'function': 'power',
            'voltage': {'unit': 'V', 'min': 2.3, 'max': 2.7, 'basis': 'ENGINEERING_DEFAULT'}}]}
        report = make_bringup(intent, graph, brief, catalog)
        self.assertEqual(report['rails'][0]['expected_voltage']['max'], 2.7)
        self.assertEqual(report['range_coverage'], 'COMPLETE')

    def test_coordinates_are_real_pad_locations_and_wrong_input_identity_fails(self):
        args = inputs()
        board = {'footprints': {'x_U': {'pads': {'7': [{'at': [4, 5]}]}}}}
        report = make_bringup(*args, board=board)
        self.assertEqual(report['rails'][0]['test_locations'][0]['pad_centers_mm'], [[4, 5]])
        args[0]['brief_id'] = 'wrong'
        with self.assertRaises(ValueError):
            make_bringup(*args)

    def test_render_preserves_unknown_and_unchecked_observations(self):
        args = inputs()
        args[3].records['part:reg']['parameters'] = {}
        text = render_bringup(make_bringup(*args))
        self.assertIn('UNKNOWN: No explicit minimum', text)
        self.assertIn('- [ ] debug: Read identity', text)
        self.assertNotIn('- [x]', text)
