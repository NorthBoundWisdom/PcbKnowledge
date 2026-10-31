"""Read-only two-layer return-copper corridor measurements (D100)."""
from fractions import Fraction

from .layout_geometry import simple_polygon


def point(value):
    return tuple(Fraction(str(number)) for number in value)


def point_distance2(p, a, b):
    vector = (b[0] - a[0], b[1] - a[1])
    length = sum(value * value for value in vector)
    if not length:
        return sum((p[i] - a[i]) ** 2 for i in range(2))
    ratio = max(0, min(1, sum((p[i] - a[i]) * vector[i] for i in range(2)) / length))
    return sum((p[i] - a[i] - ratio * vector[i]) ** 2 for i in range(2))


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])



def contains(p, polygon):
    """Exact ray crossing for rational measurements, including the boundary."""
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if cross(a, b, p) == 0 and all(min(a[i], b[i]) <= p[i] <= max(a[i], b[i]) for i in range(2)):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            crossing = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < crossing:
                inside = not inside
    return inside


def segment_distance2(a, b, c, d):
    boxes_overlap = all(max(min(a[i], b[i]), min(c[i], d[i]))
                        <= min(max(a[i], b[i]), max(c[i], d[i])) for i in range(2))
    if boxes_overlap and cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0:
        return Fraction(0)
    return min(point_distance2(a, c, d), point_distance2(b, c, d),
               point_distance2(c, a, b), point_distance2(d, a, b))


def corridor_margin2(segment, polygon):
    """Minimum centerline-to-boundary distance; reject a centerline outside copper."""
    a, b = point(segment['start']), point(segment['end'])
    vertices = [point(p) for p in polygon]
    if not contains(a, vertices) or not contains(b, vertices):
        return None
    return min(segment_distance2(a, b, c, d) for c, d in zip(vertices, vertices[1:] + vertices[:1]))


def may_contact(at, size, polygon):
    center = point(at)
    vertices = [point(p) for p in polygon]
    if contains(center, vertices):
        return True
    radius2 = sum(Fraction(str(value)) ** 2 for value in size) / 4
    return min(point_distance2(center, a, b) for a, b in zip(vertices, vertices[1:] + vertices[:1])) <= radius2


def reference_contact(board, net, layer, polygon):
    """True proves solid contact, None marks possible unmeasured contact."""
    from .layout_guard_contacts import pad_void_ambiguous, possible_pad_shape
    uncertain = False
    for footprint in board['footprints'].values():
        for pads in footprint['pads'].values():
            for pad in pads:
                if pad.get('net') != net or not (layer in pad['layers'] or '*.Cu' in pad['layers']):
                    continue
                solid = pad.get('kind') == 'smd' and not pad.get('drill') and not pad.get('geometry_unsupported')
                if solid and contains(point(pad['at']), [point(p) for p in polygon]):
                    if not pad_void_ambiguous(board, possible_pad_shape(pad)[0]):
                        return True
                uncertain |= may_contact(pad['at'], pad['size'], polygon)
    for via in board['vias']:
        if via['net'] == net:
            uncertain |= may_contact(via['at'], [via['size'], via['size']], polygon)
    return None if uncertain else False


def return_result(state, reason, **measurements):
    return {'kind': 'RETURN_PATH', 'result': state, 'reason': reason, **measurements}


def reference_polygons(board, net, layer):
    polygons = []
    for zone in board['zones']:
        if zone['net'] != net or zone['layer'] != layer:
            continue
        if zone.get('unsupported') or zone.get('layers'):
            raise ValueError('Unsupported return zone geometry')
        for polygon in zone['filled_polygons']:
            if not simple_polygon([point(p) for p in polygon]):
                raise ValueError('Return copper must be simple filled polygons without holes')
            polygons.append(polygon)
    return polygons


