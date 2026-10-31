"""Original DSN rule projection and fail-closed router-session preflight."""
from __future__ import annotations

import math
from pathlib import Path

from pcbknowledge.v2.boardview import children, field
from pcbknowledge.v2.handoff_rules import millimeters, net_widths
from pcbknowledge.v2.sexpr import Atom, dumps, parse


def read_specctra(text):
    # Specctra declares the quote delimiter using a bare quote, unlike KiCad strings.
    return parse(text.replace('(string_quote ")', '(string_quote quote)'))


def write_specctra(tree):
    return dumps(tree).replace('(string_quote quote)', '(string_quote ")') + '\n'


def _number(value):
    result = float(value)
    if not math.isfinite(result) or abs(result) > 1e9:
        raise ValueError('Invalid Specctra numeric value')
    return result


def _one(node, name):
    values = children(node, name)
    if len(values) != 1:
        raise ValueError('Expected exactly one Specctra ' + name)
    return values[0]


def _unit(node, *, session=False):
    unit = field(node, 'unit')
    resolution = field(node, 'resolution')
    factors = {'mm': 1.0, 'um': .001, 'mil': .0254, 'inch': 25.4}
    if unit:
        if len(unit) != 1 or unit[0] not in factors:
            raise ValueError('Unsupported Specctra unit')
        return factors[unit[0]]
    if session and resolution and len(resolution) == 2 and resolution[0] in factors:
        divisor = _number(resolution[1])
        if divisor <= 0:
            raise ValueError('Nonpositive Specctra resolution')
        return factors[resolution[0]] / divisor
    raise ValueError('Explicit Specctra coordinate unit is required')


def configure_dsn(text, intent, catalog):
    """Replace native net classes with the same catalog-derived routing minima as KiCad."""
    tree = read_specctra(text)
    if tree[0] != 'pcb':
        raise ValueError('Expected a Specctra PCB')
    unit = _unit(tree)
    structure, network = _one(tree, 'structure'), _one(tree, 'network')
    names = [row[1] for row in children(network, 'net')]
    expected = {net['name'] for net in intent['nets']}
    if len(names) != len(set(names)) or set(names) != expected:
        raise ValueError('Native DSN nets differ from design intent')
    fab = catalog.get(intent['fab_profile'], 'fab_profile')
    widths = net_widths(intent, fab)
    clearance = millimeters(fab['clearance_min']) / unit
    floor = millimeters(fab['trace_width_min']) / unit
    structure[:] = [item for item in structure if not isinstance(item, list) or item[0] != 'rule']
    structure.append([Atom('rule'), [Atom('width'), floor], [Atom('clearance'), clearance]])
    network[:] = [item for item in network if not isinstance(item, list) or item[0] != 'class']
    for index, width in enumerate(sorted(set(widths.values())), 1):
        nets = sorted(net for net, value in widths.items() if value == width)
        network.append([Atom('class'), 'width_' + str(index), *nets,
                        [Atom('rule'), [Atom('width'), width / unit], [Atom('clearance'), clearance]]])
    return write_specctra(tree)


def _placements(tree, unit):
    placement = children(tree, 'placement')
    if not placement:
        return {}
    if len(placement) != 1:
        raise ValueError('Duplicate Specctra placement')
    node = placement[0]
    local = _unit(node, session=True) if field(node, 'resolution') or field(node, 'unit') else unit
    result = {}
    for component in children(node, 'component'):
        for row in children(component, 'place'):
            if len(row) < 6 or row[1] in result or row[4] not in ('front', 'back'):
                raise ValueError('Malformed or duplicate session placement')
            result[row[1]] = (component[1], round(_number(row[2]) * local, 6),
                              round(_number(row[3]) * local, 6), row[4], _number(row[5]) % 360)
    return result


def _wire(node, unit, layers, minimum):
    path = _one(node, 'path')
    if len(path) < 7 or len(path[3:]) % 2 or path[1] not in layers:
        raise ValueError('Malformed route path or unknown layer')
    width = _number(path[2]) * unit
    if width + 1e-9 < minimum:
        raise ValueError('Router narrowed a net below its required width')
    points = [(_number(x) * unit, _number(y) * unit) for x, y in zip(path[3::2], path[4::2])]
    return {'layer': str(path[1]), 'width_mm': width, 'points_mm': points}


