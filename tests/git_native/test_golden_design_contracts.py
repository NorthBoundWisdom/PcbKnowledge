"""Stage 1 synthetic briefs and planned interfaces, without catalog expansion."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from tests.git_native.test_v2_record_contracts import validate


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / 'evals/golden-designs'


def read(name):
    return json.loads((GOLDEN / name).read_text(encoding='utf-8'))


class GoldenDesignContractTests(unittest.TestCase):
    def setUp(self):
        self.brief = read('g1.brief.json')
        self.graph = read('g1.block-graph.json')

    def check_graph(self, graph):
        """Check the reference answer's declared interface and requirement closure."""
        validate(graph, 'block-graph.schema.json')
        self.assertEqual(graph['brief'], self.brief['id'])
        instances = {item['id']: item for item in graph['instances']}
        self.assertEqual(len(instances), len(graph['instances']))
        requirement_ids = {item['id'] for group in ('functions', 'interfaces', 'constraints')
                           for item in self.brief[group]}
        requirement_ids.update(item['id'] for item in self.brief['mechanical']['mounting'])
        used_requirements = set(graph['requirements'])
        ports = set()
        for item in instances.values():
            self.assertTrue(set(item['requirements']) <= requirement_ids)
            used_requirements.update(item['requirements'])
            names = {port['name'] for port in item['ports']}
            self.assertEqual(len(names), len(item['ports']))
            ports.update((item['id'], name) for name in names)
        self.assertEqual(used_requirements, requirement_ids)
        self.assertEqual(len({net['net'] for net in graph['connections']}), len(graph['connections']))
        connected = []
        for net in graph['connections']:
            for endpoint in net['endpoints']:
                identity = (endpoint['instance'], endpoint['port'])
                self.assertIn(identity, ports)
                connected.append(identity)
        self.assertEqual(len(connected), len(set(connected)))
        self.assertEqual(set(connected), ports)

    def test_all_three_briefs_and_reference_graph_validate(self):
        for name in ('g1', 'g2', 'g3'):
            brief = read(name + '.brief.json')
            validate(brief, 'design-brief.schema.json')
            self.assertEqual(brief['origin'], 'SYNTHETIC')
            self.assertEqual(brief['status'], 'DRAFT')
            self.assertEqual([a['level'] for a in brief['acceptance']],
                             ['A1', 'A2', 'A3', 'A4', 'A5', 'A6'])
            self.assertEqual({a['status'] for a in brief['acceptance']}, {'NOT_RUN'})
        self.check_graph(self.graph)

    def test_g1_required_functions_and_owner_defaults(self):
        functions = {item['id']: item for item in self.brief['functions']}
        self.assertEqual(functions['mcu']['part_preferences'], ['STM32F103C8T6'])
        self.assertEqual(functions['user_leds']['count'], 2)
        self.assertEqual(functions['user_button']['count'], 1)
        self.assertEqual(functions['power_monitor']['part_preferences'], ['INA219'])
        self.assertEqual(functions['eeprom']['part_preferences'], ['24LC256'])
        self.assertEqual(self.brief['power']['sources'][0]['voltage']['value'], 5)
        self.assertEqual(self.brief['power']['rails'][0]['voltage']['value'], 3.3)
        self.assertEqual(self.brief['mechanical']['length']['max'], 50)
        self.assertEqual(self.brief['mechanical']['width']['max'], 50)
        self.assertEqual(self.brief['manufacturing']['layers'], 2)
        self.assertEqual(self.brief['manufacturing']['thickness']['value'], 1.6)
        self.assertEqual(set(self.brief['mechanical']['edge_interfaces']),
                         {item['id'] for item in self.brief['interfaces']})

    def test_reference_graph_is_planning_not_catalog_closure(self):
        self.assertEqual(self.graph['interface_status'], 'PLANNED_BLOCK_CONTRACTS')
        self.assertEqual(self.graph['status'], 'DRAFT')
        counts = {}
        for instance in self.graph['instances']:
            counts[instance['block']] = counts.get(instance['block'], 0) + 1
        self.assertEqual(counts['block:led-indicator'], 3)
        self.assertEqual(counts['block:mounting-holes'], 1)
        self.assertEqual(counts['block:mcu-core'], 1)
        self.assertEqual(counts['block:ina219-monitor'], 1)
        self.assertEqual(counts['block:i2c-eeprom'], 1)
        unknowns = [value for instance in self.graph['instances']
                    for value in instance['parameters'].values()
                    if value.get('status') == 'UNKNOWN']
        self.assertEqual(unknowns, [])

    def test_brief_rejects_raw_quantities_authority_upgrade_and_unknown_fields(self):
        mutations = [lambda d: d.update(status='AGENT_VERIFIED'),
                     lambda d: d.update(extra=True),
                     lambda d: d['power']['sources'][0].update(voltage=5),
                     lambda d: d['mechanical']['length'].update(unit='cm'),
                     lambda d: d['power']['sources'][0]['voltage'].update(unit='A'),
                     lambda d: d['acceptance'][0].update(status='PASS'),
                     lambda d: d['power']['sources'][0]['current_budget'].pop('note')]
        for mutation in mutations:
            bad = copy.deepcopy(self.brief)
            mutation(bad)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(bad, 'design-brief.schema.json')

    def test_graph_rejects_untyped_parameters_and_unsupported_port_kinds(self):
        for mutation in (lambda d: d.update(status='READY'),
                         lambda d: d['instances'][0]['parameters'].update(output_voltage=5),
                         lambda d: d['instances'][0]['parameters'].update(invented_parameter=1),
                         lambda d: d['instances'][0]['ports'][0].update(type='MAGIC'),
                         lambda d: d['connections'][0]['endpoints'][0].update(pin='1')):
            bad = copy.deepcopy(self.graph)
            mutation(bad)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(bad, 'block-graph.schema.json')

    def test_reference_answer_checks_detect_broken_connections_and_coverage(self):
        mutations = [lambda d: d['connections'][0]['endpoints'][0].update(instance='missing'),
                     lambda d: d['connections'][0]['endpoints'][0].update(port='missing'),
                     lambda d: d['connections'].append(copy.deepcopy(d['connections'][0])),
                     lambda d: d['connections'].pop(0),
                     lambda d: d['instances'].append(copy.deepcopy(d['instances'][0])),
                     lambda d: d['instances'][0]['requirements'].append('missing-requirement'),
                     lambda d: d.update(requirements=['usb_sink'])]
        for mutation in mutations:
            bad = copy.deepcopy(self.graph)
            mutation(bad)
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check_graph(bad)

    def test_every_required_g1_design_input_is_concrete(self):
        def check(value):
            if isinstance(value, dict):
                self.assertNotEqual(value.get('status'), 'UNKNOWN')
                for child in value.values():check(child)
            elif isinstance(value, list):
                for child in value:check(child)
        check(self.brief);check(self.graph)
        self.assertEqual(self.brief['power']['sources'][0]['current_budget']['value'], .5)
        self.assertEqual(self.brief['power']['rails'][0]['current_budget']['value'], .15)
        self.assertEqual(self.brief['mechanical']['height']['status'], 'UNCONSTRAINED')
        parameters = {i['id']:i['parameters'] for i in self.graph['instances']}
        self.assertEqual(parameters['mcu']['clock_frequency']['value'], 8000000)
        self.assertEqual(parameters['i2c']['bus_frequency']['value'], 100000)
        self.assertEqual(parameters['i2c']['capacitance']['value'], 1e-10)
        self.assertEqual(parameters['mounting']['drill']['value'], 3.2)


if __name__ == '__main__':
    unittest.main()
