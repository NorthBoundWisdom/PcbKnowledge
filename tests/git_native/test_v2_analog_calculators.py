"""Independent G3 hand calculations, interval corners and domain refusals."""
import itertools
import math
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate, evaluate_check
from pcbknowledge.v2.calculators_analog import INPUT_UNITS
from tests.git_native.test_v2_power_calculators import q, interval


def examples():
    return {
        'opamp_gain': {'input_current': interval(0, 10e-6, 'A'),
                       'feedback_resistance': interval(99000, 101000, 'ohm'), 'bias_voltage': q(.1, 'V')},
        'rc_filter': {'resistance': interval(990, 1010, 'ohm'), 'capacitance': interval(9e-9, 11e-9, 'F')},
        'reference_load': {'supply': interval(3.2, 3.4, 'V'), 'reference_voltage': interval(2.45, 2.55, 'V'),
                           'series_resistance': interval(99, 101, 'ohm'), 'load_current': interval(0, .001, 'A')},
        'rs485_termination': {'supply': interval(3.2, 3.4, 'V'), 'termination_a': interval(118.8, 121.2, 'ohm'),
                              'termination_b': interval(118.8, 121.2, 'ohm'),
                              'bias_up': interval(326.7, 333.3, 'ohm'),
                              'bias_down': interval(326.7, 333.3, 'ohm'), 'driver_voltage': interval(1.5, 3.4, 'V'),
                              'receiver_load_current': interval(0, .0006, 'A')},
        'trace_impedance_microstrip': {'trace_width': interval(1.45, 1.55, 'mm'),
                                       'dielectric_height': interval(1.4, 1.6, 'mm'),
                                       'copper_thickness': interval(.03, .04, 'mm'),
                                       'relative_permittivity': interval(3.8, 4.4, '1'),
                                       'model_relative_error': q(.1, '1')},
    }


