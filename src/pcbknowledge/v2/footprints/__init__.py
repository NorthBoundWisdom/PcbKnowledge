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


def _terminal_gap_inner(context, heel):
    drawing = context.record
    if context.generator != 'chip' or any(key in drawing for key in ('lead_length', 'opposite_lead_length')):
        raise ValueError('Terminal gap requires a chip without competing lead-length dimensions')
    intervals = {}
    for name in ('terminal_gap', 'lead_span'):
        quantity = drawing[name]
        if 'value' in quantity and any(key in quantity for key in ('min', 'typ', 'max')):
            raise ValueError('Ambiguous terminal geometry scalar and range')
        low, high = (context.dimension(name, bound=bound) for bound in ('min', 'max'))
        typical = context.dimension(name, bound='typ') if 'typ' in quantity else low
        if not low <= typical <= high:
            raise ValueError('Unordered terminal geometry range')
        intervals[name] = low, high
    gap, span = intervals['terminal_gap'], intervals['lead_span']
    if gap[1] >= span[0]:
        raise ValueError('Terminal gap must be smaller than the lead span throughout their ranges')
    # Contact length is (span - gap) / 2. Its correlated inner edge is gap / 2;
    # do not count the span tolerance twice when extending toe and heel.
    return gap[0] / 2 - heel


def _two_terminal_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    generator, density = context.generator, context.density
    toe, heel, side = context.fillets
    if count != 2:
        raise ValueError('Two-terminal generator requires two pins')
    if generator == 'chip':
        toe, heel, side = CHIP_FILLETS[density]
    span, width = dim('lead_span'), dim('lead_width')
    outer = span / 2 + toe
    inner = (_terminal_gap_inner(context, heel) if 'terminal_gap' in drawing else
             dim('lead_span', bound='min') / 2 - dim('lead_length') - heel)
    center = (outer + inner) / 2
    other_inner = (dim('lead_span', bound='min') / 2 - dim('opposite_lead_length') - heel
                   if 'opposite_lead_length' in drawing else inner)
    other_center = (outer + other_inner) / 2
    return [_pad(1, -center, 0, outer - inner, width + 2 * side),
            _pad(2, other_center, 0, outer - other_inner, width + 2 * side)]


def _gullwing_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    package, generator = context.package, context.generator
    toe, heel, side = context.fillets
    # D25: four-sided nominal gull-wing pads use a 0.04 mm side extension.
    # This remains above the cited maximum lead width; other families are unchanged.
    if generator == 'gullwing_four_side' and context.density == 'NOMINAL':
        side = 0.04
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


def _manufacturer_land(context):
    """Repeat the manufacturer's cited land dimensions without adding fillets."""
    sides = 4 if context.generator == 'manufacturer_four_side_land' else 2
    if context.count % sides or context.density != 'NOMINAL':
        raise ValueError('Manufacturer land requires equal side counts and nominal density')
    pitch, rows = context.dimension('pitch'), context.dimension('row_pitch')
    width, height = context.dimension('pad_width'), context.dimension('pad_height')
    per_side = context.count // sides
    pads = []
    for i in range(per_side):
        position = (i - (per_side - 1) / 2) * pitch
        pads.append(_pad(i + 1, -rows / 2, position, width, height))
        if sides == 2:
            pads.append(_pad(context.count - i, rows / 2, position, width, height))
        else:
            pads.append(_pad(per_side + i + 1, position, rows / 2, height, width))
            pads.append(_pad(3 * per_side - i, rows / 2, position, width, height))
            pads.append(_pad(4 * per_side - i, position, -rows / 2, height, width))
    pads = sorted(pads, key=lambda pad: int(pad['number']))
    numbers = context.record.get('pad_numbers')
    if numbers is not None:
        if len(numbers) != len(pads) or len(set(numbers)) != len(numbers):
            raise ValueError('Manufacturer land requires one distinct number per pad')
        for pad, number in zip(pads, numbers):
            pad['number'] = number
    return pads


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


