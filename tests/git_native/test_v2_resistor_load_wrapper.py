"""Production wrapper resolves both selected physical resistor quantities."""
from copy import deepcopy
import unittest
from pcbknowledge.v2.calculators import calculate, evaluate_check, CalculationError


def q(value, unit):
    return {'basis': 'ENGINEERING_DEFAULT', 'value': value, 'unit': unit, 'conditions': {}}


def check():
    return {'calculator': 'dual_resistor_load', 'inputs': {
        'supply': q(3.43, 'V'), 'allocation': {'parameter': 'budget'},
        'resistance_1': {'component': 'R1', 'parameter': 'resistance'},
        'resistance_2': {'component': 'R2', 'parameter': 'resistance'},
        'tcr_magnitude': q(.0001, '1/degC'), 'temperature_excursion': q(15, 'degC')},
        'require': {'output': 'allocation_margin', 'operator': 'GE', 'limit': q(0, 'A')}}


class WrapperTests(unittest.TestCase):
    def test_both_actual_resistors_and_shared_allocation_bind(self):
        parts = {ref: {'parameters': {'resistance': q(4700, 'ohm')}} for ref in ('R1', 'R2')}
        params = {'budget': q(.0015, 'A')}
        self.assertEqual(evaluate_check(check(), params, parts)['result'], 'PASS')
        for ref in parts:
            changed = deepcopy(parts)
            changed[ref]['parameters']['resistance'] = q(2200, 'ohm')
            self.assertEqual(evaluate_check(check(), params, changed)['result'], 'FAIL')
        self.assertEqual(evaluate_check(check(), {'budget': q(.001, 'A')}, parts)['result'], 'FAIL')
        self.assertEqual(evaluate_check(check(), params, {'R1': parts['R1']})['result'], 'REFUSED')

    def test_units_negative_nonfinite_extra_and_missing_refuse(self):
        values = {'supply': q(3.43, 'V'), 'allocation': q(.0015, 'A'),
                  'resistance_1': q(4700, 'ohm'), 'resistance_2': q(4700, 'ohm'),
                  'tcr_magnitude': q(.0001, '1/degC'), 'temperature_excursion': q(15, 'degC')}
        for key, value in [('supply', q(3.43, 'A')), ('allocation', q(-1, 'A')),
                           ('resistance_1', q(float('inf'), 'ohm')),
                           ('tcr_magnitude', q(-.1, '1/degC'))]:
            with self.assertRaises(CalculationError):
                calculate('dual_resistor_load', {**values, key: value})
        with self.assertRaises(CalculationError):
            calculate('single_resistor_load', values)
        del values['resistance_2']
        with self.assertRaises(CalculationError):
            calculate('dual_resistor_load', values)
