"""First-order TIA loop model against hand arithmetic and independent complex evaluation."""
import itertools
import math
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate, evaluate_check
from pcbknowledge.v2.calculators_tia_loop import INPUT_UNITS
from tests.git_native.test_v2_power_calculators import q, interval


def inputs():
    return {'gain_bandwidth': q(1e6, 'Hz'), 'input_capacitance': q(100e-12, 'F'),
            'feedback_resistance': interval(9900, 10100, 'ohm'),
            **{'feedback_capacitance_' + suffix: interval(20.9e-12, 23.1e-12, 'F') for suffix in 'abcd'}}


def independent(gbw, ci, cf, resistance):
    def loop(frequency):
        s = 2j * math.pi * frequency
        noise_gain = (1 + s * resistance * (ci + cf)) / (1 + s * resistance * cf)
        return (2 * math.pi * gbw / s) / noise_gain
    low, high = 0, gbw
    for _ in range(80):
        mid = (low + high) / 2
        if abs(loop(mid)) > 1:
            low = mid
        else:
            high = mid
    frequency = (low + high) / 2
    value = loop(frequency)
    phase = 180 + math.degrees(math.atan2(value.imag, value.real))
    return frequency, phase


class TiaLoopTests(unittest.TestCase):
    def test_hand_case_and_conditional_phase_target(self):
        point = {'gain_bandwidth': q(1e6, 'Hz'), 'input_capacitance': q(100e-12, 'F'),
                 'feedback_resistance': q(10000, 'ohm'),
                 **{'feedback_capacitance_' + suffix: q(25e-12, 'F') for suffix in 'abcd'}}
        result = calculate('tia_loop_model', point)
        self.assertAlmostEqual(result['feedback_capacitance']['min'], 100e-12)
        self.assertEqual(result['high_frequency_noise_gain']['min'], 2)
        self.assertAlmostEqual(result['feedback_pole']['min'], 159154.94309189535)
        frequency, phase = independent(1e6, 100e-12, 100e-12, 10000)
        self.assertAlmostEqual(result['crossover_frequency']['min'], frequency)
        self.assertAlmostEqual(result['phase_margin']['min'], phase)
        check = {'calculator': 'tia_loop_model', 'inputs': inputs(),
                 'require': {'output': 'phase_margin', 'operator': 'GE', 'limit': q(45, 'deg')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'PASS')
        self.assertIn('not guaranteed actual stability', result['phase_margin']['note'])
        self.assertEqual(result['phase_margin']['basis'], 'CALCULATED')
        self.assertEqual(result['phase_margin']['inputs'], point)

    def test_interval_bound_encloses_complex_corners_and_interior(self):
        requested = inputs()
        requested['gain_bandwidth'] = interval(.8e6, 1.2e6, 'Hz')
        requested['input_capacitance'] = interval(80e-12, 120e-12, 'F')
        result = calculate('tia_loop_model', requested)
        self.assertAlmostEqual(result['feedback_capacitance']['min'], 83.6e-12)
        self.assertAlmostEqual(result['feedback_capacitance']['max'], 92.4e-12)
        for gbw, ci, cf, resistance in itertools.product((.8e6, 1e6, 1.2e6), (80e-12, 100e-12, 120e-12),
                                                        (83.6e-12, 88e-12, 92.4e-12), (9900, 10000, 10100)):
            frequency, phase = independent(gbw, ci, cf, resistance)
            for key, value in (('crossover_frequency', frequency), ('phase_margin', phase)):
                self.assertGreaterEqual(value, result[key]['min'] - 1e-9)
                self.assertLessEqual(value, result[key]['max'] + 1e-9)

    def test_zero_input_capacitance_has_unity_noise_gain_and_ninety_degree_margin(self):
        requested = inputs()
        requested['input_capacitance'] = q(0, 'F')
        requested['feedback_resistance'] = q(10000, 'ohm')
        for suffix in 'abcd':
            requested['feedback_capacitance_' + suffix] = q(22e-12, 'F')
        result = calculate('tia_loop_model', requested)
        self.assertAlmostEqual(result['crossover_frequency']['min'], 1e6)
        self.assertAlmostEqual(result['phase_margin']['min'], 90)
        self.assertEqual(result['high_frequency_noise_gain']['max'], 1)

    def test_every_input_refuses_unknown_typical_negative_nonfinite_and_wrong_unit(self):
        for key, unit in INPUT_UNITS['tia_loop_model'].items():
            for bad in ({'status': 'UNKNOWN'}, {'typ': 1, 'unit': unit}, q(-1, unit),
                        q(float('inf'), unit), q(1, 'wrong')):
                with self.subTest(key=key, bad=bad), self.assertRaises(CalculationError):
                    calculate('tia_loop_model', {**inputs(), key: bad})
            if key != 'input_capacitance':
                with self.subTest(key=key), self.assertRaises(CalculationError):
                    calculate('tia_loop_model', {**inputs(), key: q(0, unit)})
        with self.assertRaises(CalculationError):
            calculate('tia_loop_model', {})

    def test_low_and_high_crossover_roots_avoid_cancellation(self):
        for gbw in (1, 1e3, 1e9):
            requested = {'gain_bandwidth': q(gbw, 'Hz'), 'input_capacitance': q(100e-12, 'F'),
                         'feedback_resistance': q(10000, 'ohm'),
                         **{'feedback_capacitance_' + suffix: q(22e-12, 'F') for suffix in 'abcd'}}
            result = calculate('tia_loop_model', requested)
            frequency, phase = independent(gbw, 100e-12, 88e-12, 10000)
            self.assertAlmostEqual(result['crossover_frequency']['min'], frequency, delta=frequency * 1e-12)
            self.assertAlmostEqual(result['phase_margin']['min'], phase)
