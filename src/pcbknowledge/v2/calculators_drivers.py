"""Drive margins and source-guided regulator design equations in SI units."""
from __future__ import annotations

import math


# TI SLVS632L pp15-17, source:ti-tps5430. Equations use Hz, H, F, V,
# A and ohm; these are the device's design-screen model coefficients.
TPS_FILTER_COEFFICIENT = 3357  # Eq8: C = 1 / (3357 * L * f_CO * V_OUT).
TPS_CROSSOVER_MIN_HZ = 2590
TPS_CROSSOVER_MAX_HZ = 24000
TPS_MAX_DUTY = .87  # Eq13.
TPS_SWITCHING_LOSS_FACTOR = .01  # Eq Psw = VIN * IOUT * .01.
TPS_MODEL_BIAS_CURRENT_A = .01  # Eq Pq = VIN * .01 A.

INPUT_UNITS = {
    'darlington_driver': {'channels': '1', 'collector_current': 'A', 'collector_drop': 'V',
                          'input_current': 'A', 'logic_voltage': 'V', 'coil_inductance': 'H',
                          'switching_frequency': 'Hz', 'ambient': 'degC', 'thermal_resistance': 'degC/W'},
    'gpio_drive': {'supply': 'V', 'high_drop': 'V', 'load_current': 'A', 'series_resistance': 'ohm',
                   'pulldown_resistance': 'ohm', 'source_current_rating': 'A', 'high_threshold': 'V'},
    'feedback_divider': {'reference_voltage': 'V', 'upper_resistance': 'ohm', 'lower_resistance': 'ohm'},
    'feedback_parallel_divider': {'reference_voltage': 'V', 'upper_resistance': 'ohm',
                                  'lower_resistance': 'ohm', 'series_resistance_a': 'ohm',
                                  'series_resistance_b': 'ohm'},
    'tps5430_filter': {'inductance': 'H', 'capacitance': 'F', 'output_voltage': 'V',
                       'capacitor_esr_max': 'ohm', 'capacitor_esr_factor': '1',
                       'series_resistance_a': 'ohm', 'series_resistance_b': 'ohm'},
    'tps5430_ccm_design': {'input_voltage': 'V', 'output_voltage': 'V', 'output_current': 'A',
                           'frequency': 'Hz', 'inductance': 'H', 'on_resistance': 'ohm',
                           'diode_drop': 'V', 'inductor_resistance': 'ohm', 'ambient': 'degC',
                           'thermal_resistance': 'degC/W', 'uvlo_voltage': 'V'},
}
INPUT_UNITS['tps5430_output_ripple'] = {**INPUT_UNITS['tps5430_ccm_design'], **INPUT_UNITS['tps5430_filter']}


def positive(b, *names):
    if any(b[name][0] <= 0 for name in names):
        raise ValueError('Positive bounds required for ' + ', '.join(names))


def darlington(b):
    channels = b['channels']
    if channels[0] != channels[1] or channels[0] < 1 or channels[0] != int(channels[0]):
        raise ValueError('Channels must be one positive integer')
    current, drop, logic, drive, inductance, frequency = (
        b[key] for key in ('collector_current', 'collector_drop', 'logic_voltage',
                           'input_current', 'coil_inductance', 'switching_frequency'))
    powers = tuple(channels[0] * (drop[i] * current[i] + logic[i] * drive[i]
                   + .5 * inductance[i] * current[i]**2 * frequency[i]) for i in (0, 1))
    ambient, theta = b['ambient'], b['thermal_resistance']
    positive(b, 'thermal_resistance')
    return {'power': (*powers, 'W'),
            'junction_temperature': (ambient[0] + powers[0] * theta[0],
                                     ambient[1] + powers[1] * theta[1], 'degC')}


def gpio(b):
    positive(b, 'pulldown_resistance', 'source_current_rating')
    supply, drop, load, series, pull, rating, threshold = (b[key] for key in INPUT_UNITS['gpio_drive'])
    low = (supply[0] - drop[1] - load[1] * series[1]) * pull[0] / (pull[0] + series[1])
    high = (supply[1] - drop[0] - load[0] * series[0]) * pull[1] / (pull[1] + series[0])
    if low < 0:
        raise ValueError('GPIO load exceeds the available source voltage')
    current = (load[0] + low / pull[1], load[1] + supply[1] / (pull[0] + series[0]))
    if current[1] > rating[0]:
        raise ValueError('GPIO source load exceeds the current condition for its high-voltage bound')
    return {'high_voltage': (low, high, 'V'), 'source_current': (*current, 'A'),
            'current_margin': (rating[0] - current[1], rating[1] - current[0], 'A'),
            'high_margin': (low - threshold[1], high - threshold[0], 'V')}


