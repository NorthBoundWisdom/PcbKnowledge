"""Conditional interval checks for DAC feedback and voltage supervision.

Initial component bounds and declared temperature coefficients remain distinct.
Exact decimal-input arithmetic and outward conversion preserve enclosures.
"""
from __future__ import annotations

import itertools
import math
from fractions import Fraction

INPUT_UNITS = {
    'dac_feedback_injection': {
        'top_resistance': 'ohm', 'bottom_resistance': 'ohm', 'injection_resistance': 'ohm',
        'reference_voltage': 'V', 'feedback_bias': 'A', 'target_voltage': 'V',
        'dac_usable_voltage': 'V', 'dac_error': 'V',
        'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
    },
    'supervisor_divider_threshold': {
        'top_resistance': 'ohm', 'bottom_resistance': 'ohm', 'threshold_voltage': 'V',
        'input_leakage': 'A', 'allowed_voltage': 'V', 'monitored_voltage': 'V',
        'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
    },
}


def resistance_bounds(bounds, name):
    """Extend initial bounds without inventing a nominal resistance.

    The maximum initial resistance times TCR and temperature excursion is a
    conservative additive allowance on each side of the initial interval.
    """
    low, high = bounds[name]
    if low <= 0:
        raise ValueError('Positive resistance required: ' + name)
    delta = high * bounds['tcr_magnitude'][1] * bounds['temperature_excursion'][1]
    if low - delta <= 0:
        raise ValueError('Thermal resistance interval crosses zero')
    return low - delta, high + delta


def feedback_intervals(bounds, top, bottom):
    injection = resistance_bounds(bounds, 'injection_resistance')
    if bounds['reference_voltage'][0] <= 0 or bounds['target_voltage'][0] <= 0:
        raise ValueError('Positive feedback reference and target required')
    corners = itertools.product(bounds['reference_voltage'], top, bottom, injection,
                                bounds['target_voltage'], (-1, 1))
    values = [reference * (1 + rt / rb + rt / rd) * rd / rt - output * rd / rt
              + sign * bounds['feedback_bias'][1] * rd
              for reference, rt, rb, rd, output, sign in corners]
    low, high = min(values), max(values)
    error = bounds['dac_error'][1]
    usable = bounds['dac_usable_voltage']
    lower = low - error - usable[0]
    upper = usable[1] - high - error
    return {
        'required_dac_voltage': (low, high, 'V'),
        'dac_range_margin': (min(lower, upper), max(lower, upper), 'V'),
        'feedback_bias_output_error': (0, top[1] * bounds['feedback_bias'][1], 'V'),
    }


def supervisor_intervals(bounds, top, bottom):
    if bounds['threshold_voltage'][0] <= 0:
        raise ValueError('Positive threshold required')
    leakage = bounds['input_leakage'][1]
    corners = itertools.product(top, bottom, bounds['threshold_voltage'], (-1, 1))
    values = [voltage * (1 + rt / rb) + sign * leakage * rt
              for rt, rb, voltage, sign in corners]
    low, high = min(values), max(values)
    allowed = bounds['allowed_voltage']
    lower, upper = low - allowed[0], allowed[1] - high
    voltage = bounds['monitored_voltage']
    return {
        'threshold_voltage': (low, high, 'V'),
        'threshold_margin': (min(lower, upper), max(lower, upper), 'V'),
        'divider_load': (voltage[0] / (top[1] + bottom[1]) - leakage,
                         voltage[1] / (top[0] + bottom[0]) + leakage, 'A'),
    }


def outward_results(raw):
    result = {}
    for key, (low, high, unit) in raw.items():
        lo, hi = float(low), float(high)
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError('Nonfinite envelope result')
        if Fraction(lo) > low:
            lo = math.nextafter(lo, -math.inf)
        if Fraction(hi) < high:
            hi = math.nextafter(hi, math.inf)
        if not math.isfinite(lo) or not math.isfinite(hi):
            raise ValueError('Outward interval exceeds finite range')
        result[key] = (lo, hi, unit)
    return result


def calculate(name, bounds):
    exact = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    top = resistance_bounds(exact, 'top_resistance')
    bottom = resistance_bounds(exact, 'bottom_resistance')
    if name == 'dac_feedback_injection':
        raw = feedback_intervals(exact, top, bottom)
    elif name == 'supervisor_divider_threshold':
        raw = supervisor_intervals(exact, top, bottom)
    else:
        raise ValueError('Unknown envelope calculator: ' + name)
    return outward_results(raw)
