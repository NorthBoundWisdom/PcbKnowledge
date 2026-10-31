"""Measure directly pad-connected filled material without routing or modifying boards."""
from fractions import Fraction

from .copper_regions import (Budget, EPS, Unsupported, contact_area, disjoint, edges,
                             material, normalize, point, scalar)


def _finding(result, reason, **values):
    return {'kind': 'COPPER_AREA', 'result': result, 'reason': reason, **values}


def _target(board, rule):
    ref, separator, pin = rule['target'].partition('.pin:')
    if not separator:
        raise Unsupported('A physical target pad is required')
    pads = board['footprints'][ref]['pads'][pin]
    if len(pads) != 1:
        raise Unsupported('Repeated physical target pads cannot be implicitly pooled')
    pad = pads[0]
    if not pad.get('net'):
        raise Unsupported('Target needs an assigned copper net')
    if pad.get('geometry_unsupported') or pad['kind'] != 'smd' or pad['shape'] != 'rect':
        raise Unsupported('Direct-area contact supports rectangular non-drilled SMD target pads')
    if pad.get('drill_size') or pad.get('drill'):
        raise Unsupported('Drilled target copper contact requires annular geometry proof')
    layers = [layer for layer in pad['layers'] if layer.endswith('.Cu')]
    if len(layers) != 1 or layers[0] == '*.Cu':
        raise Unsupported('Target needs one unambiguous copper layer')
    return pad, layers[0]


def _regions(board, pad, layer, budget):
    outline = board['outline']
    if not outline.get('closed') or not outline.get('rectangular'):
        raise Unsupported('A rectangular board boundary is required for area proof')
    xmin, ymin, xmax, ymax = [scalar(v) for v in outline['bounds']]
    if xmin >= xmax or ymin >= ymax:
        raise Unsupported('Degenerate board boundary')
    regions, other_layer = [], 0
    for zone in board['zones']:
        budget.spend()
        if zone['net'] != pad['net']:
            continue
        if zone.get('unsupported') or zone.get('layers'):
            raise Unsupported('Ambiguous multilayer or unsupported filled geometry')
        if zone['layer'] != layer:
            other_layer += len(zone['filled_polygons'])
            continue
        for points in zone['filled_polygons']:
            region = normalize(points, budget)
            if any(not (xmin <= x <= xmax and ymin <= y <= ymax) for x, y in region['outer']):
                raise Unsupported('Filled copper extends outside board boundary')
            regions.append(region)
    disjoint(regions, budget)
    return regions, other_layer


def _distance_segment_squared(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    fraction = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return (p[0] - a[0] - fraction * dx) ** 2 + (p[1] - a[1] - fraction * dy) ** 2


def _drills(board, budget):
    result = []
    for footprint in board['footprints'].values():
        for pads in footprint['pads'].values():
            for pad in pads:
                budget.spend()
                size = pad.get('drill_size')
                if size is None:
                    if pad.get('drill'):
                        raise Unsupported('Physical drill shape is missing')
                    continue
                width, height = point(size)
                if min(width, height) <= 0:
                    raise Unsupported('Invalid physical drill dimensions')
                x, y = point(pad['at'])
                dx, dy = point(pad.get('drill_offset', [0, 0]))
                angle = scalar(pad['rotation']) % 360
                if (dx or dy) and angle not in (0, 90, 180, 270):
                    raise Unsupported('Offset drill at noncardinal rotation is unsupported')
                cosine, sine = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}.get(angle, (1, 0))
                center = (x + dx * cosine + dy * sine, y - dx * sine + dy * cosine)
                result.append((center, max(width, height) / 2))
    for via in board.get('vias', []):
        budget.spend()
        drill = scalar(via['drill'])
        if drill <= 0:
            raise Unsupported('Invalid via drill')
        result.append((point(via['at']), drill / 2))
    return result


def _clear_drills(board, regions, budget):
    for center, radius in _drills(board, budget):
        for region in regions:
            if material(center, region, budget) >= 0:
                raise Unsupported('Physical drill intersects counted material; void subtraction is unproven')
            for ring in [region['outer'], *region['holes']]:
                for a, b in edges(ring):
                    budget.spend()
                    if _distance_segment_squared(center, a, b) <= (radius + EPS) ** 2:
                        raise Unsupported('Drill envelope may intersect counted material or a hole boundary')


def _indirect_possible(board, target, budget):
    for kind in ('segments', 'arcs', 'vias'):
        for item in board.get(kind, []):
            budget.spend()
            if item.get('net') == target['net']:
                return True
    # Other physical pads can bridge filled islands directly or through chains.
    # Do not infer that connectivity or thermal equivalence from equal net names.
    for footprint in board['footprints'].values():
        for pads in footprint['pads'].values():
            for pad in pads:
                budget.spend()
                if pad is not target and pad.get('net') == target['net']:
                    return True
    return False


def _measure(board, rule, budget):
    if board.get('unsupported'):
        raise Unsupported('Unsupported board geometry prevents filled-area proof')
    minimum = rule['min_area']
    if minimum.get('unit') != 'mm2' or minimum.get('status'):
        raise Unsupported('Area limit requires concrete square millimeters')
    limit = scalar(minimum['value'])
    if limit <= 0:
        raise Unsupported('Area limit must be positive')
    pad, layer = _target(board, rule)
    regions, other_layer = _regions(board, pad, layer, budget)
    contacts = [region for region in regions if contact_area(region, pad, budget) > EPS]
    if not contacts:
        raise Unsupported('No positive-area direct same-layer filled copper contact to target pad')
    _clear_drills(board, contacts, budget)
    area = sum((region['area'] for region in contacts), Fraction(0))
    excluded = len(regions) - len(contacts) + other_layer
    details = {'area_mm2': float(area), 'min_area_mm2': float(limit), 'layer': layer,
               'contacting_regions': len(contacts), 'excluded_regions': excluded,
               'subtracted_holes': sum(len(r['holes']) for r in contacts)}
    if area < limit and excluded and _indirect_possible(board, pad, budget):
        return _finding('NOT_CHECKABLE', 'Additional area would rely on unmeasured indirect copper connectivity',
                        **details)
    return _finding('PASS' if area >= limit else 'FAIL',
                    'Nonoverlapping filled material directly contacting the same physical pad; holes excluded',
                    **details)


def check_copper_area(board, rule, *, max_vertices=5000, max_work=2000000):
    """Return a finding; bounded unsupported geometry remains NOT_CHECKABLE."""
    budget = None
    try:
        budget = Budget(max_vertices, max_work)
        result = _measure(board, rule, budget)
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        result = _finding('NOT_CHECKABLE', str(error))
    if budget is not None:
        result.update(vertices_examined=budget.vertices, geometry_work=budget.work)
    return result