def feedback(b):
    positive(b, 'reference_voltage', 'upper_resistance', 'lower_resistance')
    reference, upper, lower = (b[key] for key in INPUT_UNITS['feedback_divider'])
    return {'output_voltage': (reference[0] * (1 + upper[0] / lower[1]),
                                reference[1] * (1 + upper[1] / lower[0]), 'V')}


def feedback_parallel(b):
    positive(b, *INPUT_UNITS['feedback_parallel_divider'])
    lower, first, second = (b[key] for key in ('lower_resistance', 'series_resistance_a',
                                              'series_resistance_b'))
    combined = tuple(lower[i] * (first[i] + second[i]) / (lower[i] + first[i] + second[i])
                     for i in (0, 1))
    result = feedback({'reference_voltage': b['reference_voltage'], 'upper_resistance': b['upper_resistance'],
                       'lower_resistance': combined})
    result['lower_equivalent_resistance'] = (*combined, 'ohm')
    return result


def filter_design(b):
    positive(b, 'inductance', 'capacitance', 'output_voltage', 'series_resistance_a', 'series_resistance_b')
    inductance, capacitance, voltage, cap_esr, factor, first, second = (
        b[key] for key in INPUT_UNITS['tps5430_filter'])
    if factor[0] < 1:
        raise ValueError('Capacitor ESR model factor must not reduce the source maximum')
    parallel = tuple(first[i] * second[i] / (first[i] + second[i]) for i in (0, 1))
    # The capacitor specification supplies only an upper bound. The two actual
    # series-network resistors, rather than an invented capacitor ESR, set the floor.
    esr = (parallel[0], parallel[1] + cap_esr[1] * factor[1])
    crossover = (1 / (TPS_FILTER_COEFFICIENT * inductance[1] * capacitance[1] * voltage[1]),
                 1 / (TPS_FILTER_COEFFICIENT * inductance[0] * capacitance[0] * voltage[0]))
    zero = (1 / (2 * math.pi * capacitance[1] * esr[1]),
            1 / (2 * math.pi * capacitance[0] * esr[0]))
    # Dividing f_ESR by f_CO cancels C exactly; do not compare unrelated extrema.
    ratio = (TPS_FILTER_COEFFICIENT * inductance[0] * voltage[0] / (2 * math.pi * esr[1]),
             TPS_FILTER_COEFFICIENT * inductance[1] * voltage[1] / (2 * math.pi * esr[0]))
    if crossover[0] < TPS_CROSSOVER_MIN_HZ or crossover[1] > TPS_CROSSOVER_MAX_HZ or ratio[0] <= 1:
        raise ValueError('Filter equations require 2590-24000 Hz crossover below the ESR zero')
    return {'crossover_frequency': (*crossover, 'Hz'), 'esr_zero_frequency': (*zero, 'Hz'),
            'zero_to_crossover_ratio': (*ratio, '1'), 'total_esr': (*esr, 'ohm')}


def nonideal_buck_bounds(b):
    """Enclose switched RL ramps without assuming symmetric triangular ripple.

    For each period, delta <= T / (L/A + L/B), where A and B bound the
    positive on/off inductor voltages. Start with delta <= A*T/L, which
    supplies a peak bound for the resistive off-voltage term, then refine.
    The mean lies between extrema even for exponential ramps, so peak <=
    mean+delta and valley >= mean-delta. Popoviciu's variance bound supplies
    capacitor/inductor RMS bounds without imposing triangular waveforms.
    """
    positive(b, 'input_voltage', 'output_voltage', 'output_current', 'frequency', 'inductance')
    vi, vo, current, frequency, inductance, resistance, diode, dcr = (b[key] for key in
        ('input_voltage', 'output_voltage', 'output_current', 'frequency', 'inductance',
         'on_resistance', 'diode_drop', 'inductor_resistance'))
    if vi[0] <= vo[1]:
        raise ValueError('Buck input must exceed output over the supplied interval')
    on_max = vi[1] - vo[0]
    initial_delta = on_max / (frequency[0] * inductance[0])
    off_max = vo[1] + diode[1] + (current[1] + initial_delta) * dcr[1]
    delta = on_max * off_max / ((on_max + off_max) * frequency[0] * inductance[0])
    peak = current[1] + delta
    valley = current[0] - delta
    if valley <= 0:
        raise ValueError('Nonideal CCM model requires a strictly positive proven valley current')
    on_min = vi[0] - vo[1] - peak * (resistance[1] + dcr[1])
    if on_min <= 0:
        raise ValueError('Nonideal buck cannot establish a positive on-state current ramp')
    denominator = vi[0] + diode[0] - resistance[1] * peak
    duty_max = (vo[1] + diode[1] + dcr[1] * current[1]) / denominator
    duty_min = vo[0] / (vi[1] + diode[1])
    if duty_max >= 1:
        raise ValueError('Nonideal buck duty-cycle upper bound must be below one')
    return {'duty_cycle': (duty_min, duty_max, '1'), 'ripple_current': (0, delta, 'A'),
            'peak_current': (current[0], peak, 'A'), 'valley_current': (valley, current[1], 'A'),
            'inductor_rms_current': (current[0], math.sqrt(current[1]**2 + delta**2 / 4), 'A'),
            'input_capacitor_rms_current': (0, peak / 2, 'A'),
            'output_capacitor_rms_current': (0, delta / 2, 'A')}