class AnalogCalculatorsTests(unittest.TestCase):
    def test_tia_sign_and_interval(self):
        result = calculate('opamp_gain', examples()['opamp_gain'])
        self.assertEqual(result['transimpedance']['min'], 99000)
        self.assertAlmostEqual(result['output_voltage']['min'], .1)
        self.assertAlmostEqual(result['output_voltage']['max'], 1.11)
        self.assertIn('leaves', result['output_voltage']['note'])

    def test_rc_filter_hand_calculation(self):
        result = calculate('rc_filter', examples()['rc_filter'])
        self.assertAlmostEqual(result['time_constant']['min'], 8.91e-6)
        self.assertAlmostEqual(result['time_constant']['max'], 11.11e-6)
        self.assertAlmostEqual(result['cutoff_frequency']['min'], 1 / (2 * math.pi * 11.11e-6))
        self.assertAlmostEqual(result['cutoff_frequency']['max'], 1 / (2 * math.pi * 8.91e-6))

    def test_reference_loading_and_checks(self):
        inputs = examples()['reference_load']
        result = calculate('reference_load', inputs)
        self.assertAlmostEqual(result['cathode_current']['min'], .65 / 101 - .001)
        self.assertAlmostEqual(result['cathode_current']['max'], .95 / 99)
        self.assertAlmostEqual(result['resistor_power']['max'], .95**2 / 99)
        check = {'calculator': 'reference_load', 'inputs': inputs,
                 'require': {'output': 'cathode_current', 'operator': 'GE', 'limit': q(.001, 'A')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'PASS')
        check['inputs'] = {**inputs, 'load_current': q(.02, 'A')}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')
        self.assertLess(calculate('reference_load', check['inputs'])['cathode_current']['max'], 0)

    def test_rs485_network_hand_calculation(self):
        values = (3.3, 120, 120, 330, 330, 1.5, .0006)
        inputs = {key: q(value, unit) for (key, unit), value in
                  zip(INPUT_UNITS['rs485_termination'].items(), values)}
        result = calculate('rs485_termination', inputs)
        self.assertAlmostEqual(result['idle_differential']['min'], .275 - .0006 * 55)
        self.assertAlmostEqual(result['equivalent_load']['min'], 55)
        self.assertAlmostEqual(result['driver_current']['max'], .025 + 4.8 / 660 + .0006)
        self.assertAlmostEqual(result['termination_power']['max'], .0375)
        self.assertAlmostEqual(result['bias_power']['max'], 4.8**2 / 660)
        self.assertGreater(result['driver_current']['max'], 1.5 / 55)
        check = {'calculator': 'rs485_termination', 'inputs': inputs,
                 'require': {'output': 'idle_differential', 'operator': 'GE', 'limit': q(.3, 'V')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')

    def test_microstrip_source_equation_and_common_length_units(self):
        # ADI MT-094 p3's 8.3 mil width / 10 mil height / 1.4 mil copper example.
        inputs = {'trace_width': q(8.3 * .0254, 'mm'), 'dielectric_height': q(10 * .0254, 'mm'),
                  'copper_thickness': q(1.4 * .0254, 'mm'), 'relative_permittivity': q(4, '1'),
                  'model_relative_error': q(.1, '1')}
        raw = 87 / math.sqrt(5.41) * math.log(59.8 / 8.04)
        result = calculate('trace_impedance_microstrip', inputs)['impedance']
        self.assertAlmostEqual(raw, 75.05443475969057)
        self.assertAlmostEqual(result['min'], raw * .9)
        self.assertAlmostEqual(result['max'], raw * 1.1)
        self.assertIn('not a guaranteed', result['note'])

    def test_all_corners_enclosed_and_provenance_retained(self):
        for name, inputs in examples().items():
            result = calculate(name, inputs)
            endpoints = [(v.get('min', v.get('value')), v.get('max', v.get('value'))) for v in inputs.values()]
            for corner in itertools.product(*endpoints):
                point = {key: q(value, INPUT_UNITS[name][key]) for key, value in zip(inputs, corner)}
                for key, value in calculate(name, point).items():
                    self.assertGreaterEqual(value['min'] + 1e-10, result[key]['min'], (name, key))
                    self.assertLessEqual(value['max'] - 1e-10, result[key]['max'], (name, key))
            for value in result.values():
                self.assertEqual(value['basis'], 'CALCULATED')
                self.assertEqual(value['inputs'], inputs)
                self.assertTrue(value['note'])
                self.assertLessEqual(len(value['note']), 256)

    def test_missing_unknown_typical_nonfinite_and_negative_refuse_every_model(self):
        for name, inputs in examples().items():
            key = next(iter(inputs))
            for bad in ({'status': 'UNKNOWN'}, {'typ': 1, 'unit': INPUT_UNITS[name][key]},
                        q(float('inf'), INPUT_UNITS[name][key]), q(-1, INPUT_UNITS[name][key]),
                        q(1, 'incorrect'), interval(2, 1, INPUT_UNITS[name][key])):
                with self.subTest(name=name, bad=bad), self.assertRaises(CalculationError):
                    calculate(name, {**inputs, key: bad})
            with self.subTest(name=name), self.assertRaises(CalculationError):
                calculate(name, {})

    def test_model_specific_domains_refuse(self):
        cases = [('opamp_gain', 'feedback_resistance', 0), ('rc_filter', 'resistance', 0),
                 ('rc_filter', 'capacitance', 0), ('reference_load', 'reference_voltage', 0),
                 ('reference_load', 'series_resistance', 0), ('reference_load', 'supply', 2.5),
                 ('rs485_termination', 'supply', 0), ('rs485_termination', 'termination_a', 0),
                 ('rs485_termination', 'termination_b', 0), ('rs485_termination', 'bias_up', 0),
                 ('rs485_termination', 'bias_down', 0), ('trace_impedance_microstrip', 'trace_width', 0),
                 ('trace_impedance_microstrip', 'dielectric_height', 0),
                 ('trace_impedance_microstrip', 'copper_thickness', 0),
                 ('trace_impedance_microstrip', 'relative_permittivity', .9),
                 ('trace_impedance_microstrip', 'model_relative_error', 1),
                 ('trace_impedance_microstrip', 'trace_width', .001),
                 ('trace_impedance_microstrip', 'trace_width', 100)]
        for name, key, value in cases:
            inputs = examples()[name]
            inputs[key] = q(value, INPUT_UNITS[name][key])
            with self.subTest(name=name, key=key, value=value), self.assertRaises(CalculationError):
                calculate(name, inputs)

    def test_microstrip_monotonic_directions(self):
        inputs = {key: q(value.get('value', value.get('min')), value['unit'])
                  for key, value in examples()['trace_impedance_microstrip'].items()}
        baseline = calculate('trace_impedance_microstrip', inputs)['impedance']['min']
        for key in ('trace_width', 'copper_thickness', 'relative_permittivity', 'dielectric_height'):
            changed = {**inputs, key: q(inputs[key]['value'] * 1.01, inputs[key]['unit'])}
            result = calculate('trace_impedance_microstrip', changed)['impedance']['min']
            self.assertEqual(result > baseline, key == 'dielectric_height')


    def test_rs485_independent_node_voltage_solution_encloses_interior(self):
        inputs = examples()['rs485_termination']
        envelope = calculate('rs485_termination', inputs)
        # Independent nodal conductance solve: A connected to supply through Ru,
        # B to ground through Rd, and both termination resistors between A and B.
        for fraction in (0, .25, .5, .75, 1):
            v, ra, rb, ru, rd, vd, load = [item['min'] + fraction * (item['max'] - item['min'])
                                    for item in inputs.values()]
            g = 1 / ra + 1 / rb
            a, d = 1 / ru + g, 1 / rd + g
            determinant = a * d - g * g
            va = ((v / ru - load) * d + g * load) / determinant
            vb = (a * load + g * (v / ru - load)) / determinant
            self.assertGreaterEqual(va - vb, envelope['idle_differential']['min'] - 1e-12)
            self.assertLessEqual(va - vb, envelope['idle_differential']['max'] + 1e-12)
            # With A-B=-Vd, supernode KCL solves A; the driver must supply both
            # termination current and the adverse pull-up current.
            driven_a = (v / ru - vd / rd) / (1 / ru + 1 / rd)
            driver = vd * g + (v - driven_a) / ru + load
            self.assertGreaterEqual(driver, envelope['driver_current']['min'] - 1e-12)
            self.assertLessEqual(driver, envelope['driver_current']['max'] + 1e-12)


    def test_rs485_load_can_reverse_idle_voltage_and_termination_monotonicity(self):
        inputs = examples()['rs485_termination']
        inputs.update(bias_up=interval(1980, 2020, 'ohm'), bias_down=interval(1980, 2020, 'ohm'),
                      receiver_load_current=interval(.0006, .002, 'A'))
        result = calculate('rs485_termination', inputs)
        # Above Vs/Rbias, the load reverses the idle voltage and increasing Rt
        # makes it more negative: the old unloaded corner ordering is wrong.
        minimum = (3.2 - .002 * 4040) * 60.6 / (60.6 + 4040)
        maximum = (3.4 - .0006 * 3960) * 60.6 / (60.6 + 3960)
        self.assertAlmostEqual(result['idle_differential']['min'], minimum)
        self.assertAlmostEqual(result['idle_differential']['max'], maximum)
        self.assertLess(result['idle_differential']['min'], 0)
        self.assertGreater(result['idle_differential']['max'], 0)
        for load in (-.001, float('nan')):
            with self.assertRaises(CalculationError):
                calculate('rs485_termination', {**inputs, 'receiver_load_current': q(load, 'A')})
        with self.assertRaises(CalculationError):
            calculate('rs485_termination', {**inputs, 'receiver_load_current': {'status': 'UNKNOWN'}})
