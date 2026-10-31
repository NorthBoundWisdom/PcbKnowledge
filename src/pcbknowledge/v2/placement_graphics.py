"""Derived pin-1 ink collisions; native mask expansion and silk clearance are zero."""
import math

from .boardview import transform
from .footprints import occupied_envelope, rotated_pad_size


def graphics(item, angle):
    marker = item.get('pin1_marker')
    circle = None
    if marker is not None:
        x, y = transform((marker['x'], marker['y']), (0, 0), angle)
        circle = (x, y, marker['radius'] + marker['stroke'] / 2)
    pads = []
    for pad in item['pads']:
        if 'width' not in pad or 'height' not in pad:
            if marker is not None:
                raise ValueError('Graphic collision requires physical pad dimensions')
            continue
        width, height = rotated_pad_size(pad, angle)
        x, y = transform((pad['x'], pad['y']), (0, 0), angle)
        pads.append((x - width / 2, y - height / 2, x + width / 2, y + height / 2))
    box = occupied_envelope(item)
    corners = [transform((x, y), (0, 0), angle)
               for x in (box['min_x'], box['max_x']) for y in (box['min_y'], box['max_y'])]
    envelope = (min([p[0] for p in corners] + [pad[0] for pad in pads]),
                min([p[1] for p in corners] + [pad[1] for pad in pads]),
                max([p[0] for p in corners] + [pad[2] for pad in pads]),
                max([p[1] for p in corners] + [pad[3] for pad in pads]))
    return circle, pads, envelope


def _circle_pad(circle, pad, delta):
    x, y, radius = circle
    x, y = x - delta[0], y - delta[1]
    dx = max(pad[0] - x, 0, x - pad[2])
    dy = max(pad[1] - y, 0, y - pad[3])
    return dx * dx + dy * dy < radius * radius - 1e-12


def conflicts(left, left_position, right, right_position):
    """Circle-circle and circle-pad intersections; courtyard empty space is not ink."""
    a, apads, abox = left
    b, bpads, bbox = right
    delta = (right_position[0] - left_position[0], right_position[1] - left_position[1])
    if (abox[2] <= bbox[0] + delta[0] or bbox[2] + delta[0] <= abox[0]
            or abox[3] <= bbox[1] + delta[1] or bbox[3] + delta[1] <= abox[1]):
        return False
    if a is not None and b is not None:
        distance = math.hypot(a[0] - b[0] - delta[0], a[1] - b[1] - delta[1])
        if distance < a[2] + b[2] - 1e-9:
            return True
    return ((a is not None and any(_circle_pad(a, pad, delta) for pad in bpads))
            or (b is not None and any(_circle_pad(b, pad, (-delta[0], -delta[1])) for pad in apads)))
