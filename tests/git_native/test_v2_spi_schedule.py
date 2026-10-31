"""Shared-clock scheduling and DDS rounding checks for the DAC contract."""
import unittest

from pcbknowledge.v2 import calculators_spi_schedule as MODULE
from pcbknowledge.v2.calculators import calculate as dispatch, evaluate_check, CalculationError


def calculate(bounds):
    return MODULE.calculate('spi_dac_schedule', bounds)


def fixture():
    return {
        'clock': (8000000, 8000000), 'clock_error': (0, .0001),
        'spi_divider': (2, 2), 'timer_divider': (160, 160),
        'frame_bits': (24, 24), 'firmware_cycles': (0, 80),
        'guard_time': (1.5e-6, 1.5e-6), 'minimum_guard_time': (1.183e-6, 1.183e-6),
        'serial_clock_limit': (50000000, 50000000), 'serial_half_period_minimum': (9e-9, 9e-9),
        'phase_bits': (32, 32), 'requested_frequency': (1, 1000),
        'frequency_error_limit': (.001, .001), 'accepted_sample_rate': (49995, 50005),
        'accepted_waveform_frequency': (.999, 1001),
    }


class TimingTests(unittest.TestCase):
    def test_baseline(self):
        result = calculate(fixture())
        for key, value in result.items():
            if key.endswith('_margin'):
                self.assertGreaterEqual(value[0], 0, key)
        self.assertEqual(result['sample_rate'], (49995, 50005, 'Hz'))

    def test_rounding_is_in_sampling_ratio(self):
        inputs = fixture()
        inputs.update({'clock_error': (0, 0), 'timer_divider': (200, 200),
                       'phase_bits': (10, 10), 'requested_frequency': (1000, 1000),
                       'frequency_error_limit': (.03, .03), 'accepted_sample_rate': (40000, 40000),
                       'accepted_waveform_frequency': (900, 1100)})
        result = calculate(inputs)
        self.assertGreater(result['frequency_margin'][0], 0)
        self.assertLess(result['sampling_margin'][0], 0)
        self.assertEqual(result['waveform_frequency'], (1015.625, 1015.625, 'Hz'))

    def test_shared_sample_interval_cannot_drift(self):
        inputs = fixture()
        inputs['accepted_sample_rate'] = (50000, 50000)
        self.assertLess(calculate(inputs)['sample_rate_margin'][0], 0)

    def test_actual_frequency_cannot_drop_clock_rounding(self):
        inputs = fixture()
        inputs['accepted_waveform_frequency'] = (1, 1000)
        self.assertLess(calculate(inputs)['waveform_frequency_margin'][0], 0)

    def test_firmware_budget(self):
        inputs = fixture()
        inputs['firmware_cycles'] = (0, 160)
        self.assertLess(calculate(inputs)['time_margin'][0], 0)

    def test_domains(self):
        for key, pair in [('spi_divider', (3, 3)), ('frame_bits', (16, 16)),
                          ('clock_error', (0, 1)), ('timer_divider', (160.5, 160.5)),
                          ('phase_bits', (1, 1))]:
            inputs = fixture()
            inputs[key] = pair
            with self.assertRaises(ValueError):
                calculate(inputs)

    def test_ties_upward(self):
        self.assertEqual(MODULE.phase_word(1, 4, 8), 1)


def quantities():
    units = MODULE.INPUT_UNITS['spi_dac_schedule']
    return {key: {'min': low, 'max': high, 'unit': units[key], 'basis': 'ENGINEERING_DEFAULT',
                  'conditions': {}, 'note': 'Synthetic scheduling input.'}
            for key, (low, high) in fixture().items()}


class ScheduleDispatchTests(unittest.TestCase):
    def test_shared_interval_mutation_fails_real_check(self):
        inputs = quantities()
        inputs['accepted_sample_rate'] = {'parameter': 'sample_rate'}
        parameters = {'sample_rate': quantities()['accepted_sample_rate']}
        zero = {'value': 0, 'unit': 'Hz', 'basis': 'ENGINEERING_DEFAULT', 'conditions': {}}
        check = {'calculator': 'spi_dac_schedule', 'inputs': inputs,
                 'require': {'output': 'sample_rate_margin', 'operator': 'GE', 'limit': zero}}
        self.assertEqual(evaluate_check(check, parameters)['result'], 'PASS')
        parameters['sample_rate'].update(min=50000, max=50000)
        self.assertEqual(evaluate_check(check, parameters)['result'], 'FAIL')

    def test_missing_unknown_nonfinite_or_wrong_unit_refuses(self):
        for replacement in ({'status': 'UNKNOWN'}, {'value': 1, 'unit': 'V'},
                            {'value': float('inf'), 'unit': 'Hz'}):
            inputs = quantities()
            inputs['clock'] = replacement
            with self.assertRaises(CalculationError):
                dispatch('spi_dac_schedule', inputs)
        inputs = quantities()
        del inputs['clock']
        with self.assertRaises(CalculationError):
            dispatch('spi_dac_schedule', inputs)


if __name__ == '__main__':
    unittest.main()
