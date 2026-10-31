"""First-order TIA loop planning; adopted GBW is an explicit engineering assumption."""
import math


INPUT_UNITS = {'tia_loop_model': {'gain_bandwidth': 'Hz', 'input_capacitance': 'F',
                                 'feedback_resistance': 'ohm', 'feedback_capacitance_a': 'F',
                                 'feedback_capacitance_b': 'F', 'feedback_capacitance_c': 'F',
                                 'feedback_capacitance_d': 'F'}}
INPUT_UNITS['tia_loop_total_capacitance'] = {
    'gain_bandwidth': 'Hz', 'input_capacitance': 'F',
    'feedback_resistance': 'ohm', 'feedback_capacitance': 'F'}
NOTE = ('Engineering integrator op-amp loop estimate using supplied GBW and capacitances; '
        'excludes extra amplifier poles, parasitic uncertainty and output loading. '
        'Phase margin is conditional on this model, not guaranteed actual stability.')


def crossover(omega_t, tau_zero, tau_pole):
    """Solve |A/NG|=1 for x=omega^2 using a cancellation-resistant root.

    KCL gives NG=(1+s*Rf*(Cin+Cf))/(1+s*Rf*Cf). Assume A=omega_t/s.
    Hence tau_zero^2*x^2+(1-omega_t^2*tau_pole^2)*x-omega_t^2=0.
    No third-party implementation or device-specific coefficients are used.
    """
    coefficient = 1 - (omega_t * tau_pole)**2
    radical = math.hypot(coefficient, 2 * tau_zero * omega_t)
    if coefficient >= 0:
        square = 2 * omega_t**2 / (radical + coefficient)
    else:
        square = (radical - coefficient) / (2 * tau_zero**2)
    return math.sqrt(square)


def calculate(b):
    """Historical four-capacitor contract; its exact sum enters the single numerical core."""
    capacitors = [b['feedback_capacitance_' + suffix] for suffix in 'abcd']
    if any(cap[0] <= 0 for cap in capacitors):
        raise ValueError('Four parallel feedback capacitors require positive bounds')
    total = tuple(sum(cap[i] for cap in capacitors) for i in (0, 1))
    return calculate_total({key: b[key] for key in ('gain_bandwidth', 'input_capacitance', 'feedback_resistance')}
                           | {'feedback_capacitance': total})


def calculate_total(b):
    gbw, input_cap, resistance = (b[key] for key in
                                   ('gain_bandwidth', 'input_capacitance', 'feedback_resistance'))
    feedback_cap = b['feedback_capacitance']
    if min(gbw[0], feedback_cap[0], resistance[0]) <= 0:
        raise ValueError('TIA loop model requires positive GBW, feedback capacitance and resistance')
    zero = tuple(resistance[i] * (input_cap[i] + feedback_cap[i]) for i in (0, 1))
    pole = tuple(resistance[i] * feedback_cap[i] for i in (0, 1))
    omega_t = tuple(2 * math.pi * value for value in gbw)
    # Root rises with omega_t and tau_pole, falls with tau_zero. Relax their
    # correlation to enclose all physical combinations; NG>=1 also bounds omega.
    omega = (crossover(omega_t[0], zero[1], pole[0]),
             min(omega_t[1], crossover(omega_t[1], zero[0], pole[1])))
    phase = (90 - math.degrees(math.atan(omega[1] * zero[1]))
                + math.degrees(math.atan(omega[0] * pole[0])),
             min(90, 90 - math.degrees(math.atan(omega[0] * zero[0]))
                 + math.degrees(math.atan(omega[1] * pole[1]))))
    return {'feedback_capacitance': (*feedback_cap, 'F'),
            'crossover_frequency': (omega[0] / (2 * math.pi), omega[1] / (2 * math.pi), 'Hz'),
            'phase_margin': (*phase, 'deg'),
            'high_frequency_noise_gain': (1 + input_cap[0] / feedback_cap[1],
                                           1 + input_cap[1] / feedback_cap[0], '1'),
            'feedback_pole': (1 / (2 * math.pi * pole[1]), 1 / (2 * math.pi * pole[0]), 'Hz')}
