"""Read-only, fail-closed geometry projection of exported KiCad boards."""
import math
from pathlib import Path

from .sexpr import MAX_BYTES, parse


def children(node, name):
    return [item for item in node[1:] if isinstance(item, list) and item and item[0] == name]


def field(node, name, default=None):
    values = children(node, name)
    if len(values) > 1:
        raise ValueError(f'Duplicate board field: {name}')
    return values[0][1:] if values else default


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError('Invalid board coordinate') from error
    if not math.isfinite(result) or abs(result) > 1e9:
        raise ValueError('Nonfinite or excessive board coordinate')
    return result


def positive(value):
    result = number(value)
    if result <= 0:
        raise ValueError('Nonpositive board dimension')
    return result


def point(value):
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError('Missing board coordinate')
    return [number(value[0]), number(value[1])]


def transform(local, origin, angle):
    # KiCad coordinates are y-down; positive stored angles rotate counterclockwise.
    radians = math.radians(angle)
    x, y = local
    return [origin[0] + x * math.cos(radians) + y * math.sin(radians),
            origin[1] - x * math.sin(radians) + y * math.cos(radians)]


def bounds(points):
    if not points:
        return None
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def net_name(node, nets):
    value = field(node, 'net', ['0'])
    identity = value[0]
    if identity not in nets or (len(value) > 1 and value[1] != nets[identity]):
        raise ValueError('Unknown or inconsistent board net')
    return nets[identity]


def _paste_settings(node, inherited, *, board=False, legacy_ratio=False, zero_overrides=False):
    names = (('pad_to_paste_clearance', 'pad_to_paste_clearance_ratio') if board else
             ('solder_paste_margin', 'solder_paste_margin_ratio'))
    result = dict(inherited)
    for key, name in zip(('paste_margin', 'paste_ratio'), names):
        value = field(node, name)
        # Older footprint syntax names the same percentage without "margin".
        legacy = field(node, 'solder_paste_ratio') if key == 'paste_ratio' and not board else None
        if legacy is not None and not legacy_ratio:
            raise ValueError('Unsupported pad paste ratio syntax')
        if value is not None and legacy is not None:
            raise ValueError('Conflicting solder paste ratio fields')
        value = value if value is not None else legacy
        if value is not None:
            if len(value) != 1:
                raise ValueError('Solder paste setting requires one scalar')
            scalar = number(value[0])
            if scalar == 0 and not board and not zero_overrides:
                raise ValueError('Zero solder paste overrides require the KiCad 9 board format')
            result[key] = scalar
    return result


def _pad(node, origin, angle, nets, paste, zero_overrides):
    if len(node) < 4:
        raise ValueError('Malformed board pad')
    at = field(node, 'at', ['0', '0'])
    size = point(field(node, 'size'))
    if min(size) <= 0:
        raise ValueError('Nonpositive pad size')
    drill = field(node, 'drill')
    drill_size = None
    drill_offset = [0.0, 0.0]
    if drill:
        dimensions = drill[1:3] if drill[0] == 'oval' else [drill[0], drill[0]]
        drill_size = [number(value) for value in dimensions]
        if len(drill_size) != 2 or min(drill_size) <= 0:
            raise ValueError('Nonpositive or malformed drill')
        drill_offset = point(field(['drill', *drill], 'offset', ['0', '0']))
    unsupported = node[3] not in ('rect', 'circle', 'oval')
    unsupported = unsupported or any(children(node, key) for key in ('primitives', 'rect_delta', 'chamfer'))
    return {'at': transform(point(at), origin, angle), 'local_at': point(at),
            'size': size, 'shape': node[3], 'kind': node[2], 'net': net_name(node, nets),
            'layers': field(node, 'layers', []), 'rotation': number(at[2]) if len(at) > 2 else 0.0,
            'drill': min(drill_size) if drill_size else None, 'drill_size': drill_size,
            'drill_offset': drill_offset, 'geometry_unsupported': bool(unsupported),
            **_paste_settings(node, paste, zero_overrides=zero_overrides)}