def _radial_pads(context):
    """Two round plated holes on the x axis; explicit engineering hole/pad sizes."""
    if context.count != 2 or context.package.get('mount_type') != 'THT':
        raise ValueError('Radial generator requires two through-hole terminals')
    if context.density != 'NOMINAL':
        raise ValueError('Radial explicit hole and pad sizes require nominal density')
    pitch = context.dimension('pitch', bound='typ')
    sizes = {}
    for name in ('drill', 'pad_width', 'pad_height'):
        quantity = context.record.get(name, {})
        if set(quantity) & {'value', 'min', 'typ', 'max'} != {'value'}:
            raise ValueError(f'Radial {name} requires an exact selected dimension')
        sizes[name] = context.dimension(name)
    diameter = sizes['pad_width']
    if diameter != sizes['pad_height'] or sizes['drill'] >= diameter:
        raise ValueError('Radial round pads require equal diameters and a positive annular ring')
    return [_pad(number, x, 0, diameter, diameter, kind='THROUGH_HOLE',
                 shape='ROUND', drill=sizes['drill'])
            for number, x in ((1, -pitch / 2), (2, pitch / 2))]


def _mechanical_pads(context):
    drawing, dim, count = context.record, context.dimension, context.count
    if count != 1:
        raise ValueError('Mechanical hole requires one physical hole')
    drill = dim('drill')
    return [_pad('1', 0, 0, drill, drill, kind='MECHANICAL', shape='ROUND', drill=drill)]


def _exposed_pad_margin(pad, drawing):
    if 'paste_margin' not in drawing:
        return pad
    quantity = drawing['paste_margin']
    if not isinstance(quantity, dict) or set(quantity) & {'value', 'min', 'typ', 'max'} != {'value'}:
        raise ValueError('Exposed pad paste margin requires an exact scalar')
    margin = dimension(quantity, 'exposed_pad.paste_margin', positive=False)
    if margin > 0:
        raise ValueError('Exposed pad paste margin must be nonpositive')
    pad['paste_margin'] = _round(margin)
    if min(pad['width'], pad['height']) + 2 * pad['paste_margin'] <= 0:
        raise ValueError('Exposed pad paste margin collapses the aperture')
    return pad


def _drawing_pads(package):
    context = _Drawing(package)
    if 'terminal_gap' in context.record and context.generator != 'chip':
        raise ValueError('Terminal gap is supported only by the chip generator')
    generators = {
        'chip': _two_terminal_pads,
        'molded_diode': _two_terminal_pads,
        'gullwing_two_side': _gullwing_pads,
        'gullwing_four_side': _gullwing_pads,
        'manufacturer_two_side_land': _manufacturer_land,
        'manufacturer_four_side_land': _manufacturer_land,
        'crystal_four_pad': _crystal_pads,
        'pin_header': _header_pads,
        'radial_two_lead': _radial_pads,
        'mechanical_hole': _mechanical_pads,
    }
    if context.generator not in generators:
        raise ValueError(f'Unknown footprint generator: {context.generator}')
    pads = generators[context.generator](context)
    if 'exposed_pad' in context.record:
        if context.generator not in ('gullwing_two_side', 'gullwing_four_side', 'manufacturer_four_side_land'):
            raise ValueError('Exposed pad requires a supported perimeter-lead generator')
        exposed = context.record['exposed_pad']
        if exposed['number'] in {pad['number'] for pad in pads}:
            raise ValueError('Exposed pad identity must be distinct from perimeter terminals')
        width = dimension(exposed['width'], 'exposed_pad.width')
        length = dimension(exposed['length'], 'exposed_pad.length')
        if (width > dimension(package['body']['width'], 'body.width')
                or length > dimension(package['body']['length'], 'body.length')):
            raise ValueError('Exposed pad must fit within package body')
        pads.append(_exposed_pad_margin(_pad(exposed['number'], 0, 0, width, length), exposed))
    return pads


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
        width, height = rotated_pad_size(pad)
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
    center = package['body'].get('center')
    cx = dimension(center['x'], 'body.center.x', positive=False) if center else 0
    cy = dimension(center['y'], 'body.center.y', positive=False) if center else 0
    margin = dimension(package['courtyard_margin'], 'courtyard_margin', positive=False)
    if margin < 0:
        raise ValueError('Courtyard margin cannot be negative')
    courtyard = dict(min_x=_round(min(cx - bx, *(r[0] for r in rectangles)) - margin),
                     min_y=_round(min(cy - by, *(r[1] for r in rectangles)) - margin),
                     max_x=_round(max(cx + bx, *(r[2] for r in rectangles)) + margin),
                     max_y=_round(max(cy + by, *(r[3] for r in rectangles)) + margin))
    derived = {'pads': pads, 'courtyard': courtyard, 'pin1': package['pin1']}
    derived['pin1_marker'] = pin1_marker(derived)
    return derived


