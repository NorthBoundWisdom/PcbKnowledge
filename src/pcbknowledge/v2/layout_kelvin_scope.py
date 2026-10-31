"""Conservative separation of unsupported copper from the declared sense nets."""
from .layout_kelvin_geometry import UnsupportedKelvin, point, scalar


def envelope(points, margin=0):
    if not points or len(points) > 4096:
        raise UnsupportedKelvin('Unsupported or excessive copper envelope')
    return (min(p[0] for p in points) - margin, min(p[1] for p in points) - margin,
            max(p[0] for p in points) + margin, max(p[1] for p in points) + margin)


def pad_envelope(pad):
    if pad['shape'] not in ('rect', 'circle', 'oval', 'roundrect'):
        raise UnsupportedKelvin('Unbounded unsupported pad shape')
    scalar(pad.get('rotation', 0))
    size = point(pad['size'])
    if min(size) <= 0:
        raise UnsupportedKelvin('Positive pad dimensions required')
    # Half the sum bounds the corner radius under every rotation.
    radius = sum(size) / 2
    if pad.get('drill') or pad.get('drill_size'):
        drill = point(pad.get('drill_size') or [pad['drill'], pad['drill']])
        if min(drill) <= 0:
            raise UnsupportedKelvin('Positive drill dimensions required')
        offset = point(pad.get('drill_offset', [0, 0]))
        radius = max(radius, sum(drill) / 2 + sum(abs(value) for value in offset))
    return envelope([point(pad['at'])], radius)


def arc_envelope(arc):
    a, b, c = (point(arc[key]) for key in ('start', 'mid', 'end'))
    bx, by, cx, cy = b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1]
    determinant = 2 * (bx * cy - by * cx)
    if not determinant:
        raise UnsupportedKelvin('Degenerate arc has no supported copper envelope')
    ux = ((bx * bx + by * by) * cy - (cx * cx + cy * cy) * by) / determinant
    uy = ((cx * cx + cy * cy) * bx - (bx * bx + by * by) * cx) / determinant
    width = scalar(arc['width'])
    if width <= 0:
        raise UnsupportedKelvin('Positive arc width required')
    radius_bound = abs(ux) + abs(uy) + width / 2
    return envelope([(a[0] + ux, a[1] + uy)], radius_bound)


def routing_envelopes(board):
    result = []
    for via in board.get('vias', []):
        size, drill = scalar(via['size']), scalar(via['drill'])
        if min(size, drill) <= 0:
            raise UnsupportedKelvin('Positive via dimensions required')
        result.append((via['net'], set(via['layers']), envelope([point(via['at'])], max(size, drill) / 2)))
    for arc in board.get('arcs', []):
        result.append((arc['net'], {arc['layer']}, arc_envelope(arc)))
    for zone in board.get('zones', []):
        polygons = zone.get('polygons', []) + zone.get('filled_polygons', [])
        if sum(len(polygon) for polygon in polygons) > 4096:
            raise UnsupportedKelvin('Zone envelope resource bound exceeded')
        box = envelope([point(p) for polygon in polygons for p in polygon])
        result.append((zone['net'], set(zone.get('layers', [])) | {zone['layer']}, box))
    return result


def separate_unsupported(unsupported, shapes, nets):
    relevant = [shape for shape in shapes if shape['net'] in nets]
    for net, layers, box in unsupported:
        if net in nets:
            raise UnsupportedKelvin('Unsupported copper on a declared sense net')
        for shape in relevant:
            # Through vias connect every intervening layer; unknown layer spans are conservative.
            common = len(layers) != 1 or '*.Cu' in layers or bool(layers & shape['layers'])
            overlap = all(max(box[i], shape['box'][i]) <= min(box[i + 2], shape['box'][i + 2])
                          for i in range(2))
            if common and overlap:
                raise UnsupportedKelvin('Unsupported copper or drill may contact a sense branch')


def check_outline(board, shapes, nets):
    outline = board.get('outline', {})
    if not outline.get('closed') or not outline.get('rectangular'):
        raise UnsupportedKelvin('A closed rectangular board without cutouts is required')
    box = outline['bounds']
    if len(box) != 4:
        raise UnsupportedKelvin('Four board-boundary coordinates required')
    box = tuple(scalar(value) for value in box)
    if box[0] >= box[2] or box[1] >= box[3]:
        raise UnsupportedKelvin('Positive board boundary required')
    for shape in shapes:
        if shape['net'] in nets and not all(box[i] <= shape['box'][i]
                                           and shape['box'][i + 2] <= box[i + 2] for i in range(2)):
            raise UnsupportedKelvin('Sense copper extends beyond the supported board boundary')
