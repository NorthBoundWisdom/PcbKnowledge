"""Hand-derived G2 drive and TPS5430 operating-point calculator regressions."""
import math
import unittest

from pcbknowledge.v2.calculators import CalculationError, calculate, evaluate_check
from tests.git_native.test_v2_power_calculators import q, interval


def relay():
    return {'channels': q(2, '1'), 'collector_current': q(.1, 'A'), 'collector_drop': q(2, 'V'),
            'input_current': q(.001, 'A'), 'logic_voltage': q(3.3, 'V'),
            'coil_inductance': q(.1, 'H'), 'switching_frequency': q(10, 'Hz'),
            'ambient': q(40, 'degC'), 'thermal_resistance': q(100, 'degC/W')}


def gpio():
    return {'supply': interval(3.17, 3.44, 'V'), 'high_drop': interval(0, .4, 'V'),
            'load_current': interval(0, .001, 'A'), 'series_resistance': q(10, 'ohm'),
            'pulldown_resistance': q(10000, 'ohm'), 'source_current_rating': q(.008, 'A'),
            'high_threshold': q(2.7, 'V')}


def filter_inputs():
    return {'inductance': interval(80e-6, 120e-6, 'H'), 'capacitance': interval(176e-6, 264e-6, 'F'),
            'output_voltage': interval(3.17, 3.44, 'V'), 'capacitor_esr_max': q(.016, 'ohm'),
            'capacitor_esr_factor': q(2, '1'), 'series_resistance_a': interval(.099, .101, 'ohm'),
            'series_resistance_b': interval(.099, .101, 'ohm')}


def converter():
    return {'input_voltage': interval(6, 12, 'V'), 'output_voltage': interval(3.17, 3.44, 'V'),
            'output_current': q(.15, 'A'), 'frequency': interval(400000, 600000, 'Hz'),
            'inductance': interval(80e-6, 120e-6, 'H'), 'on_resistance': q(.23, 'ohm'),
            'diode_drop': interval(0, .5, 'V'), 'inductor_resistance': q(.2, 'ohm'),
            'ambient': q(40, 'degC'), 'thermal_resistance': q(50, 'degC/W'), 'uvlo_voltage': q(5.5, 'V')}


def switched_rl(vin, vout, current, frequency, inductance, ron, dcr, diode):
    """Independent exact exponential on/off balance with duty solved for mean load."""
    period = 1 / frequency
    a, b = (ron + dcr) / inductance, dcr / inductance
    on_equilibrium, off_equilibrium = (vin - vout) / (ron + dcr), -(vout + diode) / dcr
    def waveform(duty):
        ton, toff = duty * period, (1 - duty) * period
        eon, eoff = math.exp(-a * ton), math.exp(-b * toff)
        valley = (off_equilibrium * (1 - eoff)
                  + eoff * on_equilibrium * (1 - eon)) / (1 - eon * eoff)
        peak = on_equilibrium + (valley - on_equilibrium) * eon
        def integrals(eq, start, exponent, decay, time):
            delta = start - eq
            integral = eq * time + delta * (1 - exponent) / decay
            square = eq**2 * time + 2 * eq * delta * (1 - exponent) / decay
            square += delta**2 * (1 - exponent**2) / (2 * decay)
            return integral, square
        ion, ion2 = integrals(on_equilibrium, valley, eon, a, ton)
        ioff, ioff2 = integrals(off_equilibrium, peak, eoff, b, toff)
        return valley, peak, (ion + ioff) / period, ion / period, ion2 / period, (ion2 + ioff2) / period
    low, high = .0001, .9999
    for _ in range(65):
        middle = (low + high) / 2
        if waveform(middle)[2] < current:
            low = middle
        else:
            high = middle
    valley, peak, mean, input_mean, input_square, square = waveform((low + high) / 2)
    return {'duty_cycle': (low + high) / 2, 'valley_current': valley, 'peak_current': peak,
            'ripple_current': peak - valley, 'inductor_rms_current': math.sqrt(max(0, square)),
            'input_capacitor_rms_current': math.sqrt(max(0, input_square - input_mean**2)),
            'output_capacitor_rms_current': math.sqrt(max(0, square - mean**2))}


