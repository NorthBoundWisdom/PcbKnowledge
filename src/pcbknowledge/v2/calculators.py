"""Pure engineering calculations in canonical units, with explicit input bounds."""
from __future__ import annotations

import math

from . import calculators_resistor_load
from . import calculators_geometry, calculators_envelope, calculators_envelope_power, calculators_output
from . import calculators_analog, calculators_drivers, calculators_power, calculators_protection


class CalculationError(ValueError):
    """An input is missing, unknown, inconsistent or outside the model domain."""


# External-layer empirical equation: I = k * dT**a * area_mil2**b.
# Named published coefficients, implemented directly without an IPC document.
EXTERNAL_CURRENT_COEFFICIENT = 0.048
TEMPERATURE_EXPONENT = 0.44
AREA_EXPONENT = 0.725
MM_PER_MIL = 0.0254
I2C_RC_RISE_FACTOR = 0.8473

ENVELOPE_MODULES = {
    name: module
    for module in (calculators_envelope, calculators_envelope_power, calculators_output, calculators_resistor_load)
    for name in module.INPUT_UNITS
}


INPUT_UNITS = {
    **calculators_geometry.INPUT_UNITS,
    **calculators_envelope.INPUT_UNITS,
    **calculators_envelope_power.INPUT_UNITS,
    **calculators_output.INPUT_UNITS,
    **calculators_resistor_load.INPUT_UNITS,
    'ldo_headroom': {'input_voltage': 'V', 'output_voltage': 'V', 'dropout': 'V',
                     'input_current': 'A', 'series_resistance': 'ohm'},
    'ldo_dissipation': {'input_voltage': 'V', 'output_voltage': 'V', 'output_current': 'A',
                        'quiescent_current': 'A', 'ambient': 'degC',
                        'thermal_resistance': 'degC/W'},
    'led_resistor': {'supply': 'V', 'forward_voltage': 'V', 'resistance': 'ohm'},
    'i2c_pullup': {'supply': 'V', 'low_voltage': 'V', 'sink_current': 'A',
                   'capacitance': 'F', 'rise_time': 's', 'resistance': 'ohm'},
    'shunt_resistor': {'current': 'A', 'resistance': 'ohm', 'sense_limit': 'V',
                       'power_rating': 'W'},
    'oscillator_startup': {'transconductance': 'S', 'resistance': 'ohm', 'frequency': 'Hz',
                           'shunt_capacitance': 'F', 'load_capacitance': 'F',
                           'drive_current': 'A', 'power_rating': 'W'},
    'trace_width': {'current': 'A', 'temperature_rise': 'degC', 'copper_thickness': 'mm'},
    **calculators_analog.INPUT_UNITS,
    **calculators_power.INPUT_UNITS,
    **calculators_drivers.INPUT_UNITS,
    **calculators_protection.INPUT_UNITS,
}


def validate_inputs(name, inputs, *, allow_parameters=False):
    if name not in INPUT_UNITS:
        raise CalculationError(f'Unknown calculator: {name}')
    required = INPUT_UNITS[name]
    if set(inputs) != set(required):
        raise CalculationError(f'{name} inputs must be exactly {sorted(required)}')
    for key, unit in required.items():
        value = inputs[key]
        if (allow_parameters and isinstance(value, dict)
                and set(value) in ({'parameter'}, {'component', 'parameter'},
                                   {'component', 'parameter', 'bound'})):
            continue
        bounds(value, unit, key)


def bounds(quantity, unit, name):
    if not isinstance(quantity, dict) or quantity.get('status') == 'UNKNOWN':
        raise CalculationError(f'Unknown input: {name}')
    if quantity.get('unit') != unit:
        raise CalculationError(f'{name} requires {unit}')
    if 'value' in quantity:
        low = high = quantity['value']
    else:
        low, high = quantity.get('min'), quantity.get('max')
    if low is None or high is None:
        raise CalculationError(f'{name} requires a value or guaranteed min and max')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (low, high)) or low > high:
        raise CalculationError(f'Invalid bounds: {name}')
    return low, high


def _result(name, inputs, output):
    return {key: {'min': low, 'max': high, 'unit': unit, 'conditions': {},
                  'basis': 'CALCULATED', 'calculator': name, 'inputs': inputs}
            for key, (low, high, unit) in output.items()}


