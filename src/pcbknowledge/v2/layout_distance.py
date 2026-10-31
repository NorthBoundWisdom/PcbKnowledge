"""Read-only nearest same-net copper-edge distance measurements (D90)."""
from fractions import Fraction
import math

from .layout_guard_geometry import pad_shape, shape_distance2
from .layout_guard_contacts import pad_void_ambiguous


class DistanceUnavailable(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def finding(state, reason, **measurements):
    return {'kind': 'PLACE_NEAR', 'result': state, 'reason': reason,
            'datum': 'COPPER_EDGE', **measurements}


def copper_layers(pad, enabled):
    declared = set(pad['layers'])
    return enabled if '*.Cu' in declared else declared & enabled


def candidates(board, rule):
    subject = rule['subject']
    target, separator, pin = rule['target'].partition('.pin:')
    if '.pin:' in subject or not separator or not target or not pin:
        raise DistanceUnavailable('INVALID_RULE', 'COPPER_EDGE requires a component and physical target pin')
    enabled = set(board.get('copper_layers') or [])
    if not enabled or any(not name.endswith('.Cu') for name in enabled):
        raise DistanceUnavailable('UNSUPPORTED_LAYERS', 'Explicit enabled copper layers required')
    if subject not in board['footprints'] or target not in board['footprints']:
        raise DistanceUnavailable('MISSING_COMPONENT', 'Distance endpoint component is absent')
    if pin not in board['footprints'][target]['pads'] or not board['footprints'][target]['pads'][pin]:
        raise DistanceUnavailable('MISSING_PAD', 'Target physical pin pad is absent')
    source_pads = board['footprints'][subject]['pads']
    target_pads = board['footprints'][target]['pads'][pin]
    pairs, same_net = [], False
    for number, pads in sorted(source_pads.items()):
        for source_index, source in enumerate(pads):
            for target_index, destination in enumerate(target_pads):
                if not source.get('net') or source['net'] != destination.get('net'):
                    continue
                same_net = True
                common = copper_layers(source, enabled) & copper_layers(destination, enabled)
                if common:
                    pairs.append((source, destination, {'subject_pad': subject + '.pin:' + number,
                                  'subject_pad_index': source_index, 'target_pad': rule['target'],
                                  'target_pad_index': target_index, 'net': source['net'],
                                  'common_layers': sorted(common)}))
    if not same_net:
        raise DistanceUnavailable('NO_SAME_NET_PAD', 'Subject has no pad on the target pin net')
    if not pairs:
        raise DistanceUnavailable('NO_COMMON_COPPER_LAYER', 'Same-net pads share no enabled copper layer')
    return pairs


def solid_shape(pad):
    if pad.get('kind') != 'smd' or pad.get('drill') or pad.get('drill_size'):
        raise DistanceUnavailable('UNSUPPORTED_GEOMETRY', 'Solid SMT pads without drill apertures required')
    try:
        return pad_shape(pad)
    except (KeyError, ValueError, TypeError) as error:
        raise DistanceUnavailable('UNSUPPORTED_GEOMETRY', str(error)) from error


def distance_leq(a, r, b, s):
    """Compare max(0, sqrt(a)-r) <= max(0, sqrt(b)-s) exactly."""
    if a <= r * r:
        return True
    if b <= s * s:
        return False
    difference = r - s
    if difference >= 0:
        remainder = a - b - difference * difference
        return remainder <= 0 or remainder * remainder <= 4 * difference * difference * b
    magnitude = -difference
    remainder = b + magnitude * magnitude - a
    return b >= magnitude * magnitude and remainder >= 0 and remainder * remainder >= 4 * magnitude * magnitude * b


def measure_pairs(board, pairs, limit):
    best = None
    passed = False
    for source, destination, metadata in pairs:
        first, second = solid_shape(source), solid_shape(destination)
        if pad_void_ambiguous(board, first) or pad_void_ambiguous(board, second):
            raise DistanceUnavailable(
                'DRILL_INTERSECTION', 'A physical drill aperture may remove selected pad copper')
        distance2 = shape_distance2(first, second)
        radii = first['radius'] + second['radius']
        passed |= distance2 <= (limit + radii) ** 2
        if best is None or not distance_leq(best[0], best[1], distance2, radii):
            best = distance2, radii, metadata
    distance2, radii, metadata = best
    distance = max(0.0, math.sqrt(float(distance2)) - float(radii))
    return finding('PASS' if passed else 'FAIL', 'Nearest same-net solid copper edges on a common layer',
                   distance_mm=distance, limit_mm=float(limit), **metadata)


def check_copper_edge(board, rule):
    """Measure only exported copper; never move a component or change its rule."""
    try:
        if board.get('unsupported'):
            raise DistanceUnavailable('UNSUPPORTED_GEOMETRY', 'Board contains unprojected geometry')
        if rule.get('kind') != 'PLACE_NEAR' or rule.get('datum') != 'COPPER_EDGE':
            raise DistanceUnavailable('INVALID_RULE', 'Explicit PLACE_NEAR COPPER_EDGE rule required')
        value = rule['max_distance']
        raw = value.get('value')
        if (value.get('unit') != 'mm' or value.get('status') or type(raw) not in (int, float)
                or not math.isfinite(raw) or raw < 0):
            raise DistanceUnavailable('INVALID_RULE', 'Finite nonnegative scalar millimetre limit required')
        return measure_pairs(board, candidates(board, rule), Fraction(str(raw)))
    except DistanceUnavailable as error:
        return finding('NOT_CHECKABLE', str(error), reason_code=error.code)
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError, OverflowError) as error:
        return finding('NOT_CHECKABLE', str(error), reason_code='INVALID_GEOMETRY')
