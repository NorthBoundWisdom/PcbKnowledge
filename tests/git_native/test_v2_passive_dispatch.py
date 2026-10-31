"""Actual selected components and shared budgets reach passive check calculators."""
import unittest

from pcbknowledge.v2.calculators import calculate, evaluate_check, CalculationError
from pcbknowledge.v2.calculators_passive_paths import INPUT_UNITS
from tests.git_native.test_v2_effective_capacitance import fixture as capacitors
from tests.git_native.test_v2_passive_supply import fixture as supply
from tests.git_native.test_v2_four_consumer_budget import fixture as ledger


def quantities(name, values):
    return {key: {'min': low, 'max': high, 'unit': INPUT_UNITS[name][key],
                  'basis': 'ENGINEERING_DEFAULT', 'conditions': {}, 'note': 'Synthetic selected input.'}
            for key, (low, high) in values.items()}


def check(name, inputs, output, unit):
    return {'calculator': name, 'inputs': inputs,
            'require': {'output': output, 'operator': 'GE',
                        'limit': {'value': 0, 'unit': unit, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {}}}}


class PassiveDispatchTests(unittest.TestCase):
    def test_each_selected_capacitor_is_resolved(self):
        name = 'quad_parallel_capacitance'
        for index in range(1, 5):
            with self.subTest(index=index):
                inputs = quantities(name, capacitors(4))
                parts = {'C': {'parameters': {'capacitance': inputs[f'capacitance_{index}']}}}
                inputs[f'capacitance_{index}'] = {'component': 'C', 'parameter': 'capacitance'}
                contract = check(name, inputs, 'window_margin', 'F')
                self.assertEqual(evaluate_check(contract, {}, parts)['result'], 'PASS')
                parts['C']['parameters']['capacitance'].update(min=9e-9, max=11e-9)
                self.assertEqual(evaluate_check(contract, {}, parts)['result'], 'FAIL')

    def test_selected_fuse_limit_is_live(self):
        name = 'passive_supply_path'
        inputs = quantities(name, supply())
        parts = {'F': {'parameters': {'hold_current': inputs['current_limit']}}}
        inputs['current_limit'] = {'component': 'F', 'parameter': 'hold_current'}
        contract = check(name, inputs, 'current_margin', 'A')
        self.assertEqual(evaluate_check(contract, {}, parts)['result'], 'PASS')
        parts['F']['parameters']['hold_current'].update(min=.05, max=.05)
        self.assertEqual(evaluate_check(contract, {}, parts)['result'], 'FAIL')

    def test_each_shared_consumer_budget_is_live(self):
        name = 'four_preload_four_consumer_budget'
        for index in range(1, 5):
            inputs = quantities(name, ledger())
            parameters = {'allocation': inputs[f'consumer_{index}']}
            inputs[f'consumer_{index}'] = {'parameter': 'allocation'}
            contract = check(name, inputs, 'budget_margin', 'A')
            self.assertEqual(evaluate_check(contract, parameters)['result'], 'PASS')
            parameters['allocation'].update(min=0, max=.1)
            self.assertEqual(evaluate_check(contract, parameters)['result'], 'FAIL')

    def test_unknown_wrong_units_and_nonfinite_refuse(self):
        name = 'passive_supply_path'
        for invalid in ({'status': 'UNKNOWN'}, {'value': 1, 'unit': 'V'},
                        {'value': float('nan'), 'unit': 'A'}):
            inputs = quantities(name, supply())
            inputs['current'] = invalid
            with self.assertRaises(CalculationError):
                calculate(name, inputs)


if __name__ == '__main__':
    unittest.main()
