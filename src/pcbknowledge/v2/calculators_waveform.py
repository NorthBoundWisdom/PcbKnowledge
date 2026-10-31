"""Conditional sampled sine/triangle envelope for a parallel-R RC follower.

The output metrics are half peak-to-peak amplitude and settled cycle-average.
Pointwise residual bounds DAC/follower dynamics at every sample/hold instant.
Cycle-mean residual separately bounds the aggregate DC error from those
dynamics and DDS/sample weighting. Neither acceptance interval is inferred
from jitter, sample count, or a manufacturer's typical settling time. This module does not synthesize firmware.
"""
from decimal import Decimal, localcontext
from fractions import Fraction

from .calculators_envelope import outward_results, resistance_bounds

INPUT_UNITS = {
    'sampled_waveform_envelope': {
        'filter_resistance_1': 'ohm', 'filter_resistance_2': 'ohm',
        'isolation_resistance': 'ohm', 'tcr_magnitude': '1/degC',
        'temperature_excursion': 'degC', 'filter_capacitance': 'F',
        'capacitance_retention': '1', 'load_resistance_minimum': 'ohm',
        'sample_rate': 'Hz', 'sample_jitter': 's', 'waveform_frequency': 'Hz',
        'amplitude': 'V', 'offset': 'V', 'gain_error': '1',
        'static_error': 'V', 'pointwise_residual_error': 'V',
        'cycle_mean_residual_error': 'V', 'initial_error': 'V',
        'settle_time': 's', 'relative_amplitude_limit': '1',
        'absolute_amplitude_limit': 'V', 'offset_error_limit': 'V',
    },
}
PI_UPPER = Fraction('3.14159265358979323846264338327950288419716939937511')


def exponential_upper(value):
    """Bound exp(value) for a nonpositive rational; avoid underflow to zero."""
    if value > 0:
        raise ValueError('Only decaying exponentials are supported')
    with localcontext() as context:
        context.prec = 80
        value = max(value, Fraction(-1000))
        argument = Decimal(value.numerator) / Decimal(value.denominator)
        return Fraction(argument.next_plus().exp().next_plus())


def calculate(name, bounds):
    if name not in INPUT_UNITS or set(bounds) != set(INPUT_UNITS[name]):
        raise ValueError('Exact sampled-waveform inputs required')
    b = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    if any(low < 0 or low > high for low, high in b.values()):
        raise ValueError('Nonnegative ordered intervals required')
    for key in ('filter_capacitance', 'capacitance_retention', 'load_resistance_minimum',
                'sample_rate', 'waveform_frequency', 'settle_time'):
        if b[key][0] <= 0:
            raise ValueError('Positive physical interval required: ' + key)
    if b['amplitude'][0] != 0 or b['amplitude'][1] <= 0:
        raise ValueError('Amplitude must describe the entire zero-to-maximum range')
    if b['offset'][0] != b['offset'][1] or b['offset'][0] < b['amplitude'][1]:
        raise ValueError('Fixed unipolar offset must cover the amplitude range')
    if b['gain_error'][1] >= 1:
        raise ValueError('Gain error must remain below unity')
    r1 = resistance_bounds(b, 'filter_resistance_1')
    r2 = resistance_bounds(b, 'filter_resistance_2')
    isolation = resistance_bounds(b, 'isolation_resistance')
    parallel = 1 / (1 / r1[1] + 1 / r2[1])
    tau = parallel * b['filter_capacitance'][1] * b['capacitance_retention'][1]
    gap = 1 / b['sample_rate'][0] + 2 * b['sample_jitter'][1]
    hold = 1 / b['sample_rate'][1] - 2 * b['sample_jitter'][1]
    frequency = b['waveform_frequency'][1]
    if hold <= 0 or frequency * gap > Fraction(1, 40):
        raise ValueError('At least forty samples per cycle and positive hold required')
    alpha = exponential_upper(-hold / tau)
    if not 0 < alpha < 1:
        raise ValueError('RC decay cannot be enclosed strictly below unity')
    triangle_loss = 2 * frequency * gap + 4 * frequency * gap * alpha / (1 - alpha)
    sine_loss = (PI_UPPER * frequency * gap) ** 2 / 2
    sine_loss += 2 * PI_UPPER * frequency * gap * alpha / (1 - alpha)
    attenuation = isolation[1] / (b['load_resistance_minimum'][0] + isolation[1])
    relative_error = max(sine_loss, triangle_loss) + attenuation + b['gain_error'][1]
    transient = b['initial_error'][1] * exponential_upper(-b['settle_time'][0] / tau)
    absolute_error = b['static_error'][1] + b['pointwise_residual_error'][1] + transient
    amplitude = b['amplitude'][1]
    amplitude_error = relative_error * amplitude + absolute_error
    margins = [b['absolute_amplitude_limit'][0] - absolute_error,
               b['absolute_amplitude_limit'][0] + b['relative_amplitude_limit'][0] * amplitude
               - amplitude_error]
    mean_error = b['static_error'][1] + b['cycle_mean_residual_error'][1] + transient
    offset_error = (attenuation + b['gain_error'][1]) * b['offset'][0] + mean_error
    return outward_results({
        'amplitude_error': (0, amplitude_error, 'V'),
        'offset_error': (0, offset_error, 'V'),
        'amplitude_margin': (min(margins), max(margins), 'V'),
        'offset_margin': (b['offset_error_limit'][0] - offset_error,
                          b['offset_error_limit'][1], 'V'),
        'time_constant': (0, tau, 's'),
        'triangle_peak_loss': (0, triangle_loss, '1'),
        'sine_peak_loss': (0, sine_loss, '1'),
    })
