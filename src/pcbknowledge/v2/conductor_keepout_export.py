"""Derived footprint-owned keepout zones; no fill or routing operation."""
from decimal import Decimal
import uuid

from .conductor_keepouts import number, validate_regions, validate_region
from .sexpr import Atom, dumps


def _coordinate(value):
    scaled = value * 1000000
    if scaled.denominator != 1:
        raise ValueError('Native keepout coordinates require exact nanometer representation')
    return Atom(format(Decimal(scaled.numerator) / Decimal(1000000), 'f'))


def keepout_nodes(package, *, position=(0, 0), identity=None, layers=None):
    """Footprint-contained native zone polygons use board coordinates in a board file.

    Standalone footprint exports are at origin. Handoff passes its known unplaced
    origin; KiCad subsequently owns footprint movement. No poses are selected here.
    """
    x, y = (number(v) for v in position)
    layers = ['*.Cu'] if layers is None else layers
    if not layers or any(not layer.endswith('.Cu') for layer in layers):
        raise ValueError('Native conductor keepout needs explicit copper layers')
    result = []
    for region in sorted(validate_regions(package), key=lambda row: row['id']):
        xmin, ymin, xmax, ymax = validate_region(region)
        points = [(x + xmin, y + ymin), (x + xmax, y + ymin),
                  (x + xmax, y + ymax), (x + xmin, y + ymax)]
        token = str(uuid.uuid5(uuid.NAMESPACE_URL, (identity or package['id']) + ':keepout:' + region['id']))
        node = [Atom('zone'), [Atom('net'), Atom('0')], [Atom('net_name'), ''],
                [Atom('layers'), *layers], [Atom('uuid'), token], [Atom('name'), region['id']],
                [Atom('hatch'), Atom('edge'), Atom('0.5')],
                [Atom('connect_pads'), [Atom('clearance'), Atom('0')]],
                [Atom('min_thickness'), Atom('0.01')],
                [Atom('keepout'), [Atom('tracks'), Atom('not_allowed' if 'TRACK' in region['forbid'] else 'allowed')],
                 [Atom('vias'), Atom('not_allowed' if 'VIA' in region['forbid'] else 'allowed')],
                 [Atom('pads'), Atom('allowed')], [Atom('copperpour'), Atom('allowed')],
                 [Atom('footprints'), Atom('allowed')]], [Atom('fill')],
                [Atom('polygon'), [Atom('pts'), *[[Atom('xy'), _coordinate(a), _coordinate(b)] for a, b in points]]]]
        result.append(node)
    return result


def keepout_text(package):
    return [dumps(node) for node in keepout_nodes(package)]
