"""Derived reference copper zones; native fill and all checks remain mandatory."""
from copy import deepcopy
import uuid

from .boardview import children
from .handoff import _outline
from .handoff_rules import millimeters


def _zone(net_code, name, layer, bounds, clearance, width, priority):
    x0, y0, x1, y1 = bounds
    return ['zone', ['net', str(net_code)], ['net_name', name], ['layer', layer],
            ['uuid', str(uuid.uuid5(uuid.NAMESPACE_URL, f'pcbknowledge:zone:{name}:{layer}'))],
            ['hatch', 'edge', '0.5'], ['priority', str(priority)],
            ['connect_pads', ['clearance', str(clearance)]], ['min_thickness', str(width)],
            ['fill', 'yes', ['thermal_gap', str(clearance)], ['thermal_bridge_width', str(width)]],
            ['polygon', ['pts', *[['xy', str(x), str(y)] for x, y in
                                 ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]]]]


def add_copper(tree, intent, catalog):
    """Ground reference and requested thermal zones; no assumed connectivity or area pass."""
    tree = deepcopy(tree)
    if children(tree, 'zone'):
        raise ValueError('Reference copper expects an unzoned generated board')
    width, height = _outline(intent)
    fab = catalog.get(intent['fab_profile'], 'fab_profile')
    clearance = millimeters(fab['clearance_min'])
    minimum = millimeters(fab['trace_width_min'])
    nets = {row[2]: row[1] for row in children(tree, 'net')}
    grounds = [net['name'] for net in intent['nets'] if net['class'] == 'GROUND']
    if len(grounds) != 1:
        raise ValueError('Reference ground plane requires one explicit ground net')
    specs = [(grounds[0], 'B.Cu')]
    for rule in intent['layout']:
        if rule['kind'] != 'COPPER_AREA':
            continue
        ref, separator, pin = rule['target'].partition('.pin:')
        if not separator:
            raise ValueError('Thermal copper requires an exact target pad')
        names = [net['name'] for net in intent['nets'] if {'ref': ref, 'pin': pin} in net['pins']]
        if len(names) != 1:
            raise ValueError('Thermal copper target needs one net')
        if (names[0], 'F.Cu') not in specs:
            specs.append((names[0], 'F.Cu'))
    for priority, (name, layer) in enumerate(specs, 1):
        tree.append(_zone(nets[name], name, layer, (clearance, clearance, width - clearance,
                                                  height - clearance), clearance, minimum, priority))
    return tree
