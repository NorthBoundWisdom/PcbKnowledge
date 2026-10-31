"""Read-only all-exposed-surface guard-track enclosure measurements (D101)."""
from itertools import combinations
import math
from fractions import Fraction

from .layout_geometry import simple_polygon
from .layout_return import check_drill_corridor, contains, point, point_distance2, segment_distance2
from .reference_paths import positive_mm
from .layout_guard_geometry import pad_shape, track_shape, shape_distance2


def result(state, reason, **values):
    return {'kind': 'GUARD_RING', 'result': state, 'reason': reason, **values}


def net_pads(board, net):
    return [pad for footprint in board['footprints'].values() for pads in footprint['pads'].values()
            for pad in pads if pad.get('net') == net]


def copper_layers(pad):
    return {'F.Cu', 'B.Cu'} if '*.Cu' in pad['layers'] else set(pad['layers']) & {'F.Cu', 'B.Cu'}


def surfaces(board, rule):
    if board.get('unsupported') or set(board.get('copper_layers') or []) != {'F.Cu', 'B.Cu'}:
        raise ValueError('Supported two-layer geometry required')
    if not board.get('outline', {}).get('closed') or not board['outline'].get('rectangular'):
        raise ValueError('Closed rectangular outline required')
    if rule['net'] == rule['guard_net']:
        raise ValueError('Sensitive and guard nets must differ')
    if any(item['net'] in (rule['net'], rule['guard_net']) for item in board['arcs']):
        raise ValueError('Curved guard/sensitive copper is unsupported')
    if any(item['net'] == rule['net'] for item in board['vias']):
        raise ValueError('Sensitive via copper requires another enclosure measurement')
    if any(zone['net'] in (rule['net'], rule['guard_net']) and zone['filled_polygons'] for zone in board['zones']):
        raise ValueError('Guard/sensitive filled copper requires another enclosure measurement')
    pads = net_pads(board, rule['net'])
    tracks = [item for item in board['segments'] if item['net'] == rule['net']]
    layers = [copper_layers(pad) for pad in pads] + [{track['layer']} for track in tracks]
    if not layers or any(not item or not item <= {'F.Cu', 'B.Cu'} for item in layers):
        raise ValueError('Protected pads and tracks must expose known copper surfaces')
    return [(layer, [pad for pad in pads if layer in copper_layers(pad)],
             [track for track in tracks if track['layer'] == layer])
            for layer in ('F.Cu', 'B.Cu') if any(layer in item for item in layers)]


def track_graph(tracks):
    adjacency, edges = {}, {}
    for index, track in enumerate(tracks):
        a, b = point(track['start']), point(track['end'])
        key = frozenset((a, b))
        if a == b or key in edges or Fraction(str(track['width'])) <= 0:
            raise ValueError('Degenerate or duplicated guard segment')
        edges[key] = index
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    for first, second in combinations(tracks, 2):
        a, b, c, d = map(point, (first['start'], first['end'], second['start'], second['end']))
        if {a, b}.isdisjoint({c, d}) and segment_distance2(a, b, c, d) == 0:
            raise ValueError('Guard intersections must be explicitly split at connection points')
    return adjacency, edges


def cycle(adjacency, edges, tracks):
    core = {key: set(neighbors) for key, neighbors in adjacency.items()}
    pending = [key for key, neighbors in core.items() if len(neighbors) < 2]
    while pending:
        current = pending.pop()
        for other in core.pop(current, set()):
            core[other].discard(current)
            if len(core[other]) < 2:
                pending.append(other)
    if not core:
        for a, b in combinations(tracks, 2):
            ends = list(map(point, (a['start'], a['end'], b['start'], b['end'])))
            if set(ends[:2]).isdisjoint(ends[2:]):
                radius = (Fraction(str(a['width'])) + Fraction(str(b['width']))) / 2
                if segment_distance2(*ends) <= radius * radius:
                    raise ValueError('Unsplit overlapping guard copper has ambiguous closure')
        return [], []
    if any(len(neighbors) != 2 for neighbors in core.values()):
        raise ValueError('Guard requires one unbranched centerline cycle after feed branches are removed')
    start = min(core)
    path, indices, previous, current = [], [], None, start
    while current not in path:
        path.append(current)
        following = next(node for node in sorted(core[current]) if node != previous)
        indices.append(edges[frozenset((current, following))])
        previous, current = current, following
    if current != start or len(path) != len(core) or not simple_polygon(path):
        raise ValueError('Guard must have one simple closed centerline enclosure')
    return path, indices


