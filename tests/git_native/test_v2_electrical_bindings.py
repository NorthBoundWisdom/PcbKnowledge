"""G3 functional net relations refuse electrically plausible but incorrectly wired graphs."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class ElectricalBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')

    def setUp(self):
        self.brief = read_json((ROOT / 'evals/golden-designs/g3.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g3.block-graph.json').read_bytes())

    def expand(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def move(self, instance, port, target):
        endpoint = {'instance': instance, 'port': port}
        for connection in self.graph['connections']:
            connection['endpoints'] = [item for item in connection['endpoints'] if item != endpoint]
        next(item for item in self.graph['connections'] if item['net'] == target)['endpoints'].append(endpoint)

    def test_g3_requires_nonempty_functional_groups_and_reference_passes(self):
        self.assertTrue(self.brief['electrical_bindings'])
        self.assertEqual(len(self.brief['electrical_bindings']), 6)
        result = self.expand()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        checks = [check for check in result['checks'] if check['id'].startswith('electrical-binding:')]
        self.assertEqual(len(checks), len(self.brief['electrical_bindings']))
        self.assertTrue(all(check['result'] == 'PASS' for check in checks))

    def test_five_previously_false_a2_counterexamples_refuse(self):
        cases = [('adc', 'VDD', 'NTC'), ('reference', 'VIN', 'VREF'),
                 ('photodiode', 'VREF', 'ANALOG_3V3'), ('adc', 'AIN_REF', 'INPUT_3V3'),
                 ('photodiode', 'VDD', 'VREF')]
        for instance, port, target in cases:
            self.setUp()
            self.move(instance, port, target)
            result = self.expand()
            with self.subTest(instance=instance, port=port, target=target):
                self.assertEqual(result['status'], 'REFUSED')
                self.assertTrue(any(item['path'].startswith('electrical_bindings.')
                                    for item in result['refusals']), result['refusals'])

    def test_renamed_graph_nets_and_instance_ids_do_not_change_bindings(self):
        replacements = {instance['id']: 'renamed_' + instance['id'] for instance in self.graph['instances']}
        for instance in self.graph['instances']:
            instance['id'] = replacements[instance['id']]
        for index, connection in enumerate(self.graph['connections']):
            connection['net'] = 'RENAMED_' + str(index)
            for endpoint in connection['endpoints']:
                endpoint['instance'] = replacements[endpoint['instance']]
        for field in ('pin_configurations', 'port_requirements'):
            for item in self.graph.get(field, []):
                item['instance'] = replacements[item['instance']]
        for rail in self.graph.get('bringup', {}).get('rails', []):
            for key in ('at', 'reference_at'):
                if key not in rail:
                    continue
                matches = [old for old in replacements if rail[key].startswith(old + '_')]
                self.assertEqual(len(matches), 1)
                old = matches[0]
                rail[key] = replacements[old] + rail[key][len(old):]
        result = self.expand()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])

    def test_distinct_functional_groups_cannot_be_merged(self):
        reference = next(item for item in self.graph['connections'] if item['net'] == 'VREF')
        supply = next(item for item in self.graph['connections'] if item['net'] == 'ANALOG_3V3')
        supply['endpoints'].extend(reference['endpoints'])
        self.graph['connections'].remove(reference)
        result = self.expand()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any('Distinct functional electrical bindings are shorted' in item['reason']
                            for item in result['refusals']), result['refusals'])

    def test_missing_unknown_ambiguous_and_duplicate_binding_references_refuse(self):
        binding = self.brief['electrical_bindings'][0]
        endpoint = binding['endpoints'][0]
        for replacement in ({**endpoint, 'function': 'missing'}, {**endpoint, 'port': 'MISSING'}):
            self.setUp()
            self.brief['electrical_bindings'][0]['endpoints'][0] = replacement
            self.assertEqual(self.expand()['status'], 'REFUSED')
            self.assertTrue(assess_brief(self.catalog, self.brief))
        self.setUp()
        function_id = self.brief['electrical_bindings'][0]['endpoints'][0]['function']
        next(item for item in self.brief['functions'] if item['id'] == function_id)['count'] = 2
        self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        self.brief['electrical_bindings'].append(deepcopy(self.brief['electrical_bindings'][0]))
        self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        self.brief['electrical_bindings'][1]['endpoints'].append(
            deepcopy(self.brief['electrical_bindings'][0]['endpoints'][0]))
        self.assertEqual(self.expand()['status'], 'REFUSED')

    def test_malformed_brief_and_graph_override_cannot_evade_unchanged_brief(self):
        for malformed in ([], None, [{'id': 'x', 'endpoints': []}], [{'endpoints': []}]):
            self.setUp()
            self.brief['electrical_bindings'] = malformed
            self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        self.graph['electrical_bindings'] = []
        self.assertEqual(self.expand()['status'], 'REFUSED')

    def test_reconstruction_rejects_forged_pass_and_rewired_intent(self):
        intent = self.expand()
        bundle = SimpleNamespace(catalog=self.catalog, briefs={'G3': self.brief}, commit='a' * 40)
        validate_expansion(bundle, intent, self.graph)
        tampered = deepcopy(intent)
        tampered['checks'] = [check for check in tampered['checks']
                              if not check['id'].startswith('electrical-binding:')]
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            validate_expansion(bundle, tampered, self.graph)
        tampered = deepcopy(intent)
        supply = next(net for net in tampered['nets'] if net['name'] == 'ANALOG_3V3')
        signal = next(net for net in tampered['nets'] if net['name'] == 'NTC')
        pin = next(pin for pin in supply['pins'] if pin['ref'] == 'adc_U1')
        supply['pins'].remove(pin)
        signal['pins'].append(pin)
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            validate_expansion(bundle, tampered, self.graph)
