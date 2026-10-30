"""Independent hand-calculated CCM, conduction loss and RC interval cases."""
import copy
import math
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate, evaluate_check, validate_inputs


def q(value, unit, **conditions):
    return {'value': value, 'unit': unit, 'conditions': conditions,
            'basis': 'ENGINEERING_DEFAULT', 'note': 'Synthetic model input.'}


def interval(low, high, unit):
    result = q(0, unit)
    del result['value']
    return {**result, 'min': low, 'max': high}


def buck():
    return {'input_voltage': q(12, 'V'), 'output_voltage': q(6, 'V'), 'output_current': q(1, 'A'),
            'frequency': q(100000, 'Hz'), 'inductance': q(.0001, 'H')}


class BuckCalculatorTests(unittest.TestCase):
    def test_inductor_ramp_charge_and_rms_hand_calculation(self):
        # 6 V / 100 uH for a 5 us on-time produces a 0.3 A ramp.
        result = calculate('buck_inductor_ripple', buck())
        expected = {'duty_cycle': .5, 'ripple_current': .3, 'peak_current': 1.15,
                    'valley_current': .85, 'inductor_rms_current': math.sqrt(1 + .09 / 12),
                    'input_capacitor_rms_current': math.sqrt(.25 + .5 * .09 / 12),
                    'output_capacitor_rms_current': .3 / math.sqrt(12)}
        for name, value in expected.items():
            with self.subTest(output=name):
                self.assertAlmostEqual(result[name]['min'], value)
                self.assertAlmostEqual(result[name]['max'], value)
                self.assertIn('fixed-frequency CCM', result[name]['note'])

    def test_output_charge_integral_and_esr_bound(self):
        inputs = {**buck(), 'capacitance': q(100e-6, 'F'), 'esr': q(.02, 'ohm')}
        result = calculate('buck_output_ripple', inputs)
        # Triangle charge: 0.3 A / (8 * 100 kHz * 100 uF) = 3.75 mV.
        self.assertAlmostEqual(result['capacitive_ripple']['max'], .00375)
        self.assertAlmostEqual(result['esr_ripple']['max'], .006)
        self.assertAlmostEqual(result['output_ripple']['max'], .00975)
        # Components are not necessarily in phase; their sum is an upper bound.
        self.assertAlmostEqual(result['output_ripple']['min'], .006)

    def test_interval_interior_maximum_not_just_endpoint_sampling(self):
        inputs = {**buck(), 'input_voltage': q(10, 'V'), 'output_voltage': interval(2, 8, 'V')}
        result = calculate('buck_inductor_ripple', inputs)
        self.assertAlmostEqual(result['ripple_current']['min'], .16)
        self.assertAlmostEqual(result['ripple_current']['max'], .25)
        self.assertAlmostEqual(result['duty_cycle']['min'], .2)
        self.assertAlmostEqual(result['duty_cycle']['max'], .8)

    def test_interval_ripple_peak_and_valley_enclose_independent_grid(self):
        inputs = {'input_voltage': interval(10, 14, 'V'), 'output_voltage': interval(3, 6, 'V'),
                  'output_current': interval(.8, 1.2, 'A'), 'frequency': interval(90000, 110000, 'Hz'),
                  'inductance': interval(90e-6, 110e-6, 'H')}
        result = calculate('buck_inductor_ripple', inputs)
        for vi in (10, 12, 14):
            for vo in (3, 4.5, 6):
                for frequency in (90000, 110000):
                    for inductance in (90e-6, 110e-6):
                        ripple = (vi - vo) * (vo / vi) / (frequency * inductance)
                        self.assertLessEqual(result['ripple_current']['min'], ripple + 1e-14)
                        self.assertGreaterEqual(result['ripple_current']['max'], ripple - 1e-14)
                        for current in (.8, 1.2):
                            self.assertLessEqual(result['valley_current']['min'], current - ripple / 2)
                            self.assertGreaterEqual(result['peak_current']['max'], current + ripple / 2)

    def test_dcm_boundary_zero_load_and_unknown_frequency_refuse(self):
        for current in (.15, .1, 0):
            inputs = {**buck(), 'output_current': q(current, 'A')}
            with self.subTest(current=current), self.assertRaises(CalculationError):
                calculate('buck_inductor_ripple', inputs)
        for frequency in ({'status': 'UNKNOWN'}, {'unit': 'Hz', 'typ': 100000}):
            with self.subTest(frequency=frequency), self.assertRaises(CalculationError):
                calculate('buck_inductor_ripple', {**buck(), 'frequency': frequency})

    def test_invalid_stepdown_units_bounds_and_nonfinite_refuse(self):
        invalid = [('input_voltage', q(6, 'V')), ('input_voltage', q(5, 'V')),
                   ('inductance', q(0, 'H')), ('frequency', q(0, 'Hz')),
                   ('inductance', q(.0001, 'F')), ('frequency', q(float('inf'), 'Hz')),
                   ('output_voltage', interval(6, 3, 'V')), ('output_current', q(True, 'A'))]
        for name, value in invalid:
            with self.subTest(name=name, value=value), self.assertRaises(CalculationError):
                calculate('buck_inductor_ripple', {**buck(), name: value})
        for capacitance, esr in ((0, .02), (100e-6, -.01)):
            with self.assertRaises(CalculationError):
                calculate('buck_output_ripple', {**buck(), 'capacitance': q(capacitance, 'F'), 'esr': q(esr, 'ohm')})

    def test_evaluate_check_rejects_rating_and_refuses_unsupported_domain(self):
        check = {'calculator': 'buck_inductor_ripple', 'inputs': buck(),
                 'require': {'output': 'peak_current', 'operator': 'LE', 'limit': q(1.1, 'A')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')
        check['inputs']['output_current'] = q(.1, 'A')
        self.assertEqual(evaluate_check(check, {})['result'], 'REFUSED')


class PassiveCalculatorTests(unittest.TestCase):
    def test_mosfet_loss_is_conditioned_on_supplied_resistance(self):
        conditions = {'TJ': {'value': 25, 'unit': 'degC'}, 'gate_voltage': {'value': 2.5, 'unit': 'V'}}
        inputs = {'rms_current': interval(.1, .2, 'A'),
                  'on_resistance': {**interval(.08, .12, 'ohm'), 'conditions': conditions}}
        result = calculate('mosfet_conduction_loss', inputs)['power']
        self.assertAlmostEqual(result['min'], .0008)
        self.assertAlmostEqual(result['max'], .0048)
        self.assertEqual(result['conditions'], conditions)
        self.assertIn('excludes switching losses', result['note'])
        self.assertEqual(calculate('mosfet_conduction_loss', {**inputs, 'rms_current': q(0, 'A')})['power']['max'], 0)

    def test_mosfet_missing_or_invalid_temperature_refuses(self):
        for conditions in ({}, {'TJ': {'value': 25, 'unit': 'V'}}, {'TA': {'value': float('nan'), 'unit': 'degC'}}):
            with self.subTest(conditions=conditions), self.assertRaises(CalculationError):
                calculate('mosfet_conduction_loss', {'rms_current': q(.1, 'A'),
                          'on_resistance': q(.1, 'ohm', **conditions)})

    def test_mosfet_condition_payload_must_be_finite_and_typed(self):
        conditions = [{'TJ': {'value': 25, 'unit': 'degC'},
                       'gate_voltage': {'value': float('nan'), 'unit': 'V'}},
                      {'TJ': {'value': 25}}, 'TJ=25']
        for condition in conditions:
            with self.subTest(condition=condition), self.assertRaises(CalculationError):
                calculate('mosfet_conduction_loss', {'rms_current': q(.1, 'A'),
                          'on_resistance': {**q(.1, 'ohm'), 'conditions': condition}})

    def test_rc_time_constant_and_interval_product(self):
        inputs = {'resistance': interval(9000, 11000, 'ohm'), 'capacitance': interval(90e-9, 110e-9, 'F')}
        result = calculate('rc_time', inputs)['time_constant']
        self.assertAlmostEqual(result['min'], .00081)
        self.assertAlmostEqual(result['max'], .00121)
        self.assertEqual(result['unit'], 's')
        with self.assertRaises(CalculationError):
            calculate('rc_time', {**inputs, 'capacitance': q(0, 'F')})

    def test_exact_inputs_and_parameter_projections(self):
        inputs = {'resistance': {'component': 'R1', 'parameter': 'resistance'},
                  'capacitance': {'parameter': 'capacitance'}}
        validate_inputs('rc_time', inputs, allow_parameters=True)
        with self.assertRaises(CalculationError):
            validate_inputs('rc_time', inputs)
        with self.assertRaises(CalculationError):
            calculate('rc_time', {'resistance': q(1, 'ohm'), 'capacitance': q(1, 'F'), 'extra': q(1, '1')})
        original = copy.deepcopy(inputs)
        check = {'calculator': 'rc_time', 'inputs': inputs,
                 'require': {'output': 'time_constant', 'operator': 'LE', 'limit': q(.002, 's')}}
        result = evaluate_check(check, {'capacitance': q(100e-9, 'F')},
                                {'R1': {'parameters': {'resistance': q(10000, 'ohm')}}})
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(inputs, original)