def calculate(name, inputs):
    try:
        result = _geometry(inputs) if name in calculators_geometry.INPUT_UNITS else _calculate(name, inputs)
        for value in result.values():
            bounds(value, value['unit'], 'output')
        return result
    except ArithmeticError as error:
        raise CalculationError('Calculation exceeds finite numerical domain') from error


def _geometry(inputs):
    try:
        return calculators_geometry.calculate(inputs)
    except ValueError as error:
        raise CalculationError(str(error)) from error


def _input_bounds(name, inputs):
    validate_inputs(name, inputs)
    b = {key: bounds(inputs[key], unit, key) for key, unit in INPUT_UNITS[name].items()}
    for key, (low, _) in b.items():
        if key not in ('ambient',) and low < 0:
            raise CalculationError(f'{key} must be nonnegative')
    return b


def _calculate(name, inputs):
    """Return conservative interval outputs; never silently use a typical value."""
    b = _input_bounds(name, inputs)
    if name in ENVELOPE_MODULES:
        return _calculate_envelope(name, inputs, b, ENVELOPE_MODULES[name])
    if name in calculators_analog.INPUT_UNITS:
        return _calculate_analog(name, inputs, b)
    if name in calculators_drivers.INPUT_UNITS:
        return _calculate_drivers(name, inputs, b)
    if name in calculators_protection.INPUT_UNITS:
        try:
            return _result(name, inputs, calculators_protection.calculate(name, b))
        except ValueError as error:
            raise CalculationError(str(error)) from error
    if name in calculators_power.INPUT_UNITS:
        return _calculate_power(name, inputs, b)
    if name == 'ldo_headroom':
        vi, vo, drop, current, resistance = (b[k] for k in INPUT_UNITS[name])
        result = {'headroom': (vi[0] - current[1]*resistance[1] - vo[1] - drop[1],
                              vi[1] - current[0]*resistance[0] - vo[0] - drop[0], 'V')}
    elif name == 'ldo_dissipation':
        vi, vo, current, iq, ambient, theta = (b[k] for k in INPUT_UNITS[name])
        if vi[0] < vo[1]:
            raise CalculationError('LDO input must exceed output over the specified interval')
        pmin = (vi[0]-vo[1])*current[0] + vi[0]*iq[0]
        pmax = (vi[1]-vo[0])*current[1] + vi[1]*iq[1]
        result = {'power': (pmin, pmax, 'W'),
                  'junction_temperature': (ambient[0]+pmin*theta[0], ambient[1]+pmax*theta[1], 'degC')}
    elif name == 'led_resistor':
        supply, vf, resistance = (b[k] for k in INPUT_UNITS[name])
        if resistance[0] <= 0 or supply[0] < vf[1]:
            raise CalculationError('Positive resistance and supply above forward voltage required')
        current = ((supply[0]-vf[1])/resistance[1], (supply[1]-vf[0])/resistance[0])
        result = {'current': (*current, 'A'),
                  'power': ((supply[0]-vf[1])**2/resistance[1],
                            (supply[1]-vf[0])**2/resistance[0], 'W')}
    elif name == 'i2c_pullup':
        supply, vl, sink, cap, rise, resistance = (b[k] for k in INPUT_UNITS[name])
        if min(sink[0], cap[0], rise[0], resistance[0]) <= 0 or supply[0] < vl[1]:
            raise CalculationError('Positive I2C load, rise time and resistance required')
        rmin = (supply[1]-vl[0])/sink[0]
        rmax = rise[0]/(I2C_RC_RISE_FACTOR*cap[1])
        result = {'resistance_min': (rmin, rmin, 'ohm'), 'resistance_max': (rmax, rmax, 'ohm'),
                  'margin': (min(resistance[0]-rmin, rmax-resistance[1]),
                             min(resistance[0]-rmin, rmax-resistance[1]), 'ohm'),
                  'rise_time': (I2C_RC_RISE_FACTOR*resistance[0]*cap[0],
                                I2C_RC_RISE_FACTOR*resistance[1]*cap[1], 's')}
    elif name == 'shunt_resistor':
        current, resistance, voltage, power = (b[k] for k in INPUT_UNITS[name])
        if resistance[0] <= 0 or current[1] <= 0:
            raise CalculationError('Positive shunt resistance and current required')
        vmax = current[1]*resistance[1]
        pmax = current[1]**2*resistance[1]
        result = {'voltage': (current[0]*resistance[0], vmax, 'V'),
                  'power': (current[0]**2*resistance[0], pmax, 'W'),
                  'voltage_margin': (voltage[0]-vmax, voltage[1]-current[0]*resistance[0], 'V'),
                  'power_margin': (power[0]-pmax, power[1]-current[0]**2*resistance[0], 'W')}
    elif name == 'oscillator_startup':
        gm, esr, frequency, shunt, load, current, power = (b[k] for k in INPUT_UNITS[name])
        if min(gm[0], esr[0], frequency[0], load[0], power[0]) <= 0:
            raise CalculationError('Positive oscillator source bounds required')
        # AN2867 loaded ESR from motional Rm; bound correlated terms conservatively.
        loaded_min = esr[0]*(1+shunt[0]/load[1])**2
        loaded_max = esr[1]*(1+shunt[1]/load[0])**2
        critical_min = 4*loaded_min*(2*math.pi*frequency[0])**2*(shunt[0]+load[0])**2
        critical_max = 4*loaded_max*(2*math.pi*frequency[1])**2*(shunt[1]+load[1])**2
        drive_min, drive_max = loaded_min*current[0]**2, loaded_max*current[1]**2
        result = {'margin': (gm[0]/critical_max, gm[1]/critical_min, '1'),
                  'drive_power': (drive_min, drive_max, 'W'),
                  'drive_margin': (power[0]-drive_max, power[1]-drive_min, 'W')}
    else:
        current, rise, copper = (b[k] for k in INPUT_UNITS[name])
        if rise[0] <= 0 or copper[0] <= 0:
            raise CalculationError('Positive temperature rise and copper thickness required')
        def width(i, temperature, thickness):
            area = (i/(EXTERNAL_CURRENT_COEFFICIENT*temperature**TEMPERATURE_EXPONENT))**(1/AREA_EXPONENT)
            return area*MM_PER_MIL**2/thickness
        result = {'trace_width': (width(current[0],rise[1],copper[1]),
                                  width(current[1],rise[0],copper[0]), 'mm')}
    return _result(name, inputs, result)