def enclosure(shapes, path, guard_shapes, clearance):
    enclosed = all(contains(p, path) for shape in shapes for p in shape['points'])
    passed, measured = True, []
    for shape in shapes:
        for copper in guard_shapes:
            radius = shape['radius'] + copper['radius']
            distance2 = shape_distance2(shape, copper)
            passed &= distance2 >= (radius + clearance) ** 2
            measured.append(math.sqrt(float(distance2)) - float(radius))
    return enclosed and passed, min(measured)


def via_shape(via):
    return {'points': [point(via['at'])], 'edges': [(point(via['at']), point(via['at']))],
            'radius': Fraction(str(via['size'])) / 2, 'polygon': None}


def guard_via_geometry(board, net, tracks):
    annular = {index: [] for index in range(len(tracks))}
    vias = [via for via in board['vias'] if via['net'] == net]
    for via in vias:
        size, drill = Fraction(str(via['size'])), Fraction(str(via['drill']))
        if via.get('geometry_unsupported') or not 0 < drill < size:
            raise ValueError('Guard vias require supported plated through geometry')
        if set(via.get('layers', [])) != {'F.Cu', 'B.Cu'}:
            raise ValueError('Guard vias require supported plated through geometry')
        center, inner = point(via['at']), drill / 2
        for index, track in enumerate(tracks):
            a, b = point(track['start']), point(track['end'])
            radius = Fraction(str(track['width'])) / 2
            if point_distance2(center, a, b) > (inner + radius) ** 2:
                continue
            outside = max(sum((center[i] - end[i]) ** 2 for i in range(2)) for end in (a, b))
            if center not in (a, b) or outside <= inner * inner:
                raise ValueError('Guard via interruption needs a center-ended annular crossing')
            annular[index].append((size - drill) / 2)
    return vias, annular


def physical_tracks(board, tracks, net):
    xmin, ymin, xmax, ymax = map(Fraction, map(str, board['outline']['bounds']))
    without_guard_vias = {**board, 'vias': [via for via in board['vias'] if via['net'] != net]}
    for track in tracks:
        radius = Fraction(str(track['width'])) / 2
        check_drill_corridor(without_guard_vias, track, radius)
        if any(not (xmin + radius <= x <= xmax - radius and ymin + radius <= y <= ymax - radius)
               for x, y in (point(track['start']), point(track['end']))):
            return False
    return True


