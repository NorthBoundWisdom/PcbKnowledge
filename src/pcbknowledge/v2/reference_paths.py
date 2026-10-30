"""Typed guard/reference-path requirements; copper realization remains downstream."""
import math


FIELDS = {
    'GUARD_RING': {'net', 'guard_net', 'min_clearance', 'min_width'},
    'RETURN_PATH': {'net', 'return_net'},
}
NET_FIELDS = ('net', 'sense_nets', 'nets', 'guard_net', 'return_net')


def positive_mm(value):
    number = value.get('value') if isinstance(value, dict) else None
    if (not isinstance(value, dict) or value.get('unit') != 'mm' or value.get('status')
            or isinstance(number, bool) or not isinstance(number, (int, float))
            or not math.isfinite(number) or number <= 0):
        raise ValueError('Guard geometry requires finite positive scalar millimeters')
    return number


def validate_reference_path(constraint, nets, fab=None):
    kind = constraint['kind']
    if kind not in FIELDS:
        return
    if set(constraint) != {'kind', *FIELDS[kind]}:
        raise ValueError('Wrong fields for ' + kind)
    second = 'guard_net' if kind == 'GUARD_RING' else 'return_net'
    if constraint['net'] not in nets or constraint[second] not in nets:
        raise ValueError('Guard/reference path names an unknown net')
    if constraint['net'] == constraint[second]:
        raise ValueError('Signal and guard/reference nets must remain distinct after net merging')
    if kind == 'GUARD_RING':
        for field, floor in (('min_width', 'trace_width_min'), ('min_clearance', 'clearance_min')):
            value = positive_mm(constraint[field])
            if fab is not None and value < positive_mm(fab[floor]):
                raise ValueError('Guard geometry is below the selected fab minimum: ' + field)


def validate_reference_paths(layout, nets, fab=None):
    for constraint in layout:
        validate_reference_path(constraint, nets, fab)
