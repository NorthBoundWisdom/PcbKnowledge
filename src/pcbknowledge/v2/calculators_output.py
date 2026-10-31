"""Exact series-shunt headroom with signed monitor loading."""
from fractions import Fraction

from .calculators_envelope import resistance_bounds, outward_results

INPUT_UNITS = {
    'output_shunt_budget': {
        'external_current': 'A', 'monitored_voltage': 'V', 'bias_current': 'A',
        'bus_input_resistance': 'ohm', 'attainable_voltage': 'V', 'required_voltage': 'V',
        'resistance': 'ohm', 'tcr_magnitude': '1/degC', 'temperature_excursion': 'degC',
        'sense_limit': 'V', 'power_rating': 'W',
    },
}


def calculate(name, bounds):
    if name != 'output_shunt_budget':
        raise ValueError('Unknown output calculator: ' + name)
    b = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    resistance = resistance_bounds(b, 'resistance')
    if b['bus_input_resistance'][0] <= 0 or b['required_voltage'][0] <= 0:
        raise ValueError('Positive bus resistance and required output voltage needed')
    if b['attainable_voltage'][0] <= 0 or b['monitored_voltage'][1] < b['required_voltage'][1]:
        raise ValueError('Voltage bounds do not cover required load voltage')
    if b['sense_limit'][0] <= 0 or b['power_rating'][0] <= 0:
        raise ValueError('Positive sense and resistor power ratings needed')
    current = (b['external_current'][0] - b['bias_current'][1],
               b['external_current'][1] + b['bias_current'][1]
               + b['monitored_voltage'][1] / b['bus_input_resistance'][0])
    products = [value * ohms for value in current for ohms in resistance]
    drop = min(products), max(products)
    needed = b['required_voltage'][0] + drop[0], b['required_voltage'][1] + drop[1]
    lower = needed[0] - b['attainable_voltage'][0]
    upper = b['attainable_voltage'][1] - needed[1]
    maximum_current = max(abs(value) for value in current)
    maximum_drop = max(abs(value) for value in drop)
    maximum_power = maximum_current ** 2 * resistance[1]
    return outward_results({
        'shunt_current': (*current, 'A'),
        'shunt_voltage': (*drop, 'V'),
        'required_pre_shunt_voltage': (*needed, 'V'),
        'target_margin': (min(lower, upper), max(lower, upper), 'V'),
        'sense_margin': (b['sense_limit'][0] - maximum_drop, b['sense_limit'][1], 'V'),
        'power': (0, maximum_power, 'W'),
        'power_margin': (b['power_rating'][0] - maximum_power, b['power_rating'][1], 'W'),
    })
