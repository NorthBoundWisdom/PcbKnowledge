"""Deterministic top-side placement from derived geometry; never relax constraints.

Search is finite: four right-angle orientations and a board-origin grid, with exact
edge-distance coordinates added to that grid. Heuristic beam exhaustion is not
a proof of infeasibility in the grid or continuous geometry. Copper constraints
remain the responsibility of the final layout checker and native DRC.
"""
import math

from pcbknowledge.v2.boardview import children, field, transform
from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.layout import EDGE_EQUALITY_TOLERANCE_MM, GROUP_MAX_DISTANCE_MM, quantity
from pcbknowledge.v2.layout_board import limit
from pcbknowledge.v2.layout_geometry import convex_hull, distance, overlap, polygon_area

POSITION_KINDS = {'PLACE_NEAR', 'GROUP', 'EDGE_DISTANCE', 'EDGE_PLACEMENT', 'KEEPOUT', 'MINIMIZE_LOOP'}
COPPER_KINDS = {'NET_WIDTH_MIN', 'COPPER_AREA', 'GUARD_RING', 'RETURN_PATH', 'KELVIN', 'DIFFERENTIAL_PAIR'}
EPSILON = 1e-9


class PlacementError(ValueError):
    """A failed placement search, with machine-readable cause and constraint IDs."""

    def __init__(self, reason, *, constraints=(), states=0):
        self.reason = reason
        self.constraints = tuple(constraints)
        self.states = states
        super().__init__(reason + '; constraints=' + ','.join(map(str, constraints)))


def _ref(endpoint):
    return endpoint.partition('.pin:')[0]


def _refs(rule):
    kind = rule['kind']
    if kind == 'PLACE_NEAR':
        return {_ref(rule['subject']), _ref(rule['target'])}
    if kind == 'GROUP':
        return set(rule['subjects'])
    if kind == 'MINIMIZE_LOOP':
        return {_ref(endpoint) for endpoint in rule['path']}
    return {_ref(rule['subject'])}


