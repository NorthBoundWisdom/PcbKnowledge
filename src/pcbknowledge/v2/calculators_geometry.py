"""Source-traceable signed affine geometry with exact decimal-input arithmetic."""
from decimal import Decimal
from fractions import Fraction
import math

INPUT_UNITS = {'geometry_affine': {'offset': 'mm', 'dimension': 'mm', 'factor': '1'}}
NAME = 'geometry_affine'


def bounds(q, unit):
    if not isinstance(q, dict) or q.get('unit') != unit:
        raise ValueError('Exact unit required: ' + unit)
    numeric = set(q) & {'value', 'min', 'typ', 'max'}
    if numeric == {'value'}:
        lo = hi = q['value']
    elif numeric in ({'min', 'max'}, {'min', 'typ', 'max'}):
        lo, hi = q['min'], q['max']
    else:
        raise ValueError('Value or complete guaranteed interval required')
    for v in [lo, hi] + ([q['typ']] if 'typ' in q else []):
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError('Finite real numbers, not booleans, required')
    if lo > hi or ('typ' in q and not lo <= q['typ'] <= hi):
        raise ValueError('Invalid bounds')
    return Fraction(Decimal(str(lo))), Fraction(Decimal(str(hi)))


def _anchor(q, unit, depth):
    if depth > 32:
        raise ValueError('Geometry expression depth exceeded')
    lo, hi = bounds(q, unit)
    if unit == '1':
        if q.get('basis') != 'ENGINEERING_DEFAULT' or not q.get('note'):
            raise ValueError('Affine coefficient must be an explicit mathematical convention')
    elif q.get('basis') == 'DATASHEET':
        evidence = q.get('evidence', {})
        if (not isinstance(evidence.get('source'), str)
                or not evidence['source'].startswith('source:')
                or type(evidence.get('page')) is not int or evidence['page'] < 1):
            raise ValueError('Dimensional source leaf requires an evidence anchor')
    elif q.get('basis') == 'CALCULATED':
        if q.get('calculator') != NAME:
            raise ValueError('Geometry cannot alias an unrelated calculator')
        actual = calculate(q.get('inputs'), depth + 1)['coordinate']
        keys = {'value', 'min', 'typ', 'max', 'unit'}
        if {k: v for k, v in q.items() if k in keys} != {k: v for k, v in actual.items() if k in keys}:
            raise ValueError('Nested calculated quantity does not match executable result')
    elif not (q.get('basis') == 'ENGINEERING_DEFAULT' and lo == hi == 0 and q.get('note')):
        raise ValueError('Dimensional leaves must be source-backed; only zero-origin constant exempt')
    return lo, hi


def calculate(inputs, depth=0):
    if not isinstance(inputs, dict) or set(inputs) != {'offset', 'dimension', 'factor'}:
        raise ValueError('Inputs must be exactly offset, dimension, factor')
    a, b, f = (_anchor(inputs[k], u, depth) for k, u in INPUT_UNITS[NAME].items())
    # Exact rational arithmetic on decimal-spelled inputs; no ambient context.
    products = [x * y for x in b for y in f]
    lo, hi = a[0] + min(products), a[1] + max(products)
    try:
        values = [float(lo), float(hi)]
    except OverflowError as error:
        raise ValueError('Nonfinite geometry output') from error
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Nonfinite geometry output')
    scalar = all('value' in q for q in inputs.values())
    if scalar and any(exact != 0 and rounded == 0 for exact, rounded in zip((lo, hi), values)):
        raise ValueError('Nonzero scalar geometry underflow')
    if not scalar:
        if Fraction(values[0]) > lo:
            values[0] = math.nextafter(values[0], -math.inf)
        if Fraction(values[1]) < hi:
            values[1] = math.nextafter(values[1], math.inf)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Outward-rounded geometry exceeds finite range')
    result = {'unit': 'mm', 'conditions': {}, 'basis': 'CALCULATED',
              'calculator': NAME, 'inputs': inputs}
    if scalar:
        result['value'] = values[0]
    else:
        result.update(min=values[0], max=values[1])
    return {'coordinate': result}