def _gpio_source_conditions(inputs, b):
    drop = inputs['high_drop']
    conditions = drop.get('conditions', {})
    if not isinstance(conditions, dict):
        raise CalculationError('GPIO source conditions must be typed quantities')
    keys = ('VDD_min', 'VDD_max', 'output_current')
    if drop.get('basis') == 'DATASHEET' and any(key not in conditions for key in keys):
        raise CalculationError('Datasheet GPIO high drop requires typed supply and output-current conditions')
    if not any(key in conditions for key in keys):
        return
    if any(key not in conditions for key in keys):
        raise CalculationError('GPIO source conditions must include both supply endpoints and current')
    low = bounds(conditions['VDD_min'], 'V', 'GPIO supply lower endpoint')[1]
    high = bounds(conditions['VDD_max'], 'V', 'GPIO supply upper endpoint')[0]
    rating = bounds(conditions['output_current'], 'A', 'GPIO source-current condition')[0]
    # GPIO VDD_min/VDD_max are strict endpoints, matching the cited CMOS domain.
    if not low < b['supply'][0] <= b['supply'][1] < high:
        raise CalculationError('GPIO supply is outside its strict source-voltage domain')
    if b['source_current_rating'][1] > rating:
        raise CalculationError('GPIO requested source-current rating exceeds its source condition')


def _calculate_envelope(name, inputs, b, module=calculators_envelope):
    try:
        result = _result(name, inputs, module.calculate(name, b))
    except ValueError as error:
        raise CalculationError(str(error)) from error
    for value in result.values():
        value['note'] = 'Conditional engineering interval; preserve source applicability and operating envelope.'
    return result


