"""Deterministic joint allocation of externally verified one/two-segment fanout candidates.

No native modules: candidate generation/static geometry proof is a separate process.
All lengths are millimeters. Exhaustion is failure, never an unroutability claim.
"""
import math

MAX_CANDIDATES = 1024


def point_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    square = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / square)) if square else 0
    return point_distance(p, (a[0] + t * dx, a[1] + t * dy))


def segment_distance(a, b, c, d):
    def cross(x, y, z):
        return (y[0] - x[0]) * (z[1] - x[1]) - (y[1] - x[1]) * (z[0] - x[0])
    if cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0:
        if max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])):
            if max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])):
                return 0.0
    return min(point_segment(a, c, d), point_segment(b, c, d),
               point_segment(c, a, b), point_segment(d, a, b))


def segments(row):
    points = [row['start']] + ([row['bend']] if row['bend'] is not None else [])
    points += ([row['bend2']] if row.get('bend2') is not None else []) + [row['end']]
    return list(zip(points, points[1:]))


def compatible(a, b, clearance):
    # Keep separate via holes/copper even on the same net; no overlapping drill hits.
    if point_distance(a['end'], b['end']) < (a['via_diameter'] + b['via_diameter']) / 2 + clearance:
        return False
    if a['net'] == b['net']:
        return True
    if a['layer'] == b['layer']:
        if any(segment_distance(x, y, z, w) < (a['width'] + b['width']) / 2 + clearance
               for x, y in segments(a) for z, w in segments(b)):
            return False
    # Through-vias occupy both layers, even when traces are on opposite sides.
    for trace, via in ((a, b), (b, a)):
        if any(point_segment(via['end'], x, y) < (trace['width'] + via['via_diameter']) / 2 + clearance
               for x, y in segments(trace)):
            return False
    return True


def _validate(row):
    required = {'net', 'layer', 'start', 'end', 'width', 'via_diameter', 'via_drill', 'bend'}
    if (not required <= set(row) or set(row) - required - {'bend2', 'pad_center'}
            or not isinstance(row['net'], str) or not row['net']):
        raise ValueError('Malformed fanout candidate')
    if row['layer'] not in ('F.Cu', 'B.Cu'):
        raise ValueError('Unsupported fanout layer')
    for key in ('start', 'end', 'bend', 'bend2', 'pad_center'):
        if key in ('bend', 'bend2', 'pad_center') and row.get(key) is None:
            continue
        if not isinstance(row[key], (list, tuple)) or len(row[key]) != 2:
            raise ValueError('Malformed fanout point')
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) or abs(v) > 1e9 for v in row[key]):
            raise ValueError('Nonfinite fanout coordinate')
    for key in ('width', 'via_diameter', 'via_drill'):
        value = row[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 < value <= 1e9):
            raise ValueError('Invalid fanout dimension')
    if row['via_drill'] >= row['via_diameter'] or any(a == b for a, b in segments(row)):
        raise ValueError('Invalid fanout via or zero-length trace')


def candidate_rank(row):
    return (sum(point_distance(a, b) for a, b in segments(row)), tuple(row['end']),
            tuple(row['bend'] or []), tuple(row.get('bend2') or []), tuple(row['start']))


def bounded_candidates(rows):
    """Explicit deterministic finite-domain truncation, not a geometric impossibility claim."""
    retained = sorted(rows, key=candidate_rank)[:MAX_CANDIDATES]
    return retained, {'legal_examined': len(rows), 'retained': len(retained),
                      'truncated': len(rows) - len(retained), 'candidate_limit': MAX_CANDIDATES}


def allocate(candidates, clearance, *, max_search_nodes=100000):
    """Return one compatible candidate for every endpoint or raise ValueError.

    Static pad/outline/keepout checks must already have approved every candidate.
    Search order is stable and does not change the supplied candidate records.
    """
    if not isinstance(candidates, dict) or not candidates or len(candidates) > 128:
        raise ValueError('Fanout needs 1..128 explicit endpoints')
    if (isinstance(clearance, bool) or not isinstance(clearance, (int, float))
            or not math.isfinite(clearance) or not 0 <= clearance <= 1e9):
        raise ValueError('Invalid fanout clearance')
    if type(max_search_nodes) is not int or max_search_nodes < 1:
        raise ValueError('Invalid fanout search budget')
    ordered = {}
    for endpoint, rows in candidates.items():
        if (not isinstance(endpoint, str) or not endpoint or not isinstance(rows, list)
                or not rows or len(rows) > MAX_CANDIDATES):
            raise ValueError('Missing or excessive fanout candidates: ' + str(endpoint)
                             + ' count=' + str(len(rows) if isinstance(rows, list) else 'invalid'))
        for row in rows:
            _validate(row)
        identity = {(row['net'], row['layer'], tuple(row.get('pad_center', row['start'])), row['width'],
                     row['via_diameter'], row['via_drill']) for row in rows}
        if len(identity) != 1:
            raise ValueError('Candidate alternatives changed endpoint or routing constraints')
        ordered[endpoint] = sorted(rows, key=candidate_rank)
    keys = sorted(ordered, key=lambda key: (len(ordered[key]), key))
    chosen = {}
    visited = 0

    def search(index):
        nonlocal visited
        if index == len(keys):
            return True
        key = keys[index]
        for row in ordered[key]:
            visited += 1
            if visited > max_search_nodes:
                raise ValueError('Fanout search budget exhausted; not a routability proof')
            if all(compatible(row, old, clearance) for old in chosen.values()):
                chosen[key] = row
                if search(index + 1):
                    return True
                del chosen[key]
        return False

    if not search(0):
        raise ValueError('No joint allocation among the verified fanout candidates')
    return {'allocation': {key: dict(chosen[key]) for key in sorted(chosen)}, 'search_nodes': visited}