class DriverCalculationTests(unittest.TestCase):
    def test_relay_loss_includes_all_channels_and_full_coil_energy(self):
        result = calculate('darlington_driver', relay())
        # 2 * (.2 W collector + .0033 W input + .005 W magnetic energy/s).
        self.assertAlmostEqual(result['power']['max'], .4166)
        self.assertAlmostEqual(result['junction_temperature']['max'], 81.66)
        cold = {**relay(), 'ambient': q(-40, 'degC')}
        self.assertAlmostEqual(calculate('darlington_driver', cold)['junction_temperature']['max'], 1.66)

    def test_relay_domain_rejections_and_failed_thermal_requirement(self):
        for name, value in [('channels', q(1.5, '1')), ('channels', interval(1, 2, '1')),
                            ('channels', q(0, '1')), ('thermal_resistance', q(0, 'degC/W')),
                            ('collector_current', q(-.1, 'A')), ('coil_inductance', q(.1, 'F'))]:
            with self.subTest(name=name), self.assertRaises(CalculationError):
                calculate('darlington_driver', {**relay(), name: value})
        check = {'calculator': 'darlington_driver', 'inputs': relay(),
                 'require': {'output': 'junction_temperature', 'operator': 'LE', 'limit': q(80, 'degC')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')

    def test_gpio_loaded_divider_and_current_margin(self):
        result = calculate('gpio_drive', gpio())
        self.assertAlmostEqual(result['high_voltage']['min'], (3.17 - .4 - .001 * 10) / 1.001)
        self.assertGreater(result['high_margin']['min'], 0)
        self.assertAlmostEqual(result['source_current']['max'], .001 + 3.44 / 10010)
        direct = calculate('gpio_drive', {**gpio(), 'series_resistance': q(0, 'ohm')})
        self.assertAlmostEqual(direct['high_voltage']['min'], 2.77)

    def test_gpio_source_overload_and_low_voltage_are_visible(self):
        with self.assertRaises(CalculationError):
            calculate('gpio_drive', {**gpio(), 'source_current_rating': q(.001, 'A')})
        result = calculate('gpio_drive', {**gpio(), 'high_threshold': q(3, 'V')})
        self.assertLess(result['high_margin']['min'], 0)
        for field, value in [('pulldown_resistance', q(0, 'ohm')), ('supply', q(.1, 'V')),
                             ('source_current_rating', q(0, 'A'))]:
            with self.subTest(field=field), self.assertRaises(CalculationError):
                calculate('gpio_drive', {**gpio(), field: value})

    def test_missing_or_typical_only_source_inputs_never_become_bounds(self):
        for calculator, inputs, key in [('darlington_driver', relay(), 'collector_drop'),
                                        ('gpio_drive', gpio(), 'high_drop'),
                                        ('tps5430_filter', filter_inputs(), 'capacitor_esr_max'),
                                        ('tps5430_ccm_design', converter(), 'frequency')]:
            for missing in ({'status': 'UNKNOWN'}, {'typ': 1, 'unit': inputs[key]['unit']}):
                with self.subTest(calculator=calculator), self.assertRaises(CalculationError):
                    calculate(calculator, {**inputs, key: missing})

    def test_gpio_datasheet_conditions_enforce_strict_voltage_and_current(self):
        drop = {**q(.4, 'V'), 'basis': 'DATASHEET', 'conditions':
                {'VDD_min': q(2.7, 'V'), 'VDD_max': q(3.6, 'V'), 'output_current': q(.008, 'A')}}
        good = {**gpio(), 'high_drop': drop}
        self.assertGreater(calculate('gpio_drive', good)['high_margin']['min'], 0)
        for name, value in [('supply', interval(2.7, 3.3, 'V')), ('supply', interval(3.1, 3.6, 'V')),
                            ('supply', q(3.8, 'V')), ('source_current_rating', q(.009, 'A')),
                            ('high_drop', {**drop, 'conditions': {}})]:
            with self.subTest(name=name), self.assertRaises(CalculationError):
                calculate('gpio_drive', {**good, name: value})

    def test_feedback_divider_tolerance_corners(self):
        inputs = {'reference_voltage': interval(1.196, 1.245, 'V'),
                  'upper_resistance': interval(9900, 10100, 'ohm'),
                  'lower_resistance': interval(5841, 5959, 'ohm')}
        result = calculate('feedback_divider', inputs)['output_voltage']
        self.assertAlmostEqual(result['min'], 1.196 * (1 + 9900 / 5959))
        self.assertAlmostEqual(result['max'], 1.245 * (1 + 10100 / 5841))
        with self.assertRaises(CalculationError):
            calculate('feedback_divider', {**inputs, 'lower_resistance': q(0, 'ohm')})


    def test_four_actual_feedback_resistors_determine_output_bounds(self):
        inputs = {'reference_voltage': interval(1.196, 1.245, 'V'),
                  'upper_resistance': interval(9900, 10100, 'ohm'),
                  'lower_resistance': interval(9900, 10100, 'ohm'),
                  'series_resistance_a': interval(9900, 10100, 'ohm'),
                  'series_resistance_b': interval(4653, 4747, 'ohm')}
        result = calculate('feedback_parallel_divider', inputs)
        lower_min = 9900 * (9900 + 4653) / (9900 + 9900 + 4653)
        lower_max = 10100 * (10100 + 4747) / (10100 + 10100 + 4747)
        self.assertAlmostEqual(result['lower_equivalent_resistance']['min'], lower_min)
        self.assertAlmostEqual(result['lower_equivalent_resistance']['max'], lower_max)
        self.assertAlmostEqual(result['output_voltage']['min'], 1.196 * (1 + 9900 / lower_max))
        self.assertAlmostEqual(result['output_voltage']['max'], 1.245 * (1 + 10100 / lower_min))
        self.assertGreater(result['output_voltage']['min'], 3.1)
        self.assertLess(result['output_voltage']['max'], 3.6)
        for key in ('upper_resistance', 'lower_resistance', 'series_resistance_a', 'series_resistance_b'):
            changed = calculate('feedback_parallel_divider', {**inputs, key: q(1000, 'ohm')})
            self.assertNotEqual(result['output_voltage'], changed['output_voltage'])
            with self.subTest(key=key), self.assertRaises(CalculationError):
                calculate('feedback_parallel_divider', {**inputs, key: q(0, 'ohm')})


class TPS5430CalculationTests(unittest.TestCase):
    def test_filter_correlated_ratio_and_esr_floor(self):
        result = calculate('tps5430_filter', filter_inputs())
        self.assertAlmostEqual(result['crossover_frequency']['min'], 1 / (3357 * 120e-6 * 264e-6 * 3.44))
        self.assertAlmostEqual(result['zero_to_crossover_ratio']['min'],
                               3357 * 80e-6 * 3.17 / (2 * math.pi * .0825))
        self.assertLess(result['esr_zero_frequency']['max'], 24000)
        for key, value in [('series_resistance_a', q(0, 'ohm')), ('inductance', q(1e-6, 'H')),
                           ('capacitor_esr_max', q(1, 'ohm')), ('capacitance', q(.1, 'F'))]:
            with self.subTest(key=key), self.assertRaises(CalculationError):
                calculate('tps5430_filter', {**filter_inputs(), key: value})

    def test_actual_parallel_esr_components_and_source_factor_are_bound(self):
        inputs = {**filter_inputs(), 'inductance': interval(56e-6, 120e-6, 'H'),
                  'capacitance': interval(144e-6, 216e-6, 'F')}
        result = calculate('tps5430_filter', inputs)
        self.assertAlmostEqual(result['total_esr']['min'], .0495)
        self.assertAlmostEqual(result['total_esr']['max'], .0505 + .016 * 2)
        self.assertGreater(result['zero_to_crossover_ratio']['min'], 1)
        self.assertLess(result['esr_zero_frequency']['max'], 24000)
        for key in ('series_resistance_a', 'series_resistance_b'):
            changed = calculate('tps5430_filter', {**inputs, key: interval(.08, .09, 'ohm')})
            self.assertNotEqual(result['total_esr'], changed['total_esr'])
        with self.assertRaises(CalculationError):
            calculate('tps5430_filter', {**inputs, 'capacitor_esr_factor': q(.5, '1')})
        with self.assertRaises(CalculationError):
            calculate('tps5430_filter', {**inputs, 'capacitor_esr_factor': q(20, '1')})

    def test_ccm_source_equations_at_specified_full_load_only(self):
        result = calculate('tps5430_ccm_design', converter())
        self.assertAlmostEqual(result['power']['max'], .15**2 * .23 * 3.44 / 6 + 12 * .15 * .01 + 12 * .01)
        self.assertAlmostEqual(result['output_headroom']['min'], .87 * (6 - result['peak_current']['max'] * .23 + .5) - .15 * .2 - .5 - 3.44)
        self.assertAlmostEqual(result['junction_temperature']['max'], 40 + result['power']['max'] * 50)
        self.assertIn('supplied CCM operating point', result['power']['note'])
        for load in (0, .001):
            with self.subTest(load=load), self.assertRaises(CalculationError):
                calculate('tps5430_ccm_design', {**converter(), 'output_current': q(load, 'A')})

    def test_nonideal_bounds_enclose_exponential_waveforms_and_interior_cases(self):
        inputs = {**converter(), 'input_voltage': interval(6.3, 12, 'V'),
                  'on_resistance': interval(.1, .23, 'ohm'),
                  'inductor_resistance': interval(.1, .4, 'ohm'), 'diode_drop': interval(.2, .5, 'V')}
        result = calculate('tps5430_ccm_design', inputs)
        for vin in (6.3, 9, 12):
            for vout in (3.17, 3.3, 3.44):
                for frequency in (400000, 500000, 600000):
                    for inductance in (80e-6, 100e-6, 120e-6):
                        for ron, dcr, diode in ((.1, .1, .2), (.23, .4, .5), (.17, .25, .35)):
                            actual = switched_rl(vin, vout, .15, frequency, inductance, ron, dcr, diode)
                            self.assertGreater(actual['valley_current'], 0)
                            for name, value in actual.items():
                                self.assertLessEqual(result[name]['min'], value + 1e-8, (name, actual))
                                self.assertGreaterEqual(result[name]['max'], value - 1e-8, (name, actual))

    def test_positive_ideal_valley_does_not_establish_nonideal_ccm(self):
        inputs = {**converter(), 'input_voltage': q(12, 'V'), 'output_voltage': q(3.3, 'V'),
                  'output_current': q(.04, 'A'), 'frequency': q(400000, 'Hz'),
                  'inductance': q(80e-6, 'H'), 'diode_drop': q(.5, 'V')}
        ideal = calculate('buck_inductor_ripple', {key: inputs[key] for key in
                          ('input_voltage', 'output_voltage', 'output_current', 'frequency', 'inductance')})
        self.assertGreater(ideal['valley_current']['min'], 0)
        actual = switched_rl(12, 3.3, .04, 400000, 80e-6, .23, .2, .5)
        self.assertLess(actual['valley_current'], 0)
        with self.assertRaises(CalculationError):
            calculate('tps5430_ccm_design', inputs)

    def test_56uh_tolerance_and_saturation_derating_retains_ccm_margin(self):
        inputs = {**converter(), 'inductance': interval(56e-6, 120e-6, 'H'),
                  'inductor_resistance': interval(0, .75, 'ohm')}
        result = calculate('tps5430_ccm_design', inputs)
        self.assertGreater(result['valley_current']['min'], 0)
        self.assertLess(result['peak_current']['max'], .81)

    def test_uvlo_and_on_time_use_actual_source_and_operating_inputs(self):
        result = calculate('tps5430_ccm_design', converter())
        self.assertAlmostEqual(result['input_min_margin']['min'], .5)
        self.assertAlmostEqual(result['on_time']['min'], result['duty_cycle']['min'] / 600000)
        self.assertGreater(result['on_time']['min'], 200e-9)
        with self.assertRaises(CalculationError):
            calculate('tps5430_ccm_design', {**converter(), 'uvlo_voltage': q(6.1, 'V')})

    def test_output_ripple_recomputes_nonideal_current_and_actual_esr_network(self):
        inputs = {**converter(), **filter_inputs()}
        switching = calculate('tps5430_ccm_design', {key: inputs[key] for key in converter()})
        output_filter = calculate('tps5430_filter', {key: inputs[key] for key in filter_inputs()})
        result = calculate('tps5430_output_ripple', inputs)
        delta = switching['ripple_current']['max']
        self.assertAlmostEqual(result['output_ripple']['max'],
                               delta / (400000 * 176e-6) + delta * output_filter['total_esr']['max'])
        for key, quantity in [('inductance', interval(70e-6, 100e-6, 'H')),
                              ('diode_drop', interval(0, 1, 'V')),
                              ('series_resistance_a', q(.08, 'ohm'))]:
            changed = calculate('tps5430_output_ripple', {**inputs, key: quantity})
            self.assertNotEqual(result['output_ripple']['max'], changed['output_ripple']['max'])
        with self.assertRaises(CalculationError):
            calculate('tps5430_output_ripple', {**inputs, 'output_current': q(0, 'A')})

    def test_zero_rds_lower_bound_and_input_current_budget(self):
        inputs = {**converter(), 'on_resistance': interval(0, .46, 'ohm')}
        result = calculate('tps5430_ccm_design', inputs)
        self.assertAlmostEqual(result['input_current']['max'], .15 * 1.01 + .01)
        self.assertLess(result['input_current']['max'], .2)
        self.assertAlmostEqual(result['power']['min'], 6 * .15 * .01 + 6 * .01)
        for resistance in (0, .23, .46):
            point = calculate('tps5430_ccm_design', {**inputs, 'on_resistance': q(resistance, 'ohm')})
            self.assertLessEqual(result['power']['min'], point['power']['min'])
            self.assertGreaterEqual(result['power']['max'], point['power']['max'])
            self.assertLessEqual(result['output_headroom']['min'], point['output_headroom']['min'])
        with self.assertRaises(CalculationError):
            calculate('tps5430_ccm_design', {**inputs, 'on_resistance': interval(-.01, .46, 'ohm')})

    def test_source_rds_test_conditions_cannot_be_silently_extrapolated(self):
        for conditions in ({'input_voltage': q(12, 'V')}, {'gate_voltage': q(4.5, 'V')}):
            resistance = {**q(.23, 'ohm'), 'basis': 'DATASHEET', 'conditions': conditions}
            with self.subTest(conditions=conditions), self.assertRaises(CalculationError):
                calculate('tps5430_ccm_design', {**converter(), 'on_resistance': resistance})

    def test_ccm_temperature_threshold_can_fail(self):
        check = {'calculator': 'tps5430_ccm_design', 'inputs': converter(),
                 'require': {'output': 'junction_temperature', 'operator': 'LE', 'limit': q(40, 'degC')}}
        self.assertEqual(evaluate_check(check, {})['result'], 'FAIL')