def _calculate_drivers(name, inputs, b):
    if name == 'gpio_drive':
        _gpio_source_conditions(inputs, b)
    if name in ('tps5430_ccm_design', 'tps5430_output_ripple'):
        resistance = inputs['on_resistance']
        conditions = resistance.get('conditions', {})
        if resistance.get('basis') == 'DATASHEET':
            voltage = conditions.get('input_voltage')
            if voltage is not None and bounds(voltage, 'V', 'RDS test voltage') != b['input_voltage']:
                raise CalculationError('RDS test voltage differs from the requested operating interval')
            if 'gate_voltage' in conditions:
                raise CalculationError('RDS bootstrap test voltage needs a supported engineering model input')
    try:
        output = _result(name, inputs, calculators_drivers.calculate(name, b))
    except ValueError as error:
        raise CalculationError(str(error)) from error
    if name in ('tps5430_ccm_design', 'tps5430_output_ripple'):
        for value in output.values():
            value['note'] = 'TPS5430 source design equations at the supplied CCM operating point.'
    return output


def _calculate_power(name, inputs, b):
    conditions = {}
    if name == 'mosfet_conduction_loss':
        conditions = inputs['on_resistance'].get('conditions', {})
        if not isinstance(conditions, dict):
            raise CalculationError('RDS(on) conditions must be quantities')
        for key, condition in conditions.items():
            if (not isinstance(condition, dict) or not isinstance(condition.get('unit'), str)
                    or not condition['unit']):
                raise CalculationError('RDS(on) conditions require units and finite values')
            bounds(condition, condition['unit'], key)
        temperatures = [key for key in ('TJ', 'TA') if key in conditions]
        if not temperatures:
            raise CalculationError('RDS(on) requires an explicit temperature condition')
        for key in temperatures:
            bounds(conditions[key], 'degC', key)
    try:
        result = _result(name, inputs, calculators_power.calculate(name, b))
    except ValueError as error:
        raise CalculationError(str(error)) from error
    for value in result.values():
        value['conditions'] = dict(conditions)
        if name.startswith('buck_'):
            value['note'] = ('Ideal fixed-frequency CCM model; source and block evidence must establish '
                             'this operating domain. PFM or unknown switching frequency is unsupported.')
        elif name == 'mosfet_conduction_loss':
            value['note'] = 'Conduction loss at the supplied RDS(on) conditions; excludes switching losses.'
    return result


def evaluate_check(check, parameters, components=None):
    """Resolve one block check and evaluate its worst-case output bound."""
    try:
        def resolve(value):
            if set(value) == {'parameter'}:
                return parameters[value['parameter']]
            if set(value) in ({'component', 'parameter'}, {'component', 'parameter', 'bound'}):
                quantity = (components or {})[value['component']]['parameters'][value['parameter']]
                if 'bound' not in value:
                    return quantity
                bound = value['bound']
                if bound not in ('min', 'max', 'value') or bound not in quantity:
                    raise CalculationError('Requested guaranteed bound is unavailable')
                return {
                    **{k:v for k,v in quantity.items() if k not in ('value','min','typ','max')},
                    'value': quantity[bound],
                }
            return value
        resolved = {key: resolve(value) for key, value in check['inputs'].items()}
        outputs = calculate(check['calculator'], resolved)
        requirement = check['require']
        value = outputs[requirement['output']]
        low, high = bounds(value, value['unit'], requirement['output'])
        limit_low, limit_high = bounds(resolve(requirement['limit']), value['unit'], 'limit')
        if requirement['operator'] == 'LE':
            passed = high <= limit_low
        elif requirement['operator'] == 'GE':
            passed = low >= limit_high
        else:
            raise CalculationError('Unknown comparison operator')
        return {'calculator': check['calculator'], 'result': 'PASS' if passed else 'FAIL',
                'output': requirement['output'], 'value': value}
    except (ValueError, KeyError, TypeError) as error:
        return {'calculator': check.get('calculator', ''), 'result': 'REFUSED', 'reason': str(error)}


def _calculate_analog(name, inputs, b):
    try:
        result = _result(name, inputs, calculators_analog.calculate(name, b))
    except ValueError as error:
        raise CalculationError(str(error)) from error
    for value in result.values():
        value['note'] = calculators_analog.NOTES[name]
    return result
