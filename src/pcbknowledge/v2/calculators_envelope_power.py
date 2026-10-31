"""Signed FCCM and local-load checks under explicit operating budgets."""
from __future__ import annotations

from decimal import Decimal, localcontext, ROUND_CEILING, ROUND_FLOOR
from fractions import Fraction

from .calculators_envelope import resistance_bounds, outward_results

INPUT_UNITS = {
    'monitor_input_load': {
        'monitored_voltage': 'V', 'input_bias_each': 'A', 'bus_input_resistance': 'ohm',
        'forward_budget': 'A', 'reverse_budget': 'A',
    },
    'control_rail_budget': {
        'supply_voltage': 'V', **{f'preload_{i}': 'ohm' for i in range(1, 5)},
        **{key: 'A' for key in ('mcu_current', 'dac_current', 'monitor_current', 'led_current',
                               'i2c_current', 'enable_current', 'other_current', 'total_budget', 'minimum_load')},
        'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
    },
    'fccm_buck_with_local_loads': {
        'input_voltage': 'V', 'output_voltage': 'V', 'external_current': 'A', 'frequency': 'Hz',
        'inductance': 'H', 'effective_inductance': 'H', 'bleed_resistance': 'ohm', 'top_resistance': 'ohm',
        'reference_voltage': 'V', 'hardware_gate_load_budget': 'A', 'monitor_load_budget': 'A',
        'monitor_reverse_load_budget': 'A', 'hardware_gate_reverse_load_budget': 'A',
        'injection_resistance': 'ohm', 'dac_usable_voltage': 'V', 'dac_error': 'V', 'feedback_bias': 'A',
        'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
        'current_magnitude_limit': 'A', 'total_average_limit': 'A',
        **{f'output_capacitor_{i}': 'F' for i in range(1, 6)},
        **{f'input_capacitor_{i}': 'F' for i in range(1, 4)},
        'retained_capacitance_fraction': '1', 'positive_capacitance_factor': '1',
        'output_capacitance_window': 'F', 'input_capacitance_minimum': 'F',
        'discharge_initial_voltage': 'V', 'discharge_final_voltage': 'V', 'discharge_time_limit': 's',
    },
}


def sqrt_bounds(value):
    with localcontext() as context:
        context.prec = 80
        context.rounding = ROUND_FLOOR
        lower = (Decimal(value.numerator) / Decimal(value.denominator)).sqrt().next_minus()
        context.rounding = ROUND_CEILING
        upper = (Decimal(value.numerator) / Decimal(value.denominator)).sqrt().next_plus()
        return max(Fraction(0), Fraction(lower)), Fraction(upper)


def log_upper(value):
    with localcontext() as context:
        context.prec = 80
        context.rounding = ROUND_CEILING
        quotient = Decimal(value.numerator) / Decimal(value.denominator)
        return Fraction(quotient.ln().next_plus())


def monitor_load(bounds):
    voltage, bias, resistance, forward, reverse = (bounds[key] for key in INPUT_UNITS['monitor_input_load'])
    if resistance[0] <= 0:
        raise ValueError('Positive monitor resistance required')
    low = -2 * bias[1]
    high = 2 * bias[1] + voltage[1] / resistance[0]
    return {
        'input_current': (low, high, 'A'),
        'forward_margin': (forward[0] - high, forward[1] - low, 'A'),
        'reverse_margin': (reverse[0] + low, reverse[1] + high, 'A'),
    }


def control_budget(bounds):
    voltage = bounds['supply_voltage']
    if voltage[0] <= 0:
        raise ValueError('Positive control voltage required')
    resistors = [resistance_bounds(bounds, f'preload_{i}') for i in range(1, 5)]
    preload = (sum(voltage[0] / value[1] for value in resistors),
               sum(voltage[1] / value[0] for value in resistors))
    names = ('mcu_current', 'dac_current', 'monitor_current', 'led_current',
             'i2c_current', 'enable_current', 'other_current')
    total = tuple(preload[i] + sum(bounds[key][i] for key in names) for i in (0, 1))
    budget, minimum = bounds['total_budget'], bounds['minimum_load']
    return {
        'preload_current': (*preload, 'A'), 'total_current': (*total, 'A'),
        'budget_margin': (budget[0] - total[1], budget[1] - total[0], 'A'),
        'minimum_load_margin': (preload[0] - minimum[1], preload[1] - minimum[0], 'A'),
        'preload_power_each_max': (0, max(voltage[1] ** 2 / value[0] for value in resistors), 'W'),
    }


