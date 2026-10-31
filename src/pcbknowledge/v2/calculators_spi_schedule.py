"""Conditional STM32 SPI/DDS budget with shared clock and rounded phase words.

Nearest integer ties round upward. Word selection uses the nominal sample
clock once; physical clock uncertainty scales that same word. Guard reservation
is not proof of firmware edge placement: the SPI mode/setup/hold contract and
electrical transition/load conditions remain explicit operating requirements.
"""
from fractions import Fraction
from .calculators_envelope import outward_results

INPUT_UNITS = {
    'spi_dac_schedule': {
        'clock': 'Hz', 'clock_error': '1', 'spi_divider': '1', 'timer_divider': '1',
        'frame_bits': '1', 'firmware_cycles': '1', 'guard_time': 's',
        'minimum_guard_time': 's', 'serial_clock_limit': 'Hz',
        'serial_half_period_minimum': 's', 'phase_bits': '1',
        'requested_frequency': 'Hz', 'frequency_error_limit': '1',
        'accepted_sample_rate': 'Hz', 'accepted_waveform_frequency': 'Hz',
    },
}


def phase_word(frequency, modulus, nominal_sample):
    value = Fraction(frequency) * modulus / Fraction(nominal_sample) + Fraction(1, 2)
    return value.numerator // value.denominator


def calculate(name, bounds):
    if name not in INPUT_UNITS or set(bounds) != set(INPUT_UNITS[name]):
        raise ValueError('Exact SPI scheduling inputs required')
    b = {key: tuple(Fraction(str(value)) for value in pair) for key, pair in bounds.items()}
    if any(low < 0 or high < low for low, high in b.values()):
        raise ValueError('Nonnegative ordered intervals required')
    for key in set(b) - {'clock_error', 'firmware_cycles'}:
        if b[key][0] <= 0:
            raise ValueError('Positive scheduling input required: ' + key)
    for key in ('spi_divider', 'timer_divider', 'frame_bits', 'phase_bits'):
        low, high = b[key]
        if low != high or low.denominator != 1:
            raise ValueError('Exact integer required: ' + key)
    if b['clock'][0] != b['clock'][1]:
        raise ValueError('Exact nominal clock required; uncertainty is clock_error')
    divider = b['spi_divider'][0]
    if divider not in (2, 4, 8, 16, 32, 64, 128, 256):
        raise ValueError('Unsupported STM32 SPI divider')
    if b['clock_error'][1] >= 1 or b['frame_bits'][0] != 24:
        raise ValueError('Clock uncertainty or DAC frame invalid')
    if not 1 <= b['phase_bits'][0] <= 32 or b['timer_divider'][0] > 65536:
        raise ValueError('Bounded32-bit DDS and16-bit timer required')
    clock_low = b['clock'][0] * (1 - b['clock_error'][1])
    clock_high = b['clock'][1] * (1 + b['clock_error'][1])
    sample_low = clock_low / b['timer_divider'][0]
    sample_high = clock_high / b['timer_divider'][0]
    nominal_sample = b['clock'][0] / b['timer_divider'][0]
    modulus = 2 ** int(b['phase_bits'][0])
    word_low, word_high = [phase_word(frequency, modulus, nominal_sample)
                           for frequency in b['requested_frequency']]
    if word_low <= 0 or word_high >= modulus / 2:
        raise ValueError('Positive phase word strictly below Nyquist required')
    actual_low = sample_low * word_low / modulus
    actual_high = sample_high * word_high / modulus
    free_cycles = b['timer_divider'][0] - b['frame_bits'][0] * divider - b['firmware_cycles'][1]
    worst_clock = clock_high if free_cycles >= 0 else clock_low
    time_margin = free_cycles / worst_clock - b['guard_time'][1]
    relative_error = b['clock_error'][1] + sample_high / (2 * modulus * b['requested_frequency'][0])
    sample_margins = (sample_low - b['accepted_sample_rate'][0], b['accepted_sample_rate'][1] - sample_high)
    waveform_margins = (actual_low - b['accepted_waveform_frequency'][0],
                        b['accepted_waveform_frequency'][1] - actual_high)
    scalar = {
        'time_margin': (time_margin, 's'),
        'guard_margin': (b['guard_time'][0] - b['minimum_guard_time'][1], 's'),
        'serial_clock_margin': (b['serial_clock_limit'][0] - clock_high / divider, 'Hz'),
        'serial_half_period_margin': (divider / (2 * clock_high) - b['serial_half_period_minimum'][1], 's'),
        'frequency_margin': (b['frequency_error_limit'][0] - relative_error, '1'),
        'sampling_margin': (modulus - 40 * word_high, '1'),
    }
    outputs = {key: (value, value, unit) for key, (value, unit) in scalar.items()}
    outputs.update({
        'sample_rate': (sample_low, sample_high, 'Hz'),
        'waveform_frequency': (actual_low, actual_high, 'Hz'),
        'sample_rate_margin': (min(sample_margins), max(sample_margins), 'Hz'),
        'waveform_frequency_margin': (min(waveform_margins), max(waveform_margins), 'Hz'),
        'frequency_error': (0, relative_error, '1'),
    })
    return outward_results(outputs)