def rotated_pad_size(pad, angle=0):
    """Conservative axis-aligned rectangle bounds at any physical pad rotation."""
    rotation = (pad['rotation'] + angle) % 360
    if rotation % 90 == 0:
        return ((pad['height'], pad['width']) if rotation % 180 else (pad['width'], pad['height']))
    radians = math.radians(rotation)
    cosine, sine = abs(math.cos(radians)), abs(math.sin(radians))
    return (pad['width'] * cosine + pad['height'] * sine,
            pad['width'] * sine + pad['height'] * cosine)


def pin1_marker(derived):
    """One graphic authority, retaining the original dot size and pad-corner offset."""
    first = next(p for p in derived['pads'] if p['number'] == derived['pin1'])
    width, height = rotated_pad_size(first)
    return {'x': first['x'] - width / 2 - 0.25, 'y': first['y'] - height / 2 - 0.25,
            'radius': 0.1, 'stroke': 0.1}


def occupied_envelope(derived):
    """Physical graphics envelope, separate from the unchanged authoritative courtyard."""
    box = dict(derived['courtyard'])
    marker = derived.get('pin1_marker')
    if 'pin1_marker' in derived:
        if not isinstance(marker, dict) or set(marker) != {'x', 'y', 'radius', 'stroke'}:
            raise ValueError('Malformed pin1 marker')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in marker.values()):
            raise ValueError('Nonfinite pin1 marker')
        if marker['radius'] <= 0 or marker['stroke'] < 0:
            raise ValueError('Invalid pin1 marker extent')
        extent = marker['radius'] + marker['stroke'] / 2
        for axis in ('x', 'y'):
            box['min_' + axis] = min(box['min_' + axis], marker[axis] - extent)
            box['max_' + axis] = max(box['max_' + axis], marker[axis] + extent)
    return box


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
    if package['mount_type'] == 'SMT':
        lines.append('  (attr smd)')
    elif package['mount_type'] == 'THT':
        lines.append('  (attr through_hole)')
    c = derived['courtyard']
    lines.append(
        f'  (fp_rect (start {number(c["min_x"])} {number(c["min_y"])}) '
        f'(end {number(c["max_x"])} {number(c["max_y"])}) '
        '(stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))'
    )
    marker = derived['pin1_marker']
    marker_x, marker_y = marker['x'], marker['y']
    lines.append(
        f'  (fp_circle (center {number(marker_x)} {number(marker_y)}) '
        f'(end {number(marker_x + marker["radius"])} {number(marker_y)}) '
        f'(stroke (width {number(marker["stroke"])}) (type default)) (fill solid) (layer "F.SilkS"))'
    )
    for pad in derived['pads']:
        kind = {'SMD': 'smd', 'THROUGH_HOLE': 'thru_hole', 'MECHANICAL': 'np_thru_hole'}[pad['kind']]
        shape = {'RECT': 'rect', 'ROUND': 'circle', 'OVAL': 'oval'}[pad['shape']]
        layers = '"F.Cu" "F.Paste" "F.Mask"' if kind == 'smd' else '"*.Cu" "*.Mask"'
        drill = f' (drill {number(pad["drill"])})' if 'drill' in pad else ''
        if 'drill_width' in pad:
            drill = f' (drill oval {number(pad["drill_width"])} {number(pad["drill_height"])})'
        paste = f' (solder_paste_margin {number(pad["paste_margin"])})' if 'paste_margin' in pad else ''
        lines.append(
            f'  (pad {quote("" if kind == "np_thru_hole" else pad["number"])} {kind} {shape} '
            f'(at {number(pad["x"])} {number(pad["y"])} {number(pad["rotation"])}) '
            f'(size {number(pad["width"])} {number(pad["height"])}){drill} (layers {layers}){paste})'
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
