import copy, unittest, math
from pcbknowledge.v2.calculators import calculate, evaluate_check, CalculationError

def q(v, u):
    return {'value': v, 'unit': u, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {},
        'note': 'Synthetic declared operating quantity.'}

def interval(a, b, u):
    return {'min': a, 'max': b, 'unit': u, 'basis': 'ENGINEERING_DEFAULT', 'conditions': {},
        'note': 'Synthetic operating bounds.'}

def power():
    x = {'input_voltage': interval(10.8, 13.2, 'V'), 'output_voltage': interval(2.5, 6.1, 'V'),
        'external_current': interval(0, 0.5, 'A'), 'frequency': interval(464000.0, 696000.0, 'Hz'),
        'inductance': interval(3.76e-06, 5.64e-06, 'H'), 'effective_inductance': interval(3e-06, 5.64e-06,
        'H'), 'bleed_resistance': interval(990, 1010, 'ohm'), 'top_resistance': interval(29700, 30300, 'ohm'),
        'reference_voltage': interval(0.749, 0.787, 'V'), 'hardware_gate_load_budget': q(4e-05, 'A'),
        'monitor_load_budget': q(0.00014, 'A'), 'monitor_reverse_load_budget': q(0.0001, 'A'),
        'hardware_gate_reverse_load_budget': q(1.5e-08, 'A'), 'injection_resistance': interval(14850, 15150,
        'ohm'), 'dac_usable_voltage': interval(2.5 * 16 / 4096, 2.5 * 4031 / 4096, 'V'), 'dac_error': q(0.01,
        'V'), 'feedback_bias': q(1e-07, 'A'), 'tcr_magnitude': q(0.0001, '1/degC'),
        'temperature_excursion': q(15, 'degC'), 'current_magnitude_limit': q(2, 'A'),
        'total_average_limit': q(0.507, 'A'), 'retained_capacitance_fraction': q(0.5, '1'),
        'positive_capacitance_factor': q(1.15, '1'), 'output_capacitance_window': interval(2e-05, 6.8e-05,
        'F'), 'input_capacitance_minimum': q(1e-05, 'F'), 'discharge_initial_voltage': q(7.2, 'V'),
        'discharge_final_voltage': q(0.3, 'V'), 'discharge_time_limit': q(0.5, 's')}
    for prefix, count in [('output', 5), ('input', 3)]:
        for i in range(1, count + 1):
            x[f'{prefix}_capacitor_{i}'] = interval(9e-06, 1.1e-05, 'F')
    return x

def control():
    x = {'supply_voltage': interval(3.17, 3.43, 'V'), 'mcu_current': q(0.01, 'A'), 'dac_current': q(0.002,
        'A'), 'monitor_current': q(0.001, 'A'), 'led_current': q(3.43 / 988.5, 'A'), 'i2c_current': q(0.0015,
        'A'), 'enable_current': q(0.00075, 'A'), 'other_current': q(0.001, 'A'), 'total_budget': q(0.035,
        'A'), 'minimum_load': q(0.01, 'A'), 'tcr_magnitude': q(0.0001, '1/degC'),
        'temperature_excursion': q(15, 'degC')}
    for i in range(1, 5):
        x[f'preload_{i}'] = interval(990, 1010, 'ohm')
    return x

def monitor():
    return {'monitored_voltage': interval(2.5, 6.1, 'V'), 'input_bias_each': q(5e-05, 'A'),
        'bus_input_resistance': q(160000, 'ohm'), 'forward_budget': q(0.00014, 'A'),
        'reverse_budget': q(0.0001, 'A')}