def tps5430_ccm(b):
    # Source SLVS632L pp16-17: duty headroom and estimated CCM thermal model.
    # Include diode and winding/switch losses in the waveform-domain proof.
    result = nonideal_buck_bounds(b)
    vi, vo, current, resistance, diode, dcr = (b[key] for key in
        ('input_voltage', 'output_voltage', 'output_current', 'on_resistance', 'diode_drop',
         'inductor_resistance'))
    positive(b, 'thermal_resistance', 'uvlo_voltage')
    uvlo, frequency = b['uvlo_voltage'], b['frequency']
    if vi[0] < uvlo[1]:
        raise ValueError('Buck input is below the source UVLO maximum')
    # The source's duty-headroom equation uses mean current. Bound the on-state
    # resistive drop by waveform extrema instead, preserving nonideal margin.
    peak, valley = result['peak_current'][1], result['valley_current'][0]
    headroom_low = TPS_MAX_DUTY * (vi[0] - peak * resistance[1] + diode[1]) - current[1] * dcr[1] - diode[1]
    headroom_high = TPS_MAX_DUTY * (vi[1] - valley * resistance[0] + diode[0]) - current[0] * dcr[0] - diode[0]
    loss = (current[0]**2 * resistance[0] * vo[0] / vi[1] + vi[0] * current[0] * TPS_SWITCHING_LOSS_FACTOR
            + vi[0] * TPS_MODEL_BIAS_CURRENT_A,
            current[1]**2 * resistance[1] * vo[1] / vi[0] + vi[1] * current[1] * TPS_SWITCHING_LOSS_FACTOR
            + vi[1] * TPS_MODEL_BIAS_CURRENT_A)
    ambient, theta = b['ambient'], b['thermal_resistance']
    result.update(input_current=(0, current[1] * (1 + TPS_SWITCHING_LOSS_FACTOR)
                                  + TPS_MODEL_BIAS_CURRENT_A, 'A'),
                  input_min_margin=(vi[0] - uvlo[1], vi[1] - uvlo[0], 'V'),
                  on_time=(result['duty_cycle'][0] / frequency[1],
                           result['duty_cycle'][1] / frequency[0], 's'),
                  duty_margin=(TPS_MAX_DUTY - result['duty_cycle'][1],
                               TPS_MAX_DUTY - result['duty_cycle'][0], '1'),
                  output_headroom=(headroom_low - vo[1], headroom_high - vo[0], 'V'),
                  power=(*loss, 'W'), junction_temperature=(ambient[0] + loss[0] * theta[0],
                                                          ambient[1] + loss[1] * theta[1], 'degC'))
    return result


def output_ripple_design(b):
    """Compose the accepted nonideal waveform and actual filter network inputs."""
    switching = tps5430_ccm(b)
    output_filter = filter_design(b)
    delta = switching['ripple_current'][1]
    frequency, capacitance = b['frequency'], b['capacitance']
    # A capacitor-current excursion is at most delta across a period, so the
    # total charge excursion is at most delta/f; do not assume triangular ramps.
    capacitive = delta / (frequency[0] * capacitance[0])
    resistive = delta * output_filter['total_esr'][1]
    return {'capacitive_ripple': (0, capacitive, 'V'), 'esr_ripple': (0, resistive, 'V'),
            'output_ripple': (0, capacitive + resistive, 'V')}


def calculate(name, bounds):
    functions = {'darlington_driver': darlington, 'gpio_drive': gpio, 'feedback_divider': feedback,
                 'feedback_parallel_divider': feedback_parallel,
                 'tps5430_filter': filter_design, 'tps5430_ccm_design': tps5430_ccm,
                 'tps5430_output_ripple': output_ripple_design}
    return functions[name](bounds)
