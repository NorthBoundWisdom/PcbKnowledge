"""Independent non-electrical layer openings, never terminal or copper authority."""
import math


def _scalar(quantity, unit, positive=False):
    if not isinstance(quantity, dict) or quantity.get('unit') != unit or 'value' not in quantity:
        raise ValueError('Aperture geometry requires exact scalar quantities')
    value = quantity['value']
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError('Aperture geometry must be finite')
    if abs(value) > 1e6 or (positive and value <= 0):
        raise ValueError('Aperture geometry outside supported bounds')
    result = round(value, 6)
    if value and not result:
        raise ValueError('Aperture geometry collapses after rounding')
    return result


def _opening(item, pad, layer):
    if set(item) != {'id', 'shape', 'x', 'y', 'width', 'height', 'rotation'}:
        raise ValueError('Unsupported aperture fields')
    if item['shape'] not in ('RECT', 'ROUND', 'OVAL') or not isinstance(item['id'], str) or not item['id']:
        raise ValueError('Unsupported aperture shape or identity')
    values = {key: _scalar(item[key], 'mm', key in ('width', 'height'))
              for key in ('x', 'y', 'width', 'height')}
    angle = _scalar(item['rotation'], 'deg')
    if angle % 90 or pad['rotation'] % 90:
        raise ValueError('Aperture rotations require orthogonal angles')
    if item['shape'] == 'ROUND' and values['width'] != values['height']:
        raise ValueError('Round aperture requires equal dimensions')
    x, y = values['x'], values['y']
    for _ in range(int(pad['rotation'] % 360 / 90)):
        x, y = y, -x
    return {**values, 'x': round(pad['x'] + x, 6), 'y': round(pad['y'] + y, 6),
            'rotation': (pad['rotation'] + angle) % 360, 'shape': item['shape'],
            'id': item['id'], 'pad_number': pad['number'], 'layer': layer}


def derive_apertures(package, pads):
    result, bound = [], set()
    for binding in package.get('layer_apertures', []):
        if not isinstance(binding, dict) or set(binding) - {'pad_number', 'mask', 'paste'}:
            raise ValueError('Unsupported aperture binding')
        number = binding.get('pad_number')
        candidates = [pad for pad in pads if pad['number'] == number and pad['kind'] != 'MECHANICAL']
        if len(candidates) != 1 or number in bound:
            raise ValueError('Aperture requires one unique physical copper pad binding')
        pad = candidates[0]
        bound.add(number)
        if not {'mask', 'paste'} & binding.keys():
            raise ValueError('Aperture binding requires a layer')
        for key, layer in (('mask', 'Mask'), ('paste', 'Paste')):
            if key not in binding:
                continue
            if key == 'mask' and pad['kind'] != 'SMD':
                raise ValueError('Independent mask currently requires an SMD pad')
            if key == 'paste' and 'paste_margin' in pad:
                raise ValueError('Explicit paste conflicts with scalar paste margin')
            items = binding[key]
            if not isinstance(items, list) or not 1 <= len(items) <= 64:
                raise ValueError('Aperture layer requires a nonempty bounded pattern')
            openings = [_opening(item, pad, layer) for item in items]
            if len({item['id'] for item in openings}) != len(openings):
                raise ValueError('Duplicate aperture identities')
            _nonoverlap(openings)
            result.extend(openings)
            pad.setdefault('independent_layers', []).append(layer)
    for layer in ('Mask', 'Paste'):
        _nonoverlap([item for item in result if item['layer'] == layer])
    return result


def _nonoverlap(openings):
    boxes = []
    for item in openings:
        width, height = item['width'], item['height']
        if item['rotation'] % 180:
            width, height = height, width
        box = (item['x'] - width / 2, item['y'] - height / 2,
               item['x'] + width / 2, item['y'] + height / 2)
        if any(min(box[2], b[2]) - max(box[0], b[0]) > 1e-8
               and min(box[3], b[3]) - max(box[1], b[1]) > 1e-8 for b in boxes):
            raise ValueError('Overlapping aperture bounds are unsupported')
        boxes.append(box)


def export_apertures(derived, number):
    lines = []
    for item in derived.get('apertures', []):
        shape = {'RECT': 'rect', 'ROUND': 'circle', 'OVAL': 'oval'}[item['shape']]
        lines.append(f'  (pad "" smd {shape} (at {number(item["x"])} {number(item["y"])} '
                     f'{number(item["rotation"])}) (size {number(item["width"])} {number(item["height"])}) '
                     f'(layers "F.{item["layer"]}"))')
    return lines


def separate_aperture(node, parsed):
    """Recognize only layer-only apertures; malformed candidates fail closed."""
    layers = set(parsed['layers'])
    aperture_layers = {'F.Mask', 'B.Mask', 'F.Paste', 'B.Paste'}
    if not layers or not layers <= aperture_layers:
        return False
    if (len(layers) != 1 or node[1] or parsed['net'] or parsed['kind'] != 'smd'
            or parsed['drill'] is not None or parsed['geometry_unsupported']
            or parsed['paste_margin'] or parsed['paste_ratio']):
        raise ValueError('Malformed non-electrical layer aperture')
    if any(isinstance(item, list) and item and item[0] in ('net', 'solder_mask_margin') for item in node):
        raise ValueError('Apertures cannot carry nets or mask margins')
    return True


def aperture_identity(footprint, derived):
    from .layout_identity import close_vector
    from .boardview import transform
    actual = list(footprint.get('apertures', []))
    back = footprint['layer'] == 'B.Cu'
    for item in derived.get('apertures', []):
        local = [item['x'], -item['y'] if back else item['y']]
        expected = {'at': transform(local, footprint['at'], footprint['rotation']),
                    'size': [item['width'], item['height']],
                    'rotation': footprint['rotation'] + (-item['rotation'] if back else item['rotation']),
                    'shape': {'RECT': 'rect', 'ROUND': 'circle', 'OVAL': 'oval'}[item['shape']],
                    'layers': [('B.' if back else 'F.') + item['layer']]}
        def matches(candidate):
            angle = (candidate['rotation'] - expected['rotation'] + 180) % 360 - 180
            return (candidate['shape'] == expected['shape'] and candidate['layers'] == expected['layers']
                    and abs(angle) <= .000002 and close_vector(candidate['at'], expected['at'])
                    and close_vector(candidate['size'], expected['size']))
        index = next((i for i, candidate in enumerate(actual) if matches(candidate)), None)
        if index is None:
            return False
        actual.pop(index)
    return not actual