def check_surface(board, rule, layer, pads, sensitive, tracks, connections, vias, annular):
    selected = [index for index, track in enumerate(tracks) if track['layer'] == layer]
    local = [tracks[index] for index in selected]
    guard_pads = [pad for pad in net_pads(board, rule['guard_net']) if layer in copper_layers(pad)]
    guard_pad_shapes = [pad_shape(pad) for pad in guard_pads]
    width = Fraction(str(positive_mm(rule['min_width'])))
    clearance = Fraction(str(positive_mm(rule['min_clearance'])))
    adjacency, edges = track_graph(local)
    path, indices = cycle(adjacency, edges, local)
    if not path:
        if pad_bridge(guard_pad_shapes + [via_shape(via) for via in vias], local):
            raise ValueError('Possible pad/via-mediated ring closure needs another measurement method')
        return result('FAIL', 'No closed guard track cycle', layer=layer,
                      nearest_open_gap_mm=open_gap(adjacency, edges, local),
                      open_endpoints=[list(map(float, key)) for key, neighbors in adjacency.items()
                                      if len(neighbors) == 1])
    ring = [selected[index] for index in indices]
    contact = ring[0] in connections['anchored_tracks']
    if not contact and ring[0] in connections['uncertain_tracks']:
        raise ValueError('Guard contact has possible but unproven pad or via links')
    shapes = [pad_shape(pad) for pad in pads] + [track_shape(track) for track in sensitive]
    # A via drill is not copper. Reject ambiguous protected copper inside that
    # physical void rather than treating the annular aperture as a solid disc.
    guard_holes = {'footprints': {}, 'vias': vias}
    for shape in shapes:
        for a, b in shape['edges']:
            check_drill_corridor(guard_holes, {'start': a, 'end': b}, shape['radius'])
    copper = guard_pad_shapes + [track_shape(track) for track in local] + [via_shape(via) for via in vias]
    protected, gap = enclosure(shapes, path, copper, clearance)
    widths = [Fraction(str(tracks[index]['width'])) for index in ring]
    widths.extend(value for index in ring for value in annular[index])
    minimum = min(widths)
    passed = contact and protected and minimum >= width
    return result('PASS' if passed else 'FAIL', 'Closed guard around every sensitive pad and track on this surface',
                  layer=layer, connected_to_guard_pad=contact, protected=protected, min_width_mm=float(minimum),
                  min_clearance_mm=gap, required_width_mm=float(width), required_clearance_mm=float(clearance),
                  closed_segments=len(indices), max_gap_mm=0.0, protected_pads=len(pads),
                  protected_tracks=len(sensitive))


def check_guard_ring(board, rule):
    from .layout_guard_contacts import guard_connections
    try:
        targets = surfaces(board, rule)
        tracks = [item for item in board['segments'] if item['net'] == rule['guard_net']]
        if any(track['layer'] not in ('F.Cu', 'B.Cu') for track in tracks):
            raise ValueError('Unsupported guard track layer')
        if any(pad.get('kind') != 'smd' or pad.get('drill') for pad in net_pads(board, rule['guard_net'])):
            raise ValueError('Guard terminals require solid SMT copper for this contact measurement')
        vias, annular = guard_via_geometry(board, rule['guard_net'], tracks)
        if not physical_tracks(board, tracks, rule['guard_net']):
            return result('FAIL', 'Guard corridor extends outside the physical board')
        connections = guard_connections(board, rule['guard_net'], tracks)
        reports = []
        for layer, pads, sensitive in targets:
            try:
                reports.append(check_surface(board, rule, layer, pads, sensitive, tracks, connections, vias, annular))
            except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as error:
                reports.append(result('NOT_CHECKABLE', str(error), layer=layer))
        if len(reports) == 1:
            return reports[0]
        states = {report['result'] for report in reports}
        state = 'FAIL' if 'FAIL' in states else 'NOT_CHECKABLE' if 'NOT_CHECKABLE' in states else 'PASS'
        return result(state, 'Guard enclosure on every exposed sensitive copper surface',
                      surfaces=reports, via_connections=connections['vias'])
    except (KeyError, ValueError, TypeError, IndexError, ZeroDivisionError) as error:
        return result('NOT_CHECKABLE', str(error))


def pad_bridge(shapes, tracks):
    for shape in shapes:
        touching = [track for track in tracks if shape_distance2(shape, track_shape(track))
                    <= (shape['radius'] + track_shape(track)['radius']) ** 2]
        for first, second in combinations(touching, 2):
            if {point(first['start']), point(first['end'])}.isdisjoint(
                    {point(second['start']), point(second['end'])}):
                return True
    return False


def open_gap(adjacency, edges, tracks):
    ends = [node for node, neighbors in adjacency.items() if len(neighbors) == 1]
    gaps = []
    for a, b in combinations(ends, 2):
        radii = [Fraction(str(tracks[edges[frozenset((node, next(iter(adjacency[node]))))]]['width'])) / 2
                 for node in (a, b)]
        gaps.append(max(0, math.sqrt(float(sum((a[i] - b[i]) ** 2 for i in range(2)))) - float(sum(radii))))
    return min(gaps) if gaps else None
