"""Match measured physical pads to derived authority, allowing rigid placement only."""
from .boardview import transform

GEOMETRY_TOLERANCE_MM = 0.000002


def close_vector(left, right):
    return len(left) == len(right) and all(abs(a - b) <= GEOMETRY_TOLERANCE_MM for a, b in zip(left, right))


def expected_geometry(pad, footprint):
    back = footprint['layer'] == 'B.Cu'
    local = [pad['x'], -pad['y'] if back else pad['y']]
    rotation = footprint['rotation'] + (-pad['rotation'] if back else pad['rotation'])
    drill = None
    if 'drill' in pad:
        drill = [pad['drill'], pad['drill']]
    elif 'drill_width' in pad:
        drill = [pad['drill_width'], pad['drill_height']]
    side = 'B' if back else 'F'
    layers = {side + suffix for suffix in ('.Cu', '.Paste', '.Mask')}
    if pad['kind'] != 'SMD':
        layers = {'*.Cu', '*.Mask'}
    return {'at': transform(local, footprint['at'], footprint['rotation']),
            'size': [pad['width'], pad['height']], 'rotation': rotation, 'drill_size': drill,
            'layers': layers, 'paste_margin': pad.get('paste_margin', 0.0),
            'kind': {'SMD': 'smd', 'THROUGH_HOLE': 'thru_hole', 'MECHANICAL': 'np_thru_hole'}[pad['kind']],
            'shape': {'RECT': 'rect', 'ROUND': 'circle', 'OVAL': 'oval'}[pad['shape']]}


def matches(actual, expected):
    if actual['kind'] != expected['kind'] or actual['shape'] != expected['shape']:
        return False
    if set(actual['layers']) != expected['layers']:
        return False
    if expected['kind'] == 'smd':
        if actual['paste_ratio'] != 0.0 or not close_vector([actual['paste_margin']], [expected['paste_margin']]):
            return False
    if not close_vector(actual['at'], expected['at']) or not close_vector(actual['size'], expected['size']):
        return False
    angle = (actual['rotation'] - expected['rotation'] + 180) % 360 - 180
    if abs(angle) > 0.000002:
        return False
    if not close_vector(actual.get('drill_offset', [0, 0]), [0, 0]):
        return False
    if (actual.get('drill_size') is None) != (expected['drill_size'] is None):
        return False
    return expected['drill_size'] is None or close_vector(actual['drill_size'], expected['drill_size'])


def pad_geometry_result(footprint, derived):
    """Unordered matching preserves repeated physical pads with electrical aliases."""
    if footprint['layer'] not in ('F.Cu', 'B.Cu'):
        return 'NOT_CHECKABLE', 'Unsupported footprint placement layer'
    actual = {number: list(pads) for number, pads in footprint['pads'].items()}
    if any(pad.get('geometry_unsupported') for pads in actual.values() for pad in pads):
        return 'NOT_CHECKABLE', 'Unsupported physical pad geometry'
    for pad in derived['pads']:
        expected = expected_geometry(pad, footprint)
        candidates = actual[pad['number']]
        index = next((i for i, candidate in enumerate(candidates) if matches(candidate, expected)), None)
        if index is None:
            return 'FAIL', 'Physical pad geometry differs from derived package authority'
        candidates.pop(index)
    return 'PASS', 'Physical pads match derived package geometry under rigid placement'


def authoritative_bounds(footprint, derived):
    box = derived['courtyard']
    points = [[x, y] for x in (box['min_x'], box['max_x']) for y in (box['min_y'], box['max_y'])]
    if footprint['layer'] == 'B.Cu':
        points = [[x, -y] for x, y in points]
    points = [transform(point, footprint['at'], footprint['rotation']) for point in points]
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]
