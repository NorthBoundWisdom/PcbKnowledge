"""Steady-state fuse, reverse diode and input capacitor design model."""
from __future__ import annotations

INPUT_UNITS = {
    'input_protection': {
        'input_voltage': 'V', 'input_current': 'A', 'fuse_current_rating': 'A',
        'fuse_derating': '1', 'temperature_factor': '1', 'fuse_resistance': 'ohm',
        'diode_drop': 'V', 'diode_current_rating': 'A', 'diode_reverse_rating': 'V',
        'capacitor_voltage_rating': 'V', 'minimum_output_voltage': 'V',
        'ambient': 'degC', 'diode_thermal_resistance': 'degC/W',
        'diode_rating_temperature': 'degC',
    },
}


def calculate(name, b):
    if name != 'input_protection':
        raise ValueError('Unknown input protection calculator')
    for key in ('fuse_derating', 'temperature_factor'):
        if not 0 < b[key][0] <= b[key][1] <= 1:
            raise ValueError('Fuse derating factors must be in (0, 1]')
    for key in ('fuse_current_rating', 'diode_current_rating', 'diode_reverse_rating',
                'capacitor_voltage_rating', 'minimum_output_voltage', 'diode_thermal_resistance'):
        if b[key][0] <= 0:
            raise ValueError('Positive ratings and thermal resistance required')
    vi, current, resistance, drop = (b[key] for key in
                                    ('input_voltage', 'input_current', 'fuse_resistance', 'diode_drop'))
    output = (vi[0] - current[1] * resistance[1] - drop[1],
              vi[1] - current[0] * resistance[0] - drop[0])
    if output[0] <= 0:
        raise ValueError('Protection losses exceed the available input voltage')
    fuse, derating, temperature = (b[key] for key in
                                   ('fuse_current_rating', 'fuse_derating', 'temperature_factor'))
    hold = tuple(fuse[i] * derating[i] * temperature[i] for i in (0, 1))
    diode_power = tuple(current[i] * drop[i] for i in (0, 1))
    ambient, theta = b['ambient'], b['diode_thermal_resistance']
    junction = tuple(ambient[i] + diode_power[i] * theta[i] for i in (0, 1))
    # Reversing an input while its output capacitor remains charged adds the
    # two voltage magnitudes across the blocking diode. Bound charge by VINmax.
    reverse_stress = (0, 2 * vi[1])
    required, cap, diode, reverse, rating_temperature = (b[key] for key in
        ('minimum_output_voltage', 'capacitor_voltage_rating', 'diode_current_rating',
         'diode_reverse_rating', 'diode_rating_temperature'))
    return {
        'output_voltage': (*output, 'V'),
        'headroom': (output[0] - required[1], output[1] - required[0], 'V'),
        'fuse_hold_current': (*hold, 'A'),
        'fuse_current_margin': (hold[0] - current[1], hold[1] - current[0], 'A'),
        'capacitor_voltage_margin': (cap[0] - vi[1], cap[1] - vi[0], 'V'),
        'diode_current_margin': (diode[0] - current[1], diode[1] - current[0], 'A'),
        'diode_reverse_stress': (*reverse_stress, 'V'),
        'diode_reverse_margin': (reverse[0] - reverse_stress[1], reverse[1], 'V'),
        'fuse_power': (current[0]**2 * resistance[0], current[1]**2 * resistance[1], 'W'),
        'diode_power': (*diode_power, 'W'),
        'diode_junction_temperature': (*junction, 'degC'),
        'diode_derating_margin': (rating_temperature[0] - junction[1],
                                  rating_temperature[1] - junction[0], 'degC'),
    }
