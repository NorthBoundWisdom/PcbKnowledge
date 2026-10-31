"""Read-only full-width conductor intersection with a package-local rectangle."""
from .conductor_keepouts import number, validate_region


def _point(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError('Expected measured coordinate pair')
    return tuple(number(v) for v in value)


def _local(point, footprint):
    x, y = _point(point)
    ox, oy = _point(footprint['at'])
    angle = number(footprint['rotation']) % 360
    if angle not in (0, 90, 180, 270):
        raise ValueError('Exact conductor keepout checks support cardinal component rotations only')
    cosine, sine = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[angle]
    x, y = (x - ox) * cosine - (y - oy) * sine, (x - ox) * sine + (y - oy) * cosine
    if footprint['layer'] not in ('F.Cu', 'B.Cu'):
        raise ValueError('Unknown component copper side')
    return x, -y if footprint['layer'] == 'B.Cu' else y


def _point_box(point, box):
    x, y = point
    dx = max(box[0] - x, 0, x - box[2])
    dy = max(box[1] - y, 0, y - box[3])
    return dx * dx + dy * dy


def _point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == dy == 0:
        return (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return (p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2


def _crosses(a, b, box):
    low, high = 0, 1
    for axis in (0, 1):
        delta = b[axis] - a[axis]
        if delta == 0:
            if not box[axis] <= a[axis] <= box[axis + 2]:
                return False
            continue
        limits = sorted(((box[axis] - a[axis]) / delta, (box[axis + 2] - a[axis]) / delta))
        low, high = max(low, limits[0]), min(high, limits[1])
        if low > high:
            return False
    return True


def _segment_box(a, b, box):
    if _crosses(a, b, box):
        return 0
    distances = [_point_box(a, box), _point_box(b, box)]
    distances.extend(_point_segment((x, y), a, b) for x in (box[0], box[2]) for y in (box[1], box[3]))
    return min(distances)


def _measure(board, rule, max_items):
    box = validate_region(rule['region'])
    footprint = board['footprints'][rule['subject']]
    _local(footprint['at'], footprint)
    if board.get('unsupported'):
        raise ValueError('Unsupported board geometry prevents conductor exclusion proof')
    layers = board.get('copper_layers')
    if not layers or len(set(layers)) != len(layers) or any(not layer.endswith('.Cu') for layer in layers):
        raise ValueError('Explicit board copper layer set required')
    forbid = rule['region']['forbid']
    if 'TRACK' in forbid and board.get('arcs'):
        raise ValueError('Arc conductor intersection is not supported')
    groups = [(kind, board.get(key, [])) for kind, key in [('TRACK', 'segments'), ('VIA', 'vias')]
              if kind in forbid]
    if any(not isinstance(items, list) for _, items in groups):
        raise ValueError('Conductor geometry must be explicit lists')
    if sum(len(items) for _, items in groups) > max_items:
        raise ValueError('Conductor intersection item budget exhausted')
    items = [(kind, item) for kind, group in groups for item in group]
    collisions = []
    for index, (kind, item) in enumerate(items):
        if kind == 'TRACK':
            if item['layer'] not in layers:
                raise ValueError('Track has unknown copper layer')
            radius = number(item['width']) / 2
            a, b = _local(item['start'], footprint), _local(item['end'], footprint)
            distance = _segment_box(a, b, box)
        else:
            if not item.get('layers') or not set(item['layers']) <= set(layers):
                raise ValueError('Via has unknown copper layer span')
            radius = number(item['size']) / 2
            distance = _point_box(_local(item['at'], footprint), box)
        if radius <= 0:
            raise ValueError('Nonpositive conductor width/diameter')
        if distance <= radius * radius:
            collisions.append({'kind': kind, 'index': index})
    return {'kind': 'CONDUCTOR_KEEPOUT', 'result': 'FAIL' if collisions else 'PASS',
            'reason': 'Full track/via copper is excluded from the package-local rectangle on all copper layers',
            'region': rule['region']['id'], 'collisions': collisions, 'items_checked': len(items)}


def check_conductor_keepout(board, rule, *, max_items=100000):
    try:
        if type(max_items) is not int or max_items <= 0:
            raise ValueError('Positive conductor intersection budget required')
        return _measure(board, rule, max_items)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        return {'kind': 'CONDUCTOR_KEEPOUT', 'result': 'NOT_CHECKABLE', 'reason': str(error)}
