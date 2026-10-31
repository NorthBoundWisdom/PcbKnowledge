"""Exact, read-only connectivity witnesses for guard tracks and through vias."""
from fractions import Fraction
from itertools import combinations

from .layout_guard_geometry import capsule, pad_shape, shape_distance2, track_shape
from .layout_return import point, point_distance2


SURFACES = {'F.Cu', 'B.Cu'}


def layers(item):
    declared = set(item.get('layers', []))
    return SURFACES if '*.Cu' in declared else declared & SURFACES


def join(adjacency, first, second):
    adjacency[first].add(second)
    adjacency[second].add(first)


def reachable(adjacency, roots):
    visited, pending = set(), list(roots)
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(adjacency[current] - visited)
    return visited


def possible_pad_shape(pad):
    """Unknown copper uses an enclosing disc only to avoid a false disconnection."""
    try:
        return pad_shape(pad), True
    except (KeyError, ValueError, TypeError):
        at = point(pad['at'])
        radius = sum(abs(value) for value in point(pad['size'])) / 2
        return capsule(at, at, radius), False


def track_links(tracks, shapes, adjacency, uncertain):
    for first, second in combinations(range(len(tracks)), 2):
        a, b = tracks[first], tracks[second]
        if a['layer'] != b['layer']:
            continue
        endpoints_a = {point(a['start']), point(a['end'])}
        endpoints_b = {point(b['start']), point(b['end'])}
        if endpoints_a & endpoints_b:
            join(adjacency, first, second)
        elif shape_distance2(shapes[first], shapes[second]) <= (
                shapes[first]['radius'] + shapes[second]['radius']) ** 2:
            uncertain.update((first, second))


def pad_void_ambiguous(board, shape):
    holes = [(via['at'], [via['drill'], via['drill']], [0, 0]) for via in board.get('vias', [])]
    holes.extend((pad['at'], pad.get('drill_size') or [pad['drill']] * 2, pad.get('drill_offset', [0, 0]))
                 for footprint in board['footprints'].values() for group in footprint['pads'].values()
                 for pad in group if pad.get('drill'))
    for at, size, offset in holes:
        center = point(at)
        radius = max(point(size)) / 2 + sum(abs(value) for value in point(offset))
        hole = capsule(center, center, radius)
        if shape_distance2(shape, hole) <= (shape['radius'] + radius) ** 2:
            return True
    return False


def pad_links(board, net, tracks, shapes, adjacency, anchored, uncertain):
    pads = [pad for footprint in board['footprints'].values() for group in footprint['pads'].values()
            for pad in group if pad.get('net') == net]
    for pad in pads:
        shape, known = possible_pad_shape(pad)
        solid = known and pad.get('kind') == 'smd' and not pad.get('drill')
        solid = solid and not pad_void_ambiguous(board, shape)
        contacts = []
        for index, track in enumerate(tracks):
            if track['layer'] not in layers(pad):
                continue
            distance = shape_distance2(shape, shapes[index])
            threshold = (shape['radius'] + shapes[index]['radius']) ** 2
            if solid and distance < threshold:
                contacts.append(index)
                anchored.add(index)
            elif distance <= threshold:
                uncertain.add(index)
        for first, second in zip(contacts, contacts[1:]):
            join(adjacency, first, second)
    return pads


def via_contacts(via, tracks, shapes):
    center = point(via['at'])
    radius, drill = Fraction(str(via['size'])) / 2, Fraction(str(via['drill'])) / 2
    supported = layers(via) == SURFACES and set(via.get('layers', [])) == SURFACES and 0 < drill < radius
    supported &= not via.get('geometry_unsupported', False)
    proven, possible = [], []
    for index, track in enumerate(tracks):
        if track['layer'] not in layers(via):
            continue
        a, b = point(track['start']), point(track['end'])
        distance = point_distance2(center, a, b)
        if distance > (max(radius, drill) + shapes[index]['radius']) ** 2:
            continue
        remote = b if a == center else a if b == center else None
        outside = remote is not None and sum((remote[i] - center[i]) ** 2 for i in range(2)) > drill ** 2
        if supported and outside:
            proven.append(index)
        else:
            possible.append(index)
    return proven, possible, supported


def via_links(board, net, tracks, shapes, pads, adjacency, uncertain):
    evidence = []
    for index, via in enumerate(board.get('vias', [])):
        if via.get('net') != net:
            continue
        proven, possible, supported = via_contacts(via, tracks, shapes)
        node = ('via', index)
        adjacency[node] = set()
        for track in proven:
            join(adjacency, node, track)
        uncertain.update(possible)
        if possible:
            uncertain.add(node)
        center = point(via['at'])
        circle = capsule(center, center, Fraction(str(via['size'])) / 2)
        pad_overlap = False
        for pad in pads:
            if not layers(pad) & layers(via):
                continue
            shape, _known = possible_pad_shape(pad)
            if shape_distance2(circle, shape) <= (circle['radius'] + shape['radius']) ** 2:
                pad_overlap = True
                uncertain.add(node)
        evidence.append({'via': index, 'at_mm': list(map(float, center)), 'supported': supported,
                         'diameter_mm': via['size'], 'drill_mm': via['drill'],
                         'proven_tracks': proven, 'uncertain_tracks': possible,
                         'unproved_pad_contact': pad_overlap,
                         'method': 'center endpoint crosses annulus beyond drill radius'})
    return evidence


def guard_connections(board, net, tracks):
    """Indices refer to the passed all-surface track list, not per-layer subsets.

    Only explicit endpoint, solid-pad and radial annulus witnesses establish
    connectivity. Possible unproved contacts retain uncertainty transitively.
    """
    if any(track.get('net') != net or track.get('layer') not in SURFACES for track in tracks):
        raise ValueError('Guard connections require guard-net F/B copper tracks')
    if any(point(track['start']) == point(track['end']) for track in tracks):
        raise ValueError('Guard connections require nonzero track length')
    shapes = [track_shape(track) for track in tracks]
    adjacency = {index: set() for index in range(len(tracks))}
    anchored, uncertain = set(), set()
    track_links(tracks, shapes, adjacency, uncertain)
    pads = pad_links(board, net, tracks, shapes, adjacency, anchored, uncertain)
    evidence = via_links(board, net, tracks, shapes, pads, adjacency, uncertain)
    return {'anchored_tracks': {node for node in reachable(adjacency, anchored) if isinstance(node, int)},
            'uncertain_tracks': {node for node in reachable(adjacency, uncertain) if isinstance(node, int)},
            'vias': evidence}
