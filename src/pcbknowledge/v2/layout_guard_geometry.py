"""Exact projected pad/track shapes for read-only guard measurements."""
from fractions import Fraction

from .layout_return import contains, point, segment_distance2


def capsule(a, b, radius):
    return {'points': [a, b], 'edges': [(a, b)], 'radius': radius, 'polygon': None}


def pad_shape(pad):
    if pad.get('geometry_unsupported') or pad['shape'] not in ('rect', 'circle', 'oval'):
        raise ValueError('Unsupported pad copper outline')
    x, y = point(pad['at'])
    w, h = point(pad['size'])
    rotation = Fraction(str(pad.get('rotation', 0))) % 180
    if min(w, h) <= 0 or (pad['shape'] != 'circle' and rotation not in (0, 90)):
        raise ValueError('Pads require positive cardinal geometry')
    if rotation == 90:
        w, h = h, w
    if pad['shape'] == 'rect':
        corners = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2),
                   (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)]
        return {'points': corners, 'edges': list(zip(corners, corners[1:] + corners[:1])),
                'radius': Fraction(0), 'polygon': corners}
    if pad['shape'] == 'circle' and w != h:
        raise ValueError('Circle pad dimensions disagree')
    radius = min(w, h) / 2
    dx, dy = max(0, (w - h) / 2), max(0, (h - w) / 2)
    return capsule((x - dx, y - dy), (x + dx, y + dy), radius)


def track_shape(track):
    radius = Fraction(str(track['width'])) / 2
    if radius <= 0:
        raise ValueError('Positive track width required')
    return capsule(point(track['start']), point(track['end']), radius)


def shape_distance2(first, second):
    if first['polygon'] and any(contains(p, first['polygon']) for p in second['points']):
        return Fraction(0)
    if second['polygon'] and any(contains(p, second['polygon']) for p in first['points']):
        return Fraction(0)
    return min(segment_distance2(a, b, c, d) for a, b in first['edges'] for c, d in second['edges'])

