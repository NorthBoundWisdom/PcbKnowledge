"""Recognize a narrow unfilled native rule-area grammar, never copper geometry."""


def nonconductive_keepout(node):
    from .boardview import children, field, number
    try:
        allowed = {'net', 'net_name', 'layers', 'uuid', 'name', 'hatch', 'connect_pads',
                   'min_thickness', 'keepout', 'fill', 'polygon'}
        if not isinstance(node, list) or not node or node[0] != 'zone':
            return False
        entries = node[1:]
        if any(not isinstance(entry, list) or not entry or entry[0] not in allowed for entry in entries):
            return False
        if len({entry[0] for entry in entries}) != len(entries):
            return False
        if field(node, 'net') != ['0'] or field(node, 'net_name') != [''] or field(node, 'fill') != []:
            return False
        layers = field(node, 'layers', [])
        if not layers or any(not isinstance(layer, str) or not layer.endswith('.Cu') for layer in layers):
            return False
        flags = field(node, 'keepout', [])
        names = {'tracks', 'vias', 'pads', 'copperpour', 'footprints'}
        if len(flags) != 5 or {flag[0] for flag in flags} != names:
            return False
        if any(len(flag) != 2 or flag[1] not in ('allowed', 'not_allowed') for flag in flags):
            return False
        polygon = field(node, 'polygon', [])
        if len(polygon) != 1 or polygon[0][0] != 'pts':
            return False
        points = polygon[0][1:]
        if len(points) < 3 or len(points) > 10000:
            return False
        for point in points:
            if len(point) != 3 or point[0] != 'xy':
                return False
            number(point[1])
            number(point[2])
        for name in ('uuid', 'name'):
            value = field(node, name, [])
            if len(value) != 1 or not isinstance(value[0], str):
                return False
        if field(node, 'connect_pads') != [['clearance', '0']]:
            return False
        hatch = field(node, 'hatch', [])
        thickness = field(node, 'min_thickness', [])
        if len(hatch) != 2 or hatch[0] != 'edge' or number(hatch[1]) <= 0:
            return False
        return len(thickness) == 1 and number(thickness[0]) > 0
    except (TypeError, ValueError, IndexError, KeyError):
        return False