def _graphic(node, origin, angle):
    kind = node[0].removeprefix('fp_').removeprefix('gr_')
    if kind == 'line':
        return [transform(point(field(node, key)), origin, angle) for key in ('start', 'end')]
    if kind == 'rect':
        start, end = point(field(node, 'start')), point(field(node, 'end'))
        return [transform(p, origin, angle) for p in
                (start, [end[0], start[1]], end, [start[0], end[1]], start)]
    if kind == 'poly':
        pts = field(node, 'pts', [])
        points = [transform(point(item[1:]), origin, angle) for item in pts if item[0] == 'xy']
        return points + points[:1] if points and points[-1] != points[0] else points
    return None


def _footprint(node, nets, unsupported, paste, zero_overrides):
    refs = [item[2] for item in children(node, 'property') if len(item) > 2 and item[1] == 'Reference']
    refs += [item[2] for item in children(node, 'fp_text') if len(item) > 2 and item[1] == 'reference']
    if not refs or len(set(refs)) != 1 or not refs[0]:
        raise ValueError('Missing or conflicting footprint reference')
    ref = refs[0]
    at = field(node, 'at', ['0', '0'])
    origin = point(at)
    angle = number(at[2]) if len(at) > 2 else 0.0
    paste = _paste_settings(node, paste, legacy_ratio=True, zero_overrides=zero_overrides)
    pads = {}
    for pad in children(node, 'pad'):
        pads.setdefault(pad[1], []).append(_pad(pad, origin, angle, nets, paste, zero_overrides))
        if pad[3] not in ('rect', 'roundrect', 'circle', 'oval', 'trapezoid'):
            unsupported.append(f'{ref}: unsupported pad shape {pad[3]}')
    courtyard = []
    edges = []
    for item in node[1:]:
        if not isinstance(item, list) or not item:
            continue
        layer = field(item, 'layer', [''])[0]
        if layer not in ('F.CrtYd', 'B.CrtYd'):
            continue
        points = _graphic(item, origin, angle)
        if points is None:
            unsupported.append(f'{ref}: unsupported courtyard geometry {item[0]}')
        else:
            courtyard.extend(points)
            edges.extend(zip(points, points[1:]))
    courtyard_closed = _closed(edges)
    if courtyard and not courtyard_closed:
        unsupported.append(f'{ref}: open or ambiguous courtyard')
    return ref, {'library': node[1], 'at': origin, 'rotation': angle, 'layer': field(node, 'layer', [''])[0],
                 'pads': pads, 'bounds': bounds(courtyard), 'courtyard': courtyard,
                 'courtyard_closed': courtyard_closed}


def _closed(edges):
    if not edges:
        return False
    adjacency = {}
    for start, end in edges:
        a, b = (tuple(round(n, 6) for n in point) for point in (start, end))
        if a == b:
            return False
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    visited = set()
    pending = [next(iter(adjacency))]
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(adjacency[current])
    return len(visited) == len(adjacency) and all(len(neighbors) == 2 for neighbors in adjacency.values())


def _outline(root, unsupported):
    segments = []
    arcs = []
    for item in root[1:]:
        if not isinstance(item, list) or not item or field(item, 'layer', [''])[0] != 'Edge.Cuts':
            continue
        points = _graphic(item, [0, 0], 0)
        if points is None:
            unsupported.append(f'Unsupported outline geometry: {item[0]}')
            if item[0] == 'gr_arc':
                arcs.append({key: point(field(item, key)) for key in ('start', 'mid', 'end')})
        else:
            segments.extend([[a, b] for a, b in zip(points, points[1:])])
    endpoints = {}
    for segment in segments:
        for endpoint in segment:
            key = tuple(round(n, 6) for n in endpoint)
            endpoints[key] = endpoints.get(key, 0) + 1
    closed = not arcs and _closed(segments)
    box = bounds([p for line in segments for p in line])
    rectangular = closed and len(segments) == 4 and len(endpoints) == 4 and all(
        (a[0] == b[0] or a[1] == b[1]) and a != b for a, b in segments)
    return {'bounds': box, 'rectangular': rectangular,
            'segments': segments, 'arcs': arcs, 'closed': closed}


