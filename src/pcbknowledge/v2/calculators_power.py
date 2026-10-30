"""First-principles interval models for continuous-current buck stages and passive losses."""
from __future__ import annotations

import math


BUCK_UNITS = {'input_voltage': 'V', 'output_voltage': 'V', 'output_current': 'A',
              'frequency': 'Hz', 'inductance': 'H'}
INPUT_UNITS = {
    'buck_inductor_ripple': BUCK_UNITS,
    'buck_output_ripple': {**BUCK_UNITS, 'capacitance': 'F', 'esr': 'ohm'},
    'mosfet_conduction_loss': {'rms_current': 'A', 'on_resistance': 'ohm'},
    'rc_time': {'resistance': 'ohm', 'capacitance': 'F'},
}


def _positive(b, *names):
    if any(b[name][0] <= 0 for name in names):
        raise ValueError('Positive bounds required for ' + ', '.join(names))


def buck_intervals(b):
    """Ideal fixed-frequency buck; integrate inductor voltage over one PWM period.

    Ripple is Vout*(1-Vout/Vin)/(f*L). Its maximum in Vout can be inside
    the supplied interval at Vin/2, rather than at an interval endpoint.
    """
    _positive(b, 'input_voltage', 'output_voltage', 'output_current', 'frequency', 'inductance')
    vi, vo, current, frequency, inductance = (b[key] for key in BUCK_UNITS)
    if vi[0] <= vo[1]:
        raise ValueError('Buck input must exceed output throughout the specified bounds')
    def slope(vin, vout):
        return vout * (1 - vout / vin)
    peak_voltage = min(max(vi[1] / 2, vo[0]), vo[1])
    minimum = min(slope(vi[0], endpoint) for endpoint in vo) / (frequency[1] * inductance[1])
    maximum = slope(vi[1], peak_voltage) / (frequency[0] * inductance[0])
    valley = (current[0] - maximum / 2, current[1] - minimum / 2)
    if valley[0] <= 0:
        raise ValueError('CCM model requires strictly positive inductor valley current; DCM is unsupported')
    duty = (vo[0] / vi[1], vo[1] / vi[0])
    duty_peak = min(max(.5, duty[0]), duty[1])
    input_rms_min = math.sqrt(current[0]**2 * min(d * (1 - d) for d in duty)
                              + duty[0] * minimum**2 / 12)
    input_rms_max = math.sqrt(current[1]**2 * duty_peak * (1-duty_peak) + duty[1] * maximum**2 / 12)
    return {
        'duty_cycle': (*duty, '1'),
        'ripple_current': (minimum, maximum, 'A'),
        'peak_current': (current[0] + minimum / 2, current[1] + maximum / 2, 'A'),
        'valley_current': (*valley, 'A'),
        'inductor_rms_current': (math.sqrt(current[0]**2 + minimum**2 / 12),
                                 math.sqrt(current[1]**2 + maximum**2 / 12), 'A'),
        'input_capacitor_rms_current': (input_rms_min, input_rms_max, 'A'),
        'output_capacitor_rms_current': (minimum / math.sqrt(12), maximum / math.sqrt(12), 'A'),
    }


def output_ripple(b):
    """Triangle-current charge integration plus an upper sum of ESR voltage ripple."""
    _positive(b, 'capacitance')
    result = buck_intervals(b)
    low, high, _ = result['ripple_current']
    frequency, capacitance, esr = (b[key] for key in ('frequency', 'capacitance', 'esr'))
    capacitive = (low / (8 * frequency[1] * capacitance[1]),
                  high / (8 * frequency[0] * capacitance[0]))
    resistive = (low * esr[0], high * esr[1])
    result.update(capacitive_ripple=(*capacitive, 'V'), esr_ripple=(*resistive, 'V'),
                  output_ripple=(max(capacitive[0], resistive[0]), capacitive[1] + resistive[1], 'V'))
    return result


def calculate(name, b):
    if name == 'buck_inductor_ripple':
        return buck_intervals(b)
    if name == 'buck_output_ripple':
        return output_ripple(b)
    if name == 'mosfet_conduction_loss':
        _positive(b, 'on_resistance')
        current, resistance = b['rms_current'], b['on_resistance']
        return {'power': (current[0]**2 * resistance[0], current[1]**2 * resistance[1], 'W')}
    if name == 'rc_time':
        _positive(b, 'resistance', 'capacitance')
        resistance, capacitance = b['resistance'], b['capacitance']
        return {'time_constant': (resistance[0] * capacitance[0], resistance[1] * capacitance[1], 's')}
    raise ValueError('Unknown power calculator: ' + name)
