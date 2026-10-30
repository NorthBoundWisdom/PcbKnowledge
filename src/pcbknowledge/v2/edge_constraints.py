"""Feasibility of directional edge distances to the same component or pad origin."""
from math import inf

from .layout import EDGE_EQUALITY_TOLERANCE_MM, quantity
from .layout_board import limit


AXES = (('width', 'LEFT', 'RIGHT'), ('length', 'TOP', 'BOTTOM'))


def validate_edge_constraints(layout, envelope, *, dimensions=None):
    """Intersect edge intervals and shared board spans, without fixing an envelope.

    Envelope quantities bound the maximum outline, even when written as scalars.
    Optional dimensions describe an actual rectangle, using layout_board's axes.
    Different pad endpoints are distinct reference points, not footprint origins.
    """
    intervals = {}
    for rule in layout:
        if rule['kind'] not in ('EDGE_PLACEMENT', 'EDGE_DISTANCE'):
            continue
        field = 'distance' if rule['kind'] == 'EDGE_DISTANCE' else 'max_distance'
        distance = quantity(rule, field, 'mm')
        low, high = 0, distance
        if rule['kind'] == 'EDGE_DISTANCE':
            low = max(0, distance - EDGE_EQUALITY_TOLERANCE_MM)
            high = distance + EDGE_EQUALITY_TOLERANCE_MM
        edges = intervals.setdefault(rule['subject'], {})
        previous = edges.get(rule['edge'], (0, inf))
        edges[rule['edge']] = max(low, previous[0]), min(high, previous[1])
    for axis, near, far in AXES:
        low, high = 0, limit(envelope['max_' + axis], 'max')
        if dimensions is not None:
            actual = limit({'value': dimensions[axis], 'unit': 'mm'})
            low, high = actual, min(high, actual)
        for subject, edges in sorted(intervals.items()):
            a, b = edges.get(near, (0, inf)), edges.get(far, (0, inf))
            if a[0] > a[1] + 1e-9 or b[0] > b[1] + 1e-9:
                raise ValueError('Incompatible edge constraints for ' + subject + ' on ' + axis)
            low, high = max(low, a[0] + b[0]), min(high, a[1] + b[1])
            if low > high + 1e-9 or high <= 0:
                raise ValueError('Incompatible edge constraints for shared board ' + axis + ': ' + subject)
