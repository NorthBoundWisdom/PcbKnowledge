"""Parameter limits resolve from block inputs and invalidate stale receipts."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import unittest

from pcbknowledge.v2.calculators import evaluate_check
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.schema import SCHEMA_DIR

ROOT = Path(__file__).resolve().parents[2]


def q(value, unit):
    return {'value': value, 'unit': unit, 'basis': 'ENGINEERING_DEFAULT',
            'conditions': {}, 'note': 'Synthetic limit test.'}


def check():
    return {
        'calculator': 'led_resistor',
        'inputs': {'supply': q(3.3, 'V'), 'forward_voltage': q(2, 'V'), 'resistance': q(1000, 'ohm')},
        'require': {'output': 'current', 'operator': 'LE', 'limit': {'parameter': 'current_limit'}},
    }


class ParameterLimitTests(unittest.TestCase):
    def test_live_limit_mutation_changes_result(self):
        self.assertEqual(evaluate_check(check(), {'current_limit': q(.002, 'A')})['result'], 'PASS')
        self.assertEqual(evaluate_check(check(), {'current_limit': q(.001, 'A')})['result'], 'FAIL')

    def test_missing_unknown_wrong_unit_nonfinite_refuse(self):
        for parameters in ({}, {'current_limit': {'status': 'UNKNOWN'}},
                           {'current_limit': q(.002, 'V')}, {'current_limit': q(float('nan'), 'A')}):
            self.assertEqual(evaluate_check(check(), parameters)['result'], 'REFUSED')

    def test_ge_operator_and_literal_compatibility(self):
        changed = check()
        changed['require']['operator'] = 'GE'
        self.assertEqual(evaluate_check(changed, {'current_limit': q(.001, 'A')})['result'], 'PASS')
        changed['require']['limit'] = q(.001, 'A')
        self.assertEqual(evaluate_check(changed, {})['result'], 'PASS')

    def test_shape_and_dangling_parameter_rejected_by_catalog(self):
        catalog = Catalog(ROOT, SCHEMA_DIR)
        block = deepcopy(catalog.get('block:led-indicator'))
        block['checks'][0]['require']['limit'] = {'parameter': 'undeclared'}
        with self.assertRaisesRegex(ValueError, 'Dangling calculator limit'):
            catalog._block(block)
        for bad in ({'parameter': 'current_limit', 'extra': 1},
                    {'component': 'R1', 'parameter': 'resistance'}, {'parameter': ''}):
            block['checks'][0]['require']['limit'] = bad
            with self.assertRaises(ValueError):
                catalog.structure(block, 'block.schema.json')

    def test_reconstructed_intent_rejects_changed_limit(self):
        catalog = Catalog(ROOT, SCHEMA_DIR)
        block = catalog.get('block:led-indicator')
        block['parameters']['current_limit'] = {'quantity': 'current', 'required': True}
        block['checks'][0]['require']['limit'] = {'parameter': 'current_limit'}
        graph = json.loads((ROOT/'evals/golden-designs/g1.block-graph.json').read_text(encoding='utf-8'))
        brief = json.loads((ROOT/'evals/golden-designs/g1.brief.json').read_text(encoding='utf-8'))
        affected = [item for item in graph['instances'] if item['block'] == block['id']]
        for item in affected:
            item['parameters']['current_limit'] = q(.1, 'A')
        intent = expand(catalog, graph, brief, bundle_commit='a'*40)
        self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
        bundle = SimpleNamespace(catalog=catalog, briefs={brief['id']: brief}, commit='a'*40)
        validate_expansion(bundle, intent, graph)
        affected[0]['parameters']['current_limit'] = q(1e-8, 'A')
        self.assertEqual(expand(catalog, graph, brief, bundle_commit='a'*40)['status'], 'REFUSED')
        with self.assertRaises(ValueError):
            validate_expansion(bundle, intent, graph)


if __name__ == '__main__':
    unittest.main()
