"""Necessary near-distance bounds for disjoint authoritative courtyard rectangles."""
from .placement import EPSILON, PlacementError, _box, _local_points, _ref


def minimum_separated_distance(geometry, subject, target):
    """Minimize endpoint distance over every orthogonal orientation and separating halfplane.

    Translation is unconstrained and obstacles/edges/keepouts are omitted. Consequently
    this is only a necessary bound: passing does not establish joint feasibility.
    Repeated electrical aliases use the least bound over all physical pad pairs.
    """
    left, right = _ref(subject), _ref(target)
    if left == right:
        return 0.0
    minimum = float('inf')
    for a_angle in (0, 90, 180, 270):
        a = _box(geometry[left], (0, 0, a_angle))
        for b_angle in (0, 90, 180, 270):
            b = _box(geometry[right], (0, 0, b_angle))
            for u in _local_points(subject, geometry, a_angle):
                for v in _local_points(target, geometry, b_angle):
                    bounds = (a[2] - b[0] + v[0] - u[0], b[2] - a[0] - v[0] + u[0],
                              a[3] - b[1] + v[1] - u[1], b[3] - a[1] - v[1] + u[1])
                    minimum = min(minimum, max(0.0, min(bounds)))
    return minimum


def check_isolated_near_bounds(geometry, prepared_rules):
    """Reject only a proven incompatible near rule under orthogonal courtyard geometry."""
    for index, rule in prepared_rules:
        if rule['kind'] != 'PLACE_NEAR':
            continue
        minimum = minimum_separated_distance(geometry, rule['subject'], rule['target'])
        if minimum > rule['max_distance']['value'] + EPSILON:
            raise PlacementError('Near constraint incompatible with disjoint orthogonal courtyards: '
                                 + rule['subject'] + ' / ' + rule['target']
                                 + '; minimum endpoint distance=' + str(minimum), constraints=(index,))
