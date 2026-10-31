"""Package-local track/via exclusions, projected unchanged into design intent."""
from copy import deepcopy
from fractions import Fraction
import math
import re


FIELDS = {'id', 'rectangle', 'forbid', 'layer_scope', 'scope_basis', 'scope_note', 'evidence'}


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1000000:
        raise ValueError('Finite conductor keepout coordinate required')
    return Fraction(str(value))


def quantity(value):
    if not isinstance(value, dict) or value.get('unit') != 'mm' or value.get('status'):
        raise ValueError('Conductor keepout bounds require concrete millimeters')
    return number(value.get('value'))


def validate_region(region):
    if not isinstance(region, dict) or set(region) != FIELDS:
        raise ValueError('Wrong conductor keepout fields')
    if not isinstance(region['id'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', region['id']):
        raise ValueError('Invalid conductor keepout identity')
    rectangle = region['rectangle']
    if not isinstance(rectangle, dict) or set(rectangle) != {'xmin', 'ymin', 'xmax', 'ymax'}:
        raise ValueError('Conductor keepout requires four rectangle bounds')
    values = tuple(quantity(rectangle[key]) for key in ('xmin', 'ymin', 'xmax', 'ymax'))
    if values[0] >= values[2] or values[1] >= values[3]:
        raise ValueError('Conductor keepout bounds are unordered or empty')
    if (not isinstance(region['forbid'], list) or not region['forbid']
            or len(set(region['forbid'])) != len(region['forbid'])
            or not set(region['forbid']) <= {'TRACK', 'VIA'}):
        raise ValueError('Conductor keepout supports explicit TRACK/VIA prohibition only')
    if region['layer_scope'] != 'ALL_COPPER' or region['scope_basis'] != 'ENGINEERING_DEFAULT':
        raise ValueError('Conductor keepout requires explicit all-copper engineering scope')
    if not isinstance(region['scope_note'], str) or not region['scope_note'].strip():
        raise ValueError('Conductor keepout scope decision must be explained')
    anchor = region['evidence']
    if (not isinstance(anchor, dict) or set(anchor) != {'source', 'page'}
            or not isinstance(anchor['source'], str) or not anchor['source'].startswith('source:')
            or type(anchor['page']) is not int or anchor['page'] < 1):
        raise ValueError('Conductor keepout requires source/page evidence')
    return values


def validate_regions(package):
    regions = package.get('conductor_keepouts', [])
    if not isinstance(regions, list) or len(regions) > 16:
        raise ValueError('Package conductor keepouts must be a bounded list')
    seen = set()
    for region in regions:
        validate_region(region)
        if region['id'] in seen:
            raise ValueError('Duplicate conductor keepout identity')
        seen.add(region['id'])
    return regions


def project_keepouts(components, catalog):
    result = []
    for component in sorted(components, key=lambda c: c['ref']):
        package = catalog.get(component['package'], 'package')
        for region in sorted(validate_regions(package), key=lambda r: r['id']):
            result.append({'kind': 'CONDUCTOR_KEEPOUT', 'subject': component['ref'], 'region': deepcopy(region)})
    return result


def validate_projection(intent, catalog):
    actual = [rule for rule in intent['layout'] if rule['kind'] == 'CONDUCTOR_KEEPOUT']
    expected = project_keepouts(intent['components'], catalog)
    key = lambda rule: (rule['subject'], rule['region']['id'])
    if sorted(actual, key=key) != expected:
        raise ValueError('Intent conductor keepouts differ from selected package authority')
