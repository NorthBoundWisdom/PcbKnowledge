import copy, unittest
from pcbknowledge.v2.calculators import calculate, evaluate_check, CalculationError

def q(v, u):
    return {'value': v, 'unit': u, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {},
        'note': 'Synthetic declared operating quantity.'}

def interval(a, b, u):
    return {'min': a, 'max': b, 'unit': u, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {},
        'note': 'Synthetic operating bounds.'}

def dac():
    return {'top_resistance': q(10000, 'ohm'), 'bottom_resistance': q(10000, 'ohm'),
        'injection_resistance': q(10000, 'ohm'), 'reference_voltage': q(1, 'V'), 'feedback_bias': q(0, 'A'),
            'target_voltage': q(1, 'V'), 'dac_usable_voltage': interval(0, 3, 'V'), 'dac_error': q(0, 'V'),
                'tcr_magnitude': q(0, '1/degC'), 'temperature_excursion': q(0, 'degC')}

def supervisor():
    return {'top_resistance': q(10000, 'ohm'), 'bottom_resistance': q(10000, 'ohm'), 'threshold_voltage': q(1,
        'V'), 'input_leakage': q(1e-06, 'A'), 'allowed_voltage': interval(1.9, 2.1, 'V'),
            'monitored_voltage': q(2, 'V'), 'tcr_magnitude': q(0, '1/degC'), 'temperature_excursion': q(0, 'degC')}

class EnvelopeTests(unittest.TestCase):

    def test_hand_calculated_injection_and_bias(self):
        x = dac()
        r = calculate('dac_feedback_injection', x)
        self.assertEqual(r['required_dac_voltage']['min'], 2)
        self.assertEqual(r['dac_range_margin']['min'], 1)
        x['feedback_bias'] = q(1e-06, 'A')
        r = calculate('dac_feedback_injection', x)
        self.assertAlmostEqual(r['required_dac_voltage']['min'], 1.99)
        self.assertAlmostEqual(r['required_dac_voltage']['max'], 2.01)

    def test_threshold_and_signed_leakage_load(self):
        r = calculate('supervisor_divider_threshold', supervisor())
        self.assertAlmostEqual(r['threshold_voltage']['min'], 1.99)
        self.assertAlmostEqual(r['threshold_voltage']['max'], 2.01)
        self.assertAlmostEqual(r['divider_load']['min'], 9.9e-05)
        self.assertAlmostEqual(r['divider_load']['max'], 0.000101)

    def test_leakage_mutation_changes_threshold_and_refuses_margin(self):
        x = supervisor()
        x.update(top_resistance=interval(68006.3625, 68193.6375, 'ohm'), bottom_resistance=interval(9986.25,
            10013.75, 'ohm'), threshold_voltage=interval(0.387, 0.4, 'V'), allowed_voltage=interval(3, 3.43,
                'V'), input_leakage=q(2.5e-08, 'A'))
        before = calculate('supervisor_divider_threshold', x)
        self.assertGreater(before['threshold_margin']['min'], 0)
        x['input_leakage'] = q(1e-06, 'A')
        after = calculate('supervisor_divider_threshold', x)
        self.assertNotEqual(before['threshold_voltage']['min'], after['threshold_voltage']['min'])
        self.assertLess(after['threshold_margin']['min'], 0)

    def test_actual_component_selection_resolves_each_time(self):
        x = dac()
        x['target_voltage'] = q(0.5, 'V')
        x['top_resistance'] = {'component': 'RT', 'parameter': 'resistance'}
        check = {'calculator': 'dac_feedback_injection', 'inputs': x,
            'require': {'output': 'dac_range_margin', 'operator': 'GE', 'limit': q(0, 'V')}}
        components = {'RT': {'parameters': {'resistance': q(10000, 'ohm')}}}
        a = evaluate_check(check, {}, components)
        components['RT']['parameters']['resistance'] = q(100, 'ohm')
        b = evaluate_check(check, {}, components)
        self.assertEqual(a['result'], 'PASS')
        self.assertEqual(b['result'], 'FAIL')

    def test_every_dac_input_changes_a_result(self):
        base = dac()
        base['target_voltage'] = q(0.5, 'V')
        base['tcr_magnitude'] = q(0.0001, '1/degC')
        base['temperature_excursion'] = q(15, 'degC')
        reference = calculate('dac_feedback_injection', base)
        for name in base:
            mutated = copy.deepcopy(base)
            if name == 'dac_usable_voltage':
                mutated[name] = interval(0.2, 2.8, 'V')
            else:
                mutated[name]['value'] = mutated[name]['value'] * 1.1 + 1e-06
            result = calculate('dac_feedback_injection', mutated)
            self.assertTrue(any(((r['min'], r['max']) != (reference[k]['min'], reference[k]['max']) for k,
                r in result.items())), name)

    def test_every_supervisor_input_changes_a_result(self):
        base = supervisor()
        base['tcr_magnitude'] = q(0.0001, '1/degC')
        base['temperature_excursion'] = q(15, 'degC')
        reference = calculate('supervisor_divider_threshold', base)
        for name in base:
            mutated = copy.deepcopy(base)
            if name == 'allowed_voltage':
                mutated[name] = interval(1.95, 2.05, 'V')
            else:
                mutated[name]['value'] = mutated[name]['value'] * 1.1 + 1e-06
            result = calculate('supervisor_divider_threshold', mutated)
            self.assertTrue(any(((r['min'], r['max']) != (reference[k]['min'], reference[k]['max']) for k,
                r in result.items())), name)

    def test_exact_cancellation_cannot_false_pass(self):
        x = dac()
        x.update(top_resistance=q(1, 'ohm'), bottom_resistance=q(1, 'ohm'), injection_resistance=q(1e+20,
            'ohm'), target_voltage=q(2, 'V'), dac_usable_voltage=interval(0, 0.5, 'V'))
        r = calculate('dac_feedback_injection', x)
        self.assertEqual(r['required_dac_voltage']['min'], 1)
        self.assertEqual(r['dac_range_margin']['min'], -0.5)

    def test_invalid_or_incomplete_inputs_refuse(self):
        for calc, inputs in [('dac_feedback_injection', dac()), ('supervisor_divider_threshold', supervisor())]:
            for name in inputs:
                for value in ({'status': 'UNKNOWN'}, q(float('nan'), inputs[name]['unit']), q(True,
                    inputs[name]['unit']), q(1, 'bogus')):
                    with self.subTest(calc=calc, name=name, value=value), self.assertRaises(CalculationError):
                        calculate(calc, {**inputs, name: value})
            with self.assertRaises(CalculationError):
                calculate(calc, {k: v for k, v in inputs.items() if k != 'top_resistance'})
            with self.assertRaises(CalculationError):
                calculate(calc, {**inputs, 'top_resistance': q(0, 'ohm')})

    def test_inverted_and_excessive_thermal_bounds_refuse(self):
        with self.assertRaises(CalculationError):
            calculate('dac_feedback_injection', {**dac(), 'target_voltage': interval(2, 1, 'V')})
        with self.assertRaises(CalculationError):
            calculate('dac_feedback_injection', {**dac(), 'tcr_magnitude': q(1, '1/degC'),
                'temperature_excursion': q(2, 'degC')})
if __name__ == '__main__':
    unittest.main()
