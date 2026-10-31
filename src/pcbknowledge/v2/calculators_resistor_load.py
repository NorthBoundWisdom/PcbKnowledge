"""Worst-case rail loading of one or two explicit resistive branches.

Zero downstream voltage conservatively bounds LED and asserted pull-up loading.
The zero current lower bound is not a proof of minimum rail load.
"""
from fractions import Fraction

from .calculators_envelope import outward_results, resistance_bounds

COMMON_UNITS = {
    'supply': 'V', 'allocation': 'A', 'tcr_magnitude': '1/degC',
    'temperature_excursion': 'degC', 'resistance_1': 'ohm',
}
INPUT_UNITS = {
    'single_resistor_load': dict(COMMON_UNITS),
    'dual_resistor_load': {**COMMON_UNITS, 'resistance_2': 'ohm'},
}


def calculate(name, bounds):
    if name not in INPUT_UNITS:
        raise ValueError('Unknown resistor-load calculator')
    b = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    if b['supply'][0] <= 0 or b['allocation'][0] not in (0, b['allocation'][1]):
        raise ValueError('Positive supply and zero-to-maximum or scalar allocation required')
    resistances = [resistance_bounds(b, 'resistance_1')]
    if name == 'dual_resistor_load':
        resistances.append(resistance_bounds(b, 'resistance_2'))
    maximum_current = sum(b['supply'][1] / resistance[0] for resistance in resistances)
    maximum_power = max(b['supply'][1] ** 2 / resistance[0] for resistance in resistances)
    return outward_results({
        'current': (0, maximum_current, 'A'),
        'allocation_margin': (b['allocation'][1] - maximum_current, b['allocation'][1], 'A'),
        'maximum_branch_power': (0, maximum_power, 'W'),
    })
