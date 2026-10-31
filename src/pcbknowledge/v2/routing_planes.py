"""Do not present unfilled zone outlines as proven conductive planes to a router."""
from .boardview import children
from .specctra import read_specctra, write_specctra, _number, _one


def project_routing_planes(text, board):
    tree = read_specctra(text)
    if not tree or tree[0] != 'pcb':
        raise ValueError('Routing projection requires DSN PCB')
    structure = _one(tree, 'structure')
    planes = children(structure, 'plane')
    known_nets = set(board['nets'].values()) - {''}
    zones = {(zone['net'], zone['layer']) for zone in board['zones']}
    if planes and any(zone['filled_polygons'] for zone in board['zones']):
        raise ValueError('Unfilled-plane projection cannot consume already filled zone geometry')
    removed = []
    for plane in planes:
        if len(plane) != 3 or plane[1] not in known_nets or not isinstance(plane[2], list):
            raise ValueError('Malformed or unknown conductive DSN plane')
        polygon = plane[2]
        if (len(polygon) < 9 or polygon[0] != 'polygon' or polygon[1] not in ('F.Cu', 'B.Cu')
                or len(polygon[3:]) % 2 or (plane[1], polygon[1]) not in zones):
            raise ValueError('DSN plane does not match a supported unfilled board zone')
        if _number(polygon[2]) != 0:
            raise ValueError('Unsupported nonzero-width DSN plane polygon')
        for value in polygon[3:]:
            _number(value)
        removed.append({'net': plane[1], 'layer': polygon[1]})
    structure[:] = [item for item in structure
                    if not isinstance(item, list) or not item or item[0] != 'plane']
    return write_specctra(tree), {'status': 'PASS', 'excluded_plane_count': len(removed),
                                 'excluded_planes': removed, 'source_zones_retained': True,
                                 'reason': 'Explicit net routing precedes original zone fill'}
