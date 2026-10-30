"""G3 source-shaped sensing models: hand calculations and fail-closed domains."""
import itertools
import math
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate, evaluate_check
from pcbknowledge.v2.calculators_sensing import INPUT_UNITS
from tests.git_native.test_v2_power_calculators import q, interval


def examples():
    return {
        'ntc_divider': {'supply': interval(2.35, 2.65, 'V'), 'resistance_25': interval(9500, 10500, 'ohm'),
                        'beta': interval(3947.1725, 4006.8275, 'K'), 'temperature': interval(15, 35, 'degC'),
                        'upper_resistance': interval(9900, 10100, 'ohm'),
                        'series_resistance': interval(9900, 10100, 'ohm'),
                        'capacitance': interval(90e-9, 110e-9, 'F')},
        'ferrite_loss': {'supply': interval(3.2, 3.4, 'V'), 'current': interval(0, .01, 'A'),
                         'resistance': interval(0, .06, 'ohm'), 'current_rating': q(2.3, 'A')},
        'tia_frontend': {'supply': interval(3.1994, 3.4, 'V'), 'reference_voltage': interval(2.35, 2.65, 'V'),
                         'bias_top': interval(9900, 10100, 'ohm'), 'bias_bottom': interval(9900, 10100, 'ohm'),
                         'feedback_resistance': interval(9900, 10100, 'ohm'),
                         'input_current': interval(0, 50e-6, 'A'), 'total_error': q(.05, 'V'),
                         'headroom': q(.3, 'V')},
    }