def check_return_path(board, rule):
    """Require the entire track-width corridor on the opposite copper layer.

    Each covering polygon must directly contact a physical return-net pad. This
    measures observed routes only, not signal routing completeness.
    """
    try:
        if board.get('unsupported') or set(board.get('copper_layers') or []) != {'F.Cu', 'B.Cu'}:
            raise ValueError('Supported two-layer board geometry required')
        if not board.get('outline', {}).get('closed') or not board['outline'].get('rectangular'):
            raise ValueError('Closed rectangular outline without board slots required')
        if rule['net'] == rule['return_net']:
            raise ValueError('Signal and return nets must differ')
        if any(item['net'] == rule['net'] for item in board['vias']):
            raise ValueError('Signal layer transitions need another measurement method')
        segments = [item for item in board['segments'] if item['net'] == rule['net']]
        arcs = [item for item in board['arcs'] if item['net'] == rule['net']]
        if not segments and not arcs:
            raise ValueError('No routed signal segments or arcs to measure')
        if len({item['layer'] for item in segments + arcs}) != 1:
            raise ValueError('Signal layer transitions need another measurement method')
        from .layout_return_arcs import measure_arc
        measured_arcs = [measure_arc(board, rule, arc, index) for index, arc in enumerate(arcs)]
        measured = [measure_segment(board, rule, segment, index) for index, segment in enumerate(segments)]
        failed = [item['segment'] for item in measured if not item['covered']]
        return return_result('FAIL' if failed else 'PASS',
                             'Full track-width corridor on opposite layer with direct return-pad contact',
                             segments=measured, arcs=measured_arcs, failed_segments=failed, offset_mm=0)
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as error:
        return return_result('NOT_CHECKABLE', str(error),
                             reason_code=getattr(error, 'reason_code', 'UNSUPPORTED_RETURN_GEOMETRY'))


def measure_segment(board, rule, segment, index):
    opposite = {'F.Cu': 'B.Cu', 'B.Cu': 'F.Cu'}
    layer = opposite[segment['layer']]
    radius = Fraction(str(segment['width'])) / 2
    if radius <= 0 or point(segment['start']) == point(segment['end']):
        raise ValueError('Positive width and nonzero signal length required')
    check_drill_corridor(board, segment, radius)
    polygons = reference_polygons(board, rule['return_net'], layer)
    candidates = []
    observed = []
    uncertain = False
    for polygon in polygons:
        margin = corridor_margin2(segment, polygon)
        if margin is not None:
            observed.append(margin)
        if margin is None or margin < radius * radius:
            continue
        contact = reference_contact(board, rule['return_net'], layer, polygon)
        if contact is True:
            candidates.append(margin)
        elif contact is None:
            uncertain = True
    if not candidates and uncertain:
        raise ValueError('Possible return contact needs pad-edge or routed via connection proof')
    best = max(observed, default=None)
    return {'segment': index, 'signal_layer': segment['layer'], 'reference_layer': layer,
            'width_mm': float(2 * radius), 'covered': bool(candidates),
            'observed_boundary_distance_squared_mm2': float(best) if best is not None else None}


def check_drill_corridor(board, segment, radius):
    """Reject possible physical voids not represented by simple filled polygons."""
    holes = [(via['at'], [via['drill'], via['drill']], [0, 0]) for via in board['vias']]
    holes.extend((pad['at'], pad.get('drill_size') or [pad['drill']] * 2, pad.get('drill_offset', [0, 0]))
                 for footprint in board['footprints'].values() for pads in footprint['pads'].values()
                 for pad in pads if pad.get('drill'))
    a, b = point(segment['start']), point(segment['end'])
    for at, size, offset in holes:
        # A circumscribing disc also bounds slotted and offset holes. A possible
        # overlap is unknown, never a fabricated precise clearance violation.
        bound = max(Fraction(str(value)) for value in size) / 2
        bound += sum(abs(Fraction(str(value))) for value in offset)
        if point_distance2(point(at), a, b) <= (radius + bound) ** 2:
            raise ValueError('Drill aperture may interrupt the return-copper corridor')
