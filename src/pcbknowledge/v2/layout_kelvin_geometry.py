"""Exact finite-width contacts for the supported Kelvin copper primitives."""
from fractions import Fraction
import math


class UnsupportedKelvin(ValueError):
    pass


def scalar(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsupportedKelvin('Numeric copper geometry required')
    if abs(value) > 1000000 or not math.isfinite(value):
        raise UnsupportedKelvin('Nonfinite or excessive copper geometry')
    return Fraction(str(value))


def point(value):
    if len(value) != 2:
        raise UnsupportedKelvin('Two-dimensional copper geometry required')
    return tuple(scalar(item) for item in value)


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def point_distance2(p, a, b):
    delta = tuple(b[i] - a[i] for i in range(2))
    length = sum(value * value for value in delta)
    if not length:
        return sum((p[i] - a[i]) ** 2 for i in range(2))
    t = max(0, min(1, sum((p[i] - a[i]) * delta[i] for i in range(2)) / length))
    return sum((p[i] - a[i] - t * delta[i]) ** 2 for i in range(2))


def segment_distance2(a, b, c, d):
    boxes = all(max(min(a[i], b[i]), min(c[i], d[i]))
                <= min(max(a[i], b[i]), max(c[i], d[i])) for i in range(2))
    if boxes and cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0:
        return Fraction(0)
    return min(point_distance2(a, c, d), point_distance2(b, c, d),
               point_distance2(c, a, b), point_distance2(d, a, b))


def corners(box):
    return [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]


def inside(p, shape, strict=False):
    if shape['shape'] == 'rect':
        box = shape['box']
        return all(box[i] < p[i] < box[i + 2] if strict else box[i] <= p[i] <= box[i + 2]
                   for i in range(2))
    distance = point_distance2(p, shape['a'], shape['b'])
    return distance < shape['radius'] ** 2 if strict else distance <= shape['radius'] ** 2


def capsule(a, b, radius, layers, terminal=None):
    if radius <= 0:
        raise UnsupportedKelvin('Positive copper dimensions required')
    return {'shape': 'capsule', 'a': a, 'b': b, 'radius': radius, 'layers': layers, 'terminal': terminal,
            'box': (min(a[0], b[0]) - radius, min(a[1], b[1]) - radius,
                    max(a[0], b[0]) + radius, max(a[1], b[1]) + radius)}


def pad_shape(pad, terminal):
    if pad.get('geometry_unsupported') or pad.get('drill') or pad.get('drill_size'):
        raise UnsupportedKelvin('Unsupported pad geometry or drilled copper')
    if pad.get('kind') != 'smd':
        raise UnsupportedKelvin('Only solid SMD pads are supported')
    layers = {layer for layer in pad['layers'] if layer.endswith('.Cu')}
    if len(layers) != 1 or '*.Cu' in layers:
        raise UnsupportedKelvin('One explicit pad copper layer required')
    at, size = point(pad['at']), point(pad['size'])
    if min(size) <= 0:
        raise UnsupportedKelvin('Positive pad dimensions required')
    if pad['shape'] == 'circle' and size[0] == size[1]:
        return capsule(at, at, size[0] / 2, layers, terminal)
    rotation = scalar(pad.get('rotation', 0)) % 360
    if pad['shape'] != 'rect' or rotation % 90:
        raise UnsupportedKelvin('Only circular or cardinally rotated rectangular pads are supported')
    if rotation % 180:
        size = size[::-1]
    return {'shape': 'rect', 'layers': layers, 'terminal': terminal,
            'box': (at[0] - size[0] / 2, at[1] - size[1] / 2,
                    at[0] + size[0] / 2, at[1] + size[1] / 2)}


def track_shape(track):
    layer = track['layer']
    if not layer.endswith('.Cu') or layer == '*.Cu':
        raise UnsupportedKelvin('Explicit track copper layer required')
    return capsule(point(track['start']), point(track['end']), scalar(track['width']) / 2, {layer})


def contact(left, right):
    """Return negative for separation, zero for tangency, positive for copper overlap."""
    if not left['layers'] & right['layers']:
        return -1
    if left['shape'] == right['shape'] == 'rect':
        return min(min(left['box'][i + 2], right['box'][i + 2])
                   - max(left['box'][i], right['box'][i]) for i in range(2))
    if left['shape'] == 'rect':
        left, right = right, left
    if right['shape'] == 'capsule':
        return (left['radius'] + right['radius']) ** 2 - segment_distance2(
            left['a'], left['b'], right['a'], right['b'])
    vertices = corners(right['box'])
    distance = 0 if inside(left['a'], right) or inside(left['b'], right) else min(
        segment_distance2(left['a'], left['b'], a, b) for a, b in zip(vertices, vertices[1:] + vertices[:1]))
    return left['radius'] ** 2 - distance


def contact_region(left, right, target):
    """Bound the entire contact, not merely a centerline crossing or track endpoint."""
    if not left['layers'] & right['layers'] & target['layers']:
        return 'OUTSIDE'
    box = tuple(max(left['box'][i], right['box'][i]) for i in range(2)) + tuple(
        min(left['box'][i], right['box'][i]) for i in (2, 3))
    if all(inside(p, target, strict=True) for p in corners(box)):
        return 'TARGET'
    probe = {'shape': 'rect', 'box': box, 'layers': target['layers']}
    if contact(probe, target) < 0:
        return 'OUTSIDE'
    raise UnsupportedKelvin('Copper contact straddles the target-pad boundary')


def end_inside(shape, target):
    """A whole round end must lie inside the pad; crossing tracks stay unsupported."""
    radius = shape['radius']
    for end in (shape['a'], shape['b']):
        if target['shape'] == 'rect':
            if all(target['box'][i] < end[i] - radius and end[i] + radius < target['box'][i + 2]
                   for i in range(2)):
                return True
        elif target['radius'] > radius:
            if point_distance2(end, target['a'], target['a']) < (target['radius'] - radius) ** 2:
                return True
    return False
