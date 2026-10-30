"""G3 sensing-path DC models, with explicitly supplied engineering error budgets."""
from __future__ import annotations

import itertools
import math


INPUT_UNITS = {
    'ntc_divider': {'supply': 'V', 'resistance_25': 'ohm', 'beta': 'K', 'temperature': 'degC',
                    'upper_resistance': 'ohm', 'series_resistance': 'ohm', 'capacitance': 'F'},
    'ferrite_loss': {'supply': 'V', 'current': 'A', 'resistance': 'ohm', 'current_rating': 'A'},
    'tia_frontend': {'supply': 'V', 'reference_voltage': 'V', 'bias_top': 'ohm', 'bias_bottom': 'ohm',
                     'feedback_resistance': 'ohm', 'input_current': 'A', 'total_error': 'V', 'headroom': 'V'},
}
NOTES = {
    'ntc_divider': ('Beta approximation for the G3 15-35 degC scenario, not a guaranteed resistance curve. '
                    'NTC to ground; high-Z ADC after series-R/shunt-C with supplied effective C. '
                    'Excludes self-heating and ADC loading.'),
    'ferrite_loss': ('DC series resistance at supplied operating conditions; no AC attenuation or thermal model. '
                     'Current rating is an explicit limit, not a predicted operating current.'),
    'tia_frontend': ('Ideal positive-current-leaving-node TIA with unloaded reference divider, plus supplied '
                     'symmetric aggregate output-error budget and rail margin. These assumptions do not establish '
                     'stability or a guaranteed device error.'),
}


def positive(b, *names):
    if any(b[name][0] <= 0 for name in names):
        raise ValueError('Positive bounds required for ' + ', '.join(names))


def ntc_divider(b):
    """Vishay application note 29053 Eq1: R=R25*exp(B*(1/T-1/298.15)).

    https://www.vishay.com/docs/29053/ntcappnote.pdf
    Beta dependence reverses at 25 degC; use corners, not a fixed Beta ordering.
    NTC dissipation V^2*R/(Ru+R)^2 peaks at R=Ru, possibly inside the interval.
    The 15-35 degC guard is the selected G3 model domain, not a vendor accuracy claim.
    """
    positive(b, 'supply', 'resistance_25', 'beta', 'upper_resistance', 'capacitance')
    supply, nominal, beta, temperature, upper, series, cap = (b[key] for key in INPUT_UNITS['ntc_divider'])
    if temperature[0] < 15 or temperature[1] > 35:
        raise ValueError('NTC Beta model is limited to the G3 15-35 degC scenario')
    values = [r * math.exp(beta_value * (1 / (t + 273.15) - 1 / 298.15))
              for r, beta_value, t in itertools.product(nominal, beta, temperature)]
    sensor = (min(values), max(values))
    output = (supply[0] * sensor[0] / (upper[1] + sensor[0]),
               supply[1] * sensor[1] / (upper[0] + sensor[1]))
    equivalent = tuple(series[i] + upper[i] * sensor[i] / (upper[i] + sensor[i]) for i in (0, 1))
    time = tuple(equivalent[i] * cap[i] for i in (0, 1))
    peak_r = min(max(upper[0], sensor[0]), sensor[1])
    maximum_power = supply[1]**2 * peak_r / (upper[0] + peak_r)**2
    return {'sensor_resistance': (*sensor, 'ohm'), 'output_voltage': (*output, 'V'),
            'pole_frequency': (1 / (2 * math.pi * time[1]), 1 / (2 * math.pi * time[0]), 'Hz'),
            'max_sensor_power': (maximum_power, maximum_power, 'W')}


def ferrite_loss(b):
    positive(b, 'supply', 'current_rating')
    supply, current, resistance, rating = (b[key] for key in INPUT_UNITS['ferrite_loss'])
    drop = tuple(current[i] * resistance[i] for i in (0, 1))
    if supply[0] <= drop[1]:
        raise ValueError('Ferrite loss consumes the available supply')
    return {'voltage_drop': (*drop, 'V'), 'output_voltage': (supply[0] - drop[1], supply[1] - drop[0], 'V'),
            'power': (current[0]**2 * resistance[0], current[1]**2 * resistance[1], 'W'),
            'current_margin': (rating[0] - current[1], rating[1] - current[0], 'A')}


def tia_frontend(b):
    positive(b, 'supply', 'reference_voltage', 'bias_top', 'bias_bottom', 'feedback_resistance')
    supply, reference, top, bottom, feedback, current, error, headroom = (
        b[key] for key in INPUT_UNITS['tia_frontend'])
    if 2 * headroom[1] >= supply[0]:
        raise ValueError('Rail margins must leave a nonempty output interval')
    bias = (reference[0] * bottom[0] / (top[1] + bottom[0]),
             reference[1] * bottom[1] / (top[0] + bottom[1]))
    ideal = tuple(bias[i] + current[i] * feedback[i] for i in (0, 1))
    output = (ideal[0] - error[1], ideal[1] + error[1])
    return {'bias_voltage': (*bias, 'V'), 'ideal_output_voltage': (*ideal, 'V'),
            'output_voltage': (*output, 'V'),
            'low_headroom_margin': (output[0] - headroom[1], output[1] - headroom[0], 'V'),
            'high_headroom_margin': (supply[0] - headroom[1] - output[1],
                                      supply[1] - headroom[0] - output[0], 'V')}


def calculate(name, b):
    return {'ntc_divider': ntc_divider, 'ferrite_loss': ferrite_loss, 'tia_frontend': tia_frontend}[name](b)