def _routing(root, nets, unsupported):
    result = {'segments': [], 'arcs': [], 'vias': [], 'zones': []}
    for kind in ('segment', 'arc'):
        for node in children(root, kind):
            item = {key: point(field(node, key)) for key in
                    (('start', 'end') if kind == 'segment' else ('start', 'mid', 'end'))}
            item.update(width=positive(field(node, 'width')[0]), net=net_name(node, nets),
                        layer=field(node, 'layer', [''])[0])
            result[kind + 's'].append(item)
    for node in children(root, 'via'):
        result['vias'].append({'at': point(field(node, 'at')), 'size': positive(field(node, 'size')[0]),
                               'drill': positive(field(node, 'drill')[0]), 'net': net_name(node, nets),
                               'layers': field(node, 'layers', [])})
    for node in children(root, 'zone'):
        item = {'net': net_name(node, nets), 'layer': field(node, 'layer', [''])[0],
                'layers': field(node, 'layers', []), 'polygons': [], 'filled_polygons': []}
        for kind in ('polygon', 'filled_polygon'):
            for polygon in children(node, kind):
                pts = field(polygon, 'pts', [])
                layer = field(polygon, 'layer', [item['layer']])[0]
                if layer != item['layer'] or item['layers'] or any(p[0] != 'xy' for p in pts):
                    unsupported.append('Unsupported multilayer or curved zone polygon')
                if children(polygon, 'hole') or children(node, 'keepout'):
                    unsupported.append('Unsupported zone hole or keepout geometry')
                item[kind + 's'].append([point(p[1:]) for p in pts if p[0] == 'xy'])
        result['zones'].append(item)
    return result


def _board_requirements(root):
    general = field(root, 'general')
    thickness = field(['general', *general], 'thickness') if general is not None else None
    thickness_mm = number(thickness[0]) if thickness else None
    if thickness_mm is not None and thickness_mm <= 0:
        raise ValueError('Nonpositive board thickness')
    layers = field(root, 'layers')
    copper_layers = None
    if layers is not None:
        if any(not isinstance(layer, list) or len(layer) < 3 for layer in layers):
            raise ValueError('Malformed board layer declaration')
        names = [layer[1] for layer in layers]
        identities = [layer[0] for layer in layers]
        if len(set(names)) != len(names) or len(set(identities)) != len(identities):
            raise ValueError('Duplicate board layer declaration')
        copper_layers = [name for name in names if name.endswith('.Cu')]
    return {'thickness_mm': thickness_mm, 'copper_layers': copper_layers}


def board_from_text(text):
    try:
        root = parse(text)
        if not root or root[0] != 'kicad_pcb':
            raise ValueError('Not a KiCad board')
        zero_overrides = field(root, 'version') == ['20241229']
        nets = {'0': ''}
        names = set()
        for node in children(root, 'net'):
            if len(node) != 3 or (node[1] in nets and node[1] != '0') or node[2] in names:
                raise ValueError('Duplicate or malformed board net')
            if node[1] == '0' and node[2] != '':
                raise ValueError('Board net zero must be unassigned')
            nets[node[1]] = node[2]
            names.add(node[2])
        unsupported = []
        footprints = {}
        setup = ['setup', *field(root, 'setup', [])]
        paste = _paste_settings(setup, {'paste_margin': 0.0, 'paste_ratio': 0.0}, board=True)
        for node in children(root, 'footprint'):
            ref, footprint = _footprint(node, nets, unsupported, paste, zero_overrides)
            if ref in footprints:
                raise ValueError('Duplicate footprint reference')
            footprints[ref] = footprint
        return {'footprints': footprints, 'nets': nets, 'outline': _outline(root, unsupported),
                'unsupported': unsupported, **_routing(root, nets, unsupported), **_board_requirements(root)}
    except (IndexError, TypeError, KeyError) as error:
        raise ValueError('Malformed KiCad board geometry') from error


def parse_board(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Unsafe or oversized board input')
    return board_from_text(path.read_text(encoding='utf-8'))
