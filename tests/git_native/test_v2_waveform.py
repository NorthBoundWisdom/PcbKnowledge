"""Synthetic mutation tests for the frozen waveform helper only."""
import unittest

from pcbknowledge.v2 import calculators_waveform as MODULE
from pcbknowledge.v2.calculators import calculate as dispatch, evaluate_check, CalculationError


def fixture():
    return {
        'filter_resistance_1': (990, 1010), 'filter_resistance_2': (990, 1010),
        'isolation_resistance': (9.9, 10.1), 'tcr_magnitude': (0, .0001),
        'temperature_excursion': (0, 15), 'filter_capacitance': (9e-9, 11e-9),
        'capacitance_retention': (.5, 1.15), 'load_resistance_minimum': (10000, 10000),
        'sample_rate': (49995, 50005), 'sample_jitter': (0, .5e-6),
        'waveform_frequency': (1, 1000.1), 'amplitude': (0, 1), 'offset': (1.25, 1.25),
        'gain_error': (0, .01), 'static_error': (0, .004),
        'pointwise_residual_error': (0, .005), 'cycle_mean_residual_error': (0, .005), 'initial_error': (0, 5.25),
        'settle_time': (.001, .001), 'relative_amplitude_limit': (.05, .05),
        'absolute_amplitude_limit': (.025, .025), 'offset_error_limit': (.025, .025),
    }


def calculate(inputs):
    return MODULE.calculate('sampled_waveform_envelope', inputs)


class WaveformTests(unittest.TestCase):
    def test_baseline(self):
        result = calculate(fixture())
        self.assertGreater(result['amplitude_margin'][0], 0)
        self.assertGreater(result['offset_margin'][0], 0)

    def test_offset_includes_loading_and_dynamic_error(self):
        inputs = fixture()
        inputs['isolation_resistance'] = (118.8, 121.2)
        self.assertLess(calculate(inputs)['offset_margin'][0], 0)

    def test_both_physical_filter_resistors_bind(self):
        result = calculate(fixture())
        for name in ('filter_resistance_1', 'filter_resistance_2'):
            inputs = fixture()
            inputs[name] = (1980, 2020)
            self.assertGreater(calculate(inputs)['time_constant'][1], result['time_constant'][1])

    def test_source_capacitance_and_retention_bind(self):
        inputs = fixture()
        inputs['capacitance_retention'] = (.5, 10)
        self.assertLess(calculate(inputs)['amplitude_margin'][0], 0)

    def test_all_amplitudes_not_only_fullscale(self):
        inputs = fixture()
        inputs['waveform_frequency'] = (1, 1)
        inputs['pointwise_residual_error'] = (0, .026)
        self.assertLess(calculate(inputs)['amplitude_margin'][0], 0)

    def test_domain_refusals(self):
        mutations = {
            'sample_jitter': (0, .1), 'amplitude': (.1, 1),
            'offset': (1, 1.25), 'filter_capacitance': (0, 1e-8),
            'sample_rate': (1000, 1000), 'gain_error': (0, 1),
        }
        for key, value in mutations.items():
            inputs = fixture()
            inputs[key] = value
            with self.assertRaises(ValueError, msg=key):
                calculate(inputs)

    def test_unenclosable_decay_fails_closed(self):
        inputs = fixture()
        inputs['filter_capacitance'] = (1e100, 1e100)
        inputs['initial_error'] = (0, 0)
        with self.assertRaises(ValueError):
            calculate(inputs)

    def test_every_output_is_ordered(self):
        for low, high, unit in calculate(fixture()).values():
            self.assertLessEqual(low, high, unit)

    def test_mean_and_pointwise_contracts_are_separate(self):
        inputs = fixture()
        baseline = calculate(inputs)
        inputs['cycle_mean_residual_error'] = (0, .03)
        result = calculate(inputs)
        self.assertLess(result['offset_margin'][0], 0)
        self.assertEqual(result['amplitude_margin'], baseline['amplitude_margin'])
        inputs = fixture()
        inputs['pointwise_residual_error'] = (0, .03)
        result = calculate(inputs)
        self.assertLess(result['amplitude_margin'][0], 0)
        self.assertEqual(result['offset_margin'], baseline['offset_margin'])

    def test_input_is_read_only(self):
        inputs = fixture()
        original = dict(inputs)
        calculate(inputs)
        self.assertEqual(inputs, original)


def quantities():
    units = MODULE.INPUT_UNITS['sampled_waveform_envelope']
    return {key: {'min': low, 'max': high, 'unit': units[key], 'basis': 'ENGINEERING_DEFAULT',
                  'conditions': {}, 'note': 'Synthetic operating bound.'}
            for key, (low, high) in fixture().items()}


class WaveformDispatchTests(unittest.TestCase):
    def test_selected_component_and_parameter_refs_are_live(self):
        inputs = quantities()
        inputs['isolation_resistance'] = {'component': 'R', 'parameter': 'resistance'}
        inputs['cycle_mean_residual_error'] = {'parameter': 'mean_error'}
        parameters = {'mean_error': quantities()['cycle_mean_residual_error']}
        parts = {'R': {'parameters': {'resistance': quantities()['isolation_resistance']}}}
        limit = {'value': 0, 'unit': 'V', 'basis': 'ENGINEERING_DEFAULT', 'conditions': {}}
        check = {'calculator': 'sampled_waveform_envelope', 'inputs': inputs,
                 'require': {'output': 'offset_margin', 'operator': 'GE', 'limit': limit}}
        self.assertEqual(evaluate_check(check, parameters, parts)['result'], 'PASS')
        parts['R']['parameters']['resistance'].update(min=118.8, max=121.2)
        self.assertEqual(evaluate_check(check, parameters, parts)['result'], 'FAIL')
        parts['R']['parameters']['resistance'] = quantities()['isolation_resistance']
        parameters['mean_error']['max'] = .03
        self.assertEqual(evaluate_check(check, parameters, parts)['result'], 'FAIL')

    def test_unknown_wrong_unit_and_numeric_domain_refuse(self):
        for replacement in ({'status': 'UNKNOWN'}, {'value': 1, 'unit': 'A'},
                            {'value': float('nan'), 'unit': 'V'}):
            inputs = quantities()
            inputs['amplitude'] = replacement
            with self.assertRaises(CalculationError):
                dispatch('sampled_waveform_envelope', inputs)
        inputs = quantities()
        inputs['filter_capacitance'].update(min=1e100, max=1e100)
        with self.assertRaises(CalculationError):
            dispatch('sampled_waveform_envelope', inputs)


if __name__ == '__main__':
    unittest.main()