def _padstack_shapes(node, unit):
    shapes = []
    for shape in children(node, 'shape'):
        if len(shape) != 2 or not isinstance(shape[1], list):
            raise ValueError('Unsupported session via shape')
        circle = shape[1]
        if circle[0] != 'circle' or len(circle) not in (3, 5):
            raise ValueError('Only circular through-via padstacks are supported')
        diameter = _number(circle[2]) * unit
        if diameter <= 0 or (len(circle) == 5 and any(_number(value) != 0 for value in circle[3:])):
            raise ValueError('Invalid session via copper')
        shapes.append((str(circle[1]), round(diameter, 9)))
    if not shapes or len(shapes) != len(set(shapes)):
        raise ValueError('Missing or duplicate session via shapes')
    return sorted(shapes)


def _validate_padstacks(dsn, library, unit):
    source = {row[1]: row for row in children(_one(dsn, 'library'), 'padstack')}
    allowed = field(_one(dsn, 'structure'), 'via', [])
    result = {row[1]: row for row in children(library, 'padstack')}
    if len(result) != len(children(library, 'padstack')):
        raise ValueError('Duplicate session via padstack')
    for name, row in result.items():
        if name not in allowed or name not in source:
            raise ValueError('Session defines an unknown via padstack')
        if _padstack_shapes(row, unit) != _padstack_shapes(source[name], _unit(dsn)):
            raise ValueError('Router changed via copper geometry')
    return result


def validate_session(text, dsn_text, widths, *, dsn_name):
    """Check identities, placements and route geometry before invoking native import."""
    tree, dsn = read_specctra(text), read_specctra(dsn_text)
    if tree[0] != 'session' or dsn[0] != 'pcb':
        raise ValueError('Expected a Specctra session and original DSN')
    base = field(tree, 'base_design')
    expected_names = {str(dsn_name), Path(dsn_name).stem}
    if not base or len(base) != 1 or base[0].replace('\\', '/').split('/')[-1] not in expected_names:
        raise ValueError('Session base design differs from original DSN')
    routes = _one(tree, 'routes')
    unit = _unit(routes, session=True)
    original = _placements(dsn, _unit(dsn))
    actual = _placements(tree, unit)
    if actual and actual != original:
        raise ValueError('Router session changes component placement')
    layers = {row[1] for row in children(_one(dsn, 'structure'), 'layer')}
    if layers != {'F.Cu', 'B.Cu'}:
        raise ValueError('Only the declared two-layer route stack is supported')
    library = _one(routes, 'library_out')
    padstacks = _validate_padstacks(dsn, library, unit)
    network = _one(routes, 'network_out')
    names = [row[1] for row in children(network, 'net')]
    if len(names) != len(set(names)) or set(names) - set(widths):
        raise ValueError('Unknown or duplicate session net')
    wires, vias = [], []
    for net in children(network, 'net'):
        for wire in children(net, 'wire'):
            wires.append({'net': str(net[1]), **_wire(wire, unit, layers, widths[net[1]])})
        for via in children(net, 'via'):
            if len(via) < 4 or via[1] not in padstacks:
                raise ValueError('Unknown or malformed session via')
            vias.append({'net': str(net[1]), 'padstack': str(via[1]),
                         'at_mm': [_number(via[2]) * unit, _number(via[3]) * unit]})
        if any(isinstance(item, list) and item[0] not in ('wire', 'via') for item in net[2:]):
            raise ValueError('Unsupported routed-net session geometry')
    return {'wire_count': len(wires), 'via_count': len(vias), 'wires': wires, 'vias': vias}


def verify_native_vias(text, fab):
    """Native KiCad via identifiers encode diameter and drill in micrometers."""
    import re
    tree = read_specctra(text)
    unit = _unit(tree)
    allowed = field(_one(tree, 'structure'), 'via', [])
    library = {row[1]: row for row in children(_one(tree, 'library'), 'padstack')}
    if not allowed:
        raise ValueError('Native DSN has no routing via definition')
    for name in allowed:
        match = re.fullmatch(r'Via\[0-1\]_(\d+):(\d+)_um', name)
        if not match or name not in library:
            raise ValueError('Unsupported native DSN via drill encoding')
        diameter, drill = (int(value) / 1000 for value in match.groups())
        if drill < millimeters(fab['drill_min']):
            raise ValueError('Native DSN via drill is below fab minimum')
        if (diameter - drill) / 2 + 1e-9 < millimeters(fab['annular_ring_min']):
            raise ValueError('Native DSN via annular ring is below fab minimum')
        expected = [('B.Cu', diameter), ('F.Cu', diameter)]
        if _padstack_shapes(library[name], unit) != expected:
            raise ValueError('Native DSN via copper does not match drill identifier')
