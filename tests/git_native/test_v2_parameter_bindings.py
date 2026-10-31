"""Shared operating inputs cannot drift across bound consumers."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.parameter_bindings import parameters_for, validate_bindings
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class SharedParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_catalog = Catalog(ROOT, ROOT / 'schemas')

    def setUp(self):
        self.catalog = deepcopy(self.base_catalog)
        self.brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())
        self.value = {'value': 4700, 'unit': 'ohm', 'basis': 'ENGINEERING_DEFAULT',
                      'conditions': {}, 'note': 'Synthetic shared operating input.'}
        self.brief['parameter_bindings'] = [{'id': 'shared_limit', 'value': self.value,
            'endpoints': [{'function': 'input_protection', 'parameter': 'resistance'},
                          {'function': 'power_led', 'parameter': 'resistance'}]}]
        self.targets = []
        for instance in self.graph['instances']:
            if {'input_protection', 'power_led'} & set(instance['requirements']):
                block = self.catalog.records[instance['block']]
                block['parameters']['resistance'] = {'quantity': 'resistance', 'required': False}
                instance['parameters']['resistance'] = deepcopy(self.value)
                self.targets.append(instance)

    def result(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def test_single_authority_projects_and_checks_without_mutation(self):
        saved = deepcopy(self.brief)
        function = next(f for f in self.brief['functions'] if f['id'] == 'power_led')
        self.assertEqual(parameters_for(self.brief, function)['resistance'], self.value)
        self.assertEqual(self.brief, saved)
        self.assertEqual(assess_brief(self.catalog, self.brief), [])
        result = self.result()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        self.assertEqual(next(c for c in result['checks'] if c['id'] == 'parameter-binding:shared_limit')
                         ['result'], 'PASS')

    def test_each_consumer_value_condition_and_missing_input_refuse(self):
        for index in range(2):
            for mode in ('number', 'condition', 'missing'):
                self.setUp()
                target = self.targets[index]['parameters']
                if mode == 'number':
                    target['resistance']['value'] += 1
                elif mode == 'condition':
                    target['resistance']['conditions'] = {'TA': {'value': 80, 'unit': 'degC'}}
                else:
                    del target['resistance']
                with self.subTest(index=index, mode=mode):
                    result = self.result()
                    self.assertEqual(result['status'], 'REFUSED')
                    self.assertTrue(any(r['path'] == 'parameter_bindings.shared_limit'
                                        for r in result['refusals']), result['refusals'])

    def test_duplicate_local_definition_unknown_function_and_ambiguous_count_refuse(self):
        for mode in ('duplicate', 'unknown', 'count', 'endpoint', 'identity'):
            self.setUp()
            function = next(f for f in self.brief['functions'] if f['id'] == 'power_led')
            binding = self.brief['parameter_bindings'][0]
            if mode == 'duplicate':
                function['parameters']['resistance'] = deepcopy(self.value)
            elif mode == 'unknown':
                binding['endpoints'][0]['function'] = 'absent'
            elif mode == 'count':
                function['count'] = 2
            elif mode == 'endpoint':
                binding['endpoints'].append(deepcopy(binding['endpoints'][0]))
            else:
                self.brief['parameter_bindings'].append(deepcopy(binding))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_bindings(self.brief, self.catalog)

    def test_unknown_unit_unknown_quantity_and_nonfinite_refuse(self):
        for value in ({'status': 'UNKNOWN'}, {'value': float('inf'), 'unit': 'ohm'},
                      {'value': 2, 'unit': 'V'}, {'value': True, 'unit': 'ohm'}):
            self.setUp()
            self.brief['parameter_bindings'][0]['value'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_bindings(self.brief, self.catalog)

    def test_source_anchor_is_validated_and_retained_in_dependency_closure(self):
        anchor = {'source': 'source:ti-ina219', 'page': 3}
        self.value['evidence'] = anchor
        for instance in self.targets:
            instance['parameters']['resistance'] = deepcopy(self.value)
        result = self.result()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        self.assertIn(anchor, result['evidence'])
        self.assertIn(anchor['source'], result['dependencies'])
        self.value['evidence']['page'] = 9999
        self.assertEqual(self.result()['status'], 'REFUSED')

    def test_reconstructed_intent_rejects_deleted_binding_result(self):
        result = self.result()
        bundle = SimpleNamespace(catalog=self.catalog, briefs={'G1': self.brief}, commit='a' * 40)
        validate_expansion(bundle, result, self.graph)
        result['checks'] = [c for c in result['checks'] if c['id'] != 'parameter-binding:shared_limit']
        with self.assertRaises(ValueError):
            validate_expansion(bundle, result, self.graph)

    def test_screening_names_malformed_parameter_binding_once(self):
        self.brief['parameter_bindings'][0]['endpoints'][0]['function'] = 'absent'
        results = assess_brief(self.catalog, self.brief)
        self.assertEqual(len(results), 1, results)
        self.assertEqual(results[0]['path'], 'parameter_bindings')
        self.assertEqual(results[0]['code'], 'INVALID_REFERENCE')

    def test_no_binding_keeps_prior_intent_exactly(self):
        del self.brief['parameter_bindings']
        for instance in self.targets:
            del instance['parameters']['resistance']
            del self.catalog.records[instance['block']]['parameters']['resistance']
        actual = self.result()
        original = expand(self.base_catalog, self.graph, self.brief, bundle_commit='a' * 40)
        self.assertEqual(actual, original)


if __name__ == '__main__':
    unittest.main()
