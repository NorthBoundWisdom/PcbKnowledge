"""Exact selected passive supply-path and dual/quad capacitor checks."""
from fractions import Fraction
from .calculators_envelope import outward_results, resistance_bounds

COMMON_UNITS = {
    'retained_lower_factor': '1', 'positive_upper_factor': '1', 'required_window': 'F',
}
INPUT_UNITS = {
    'four_preload_four_consumer_budget': {
        'supply_voltage': 'V', **{f'preload_{i}': 'ohm' for i in range(1, 5)},
        **{f'consumer_{i}': 'A' for i in range(1, 5)},
        'total_budget': 'A', 'minimum_load': 'A',
        'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
    },
    'triple_resistor_load_with_base': {
        'resistance_1': 'ohm', 'resistance_2': 'ohm', 'resistance_3': 'ohm',
        'supply': 'V', 'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
        'base_current': 'A', 'allocation': 'A',
    },
    'passive_supply_path': {
        'source_voltage': 'V', 'series_resistance': 'ohm', 'current': 'A',
        'distribution_drop': 'V', 'accepted_output_voltage': 'V',
        'current_limit': 'A', 'current_limit_factor': '1',
    },
    'dual_parallel_capacitance': {
        **COMMON_UNITS, 'capacitance_1': 'F', 'capacitance_2': 'F',
    },
    'quad_parallel_capacitance': {
        **COMMON_UNITS, **{f'capacitance_{i}': 'F' for i in range(1, 5)},
    },
}


def calculate(name, bounds):
    if name not in INPUT_UNITS or set(bounds) != set(INPUT_UNITS[name]):
        raise ValueError('Exact passive-path budget inputs required')
    b = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    if name == 'four_preload_four_consumer_budget':
        return four_consumer_budget(b)
    if name == 'triple_resistor_load_with_base':
        return triple_load(b)
    if name == 'passive_supply_path':
        return supply_path(b)
    if any(low <= 0 or high < low for low, high in b.values()):
        raise ValueError('Positive ordered capacitance inputs required')
    if b['retained_lower_factor'][1] > 1 or b['positive_upper_factor'][0] < 1:
        raise ValueError('Retention must not exceed unity; positive upper factor must be at least unity')
    names = [key for key in INPUT_UNITS[name] if key.startswith('capacitance_')]
    low = sum(b[key][0] for key in names) * b['retained_lower_factor'][0]
    high = sum(b[key][1] for key in names) * b['positive_upper_factor'][1]
    window = b['required_window']
    margins = low - window[0], window[1] - high
    return outward_results({
        'effective_capacitance': (low, high, 'F'),
        'window_margin': (min(margins), max(margins), 'F'),
    })


def supply_path(b):
    if any(low < 0 or high < low for low, high in b.values()):
        raise ValueError('Nonnegative ordered passive-path intervals required')
    if b['source_voltage'][0] <= 0 or b['accepted_output_voltage'][0] <= 0:
        raise ValueError('Positive supply and accepted output required')
    factor = b['current_limit_factor']
    if b['current_limit'][0] <= 0 or not 0 < factor[0] <= factor[1] <= 1:
        raise ValueError('Positive sourced current limit and derating factors in(0,1] required')
    effective_limit = tuple(b['current_limit'][i] * b['current_limit_factor'][i] for i in (0, 1))
    drop = tuple(b['current'][i] * b['series_resistance'][i]
                 + b['distribution_drop'][i] for i in (0, 1))
    output = b['source_voltage'][0] - drop[1], b['source_voltage'][1] - drop[0]
    if output[0] <= 0:
        raise ValueError('Loss envelope consumes the supply')
    accepted = b['accepted_output_voltage']
    margins = output[0] - accepted[0], accepted[1] - output[1]
    return outward_results({
        'output_voltage': (*output, 'V'), 'voltage_drop': (*drop, 'V'),
        'voltage_margin': (min(margins), max(margins), 'V'),
        'current_margin': (effective_limit[0] - b['current'][1],
                           effective_limit[1] - b['current'][0], 'A'),
        'series_power': (b['current'][0] ** 2 * b['series_resistance'][0],
                         b['current'][1] ** 2 * b['series_resistance'][1], 'W'),
    })


def triple_load(b):
    if any(low < 0 or high < low for low, high in b.values()):
        raise ValueError('Nonnegative ordered load intervals required')
    if b['supply'][0] <= 0 or b['allocation'][0] not in (0, b['allocation'][1]):
        raise ValueError('Positive supply and scalar/zero-to-max allocation required')
    if b['base_current'][0] not in (0, b['base_current'][1]):
        raise ValueError('Base current is a scalar or zero-to-max budget, not proven minimum')
    resistors = [resistance_bounds(b, f'resistance_{i}') for i in range(1, 4)]
    maximum = b['base_current'][1] + sum(b['supply'][1] / value[0] for value in resistors)
    power = max(b['supply'][1] ** 2 / value[0] for value in resistors)
    return outward_results({
        'current': (0, maximum, 'A'),
        'allocation_margin': (b['allocation'][1] - maximum, b['allocation'][1], 'A'),
        'maximum_branch_power': (0, power, 'W'),
    })


def four_consumer_budget(b):
    # Same exact physical-preload equations as the historical control_rail_budget;
    # consumer allocations deliberately contribute no proven minimum current.
    if any(low < 0 or high < low for low, high in b.values()):
        raise ValueError('Nonnegative ordered current-ledger inputs required')
    if b['supply_voltage'][0] <= 0 or b['total_budget'][0] <= 0:
        raise ValueError('Positive supply and current capacity required')
    resistors = [resistance_bounds(b, f'preload_{i}') for i in range(1, 5)]
    voltage = b['supply_voltage']
    preload = tuple(sum(voltage[i] / value[1-i] for value in resistors) for i in (0, 1))
    total = preload[1] + sum(b[f'consumer_{i}'][1] for i in range(1, 5))
    budget, required = b['total_budget'], b['minimum_load']
    return outward_results({
        'preload_current': (*preload, 'A'),
        'total_current': (preload[0], total, 'A'),
        'budget_margin': (budget[0] - total, budget[1] - preload[0], 'A'),
        'minimum_load_margin': (preload[0] - required[1], preload[1] - required[0], 'A'),
        'preload_power_each_max': (0, max(voltage[1] ** 2 / value[0] for value in resistors), 'W'),
    })
