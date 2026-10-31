"""Read-only necessary distance bounds; no placement or feasibility search."""
from fractions import Fraction

from .footprints import derive_footprint


def _scalar(value):
    if value.get('unit') != 'mm' or value.get('status') or type(value.get('value')) not in (int, float):
        return None
    try:
        number = Fraction(str(value['value']))
    except (ValueError, ZeroDivisionError):
        return None
    return number if number >= 0 else None


def _endpoint_radius(catalog, component, endpoint):
    """An inscribed disk centered at the measured origin or physical pad center."""
    part = catalog.get(component['part'], 'part')
    package = catalog.get(component['package'], 'package')
    if part['package'] != package['id']:
        return None
    footprint = derive_footprint(package)
    box = {key: Fraction(str(value)) for key, value in footprint['courtyard'].items()}
    _, marker, pin = endpoint.partition('.pin:')
    points = [(Fraction(0), Fraction(0))]
    if marker:
        numbers = {item['number'] for item in part['pins'] if pin in (item['name'], item['number'])}
        points = [(Fraction(str(pad['x'])), Fraction(str(pad['y']))) for pad in footprint['pads']
                  if pad['number'] in numbers]
    if not points:
        return None
    radii = [min(x - box['min_x'], box['max_x'] - x, y - box['min_y'], box['max_y'] - y)
             for x, y in points]
    # If any eligible measurement point is outside its courtyard, no disk proof.
    if min(radii) < 0:
        return None
    return min(radii)


def isolated_near_bounds(catalog, intent):
    """Return necessary bounds under explicit projected KEEPOUT exclusion.

    Each courtyard contains an open disk around its measurement point. Two such
    disks cannot intersect when explicit KEEPOUT excludes authoritative projected
    courtyard bounding boxes, regardless of mount type or board face.
    Their radii sum, plus the exclusion margin, bounds center distance under any
    rotation. This proves impossibility, never the existence of a placement.
    """
    if intent.get('status') != 'EXPANDED':
        return []
    components = {item['ref']: item for item in intent['components']}
    bounds = []
    for rule in intent['layout']:
        if rule['kind'] != 'PLACE_NEAR' or rule.get('datum', 'ORIGIN_PAD_CENTER') != 'ORIGIN_PAD_CENTER':
            continue
        refs = [rule[name].partition('.pin:')[0] for name in ('subject', 'target')]
        if refs[0] == refs[1] or any(ref not in components for ref in refs):
            continue
        margins = [_scalar(item['margin']) for item in intent['layout']
                   if item['kind'] == 'KEEPOUT' and item['subject'] in refs]
        if not margins or any(value is None for value in margins):
            continue
        limit = _scalar(rule['max_distance'])
        if limit is None:
            continue
        radii = [_endpoint_radius(catalog, components[ref], rule[field])
                 for ref, field in zip(refs, ('subject', 'target'))]
        if any(value is None for value in radii):
            continue
        lower = sum(radii) + max(margins)
        bounds.append({'subject': rule['subject'], 'target': rule['target'],
                       'lower_bound_mm': lower, 'limit_mm': limit, 'impossible': lower > limit})
    return bounds


def validate_near_bounds(catalog, intent):
    bounds = isolated_near_bounds(catalog, intent)
    for bound in bounds:
        if bound['impossible']:
            raise ValueError(
                f"PLACE_NEAR {bound['subject']} -> {bound['target']} is impossible under projected "
                f"explicit KEEPOUT: isolated center-distance lower bound {bound['lower_bound_mm']} mm "
                f"exceeds {bound['limit_mm']} mm")
    return len(bounds)
