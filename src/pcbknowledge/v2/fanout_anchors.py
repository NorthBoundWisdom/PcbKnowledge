"""Bounded strict-interior pad attachment candidates; no footprint mutation."""
import math
from .fanout_solver import point_segment


def inside_pad(local, size, shape):
    x, y = local
    width, height = size
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (*local, *size)) or min(size) <= 0:
        raise ValueError('Invalid pad attachment geometry')
    epsilon = 1e-6
    if shape == 'rect':
        return abs(x) < width / 2 - epsilon and abs(y) < height / 2 - epsilon
    if shape == 'circle':
        if width != height:
            raise ValueError('Circular pad has unequal diameters')
        return math.hypot(x, y) < width / 2 - epsilon
    if shape == 'oval':
        if width >= height:
            distance = point_segment(local, [-(width-height)/2, 0], [(width-height)/2, 0])
        else:
            distance = point_segment(local, [0, -(height-width)/2], [0, (height-width)/2])
        return distance < min(size) / 2 - epsilon
    raise ValueError('Unsupported off-center pad shape')


def attachment_points(center, size, rotation, shape):
    if not math.isfinite(rotation):
        raise ValueError('Invalid pad angle')
    angle = math.radians(rotation)
    c, s = math.cos(angle), math.sin(angle)
    result = []
    fractions = [(0, 0)]
    for offset in (1/16, 1/8, 1/4):
        fractions.extend([(-offset, 0), (offset, 0), (0, -offset), (0, offset),
                          (-offset, -offset), (-offset, offset), (offset, -offset), (offset, offset)])
    for fx, fy in fractions:
        local = [fx * size[0], fy * size[1]]
        if inside_pad(local, size, shape):
            result.append([round(center[0] + local[0]*c + local[1]*s, 6),
                           round(center[1] - local[0]*s + local[1]*c, 6)])
    return result