def current_intervals(bounds):
    names = ('input_voltage', 'output_voltage', 'external_current', 'frequency', 'effective_inductance')
    vin, vout, current, frequency, inductance = (bounds[key] for key in names)
    if any(value[0] <= 0 for value in (vin, vout, frequency, inductance)) or vin[0] <= vout[1]:
        raise ValueError('Positive step-down voltage, frequency and inductance required')
    if not bounds['inductance'][0] <= inductance[1] <= bounds['inductance'][1]:
        raise ValueError('Effective inductance maximum must lie within selected initial component bounds')
    bleed = resistance_bounds(bounds, 'bleed_resistance')
    top = resistance_bounds(bounds, 'top_resistance')
    reference = bounds['reference_voltage']
    if reference[0] <= 0 or vout[0] <= reference[1]:
        raise ValueError('Positive feedback branch must draw from output throughout range')
    local = (vout[0] / bleed[1] + (vout[0] - reference[1]) / top[1]
             - bounds['monitor_reverse_load_budget'][1] - bounds['hardware_gate_reverse_load_budget'][1],
             vout[1] / bleed[0] + (vout[1] - reference[0]) / top[0]
             + bounds['hardware_gate_load_budget'][1] + bounds['monitor_load_budget'][1])
    average = (current[0] + local[0], current[1] + local[1])
    slope = lambda source, output: output * (1 - output / source)
    ripple_min = min(slope(vin[0], value) for value in vout) / (frequency[1] * inductance[1])
    interior = min(max(vin[1] / 2, vout[0]), vout[1])
    ripple_max = slope(vin[1], interior) / (frequency[0] * inductance[0])
    valley = (average[0] - ripple_max / 2, average[1] - ripple_min / 2)
    peak = (average[0] + ripple_min / 2, average[1] + ripple_max / 2)
    magnitude = max(abs(value) for value in valley + peak)
    average_max = max(abs(value) for value in average)
    rms = sqrt_bounds(average_max ** 2 + ripple_max ** 2 / 12)[1]
    root12 = sqrt_bounds(Fraction(12))
    return {
        'local_current': (*local, 'A'), 'total_average_current': (*average, 'A'),
        'ripple_current': (ripple_min, ripple_max, 'A'), 'valley_current': (*valley, 'A'),
        'peak_current': (*peak, 'A'), 'inductor_rms_current': (0, rms, 'A'),
        'output_capacitor_rms_current': (ripple_min / root12[1], ripple_max / root12[0], 'A'),
        'current_margin': (bounds['current_magnitude_limit'][0] - magnitude,
                           bounds['current_magnitude_limit'][1], 'A'),
        'average_margin': (bounds['total_average_limit'][0] - average[1],
                           bounds['total_average_limit'][1] - average[0], 'A'),
    }


def capacitance_intervals(bounds):
    retained, positive = bounds['retained_capacitance_fraction'], bounds['positive_capacitance_factor']
    if not 0 < retained[0] <= retained[1] <= 1 or positive[0] < 1:
        raise ValueError('Invalid effective capacitance factors')
    output = [bounds[f'output_capacitor_{i}'] for i in range(1, 6)]
    input_caps = [bounds[f'input_capacitor_{i}'] for i in range(1, 4)]
    if any(value[0] <= 0 for value in output + input_caps):
        raise ValueError('Positive selected capacitors required')
    minimum = sum(value[0] for value in output) * retained[0]
    maximum = sum(value[1] for value in output) * positive[1]
    input_minimum = sum(value[0] for value in input_caps) * retained[0]
    if maximum < minimum:
        raise ValueError('Inverted effective capacitance interval')
    window, required = bounds['output_capacitance_window'], bounds['input_capacitance_minimum']
    margins = (minimum - window[0], window[1] - maximum, input_minimum - required[1])
    return {
        'effective_output_capacitance': (minimum, maximum, 'F'),
        'effective_input_capacitance': (input_minimum, sum(x[1] for x in input_caps) * positive[1], 'F'),
        'capacitance_margin': (min(margins), max(margins), 'F'),
    }


def discharge_intervals(bounds, maximum_capacitance):
    initial, final = bounds['discharge_initial_voltage'], bounds['discharge_final_voltage']
    if initial[0] < bounds['output_voltage'][1]:
        raise ValueError('Discharge initial bound must cover the declared operating output')
    if final[0] <= 0 or initial[0] <= final[1]:
        raise ValueError('Discharge initial must exceed positive final voltage')
    bleed = resistance_bounds(bounds, 'bleed_resistance')
    top = resistance_bounds(bounds, 'top_resistance')
    injection = resistance_bounds(bounds, 'injection_resistance')
    # RB only shunts current away from output; omitting it encloses the source path.
    dac_maximum = bounds['dac_usable_voltage'][1] + bounds['dac_error'][1]
    source_current = (bounds['monitor_reverse_load_budget'][1]
                      + bounds['hardware_gate_reverse_load_budget'][1]
                      + bounds['feedback_bias'][1] + dac_maximum / (top[0] + injection[0]))
    equilibrium = bleed[1] * source_current
    if final[0] <= equilibrium:
        raise ValueError('Discharge target is unreachable with sustained source current')
    ratio = (initial[1] - equilibrium) / (final[0] - equilibrium)
    maximum = bleed[1] * maximum_capacitance * log_upper(ratio)
    limit = bounds['discharge_time_limit']
    return {
        'discharge_source_current': (0, source_current, 'A'),
        'discharge_equilibrium_voltage': (0, equilibrium, 'V'),
        'discharge_time': (0, maximum, 's'),
        'discharge_margin': (limit[0] - maximum, limit[1], 's'),
    }


def calculate(name, bounds):
    exact = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    if name == 'monitor_input_load':
        raw = monitor_load(exact)
    elif name == 'control_rail_budget':
        raw = control_budget(exact)
    elif name == 'fccm_buck_with_local_loads':
        raw = {**current_intervals(exact), **capacitance_intervals(exact)}
        raw.update(discharge_intervals(exact, raw['effective_output_capacitance'][1]))
    else:
        raise ValueError('Unknown envelope power calculator: ' + name)
    return outward_results(raw)