class SensingCalculatorTests(unittest.TestCase):
    def test_ntc_reference_temperature_and_interior_power_peak(self):
        inputs = examples()['ntc_divider']
        inputs.update(supply=q(2.5, 'V'), resistance_25=q(10000, 'ohm'), beta=q(3977, 'K'),
                      temperature=q(25, 'degC'), upper_resistance=q(10000, 'ohm'),
                      series_resistance=q(10000, 'ohm'), capacitance=q(100e-9, 'F'))
        result = calculate('ntc_divider', inputs)
        self.assertEqual(result['sensor_resistance']['min'], 10000)
        self.assertEqual(result['output_voltage']['min'], 1.25)
        self.assertAlmostEqual(result['pole_frequency']['min'], 1 / (2 * math.pi * .0015))
        self.assertAlmostEqual(result['max_sensor_power']['max'], .00015625)
        inputs['temperature'] = interval(15, 35, 'degC')
        result = calculate('ntc_divider', inputs)
        self.assertAlmostEqual(result['max_sensor_power']['max'], .00015625)
        # Temperature endpoints dissipate less than the interior Rntc=Rupper maximum.
        for temperature in (15, 35):
            corner = calculate('ntc_divider', {**inputs, 'temperature': q(temperature, 'degC')})
            self.assertLess(corner['max_sensor_power']['max'], result['max_sensor_power']['max'])

    def test_ntc_beta_sign_change_and_sampled_independent_network(self):
        inputs = examples()['ntc_divider']
        result = calculate('ntc_divider', inputs)
        low = 9500 * math.exp(4006.8275 * (1 / 308.15 - 1 / 298.15))
        high = 10500 * math.exp(4006.8275 * (1 / 288.15 - 1 / 298.15))
        self.assertAlmostEqual(result['sensor_resistance']['min'], low)
        self.assertAlmostEqual(result['sensor_resistance']['max'], high)
        for temperature in range(15, 36):
            for nominal, beta, upper in itertools.product((9500, 10500), (3947.1725, 4006.8275), (9900, 10100)):
                sensor = nominal * math.exp(beta * (1 / (temperature + 273.15) - 1 / 298.15))
                current = 2.65 / (upper + sensor)
                self.assertLessEqual(current**2 * sensor, result['max_sensor_power']['max'] + 1e-12)
                self.assertLessEqual(current * sensor, result['output_voltage']['max'] + 1e-12)
                self.assertGreaterEqual(2.35 / (upper + sensor) * sensor,
                                        result['output_voltage']['min'] - 1e-12)

    def test_ferrite_loss_and_current_limit(self):
        inputs = examples()['ferrite_loss']
        result = calculate('ferrite_loss', inputs)
        self.assertAlmostEqual(result['output_voltage']['min'], 3.1994)
        self.assertAlmostEqual(result['power']['max'], .000006)
        self.assertAlmostEqual(result['current_margin']['min'], 2.29)
        check = {'calculator': 'ferrite_loss', 'inputs': {**inputs, 'current_rating': q(.005, 'A')},
                 'require': {'output': 'current_margin', 'operator': 'GE', 'limit': q(0, 'A')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')

    def test_tia_divider_error_and_both_headroom_limits(self):
        inputs = examples()['tia_frontend']
        result = calculate('tia_frontend', inputs)
        low = 2.35 * 9900 / 20000
        high = 2.65 * 10100 / 20000 + 50e-6 * 10100
        self.assertAlmostEqual(result['bias_voltage']['min'], low)
        self.assertAlmostEqual(result['ideal_output_voltage']['max'], high)
        self.assertAlmostEqual(result['output_voltage']['min'], low - .05)
        self.assertAlmostEqual(result['output_voltage']['max'], high + .05)
        self.assertAlmostEqual(result['low_headroom_margin']['min'], low - .05 - .3)
        self.assertAlmostEqual(result['high_headroom_margin']['min'], 3.1994 - .3 - high - .05)
        for output in ('low_headroom_margin', 'high_headroom_margin'):
            check = {'calculator': 'tia_frontend', 'inputs': {**inputs, 'total_error': q(2, 'V')},
                     'require': {'output': output, 'operator': 'GE', 'limit': q(0, 'V')}}
            self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')

    def test_corner_enclosure_and_explicit_assumptions(self):
        for name, inputs in examples().items():
            envelope = calculate(name, inputs)
            endpoints = [(v.get('min', v.get('value')), v.get('max', v.get('value'))) for v in inputs.values()]
            for corner in itertools.product(*endpoints):
                point = {key: q(value, INPUT_UNITS[name][key]) for key, value in zip(inputs, corner)}
                for key, value in calculate(name, point).items():
                    if key != 'max_sensor_power':
                        self.assertGreaterEqual(value['min'] + 1e-10, envelope[key]['min'], (name, key))
                    self.assertLessEqual(value['max'] - 1e-10, envelope[key]['max'], (name, key))
            for value in envelope.values():
                self.assertEqual(value['basis'], 'CALCULATED')
                self.assertEqual(value['inputs'], inputs)
                self.assertTrue(value['note'])
                self.assertLessEqual(len(value['note']), 256)

    def test_all_inputs_reject_unknown_nonfinite_negative_and_typical(self):
        for name, inputs in examples().items():
            for key, unit in INPUT_UNITS[name].items():
                for bad in ({'status': 'UNKNOWN'}, q(float('nan'), unit), q(-1, unit), {'typ': 1, 'unit': unit}):
                    with self.subTest(name=name, key=key, bad=bad), self.assertRaises(CalculationError):
                        calculate(name, {**inputs, key: bad})

    def test_zero_domains_temperature_domain_and_excessive_drop_refuse(self):
        positive = {'ntc_divider': ('supply', 'resistance_25', 'beta', 'upper_resistance', 'capacitance'),
                    'ferrite_loss': ('supply', 'current_rating'),
                    'tia_frontend': ('supply', 'reference_voltage', 'bias_top', 'bias_bottom', 'feedback_resistance')}
        for name, keys in positive.items():
            for key in keys:
                with self.subTest(name=name, key=key), self.assertRaises(CalculationError):
                    calculate(name, {**examples()[name], key: q(0, INPUT_UNITS[name][key])})
        for temperature in (0, 14.99, 35.01):
            with self.assertRaises(CalculationError):
                calculate('ntc_divider', {**examples()['ntc_divider'], 'temperature': q(temperature, 'degC')})
        with self.assertRaises(CalculationError):
            calculate('ferrite_loss', {**examples()['ferrite_loss'], 'current': q(100, 'A')})
        with self.assertRaises(CalculationError):
            calculate('tia_frontend', {**examples()['tia_frontend'], 'headroom': q(2, 'V')})
