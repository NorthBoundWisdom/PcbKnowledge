"""Input protection arithmetic and each margin's failing side use synthetic inputs."""
import copy
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate, evaluate_check


def q(unit, value=None, **bounds):
    result = {'unit': unit, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {}}
    result.update({'value': value} if value is not None else bounds)
    return result


class InputProtectionTests(unittest.TestCase):
    def setUp(self):
        self.inputs = {
            'input_voltage': q('V', min=7, max=12), 'input_current': q('A', .5),
            'fuse_current_rating': q('A', 1), 'fuse_derating': q('1', .75),
            'temperature_factor': q('1', .9), 'fuse_resistance': q('ohm', min=0, max=.156),
            'diode_drop': q('V', min=0, max=.6), 'diode_current_rating': q('A', 1),
            'diode_reverse_rating': q('V', 40), 'capacitor_voltage_rating': q('V', 25),
            'minimum_output_voltage': q('V', 5.5505), 'ambient': q('degC', 40),
            'diode_thermal_resistance': q('degC/W', 176), 'diode_rating_temperature': q('degC', 100),
        }

    def test_hand_calculated_losses_headroom_and_charged_cap_reverse_stress(self):
        output = calculate('input_protection', self.inputs)
        expected = {'output_voltage': ('min', 6.322), 'fuse_hold_current': ('min', .675),
                    'headroom': ('min', .7715), 'fuse_power': ('max', .039),
                    'diode_power': ('max', .3), 'diode_junction_temperature': ('max', 92.8),
                    'diode_reverse_stress': ('max', 24)}
        for name, (bound, value) in expected.items():
            self.assertAlmostEqual(output[name][bound], value)

    def test_each_margin_can_fail(self):
        cases = [
            ('input_voltage', q('V', min=5.5, max=12), 'headroom', 'V'),
            ('input_current', q('A', .7), 'fuse_current_margin', 'A'),
            ('capacitor_voltage_rating', q('V', 10), 'capacitor_voltage_margin', 'V'),
            ('diode_current_rating', q('A', .4), 'diode_current_margin', 'A'),
            ('diode_reverse_rating', q('V', 20), 'diode_reverse_margin', 'V'),
            ('ambient', q('degC', 50), 'diode_derating_margin', 'degC'),
        ]
        for key, value, output, unit in cases:
            with self.subTest(output=output):
                inputs = {**self.inputs, key: value}
                check = {'calculator': 'input_protection', 'inputs': inputs,
                         'require': {'output': output, 'operator': 'GE', 'limit': q(unit, 0)}}
                self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')

    def test_junction_ceiling_can_fail(self):
        inputs = {**self.inputs, 'ambient': q('degC', 90)}
        check = {'calculator': 'input_protection', 'inputs': inputs,
                 'require': {'output': 'diode_junction_temperature', 'operator': 'LE',
                             'limit': q('degC', 125)}}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')

    def test_invalid_domains_and_missing_ratings_refuse(self):
        for key, value in [('fuse_derating', q('1', 0)), ('temperature_factor', q('1', 1.1)),
                           ('diode_thermal_resistance', q('degC/W', 0)),
                           ('diode_current_rating', q('A', 0)), ('fuse_resistance', q('ohm', -1)),
                           ('input_voltage', q('V', .1))]:
            with self.subTest(key=key):
                with self.assertRaises(CalculationError):
                    calculate('input_protection', {**self.inputs, key: value})
        missing = copy.deepcopy(self.inputs)
        del missing['diode_reverse_rating']
        with self.assertRaises(CalculationError):
            calculate('input_protection', missing)

    def test_zero_current_is_a_valid_no_load_case(self):
        output = calculate('input_protection', {**self.inputs, 'input_current': q('A', 0)})
        self.assertEqual(output['fuse_power']['max'], 0)
        self.assertEqual(output['diode_power']['max'], 0)
        self.assertEqual(output['diode_junction_temperature']['max'], 40)
