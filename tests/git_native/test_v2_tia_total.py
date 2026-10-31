"""Canonical total capacitance keeps the original loop equation and fail-closed inputs."""
import copy
import hashlib
import json
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate


def quantity(value, unit):
    return {'value': value, 'unit': unit}


def requested():
    return {'gain_bandwidth': quantity(1e6, 'Hz'), 'input_capacitance': quantity(100e-12, 'F'),
            'feedback_resistance': {'min': 9900, 'max': 10100, 'unit': 'ohm'},
            'feedback_capacitance': {'min': 95e-12, 'max': 105e-12, 'unit': 'F'}}


class TotalModelTests(unittest.TestCase):
    def test_single_part_meets_existing_phase_target_and_signal_bandwidth(self):
        inputs = requested()
        before = copy.deepcopy(inputs)
        result = calculate('tia_loop_total_capacitance', inputs)
        self.assertGreater(result['phase_margin']['min'], 45)
        self.assertGreater(result['feedback_pole']['min'], 1)
        self.assertAlmostEqual(result['phase_margin']['min'], 78.20733205493475)
        self.assertEqual(inputs, before)
        self.assertEqual(result['phase_margin']['inputs'], inputs)

    def test_public_calculator_rejects_historical_partial_and_mixed_shapes(self):
        old = requested()
        del old['feedback_capacitance']
        old.update({'feedback_capacitance_' + key: quantity(22e-12, 'F') for key in 'abcd'})
        for inputs in [old, {**old, 'feedback_capacitance': quantity(88e-12, 'F')},
                       {key: value for key, value in old.items() if not key.endswith('_d')}]:
            with self.assertRaises(CalculationError):
                calculate('tia_loop_total_capacitance', inputs)

    def test_total_capacitance_invalid_or_unknown_fails(self):
        for value in [quantity(0, 'F'), quantity(-1, 'F'), quantity(float('inf'), 'F'),
                      quantity(100, 'pF'), {'typ': 100e-12, 'unit': 'F'}, {'status': 'UNKNOWN'}]:
            with self.assertRaises(CalculationError):
                calculate('tia_loop_total_capacitance', {**requested(), 'feedback_capacitance': value})

    def test_old_id_exact_positive_negative_result_hashes(self):
        from pcbknowledge.v2.calculators import evaluate_check
        from tests.git_native.test_v2_tia_loop import inputs
        values = inputs()
        results = {'outputs': calculate('tia_loop_model', values)}
        for limit in (45, 89):
            results[str(limit)] = evaluate_check({'calculator': 'tia_loop_model', 'inputs': values,
                'require': {'output': 'phase_margin', 'operator': 'GE',
                            'limit': {'value': limit, 'unit': 'deg'}}}, {})
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(hashlib.sha256(canonical(results)).hexdigest(),
                         '9c87ab2cca05bcc31fc42de3ea9e55779681cacc6d70cdd91b43da9c17fea64a')
        self.assertEqual(results['45']['result'], 'PASS')
        self.assertEqual(results['89']['result'], 'FAIL')
        for bad in (requested(), {**values, 'feedback_capacitance': quantity(88e-12, 'F')},
                    {key: value for key, value in values.items() if not key.endswith('_d')}):
            with self.assertRaises(CalculationError):
                calculate('tia_loop_model', bad)
