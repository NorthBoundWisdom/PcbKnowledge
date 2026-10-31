"""Conservative full-circle enclosure proof for observed return-path arcs."""
from fractions import Fraction
from math import isqrt

from .layout_return import corridor_margin2, point, reference_contact, reference_polygons


class ArcNotCheckable(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.reason_code = code


def ceil_radius_nm(radius2):
    """Smallest integer-nanometre radius whose square encloses radius2 (mm2)."""
    if radius2 <= 0:
        raise ArcNotCheckable('DEGENERATE_ARC', 'Positive circumcircle radius required')
    scaled = radius2 * 10**12
    radius = isqrt(scaled.numerator // scaled.denominator)
    if radius * radius * scaled.denominator < scaled.numerator:
        radius += 1
    return Fraction(radius, 10**6)


def circle_box(arc):
    a, b, c = (point(arc[key]) for key in ('start', 'mid', 'end'))
    bx, by = b[0] - a[0], b[1] - a[1]
    cx, cy = c[0] - a[0], c[1] - a[1]
    denominator = 2 * (bx * cy - by * cx)
    if not denominator:
        raise ArcNotCheckable('DEGENERATE_ARC', 'Distinct noncollinear arc points required')
    b2, c2 = bx * bx + by * by, cx * cx + cy * cy
    dx, dy = (b2 * cy - c2 * by) / denominator, (bx * c2 - cx * b2) / denominator
    center = (a[0] + dx, a[1] + dy)
    radius = ceil_radius_nm(dx * dx + dy * dy)
    return (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)


def check_box_voids(board, box, half_width):
    holes = [(via['at'], [via['drill']] * 2, [0, 0]) for via in board['vias']]
    holes.extend((pad['at'], pad.get('drill_size') or [pad['drill']] * 2, pad.get('drill_offset', [0, 0]))
                 for footprint in board['footprints'].values() for pads in footprint['pads'].values()
                 for pad in pads if pad.get('drill'))
    for at, size, offset in holes:
        center = point(at)
        radius = max(Fraction(str(value)) for value in size) / 2
        radius += sum(abs(Fraction(str(value))) for value in offset)
        distance2 = sum(max(box[i] - center[i], 0, center[i] - box[i + 2]) ** 2 for i in range(2))
        if distance2 <= (radius + half_width) ** 2:
            raise ArcNotCheckable('ARC_BOX_DRILL_INTERSECTION', 'Physical hole may interrupt arc enclosure')


def measure_arc(board, rule, arc, index):
    try:
        layer = {'F.Cu': 'B.Cu', 'B.Cu': 'F.Cu'}[arc['layer']]
        half_width = Fraction(str(arc['width'])) / 2
        if half_width <= 0:
            raise ArcNotCheckable('INVALID_ARC_WIDTH', 'Positive arc width required')
        box = circle_box(arc)
        outline = tuple(Fraction(str(value)) for value in board['outline']['bounds'])
        if (box[0] - half_width < outline[0] or box[1] - half_width < outline[1]
                or box[2] + half_width > outline[2] or box[3] + half_width > outline[3]):
            raise ArcNotCheckable('ARC_BOX_OUTSIDE_OUTLINE', 'Full arc enclosure is not inside the board outline')
        check_box_voids(board, box, half_width)
        vertices = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
        edges = [{'start': a, 'end': b} for a, b in zip(vertices, vertices[1:] + vertices[:1])]
        for polygon in reference_polygons(board, rule['return_net'], layer):
            margins = [corridor_margin2(edge, polygon) for edge in edges]
            if any(value is None or value < half_width ** 2 for value in margins):
                continue
            if reference_contact(board, rule['return_net'], layer, polygon) is True:
                return {'arc': index, 'signal_layer': arc['layer'], 'reference_layer': layer,
                        'width_mm': float(2 * half_width), 'covered': True,
                        'method': 'OUTWARD_NM_FULL_CIRCLE_BOX', 'enclosure_bounds_mm': [float(v) for v in box]}
        raise ArcNotCheckable('ARC_ENCLOSURE_UNPROVED',
                              'One directly contacted return polygon must cover the entire arc enclosure')
    except ArcNotCheckable:
        raise
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as error:
        raise ArcNotCheckable('UNSUPPORTED_ARC_GEOMETRY', str(error)) from error