def _finite(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PlacementError('Invalid finite ' + name)
    if positive and value <= 0:
        raise PlacementError('Nonpositive ' + name)
    return float(value)


def _validate_geometry(geometry):
    for ref, item in geometry.items():
        if not isinstance(ref, str) or not ref or '.pin:' in ref:
            raise PlacementError('Invalid component reference')
        box = item['courtyard']
        values = [_finite(box[key], 'courtyard') for key in ('min_x', 'min_y', 'max_x', 'max_y')]
        if values[0] >= values[2] or values[1] >= values[3]:
            raise PlacementError('Degenerate courtyard: ' + ref)
        for pad in item['pads']:
            _finite(pad['x'], 'pad x')
            _finite(pad['y'], 'pad y')
            if not isinstance(pad['number'], str):
                raise PlacementError('Invalid physical pad number')


def _local_points(endpoint, geometry, angle):
    ref, separator, pin = endpoint.partition('.pin:')
    points = [[0.0, 0.0]]
    if separator:
        points = [[pad['x'], pad['y']] for pad in geometry[ref]['pads'] if pad['number'] == pin]
        if not points:
            raise PlacementError('Unknown physical endpoint: ' + endpoint)
    return [transform(point, (0, 0), angle) for point in points]


def _points(endpoint, geometry, positions):
    ref = _ref(endpoint)
    x, y, angle = positions[ref]
    return [[x + p[0], y + p[1]] for p in _local_points(endpoint, geometry, angle)]


def _box(item, position):
    box = item['courtyard']
    x, y, angle = position
    points = [transform((a, b), (x, y), angle)
              for a in (box['min_x'], box['max_x']) for b in (box['min_y'], box['max_y'])]
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def _edge_ok(rule, geometry, positions, width, height):
    x, y = _points(rule['subject'], geometry, positions)[0]
    if not -EPSILON <= x <= width + EPSILON or not -EPSILON <= y <= height + EPSILON:
        return False
    observed = {'LEFT': x, 'RIGHT': width - x, 'TOP': y, 'BOTTOM': height - y}[rule['edge']]
    if rule['kind'] == 'EDGE_DISTANCE':
        return abs(observed - quantity(rule, 'distance', 'mm')) <= EDGE_EQUALITY_TOLERANCE_MM + EPSILON
    return observed <= quantity(rule, 'max_distance', 'mm') + EPSILON


def _rule_ok(rule, geometry, positions, width, height):
    refs = _refs(rule)
    placed = refs.intersection(positions)
    if rule['kind'] == 'GROUP':
        points = [positions[ref][:2] for ref in sorted(placed)]
        return all(distance(a, b) <= GROUP_MAX_DISTANCE_MM + EPSILON
                   for i, a in enumerate(points) for b in points[i + 1:])
    if not refs <= positions.keys():
        return True
    kind = rule['kind']
    if kind.startswith('EDGE_'):
        return _edge_ok(rule, geometry, positions, width, height)
    if kind == 'PLACE_NEAR':
        closest = min(distance(a, b) for a in _points(rule['subject'], geometry, positions)
                      for b in _points(rule['target'], geometry, positions))
        return closest <= quantity(rule, 'max_distance', 'mm') + EPSILON
    if kind == 'MINIMIZE_LOOP':
        points = [point for endpoint in rule['path'] for point in _points(endpoint, geometry, positions)]
        return polygon_area(convex_hull(points)) <= quantity(rule, 'max_area', 'mm2') + EPSILON
    if kind == 'KEEPOUT':
        ref = rule['subject']
        box = _box(geometry[ref], positions[ref])
        margin = quantity(rule, 'margin', 'mm')
        inflated = [box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin]
        return all(other == ref or not overlap(inflated, _box(geometry[other], position))
                   for other, position in positions.items())
    raise PlacementError('Unsupported placement rule: ' + kind)


def _prepare_rules(rules, geometry):
    prepared = []
    for index, rule in enumerate(rules):
        kind = rule['kind']
        if kind in COPPER_KINDS:
            continue
        if kind not in POSITION_KINDS:
            raise PlacementError('Unsupported constraint kind: ' + kind, constraints=(index,))
        if not _refs(rule) <= geometry.keys():
            raise PlacementError('Unknown component in placement constraint', constraints=(index,))
        if kind.startswith('EDGE_') and rule['edge'] not in {'LEFT', 'RIGHT', 'TOP', 'BOTTOM'}:
            raise PlacementError('Unknown directional edge', constraints=(index,))
        if kind == 'KEEPOUT' and '.pin:' in rule['subject']:
            raise PlacementError('Keepout requires a footprint subject', constraints=(index,))
        fields = {'PLACE_NEAR': ('max_distance', 'mm'), 'KEEPOUT': ('margin', 'mm'),
                  'EDGE_DISTANCE': ('distance', 'mm'), 'EDGE_PLACEMENT': ('max_distance', 'mm'),
                  'MINIMIZE_LOOP': ('max_area', 'mm2')}
        if kind in fields:
            quantity(rule, *fields[kind])
        endpoints = list(rule.get('path', []))
        endpoints += [rule[key] for key in ('subject', 'target') if key in rule]
        for endpoint in endpoints:
            _local_points(endpoint, geometry, 0)
        prepared.append((index, rule))
    return prepared


def _axis_values(low, high, grid, exact):
    if low > high + EPSILON:
        return []
    values = {round(i * grid, 9) for i in range(math.ceil((low - EPSILON) / grid),
                                               math.floor((high + EPSILON) / grid) + 1)}
    values.update(round(value, 9) for value in exact if low - EPSILON <= value <= high + EPSILON)
    return sorted(values)


def _domain(ref, angle, geometry, rules, width, height, grid):
    box = _box(geometry[ref], (0, 0, angle))
    lower, upper = [-box[0], -box[1]], [width - box[2], height - box[3]]
    exact = [[], []]
    for _, rule in rules:
        if not rule['kind'].startswith('EDGE_') or _ref(rule['subject']) != ref:
            continue
        offset = _local_points(rule['subject'], geometry, angle)[0]
        edge = rule['edge']
        axis = 0 if edge in {'LEFT', 'RIGHT'} else 1
        span = width if axis == 0 else height
        target = quantity(rule, 'distance' if rule['kind'] == 'EDGE_DISTANCE' else 'max_distance', 'mm')
        near = edge in {'LEFT', 'TOP'}
        if rule['kind'] == 'EDGE_DISTANCE':
            origin = (target if near else span - target) - offset[axis]
            exact[axis].append(origin)
            lower[axis] = max(lower[axis], origin - EDGE_EQUALITY_TOLERANCE_MM)
            upper[axis] = min(upper[axis], origin + EDGE_EQUALITY_TOLERANCE_MM)
        elif near:
            upper[axis] = min(upper[axis], target - offset[axis])
            lower[axis] = max(lower[axis], -offset[axis])
        else:
            lower[axis] = max(lower[axis], span - target - offset[axis])
            upper[axis] = min(upper[axis], span - offset[axis])
    return (_axis_values(lower[0], upper[0], grid, exact[0]),
            _axis_values(lower[1], upper[1], grid, exact[1]))


def _priority(ref, positions, geometry, rules, mechanical):
    attached = sum(bool((_refs(rule) - {ref}).intersection(positions))
                   for _, rule in rules if ref in _refs(rule))
    edge = any(rule['kind'].startswith('EDGE_') and _ref(rule['subject']) == ref for _, rule in rules)
    anchors = len({p['number'] for p in geometry[ref]['pads']}) > 2
    degree = sum(ref in _refs(rule) for _, rule in rules)
    courtyard = geometry[ref]['courtyard']
    area = (courtyard['max_x'] - courtyard['min_x']) * (courtyard['max_y'] - courtyard['min_y'])
    return (0 if ref in mechanical else 1 if edge else 2 if attached else 3 if anchors else 4,
            -attached, -degree, -area, ref)


def _score(ref, position, positions, geometry, rules, width, height):
    tentative = {**positions, ref: position}
    score = 0.0
    attached = False
    for _, rule in rules:
        if ref not in _refs(rule):
            continue
        if rule['kind'] == 'PLACE_NEAR' and _refs(rule) <= tentative.keys():
            score += min(distance(a, b) for a in _points(rule['subject'], geometry, tentative)
                         for b in _points(rule['target'], geometry, tentative))
            attached = True
        elif rule['kind'] == 'GROUP':
            score += sum(distance(position[:2], positions[r][:2]) for r in rule['subjects'] if r in positions)
            attached = attached or bool(set(rule['subjects']).intersection(positions))
    if not attached:
        score = distance(position[:2], (width / 2, height / 2))
    return (round(score, 9), position[2], position[1], position[0])


def validate_positions(geometry, rules, positions, width, height):
    """Independently verify all placement constraints; raises instead of returning partial success."""
    if set(positions) != set(geometry):
        raise PlacementError('Incomplete placement references')
    boxes = {}
    for ref, position in positions.items():
        if len(position) != 3 or position[2] not in (0, 90, 180, 270):
            raise PlacementError('Invalid top-side placement orientation')
        for value in position:
            _finite(value, 'placement coordinate')
        box = _box(geometry[ref], position)
        if box[0] < -EPSILON or box[1] < -EPSILON or box[2] > width + EPSILON or box[3] > height + EPSILON:
            raise PlacementError('Courtyard outside board: ' + ref)
        if any(overlap(box, previous) for previous in boxes.values()):
            raise PlacementError('Courtyard collision: ' + ref)
        boxes[ref] = box
    failed = [index for index, rule in _prepare_rules(rules, geometry)
              if not _rule_ok(rule, geometry, positions, width, height)]
    if failed:
        raise PlacementError('Placement constraints unsatisfied', constraints=failed)


def place_geometry(geometry, rules, width, height, *, mechanical=(), grid_mm=0.5, max_states=200000):
    """Solve a finite heuristic domain and independently validate every returned position."""
    from .placement_search import solve_geometry
    return solve_geometry(geometry, rules, width, height, mechanical=mechanical,
                          grid_mm=grid_mm, max_states=max_states)


def place_components(intent, catalog, *, grid_mm=0.5, max_states=200000):
    """Return ref -> (x_mm, y_mm, degrees), without modifying intent, catalog or board."""
    if intent.get('status') != 'EXPANDED':
        raise PlacementError('Placement requires expanded intent')
    if intent['manufacturing']['assembly_side'] != 'TOP':
        raise PlacementError('Placement supports top-side assembly only')
    envelope = intent['mechanical']['outline_envelope']
    if envelope['shape'] != 'RECTANGLE':
        raise PlacementError('Placement requires rectangular outline')
    components = intent['components']
    if len({item['ref'] for item in components}) != len(components):
        raise PlacementError('Duplicate component reference')
    geometry = {item['ref']: derive_footprint(catalog.get(item['package'], 'package')) for item in components}
    return place_geometry(geometry, intent['layout'], limit(envelope['max_width'], 'max'),
                          limit(envelope['max_length'], 'max'),
                          mechanical=[item['ref'] for item in intent['mechanical']['mounting']],
                          grid_mm=grid_mm, max_states=max_states)


def apply_positions(tree, positions):
    """Apply rigid transforms only; pad stored rotation is absolute in KiCad boards."""
    from copy import deepcopy
    tree = deepcopy(tree)
    references = set()
    for footprint in children(tree, 'footprint'):
        ref = next(item[2] for item in children(footprint, 'property') if item[1] == 'Reference')
        if ref in references or ref not in positions:
            raise ValueError('Placement references must match board exactly')
        references.add(ref)
        position = positions[ref]
        if len(position) != 3 or not all(math.isfinite(value) for value in position) or position[2] % 90:
            raise ValueError('Placement requires finite coordinates and orthogonal rotations')
        old = field(footprint, 'at', ['0', '0', '0'])
        old_angle = float(old[2]) if len(old) > 2 else 0
        footprint[:] = [node for node in footprint if not isinstance(node, list) or node[0] != 'at']
        footprint.insert(2, ['at', *map(str, position)])
        for pad in children(footprint, 'pad'):
            at = children(pad, 'at')[0]
            local_angle = float(at[3]) - old_angle if len(at) > 3 else -old_angle
            at[1:] = [*at[1:3], str((local_angle + position[2]) % 360)]
    if references != set(positions):
        raise ValueError('Placement has unknown board references')
    return tree
