"""Conservative continuous-domain bounds for two near constraints sharing an anchor."""
from itertools import combinations
import math

from .placement import EPSILON, PlacementError, _box, _local_points, _ref


def clipped_circle_box(center, radius, axis, boundary, greater):
    """Enclose a disk/halfplane intersection; never substitute this box for acceptance."""
    radius += EPSILON
    low, high = center[axis] - radius, center[axis] + radius
    if greater:
        low = max(low, boundary - EPSILON)
    else:
        high = min(high, boundary + EPSILON)
    if low > high:
        return None
    nearest = max(low - center[axis], center[axis] - high, 0)
    extent = math.sqrt(max(0, radius * radius - nearest * nearest)) + EPSILON
    other = 1 - axis
    ranges = [(center[other] - extent, center[other] + extent), (low, high)]
    return (ranges[1][0], ranges[0][0], ranges[1][1], ranges[0][1]) if axis == 0 else (
        ranges[0][0], ranges[1][0], ranges[0][1], ranges[1][1])


def near_origin_domains(geometry, rule, anchor_angle):
    anchor, subject = _ref(rule['target']), _ref(rule['subject'])
    anchor_box = _box(geometry[anchor], (0, 0, anchor_angle))
    domains = []
    for angle in (0, 90, 180, 270):
        box = _box(geometry[subject], (0, 0, angle))
        sides = [(0, anchor_box[2] - box[0], True), (0, anchor_box[0] - box[2], False),
                 (1, anchor_box[3] - box[1], True), (1, anchor_box[1] - box[3], False)]
        for target in _local_points(rule['target'], geometry, anchor_angle):
            for point in _local_points(rule['subject'], geometry, angle):
                center = target[0] - point[0], target[1] - point[1]
                for axis, boundary, greater in sides:
                    bounds = clipped_circle_box(center, rule['max_distance']['value'], axis, boundary, greater)
                    if bounds is not None:
                        domains.append((box, bounds))
    return domains


def possibly_separated(first, second):
    a, ar = first
    b, br = second
    return (ar[0] + a[2] <= br[2] + b[0] + EPSILON or br[0] + b[2] <= ar[2] + a[0] + EPSILON
            or ar[1] + a[3] <= br[3] + b[1] + EPSILON or br[1] + b[3] <= ar[3] + a[1] + EPSILON)


def shared_anchor_pair_possible(geometry, first, second):
    """False proves incompatibility; True only means these necessary bounds pass."""
    for angle in (0, 90, 180, 270):
        left = near_origin_domains(geometry, first, angle)
        right = near_origin_domains(geometry, second, angle)
        if any(possibly_separated(a, b) for a in left for b in right):
            return True
    return False


def check_shared_anchor_pairs(geometry, prepared):
    grouped = {}
    for index, rule in prepared:
        if rule['kind'] == 'PLACE_NEAR' and _ref(rule['subject']) != _ref(rule['target']):
            grouped.setdefault(_ref(rule['target']), []).append((index, rule))
    for rules in grouped.values():
        for (ai, a), (bi, b) in combinations(rules, 2):
            if _ref(a['subject']) != _ref(b['subject']) and not shared_anchor_pair_possible(geometry, a, b):
                raise PlacementError('Shared-anchor near constraints have incompatible continuous courtyard domains',
                                     constraints=(ai, bi))


def shared_anchor_packing_possible(geometry, rules):
    """Necessary common-cross-section packing bound, over continuous origin domains."""
    anchors = {_ref(rule['target']) for rule in rules}
    subjects = {_ref(rule['subject']) for rule in rules}
    if len(anchors) != 1 or len(subjects) != len(rules):
        raise ValueError('Packing proof requires one anchor and distinct subjects')
    for angle in (0, 90, 180, 270):
        domains = [near_origin_domains(geometry, rule, angle) for rule in rules]
        if any(not values for values in domains):
            continue
        impossible = False
        for axis in (0, 1):
            low = max(bounds[axis + 2] + box[axis] for values in domains for box, bounds in values)
            high = min(bounds[axis] + box[axis + 2] for values in domains for box, bounds in values)
            if high - low <= EPSILON:
                continue
            other = 1 - axis
            start = min(bounds[other] + box[other] for values in domains for box, bounds in values)
            end = max(bounds[other + 2] + box[other + 2] for values in domains for box, bounds in values)
            required = sum(min(box[other + 2] - box[other] for box, _ in values) for values in domains)
            if required > end - start + EPSILON:
                impossible = True
        if not impossible:
            return True
    return False
