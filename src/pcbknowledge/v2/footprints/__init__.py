"""Original footprint rules; drawing records are authority, copper is derived.

All dimensions are millimetres. These practical fillets are engineering defaults,
not an implementation of an IPC standard. Density selects toe / heel / side
extensions. Courtyards enclose the largest stated body and generated copper.
Axes: x right, y down, viewed from above. Pin 1 starts at upper left for ICs.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# Toe, heel, and side extensions beyond the rectangular lead contact.
FILLETS = {
    'COMPACT': (0.15, 0.05, 0.025),
    'NOMINAL': (0.30, 0.10, 0.05),
    'ROBUST': (0.45, 0.15, 0.075),
}
CHIP_FILLETS = {
    'COMPACT': (0.10, 0.00, 0.025),
    'NOMINAL': (0.20, 0.05, 0.05),
    'ROBUST': (0.30, 0.10, 0.075),
}
HEADER_ANNULAR_RING = 0.30
HEADER_HOLE_ALLOWANCE = 0.20


def dimension(value, field, *, bound='max', positive=True):
    """Resolve a cited numeric dimension, refusing unknowns or wrong units."""
    if not isinstance(value, dict) or value.get('unit') != 'mm':
        raise ValueError(f'Footprint dimension {field} requires mm')
    number = value.get('value', value.get(bound, value.get('typ')))
    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
        raise ValueError(f'Footprint dimension {field} is unknown')
    if positive and number <= 0:
        raise ValueError(f'Footprint dimension {field} must be positive')
    return float(number)


def _round(value):
    result = round(float(value), 6)
    return 0.0 if result == 0 else result


def _pad(number, x, y, width, height, *, kind='SMD', shape='RECT', drill=None):
    result = dict(number=str(number), kind=kind, shape=shape, x=_round(x), y=_round(y),
                  width=_round(width), height=_round(height), rotation=0.0)
    if drill is not None:
        result['drill'] = _round(drill)
    return result


class _Drawing:
    """Validated dimensions and selected original rule inputs for one package."""

    def __init__(self, package):
        self.package = package
        self.record = package['drawing']
        self.generator = package['generator']
        self.density = package['density']
        if self.density not in FILLETS:
            raise ValueError('Unknown footprint density')
        self.count = self.record['pin_count']
        if isinstance(self.count, bool) or not isinstance(self.count, int) or not 1 <= self.count <= 256:
            raise ValueError('Invalid drawing pin_count')
        self.fillets = FILLETS[self.density]

    def dimension(self, name, **kwargs):
        if name not in self.record:
            raise ValueError(f'{self.generator} requires drawing.{name}')
        return dimension(self.record[name], name, **kwargs)


def _two_terminal_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    generator, density = context.generator, context.density
    toe, heel, side = context.fillets
    if count != 2:
        raise ValueError('Two-terminal generator requires two pins')
    if generator == 'chip':
        toe, heel, side = CHIP_FILLETS[density]
    span, length, width = dim('lead_span'), dim('lead_length'), dim('lead_width')
    outer = span / 2 + toe
    inner = dim('lead_span', bound='min') / 2 - length - heel
    center = (outer + inner) / 2
    other_length = dim('opposite_lead_length') if 'opposite_lead_length' in drawing else length
    other_inner = dim('lead_span', bound='min') / 2 - other_length - heel
    other_center = (outer + other_inner) / 2
    return [_pad(1, -center, 0, outer - inner, width + 2 * side),
            _pad(2, other_center, 0, outer - other_inner, width + 2 * side)]


def _gullwing_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    package, generator = context.package, context.generator
    toe, heel, side = context.fillets
    span, width, pitch = dim('lead_span'), dim('lead_width'), dim('pitch')
    if 'lead_length' in drawing:
        length = dim('lead_length')
    elif 'tab' in drawing:
        # SOT-223 drawings may give only total span and body width. Use the
        # projected overhang as the original contact-length design rule.
        length = (span - dimension(package['body']['width'], 'body.width')) / 2
        if length <= 0:
            raise ValueError('Lead span must exceed body width')
    else:
        raise ValueError('Gull-wing drawing requires lead_length')
    outer = span / 2 + toe
    if 'lead_length' in drawing:
        inner = dim('lead_span', bound='min') / 2 - length - heel
    else:
        inner = dimension(package['body']['width'], 'body.width', bound='min') / 2 - heel
    center = (outer + inner) / 2
    pad_length, pad_width = outer - inner, width + 2 * side
    if 'tab' in drawing:
        if generator != 'gullwing_two_side' or count != 3:
            raise ValueError('Tab generator requires three primary terminals')
        pads = [_pad(i + 1, -center, (i - 1) * pitch, pad_length, pad_width) for i in range(3)]
        tab = drawing['tab']
        pads.append(_pad(tab['number'], center, 0, pad_length,
                         dimension(tab['width'], 'tab.width') + 2 * side))
        if tab['number'] not in {'1', '2', '3'}:
            raise ValueError('Tab must share an evidenced primary terminal number')
        return pads
    sides = 2 if generator == 'gullwing_two_side' else 4
    if sides == 2 and count in (3, 5):
        left = (count + 1) // 2
        right = count // 2
        pads = [_pad(i + 1, -center, (i - (left - 1) / 2) * pitch, pad_length, pad_width)
                for i in range(left)]
        pads.extend(_pad(count - i, center, (i - (right - 1) / 2) * pitch, pad_length, pad_width)
                    for i in range(right))
        return sorted(pads, key=lambda p: int(p['number']))
    if count % sides:
        raise ValueError('Pin count must divide equally across package sides')
    per_side = count // sides
    pads = []
    for i in range(per_side):
        position = (i - (per_side - 1) / 2) * pitch
        pads.append(_pad(i + 1, -center, position, pad_length, pad_width))
        if sides == 2:
            pads.append(_pad(count - i, center, position, pad_length, pad_width))
        else:
            pads.append(_pad(per_side + i + 1, position, center, pad_width, pad_length))
            pads.append(_pad(3 * per_side - i, center, position, pad_length, pad_width))
            pads.append(_pad(4 * per_side - i, position, -center, pad_width, pad_length))
    return sorted(pads, key=lambda p: int(p['number']))


def _crystal_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    toe, heel, side = context.fillets
    if count != 4:
        raise ValueError('Crystal generator requires four pads')
    x, y = dim('pitch') / 2, dim('row_pitch') / 2
    width, height = dim('pad_width'), dim('pad_height')
    numbers = drawing.get('pad_numbers', ['1', '2', '3', '4'])
    if len(numbers) != 4 or len(set(numbers)) != 4:
        raise ValueError('Crystal requires four distinct drawing pad numbers')
    return [_pad(n, px, py, width + 2 * side, height + toe + heel)
            for n, (px, py) in zip(numbers, [(-x, y), (x, y), (x, -y), (-x, -y)])]


def _header_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    rows = drawing.get('row_count', 1)
    if rows not in (1, 2) or count % rows:
        raise ValueError('Invalid header row arrangement')
    pitch = dim('pitch')
    row_pitch = dim('row_pitch') if rows == 2 else 0
    # A cited hole dimension is authoritative; otherwise a square pin requires
    # its diagonal plus the named assembly allowance.
    drill = dim('drill') if 'drill' in drawing else math.sqrt(2) * dim('lead_width') + HEADER_HOLE_ALLOWANCE
    diameter = drill + 2 * HEADER_ANNULAR_RING
    columns = count // rows
    return [_pad(c * rows + r + 1, (r - (rows - 1) / 2) * row_pitch,
                 (c - (columns - 1) / 2) * pitch, diameter, diameter,
                 kind='THROUGH_HOLE', shape='RECT' if c == r == 0 else 'ROUND', drill=drill)
            for c in range(columns) for r in range(rows)]


def _mechanical_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    if count != 1:
        raise ValueError('Mechanical hole requires one physical hole')
    drill = dim('drill')
    return [_pad('1', 0, 0, drill, drill, kind='MECHANICAL', shape='ROUND', drill=drill)]


def _drawing_pads(package):
    context = _Drawing(package)
    generators = {
        'chip': _two_terminal_pads,
        'molded_diode': _two_terminal_pads,
        'gullwing_two_side': _gullwing_pads,
        'gullwing_four_side': _gullwing_pads,
        'crystal_four_pad': _crystal_pads,
        'pin_header': _header_pads,
        'mechanical_hole': _mechanical_pads,
    }
    if context.generator not in generators:
        raise ValueError(f'Unknown footprint generator: {context.generator}')
    return generators[context.generator](context)


def _explicit_pads(package):
    result = []
    for pad in package['explicit_pads']:
        converted = {key: pad[key] for key in ('number', 'kind', 'shape')}
        for name in ('x', 'y', 'width', 'height', 'drill', 'drill_width', 'drill_height'):
            if name in pad:
                converted[name] = _round(dimension(pad[name], name, positive=name not in ('x', 'y')))
        rotation = pad['rotation']
        if rotation.get('unit') != 'deg' or 'value' not in rotation or rotation['value'] % 90:
            raise ValueError('Explicit pad rotation requires a multiple of 90 degrees')
        converted['rotation'] = float(rotation['value'] % 360)
        result.append(converted)
    return result


def derive_footprint(package):
    """Derive and validate physical pads without mutating authority records."""
    standard = all(key in package for key in ('drawing', 'generator', 'density'))
    explicit = 'explicit_pads' in package
    if standard == explicit or (explicit and any(k in package for k in ('drawing', 'generator', 'density'))):
        raise ValueError('Package requires exactly one geometry authority form')
    pads = _drawing_pads(package) if standard else _explicit_pads(package)
    if not pads or package['pin1'] not in {p['number'] for p in pads}:
        raise ValueError('Package pin1 has no pad')
    rectangles = []
    for pad in pads:
        width, height = pad['width'], pad['height']
        if width <= 0 or height <= 0:
            raise ValueError('Pad dimensions must be positive')
        hole_fields = {key for key in ('drill', 'drill_width', 'drill_height') if key in pad}
        if pad['kind'] in ('THROUGH_HOLE', 'MECHANICAL'):
            if hole_fields == {'drill'}:
                dx = dy = pad['drill']
            elif hole_fields == {'drill_width', 'drill_height'}:
                dx, dy = pad['drill_width'], pad['drill_height']
            else:
                raise ValueError('Hole requires a round drill or both oval drill dimensions')
            if dx <= 0 or dy <= 0 or dx > width or dy > height:
                raise ValueError('Hole must fit its pad')
        elif hole_fields:
            raise ValueError('SMD pads cannot have drills')
        if pad['rotation'] % 180:
            width, height = height, width
        rect = (pad['x'] - width / 2, pad['y'] - height / 2, pad['x'] + width / 2, pad['y'] + height / 2)
        for other in rectangles:
            if (min(rect[2], other[2]) - max(rect[0], other[0]) > 1e-8
                    and min(rect[3], other[3]) - max(rect[1], other[1]) > 1e-8):
                raise ValueError('Overlapping physical pads')
        rectangles.append(rect)
    # Body width is x and length is y for the standard top-view generators.
    bx = dimension(package['body']['width'], 'body.width') / 2
    by = dimension(package['body']['length'], 'body.length') / 2
    if dimension(package['body']['height'], 'body.height', positive=False) < 0:
        raise ValueError('Body height cannot be negative')
    margin = dimension(package['courtyard_margin'], 'courtyard_margin', positive=False)
    if margin < 0:
        raise ValueError('Courtyard margin cannot be negative')
    courtyard = dict(min_x=_round(min(-bx, *(r[0] for r in rectangles)) - margin),
                     min_y=_round(min(-by, *(r[1] for r in rectangles)) - margin),
                     max_x=_round(max(bx, *(r[2] for r in rectangles)) + margin),
                     max_y=_round(max(by, *(r[3] for r in rectangles)) + margin))
    return {'pads': pads, 'courtyard': courtyard, 'pin1': package['pin1']}


def footprint_name(package_or_id):
    """Canonical library item name; export_library rejects normalization collisions."""
    identity = package_or_id['id'] if isinstance(package_or_id, dict) else package_or_id
    if not isinstance(identity, str) or not identity.startswith('package:'):
        raise ValueError('Footprint requires a package identity')
    suffix = identity.split(':', 1)[1]
    if not suffix or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789/_-' for c in suffix):
        raise ValueError('Unsafe footprint identity')
    return suffix.replace('/', '_')


def export_kicad(package):
    """Return deterministic KiCad footprint text; no third-party library copied."""
    derived = derive_footprint(package)
    name = footprint_name(package)
    quote = lambda value: json.dumps(str(value), ensure_ascii=True)
    number = lambda value: format(value, '.6f').rstrip('0').rstrip('.') or '0'
    lines = [f'(footprint {quote(name)}', '  (version 20240108)', '  (generator "pcbknowledge")', '  (layer "F.Cu")']
    c = derived['courtyard']
    lines.append(
        f'  (fp_rect (start {number(c["min_x"])} {number(c["min_y"])}) '
        f'(end {number(c["max_x"])} {number(c["max_y"])}) '
        '(stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))'
    )
    # A marker outside pin 1's copper avoids confusing silkscreen with authority.
    first = next(p for p in derived['pads'] if p['number'] == package['pin1'])
    marker_x = first['x'] - first['width'] / 2 - 0.25
    marker_y = first['y'] - first['height'] / 2 - 0.25
    lines.append(
        f'  (fp_circle (center {number(marker_x)} {number(marker_y)}) '
        f'(end {number(marker_x + 0.1)} {number(marker_y)}) '
        '(stroke (width 0.1) (type default)) (fill solid) (layer "F.SilkS"))'
    )
    for pad in derived['pads']:
        kind = {'SMD': 'smd', 'THROUGH_HOLE': 'thru_hole', 'MECHANICAL': 'np_thru_hole'}[pad['kind']]
        shape = {'RECT': 'rect', 'ROUND': 'circle', 'OVAL': 'oval'}[pad['shape']]
        layers = '"F.Cu" "F.Paste" "F.Mask"' if kind == 'smd' else '"*.Cu" "*.Mask"'
        drill = f' (drill {number(pad["drill"])})' if 'drill' in pad else ''
        if 'drill_width' in pad:
            drill = f' (drill oval {number(pad["drill_width"])} {number(pad["drill_height"])})'
        lines.append(
            f'  (pad {quote(pad["number"])} {kind} {shape} '
            f'(at {number(pad["x"])} {number(pad["y"])} {number(pad["rotation"])}) '
            f'(size {number(pad["width"])} {number(pad["height"])}){drill} (layers {layers}))'
        )
    lines.append(')')
    return '\n'.join(lines) + '\n'


def export_library(packages, directory):
    packages = list(packages)
    names = [footprint_name(package) for package in packages]
    if len(names) != len(set(names)):
        raise ValueError('Footprint library name collision')
    rendered = {package['id']: export_kicad(package) for package in packages}
    directory = Path(directory).absolute()
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ValueError('Footprint output directory cannot traverse symlinks')
    for name in names:
        destination = directory / (name + '.kicad_mod')
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise ValueError('Unsafe footprint output file')
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for package in sorted(packages, key=lambda p: p['id']):
        name = footprint_name(package) + '.kicad_mod'
        path = directory / name
        path.write_text(rendered[package['id']], encoding='utf-8', newline='\n')
        paths.append(path)
    return paths
