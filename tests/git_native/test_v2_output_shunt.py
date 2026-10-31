"""The sense range alone does not prove a commanded output is attainable."""
from copy import deepcopy
import unittest

from pcbknowledge.v2.calculators import calculate, evaluate_check, CalculationError


def q(value, unit):
    return {'basis': 'ENGINEERING_DEFAULT', 'value': value, 'unit': unit,
            'conditions': {}, 'note': 'Synthetic operating input.'}


def interval(low, high, unit):
    result = q(0, unit)
    del result['value']
    return {**result, 'min': low, 'max': high}


def inputs():
    return {
        'external_current': interval(0, .5, 'A'), 'monitored_voltage': interval(2.49, 6.1, 'V'),
        'bias_current': q(50e-6, 'A'), 'bus_input_resistance': q(160000, 'ohm'),
        'attainable_voltage': interval(2.49, 6.06, 'V'), 'required_voltage': interval(2.5, 6, 'V'),
        'resistance': interval(.099, .101, 'ohm'), 'tcr_magnitude': q(600e-6, '1/degC'),
        'temperature_excursion': q(15, 'degC'), 'sense_limit': q(.08, 'V'), 'power_rating': q(.25, 'W'),
    }


class OutputShuntTests(unittest.TestCase):
    def test_default_realistic_range_includes_all_downstream_loads(self):
        result = calculate('output_shunt_budget', inputs())
        self.assertAlmostEqual(result['shunt_current']['max'], .500088125)
        self.assertAlmostEqual(result['shunt_current']['min'], -50e-6)
        self.assertGreater(result['required_pre_shunt_voltage']['max'], 6.05096)
        self.assertLess(result['required_pre_shunt_voltage']['min'], 2.5)
        for key in ('target_margin', 'sense_margin', 'power_margin'):
            self.assertGreater(result[key]['min'], 0)

    def test_point15ohm_passes_sense_but_fails_target(self):
        old = calculate('shunt_resistor', {
            'current': q(.5, 'A'), 'resistance': q(.15, 'ohm'),
            'sense_limit': q(.08, 'V'), 'power_rating': q(.25, 'W')})
        self.assertGreater(old['voltage_margin']['min'], 0)
        new = calculate('output_shunt_budget', {**inputs(), 'resistance': q(.15, 'ohm')})
        self.assertGreater(new['sense_margin']['min'], 0)
        self.assertLess(new['target_margin']['min'], 0)

    def test_minimum_setpoint_needs_signed_backfeed_allowance(self):
        changed = {**inputs(), 'attainable_voltage': interval(2.5, 6.06, 'V')}
        self.assertLess(calculate('output_shunt_budget', changed)['target_margin']['min'], 0)

    def test_actual_selected_shunt_reference_mutation(self):
        case = inputs()
        case['resistance'] = {'component': 'R1', 'parameter': 'resistance'}
        check = {'calculator': 'output_shunt_budget', 'inputs': case,
                 'require': {'output': 'target_margin', 'operator': 'GE', 'limit': q(0, 'V')}}
        components = {'R1': {'parameters': {'resistance': interval(.099, .101, 'ohm')}}}
        self.assertEqual(evaluate_check(check, {}, components)['result'], 'PASS')
        components['R1']['parameters']['resistance'] = q(.15, 'ohm')
        self.assertEqual(evaluate_check(check, {}, components)['result'], 'FAIL')

    def test_all_inputs_bind_or_refuse(self):
        original = calculate('output_shunt_budget', inputs())
        for name in inputs():
            changed = deepcopy(inputs())
            for field in ('value', 'min', 'max'):
                if field in changed[name]:
                    changed[name][field] *= 2
            try:
                actual = calculate('output_shunt_budget', changed)
            except CalculationError:
                continue
            self.assertTrue(any((value['min'], value['max']) != (original[key]['min'], original[key]['max'])
                                for key, value in actual.items()), name)

    def test_unknown_wrong_unit_nonfinite_and_nonpositive_refuse(self):
        for name, value in inputs().items():
            for bad in ({'status': 'UNKNOWN'}, q(float('nan'), value['unit']), q(1, 'bogus')):
                with self.subTest(name=name), self.assertRaises(CalculationError):
                    calculate('output_shunt_budget', {**inputs(), name: bad})
        for name in ('resistance', 'bus_input_resistance', 'required_voltage', 'sense_limit', 'power_rating'):
            with self.subTest(name=name), self.assertRaises(CalculationError):
                calculate('output_shunt_budget', {**inputs(), name: q(0, inputs()[name]['unit'])})


if __name__ == '__main__':
    unittest.main()