class PowerEnvelopeTests(unittest.TestCase):

    def test_full_zero_to_half_amp_signed_fccm(self):
        r = calculate('fccm_buck_with_local_loads', power())
        self.assertGreater(r['total_average_current']['min'], 0.002)
        self.assertGreater(r['total_average_current']['max'], 0.5065)
        self.assertLess(r['valley_current']['min'], 0)
        self.assertGreater(r['peak_current']['max'], 1.685)
        for n in ['current_margin', 'average_margin', 'capacitance_margin', 'discharge_margin']:
            self.assertGreaterEqual(r[n]['min'], 0)
        self.assertAlmostEqual(r['effective_output_capacitance']['max'], 6.325e-05)
        equilibrium = 1011.515 * (0.0001 + 1.5e-08 + 1e-07 + (2.5 * 4031 / 4096 + 0.01) / (29654.55 + 14827.275))
        self.assertAlmostEqual(r['discharge_time']['max'],
            1011.515 * 6.325e-05 * math.log((7.2 - equilibrium) / (0.3 - equilibrium)))
        self.assertGreater(r['discharge_time']['max'], 0.2287)

    def test_sustained_reverse_current_makes_discharge_unreachable(self):
        with self.assertRaisesRegex(CalculationError, 'unreachable'):
            calculate('fccm_buck_with_local_loads', {**power(), 'monitor_reverse_load_budget': q(0.001, 'A')})

    def test_gate_reverse_budget_moves_active_lower_bounds(self):
        original = calculate('fccm_buck_with_local_loads', power())
        changed = calculate('fccm_buck_with_local_loads', {**power(),
            'hardware_gate_reverse_load_budget': q(1e-06, 'A')})
        self.assertLess(changed['local_current']['min'], original['local_current']['min'])
        self.assertLess(changed['valley_current']['min'], original['valley_current']['min'])

    def test_interior_ripple_maximum_is_not_endpoint_only(self):
        x = {**power(), 'input_voltage': interval(10, 14, 'V'), 'output_voltage': interval(4, 9, 'V'),
            'discharge_initial_voltage': q(10, 'V')}
        result = calculate('fccm_buck_with_local_loads', x)
        self.assertAlmostEqual(result['ripple_current']['max'], 3.5 / (464000.0 * 3e-06))

    def test_initial_discharge_must_cover_operating_output(self):
        with self.assertRaisesRegex(CalculationError, 'initial bound'):
            calculate('fccm_buck_with_local_loads', {**power(), 'discharge_initial_voltage': q(5, 'V')})

    def test_dcm_legacy_model_still_refuses(self):
        x = power()
        y = {k: x[k] for k in ('input_voltage', 'output_voltage', 'frequency', 'inductance')}
        y['output_current'] = interval(0, 0.5, 'A')
        with self.assertRaises(CalculationError):
            calculate('buck_inductor_ripple', y)

    def test_each_actual_capacitor_part_is_consumed(self):
        for prefix, count in [('output', 5), ('input', 3)]:
            for i in range(1, count + 1):
                x = power()
                x[f'{prefix}_capacitor_{i}'] = q(1e-12, 'F')
                r = calculate('fccm_buck_with_local_loads', x)
                self.assertLess(r['capacitance_margin']['min'], 0, (prefix, i))

    def test_current_limit_and_discharge_mutations_fail(self):
        for key, value, out in [('external_current', interval(0, 1, 'A'), 'current_margin'),
            ('monitor_load_budget', q(0.001, 'A'), 'average_margin'), ('discharge_initial_voltage', q(1000,
            'V'), 'discharge_margin'), ('positive_capacitance_factor', q(2, '1'), 'capacitance_margin')]:
            r = calculate('fccm_buck_with_local_loads', {**power(), key: value})
            self.assertLess(r[out]['min'], 0, key)

    def test_inductor_and_frequency_domain(self):
        for key, value in [('inductance', interval(8e-07, 1.2e-06, 'H')), ('inductance', interval(0.0008,
            0.0012, 'H')), ('frequency', q(0, 'Hz')), ('effective_inductance', q(0, 'H')), ('input_voltage',
            q(5, 'V')), ('discharge_final_voltage', q(8, 'V'))]:
            with self.subTest(key=key), self.assertRaises(CalculationError):
                calculate('fccm_buck_with_local_loads', {**power(), key: value})

    def test_control_physical_preloads_and_allocations(self):
        r = calculate('control_rail_budget', control())
        self.assertGreater(r['minimum_load_margin']['min'], 0)
        self.assertGreater(r['budget_margin']['min'], 0)
        for i in range(1, 5):
            x = control()
            x[f'preload_{i}'] = q(1000000000.0, 'ohm')
            self.assertLess(calculate('control_rail_budget', x)['minimum_load_margin']['min'], 0)
        for key in ['mcu_current', 'dac_current', 'monitor_current', 'led_current', 'i2c_current',
            'enable_current', 'other_current']:
            x = control()
            x[key] = q(0.04, 'A')
            self.assertLess(calculate('control_rail_budget', x)['budget_margin']['min'], 0, key)

    def test_monitor_bidirectional_bounds(self):
        r = calculate('monitor_input_load', monitor())
        self.assertEqual(r['input_current']['min'], -0.0001)
        self.assertAlmostEqual(r['input_current']['max'], 0.000138125)
        self.assertGreaterEqual(r['forward_margin']['min'], 0)
        self.assertGreaterEqual(r['reverse_margin']['min'], 0)
        for key, value, out in [('input_bias_each', q(0.0001, 'A'), 'forward_margin'),
            ('bus_input_resistance', q(1000, 'ohm'), 'forward_margin'), ('reverse_budget', q(1e-05, 'A'),
            'reverse_margin')]:
            self.assertLess(calculate('monitor_input_load', {**monitor(), key: value})[out]['min'], 0)

    def test_every_power_and_control_input_is_bound(self):
        for name, inputs in [('fccm_buck_with_local_loads', power()), ('control_rail_budget', control()),
            ('monitor_input_load', monitor())]:
            original = calculate(name, inputs)
            for key in inputs:
                changed = copy.deepcopy(inputs)
                for field in ('value', 'min', 'max'):
                    if field in changed[key]:
                        changed[key][field] *= 2
                try:
                    actual = calculate(name, changed)
                except CalculationError:
                    continue
                self.assertTrue(any(((v['min'], v['max']) != (original[k]['min'], original[k]['max']) for k,
                    v in actual.items())), (name, key))

    def test_all_new_inputs_strict_unknown_wrongunit_nonfinite(self):
        for name, inputs in [('fccm_buck_with_local_loads', power()), ('control_rail_budget', control()),
            ('monitor_input_load', monitor())]:
            for key in inputs:
                for bad in [q(float('inf'), inputs[key]['unit']), q(1, 'bogus'), {'status': 'UNKNOWN'}]:
                    with self.subTest(name=name, key=key), self.assertRaises(CalculationError):
                        calculate(name, {**inputs, key: bad})
if __name__ == '__main__':
    unittest.main()
