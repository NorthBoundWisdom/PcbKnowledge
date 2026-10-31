"""First-principles G3 DC and single-pole interval calculations."""
from __future__ import annotations

import itertools
import math

from . import calculators_sensing, calculators_tia_loop


INPUT_UNITS = {
    **calculators_sensing.INPUT_UNITS,
    **calculators_tia_loop.INPUT_UNITS,
    'opamp_gain': {'input_current': 'A', 'feedback_resistance': 'ohm', 'bias_voltage': 'V'},
    'rc_filter': {'resistance': 'ohm', 'capacitance': 'F'},
    'reference_load': {'supply': 'V', 'reference_voltage': 'V',
                       'series_resistance': 'ohm', 'load_current': 'A'},
    'rs485_termination': {'supply': 'V', 'termination_a': 'ohm', 'termination_b': 'ohm',
                          'bias_up': 'ohm', 'bias_down': 'ohm', 'driver_voltage': 'V',
                          'receiver_load_current': 'A'},
    'trace_impedance_microstrip': {'trace_width': 'mm', 'dielectric_height': 'mm',
                                   'copper_thickness': 'mm', 'relative_permittivity': '1',
                                   'model_relative_error': '1'},
}
NOTES = {
    **calculators_sensing.NOTES,
    'tia_loop_model': calculators_tia_loop.NOTE,
    'tia_loop_total_capacitance': calculators_tia_loop.NOTE,
    'opamp_gain': ('Ideal DC TIA: positive input current leaves the summing node, Vout=Vbias+I*Rf. '
                   'Excludes offset, bias current, finite loop gain, stability and output limits.'),
    'rc_filter': 'Unloaded ideal series-R shunt-C low-pass driven by a zero-impedance voltage source.',
    'reference_load': ('DC shunt reference at the supplied regulated voltage; negative cathode current '
                       'fails regulation. Check current limits and resistor power separately.'),
    'rs485_termination': ('Ideal DC two-termination network with one pull-up/pull-down pair; driver current '
                          'and powers use polarity opposing bias. Includes supplied adverse differential '
                          'receiver load; '
                          'excludes common-mode effects.'),
    'trace_impedance_microstrip': ('ADI MT-094 Eq3 surface microstrip estimate with explicit model allowance; '
                                   'not a guaranteed physical bound. Uncoupled trace over continuous plane, '
                                   'no solder mask; not differential impedance or EMI.'),
}


def positive(b, *names):
    if any(b[name][0] <= 0 for name in names):
        raise ValueError('Positive bounds required for ' + ', '.join(names))


def opamp_gain(b):
    """KCL at the ideal virtual-ground node, current directed out of that node."""
    positive(b, 'feedback_resistance')
    current, resistance, bias = (b[key] for key in INPUT_UNITS['opamp_gain'])
    return {'transimpedance': (*resistance, 'ohm'),
            'output_voltage': (bias[0] + current[0] * resistance[0],
                               bias[1] + current[1] * resistance[1], 'V')}


def rc_filter(b):
    positive(b, 'resistance', 'capacitance')
    resistance, capacitance = (b[key] for key in INPUT_UNITS['rc_filter'])
    time = (resistance[0] * capacitance[0], resistance[1] * capacitance[1])
    return {'time_constant': (*time, 's'),
            'cutoff_frequency': (1 / (2 * math.pi * time[1]), 1 / (2 * math.pi * time[0]), 'Hz')}


def reference_load(b):
    positive(b, 'reference_voltage', 'series_resistance')
    supply, reference, resistance, load = (b[key] for key in INPUT_UNITS['reference_load'])
    if supply[0] <= reference[1]:
        raise ValueError('Supply must exceed reference throughout the interval')
    voltage = (supply[0] - reference[1], supply[1] - reference[0])
    return {'cathode_current': (voltage[0] / resistance[1] - load[1],
                                voltage[1] / resistance[0] - load[0], 'A'),
            'resistor_power': (voltage[0]**2 / resistance[1], voltage[1]**2 / resistance[0], 'W')}


def rs485_termination(b):
    """Reduce two parallel terminations and the series bias path using KCL.

    Worst driven polarity: |I|=Vd/Rt+(Vs+Vd)/(Ru+Rd)+Iload.
    Idle V=(Vs-Iload*Rb)*Rt/(Rt+Rb) is separately monotonic, but its
    direction in Rt depends on Vs-Iload*Rb, so enumerate endpoint corners.
    Powers are totals for each resistor group, not individual resistor ratings.
    """
    positive(b, 'supply', 'termination_a', 'termination_b', 'bias_up', 'bias_down')
    supply, first, second, up, down, drive, load = (b[key] for key in INPUT_UNITS['rs485_termination'])
    term = tuple(1 / (1 / first[i] + 1 / second[i]) for i in (0, 1))
    bias = tuple(up[i] + down[i] for i in (0, 1))
    equivalent = tuple(1 / (1 / term[i] + 1 / bias[i]) for i in (0, 1))
    idle_values = [(v - i * rb) * rt / (rt + rb)
                   for v, i, rb, rt in itertools.product(supply, load, bias, term)]
    idle = (min(idle_values), max(idle_values))
    current = (drive[0] / term[1] + (supply[0] + drive[0]) / bias[1] + load[0],
               drive[1] / term[0] + (supply[1] + drive[1]) / bias[0] + load[1])
    return {'idle_differential': (*idle, 'V'), 'equivalent_load': (*equivalent, 'ohm'),
            'driver_current': (*current, 'A'),
            'termination_power': (drive[0]**2 / term[1], drive[1]**2 / term[0], 'W'),
            'bias_power': ((supply[0] + drive[0])**2 / bias[1],
                           (supply[1] + drive[1])**2 / bias[0], 'W')}


def microstrip(b):
    """ADI MT-094 Rev0 (01/09), pp3-4 Eq3 and its accuracy discussion.

    https://www.analog.com/media/en/training-seminars/tutorials/MT-094.pdf
    Z=87/sqrt(er+1.41)*ln(5.98*h/(0.8*w+t)), dimensions in common units.
    Implemented directly, not from third-party code. The source describes best
    accuracy at 50-100 ohm: refuse any raw endpoint outside that interval.
    Model allowance is a user decision, not a sourced guaranteed error bound.
    """
    positive(b, 'trace_width', 'dielectric_height', 'copper_thickness')
    width, height, copper, dielectric, error = (b[key] for key in INPUT_UNITS['trace_impedance_microstrip'])
    if dielectric[0] < 1 or error[1] >= 1:
        raise ValueError('Relative permittivity must be >=1 and model allowance must be <1')
    def impedance(w, h, t, er):
        return 87 / math.sqrt(er + 1.41) * math.log(5.98 * h / (.8 * w + t))
    low = impedance(width[1], height[0], copper[1], dielectric[1])
    high = impedance(width[0], height[1], copper[0], dielectric[0])
    if low < 50 or high > 100:
        raise ValueError('Microstrip approximation requires raw impedance bounds within 50-100 ohm')
    return {'impedance': (low * (1 - error[1]), high * (1 + error[1]), 'ohm')}


def calculate(name, b):
    if name == 'tia_loop_total_capacitance':
        return calculators_tia_loop.calculate_total(b)
    if name == 'tia_loop_model':
        return calculators_tia_loop.calculate(b)
    if name in calculators_sensing.INPUT_UNITS:
        return calculators_sensing.calculate(name, b)
    functions = {'opamp_gain': opamp_gain, 'rc_filter': rc_filter, 'reference_load': reference_load,
                 'rs485_termination': rs485_termination, 'trace_impedance_microstrip': microstrip}
    return functions[name](b)
