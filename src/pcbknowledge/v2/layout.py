"""Read-only measured layout checks; placement is never proof of completed routing."""
from collections import Counter
from itertools import combinations
import math

from .footprints import derive_footprint
from .layout_identity import authoritative_bounds, pad_geometry_result
from .layout_board import board_requirements
from .layout_return import check_return_path
from .layout_guard import check_guard_ring
from .layout_kelvin import check_kelvin
from .layout_copper_area import check_copper_area
from .layout_geometry import convex_hull, distance, overlap, polygon_area

GROUP_MAX_DISTANCE_MM = 10.0
EDGE_EQUALITY_TOLERANCE_MM = 0.01


def finding(kind, result, reason, **measurements):
    return {'kind': kind, 'result': result, 'reason': reason, **measurements}


def measured(kind, passed, reason, **measurements):
    return finding(kind, 'PASS' if passed else 'FAIL', reason, **measurements)


def quantity(record, field, unit):
    value = record[field]
    if value.get('unit') != unit or 'value' not in value:
        raise ValueError('A resolved scalar ' + unit + ' limit is required')
    number = value['value']
    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0:
        raise ValueError('A finite nonnegative scalar limit is required')
    return number


def identity_check(board, intent, catalog):
    footprints = board['footprints']
    components = {item['ref']: item for item in intent['components']}
    if set(footprints) != set(components):
        return finding('IDENTITY', 'FAIL', 'Board references differ from expanded intent')
    if set(board['nets'].values()) - {''} != {net['name'] for net in intent['nets']}:
        return finding('IDENTITY', 'FAIL', 'Declared board net names differ from expanded intent')
    expected_nets = {(pin['ref'], pin['pin']): net['name'] for net in intent['nets'] for pin in net['pins']}
    for ref, component in components.items():
        footprint = footprints[ref]
        if footprint.get('library') != component['footprint']:
            return finding('IDENTITY', 'FAIL', 'Footprint library identity differs: ' + ref)
        package = catalog.get(component['package'], 'package')
        derived = derive_footprint(package)
        expected = Counter('' if pad['kind'] == 'MECHANICAL' else pad['number'] for pad in derived['pads'])
        actual = Counter({number: len(pads) for number, pads in footprint['pads'].items()})
        if expected != actual:
            return finding('IDENTITY', 'FAIL', 'Physical pad identities or multiplicities differ: ' + ref)
        from .apertures import aperture_identity
        if not aperture_identity(footprint, derived):
            return finding('IDENTITY', 'FAIL', 'Layer aperture geometry differs: ' + ref)
        result, reason = pad_geometry_result(footprint, derived)
        if result != 'PASS':
            return finding('IDENTITY', result, reason + ': ' + ref)
        for number, pads in footprint['pads'].items():
            net = expected_nets.get((ref, number), '')
            if any((pad.get('net') or '') != net for pad in pads):
                return finding('IDENTITY', 'FAIL', 'Physical pad net differs: ' + ref + '.' + number)
    return finding('IDENTITY', 'PASS', 'Exact reference, footprint, physical pad and pad-net identities match')


class LayoutChecks:
    def __init__(self, board, intent, catalog):
        self.board = board
        self.intent = intent
        self.catalog = catalog
        self.footprints = board['footprints']
        self.authority_bounds = {}
        for component in intent['components']:
            footprint = self.footprints[component['ref']]
            derived = derive_footprint(catalog.get(component['package'], 'package'))
            self.authority_bounds[component['ref']] = authoritative_bounds(footprint, derived)

    def points(self, endpoint):
        ref, separator, pin = endpoint.partition('.pin:')
        footprint = self.footprints[ref]
        if not separator:
            return [footprint['at']]
        return [pad['at'] for pad in footprint['pads'][pin]]

    def place_near(self, rule):
        value = min(distance(a, b) for a in self.points(rule['subject']) for b in self.points(rule['target']))
        limit = quantity(rule, 'max_distance', 'mm')
        return measured(rule['kind'], value <= limit, 'Origin/pad-center nearest distance', distance_mm=value)

    def group(self, rule):
        points = [self.footprints[ref]['at'] for ref in rule['subjects']]
        value = max((distance(a, b) for a, b in combinations(points, 2)), default=0)
        return measured('GROUP', value <= GROUP_MAX_DISTANCE_MM, 'Maximum pairwise footprint-origin distance',
                        distance_mm=value, limit_mm=GROUP_MAX_DISTANCE_MM)

    def edge(self, rule):
        outline = self.board['outline']
        if not outline.get('closed') or not outline.get('rectangular'):
            return finding(rule['kind'], 'NOT_CHECKABLE', 'Closed rectangular outline required for directional edges')
        xmin, ymin, xmax, ymax = outline['bounds']
        x, y = self.points(rule['subject'])[0]
        distances = {'LEFT': x - xmin, 'RIGHT': xmax - x, 'TOP': y - ymin, 'BOTTOM': ymax - y}
        value = distances[rule['edge']]
        inside = xmin <= x <= xmax and ymin <= y <= ymax
        if rule['kind'] == 'EDGE_DISTANCE':
            limit = quantity(rule, 'distance', 'mm')
            passed = abs(value - limit) <= EDGE_EQUALITY_TOLERANCE_MM + 1e-9
        else:
            passed = value <= quantity(rule, 'max_distance', 'mm')
        return measured(rule['kind'], inside and passed,
                        'Footprint-origin distance to specified edge', distance_mm=value)

    def keepout(self, rule):
        if self.board.get('unsupported'):
            return finding('KEEPOUT', 'NOT_CHECKABLE', 'Unsupported geometry prevents enclosure proof')
        target = self.footprints[rule['subject']]
        if any(not item.get('courtyard_closed') for item in self.footprints.values()):
            return finding('KEEPOUT', 'NOT_CHECKABLE', 'Every footprint needs a supported courtyard enclosure')
        margin = quantity(rule, 'margin', 'mm')
        box = self.authority_bounds[rule['subject']]
        inflated = [box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin]
        collisions = [ref for ref, item in self.footprints.items()
                      if ref != rule['subject'] and overlap(inflated, self.authority_bounds[ref])]
        return measured('KEEPOUT', not collisions,
                        'Authoritative derived courtyard bounding-box exclusion', collisions=collisions)

    def width(self, rule):
        widths = [item['width'] for key in ('segments', 'arcs') for item in self.board[key]
                  if item['net'] == rule['net']]
        if not widths:
            return finding('NET_WIDTH_MIN', 'NOT_CHECKABLE', 'No routed segments or arcs on requested net')
        value = min(widths)
        return measured('NET_WIDTH_MIN', value >= quantity(rule, 'min_width', 'mm'),
                        'Minimum observed routed track width; not proof of routing completeness', min_width_mm=value)

    def loop(self, rule):
        points = [point for endpoint in rule['path'] for point in self.points(endpoint)]
        area = polygon_area(convex_hull(points))
        result = 'FAIL' if area > quantity(rule, 'max_area', 'mm2') else 'PASS'
        return finding('MINIMIZE_LOOP', result, 'Pad-center convex-hull estimate only; routed return path is unproven',
                       estimated_area_mm2=area)

    def copper(self, rule):
        return check_copper_area(self.board, rule)

    def check(self, rule):
        if rule['kind'] == 'CONDUCTOR_KEEPOUT':
            from .layout_conductor_keepout import check_conductor_keepout
            return check_conductor_keepout(self.board, rule)
        handlers = {'PLACE_NEAR': self.place_near, 'GROUP': self.group, 'EDGE_PLACEMENT': self.edge,
                    'EDGE_DISTANCE': self.edge, 'KEEPOUT': self.keepout, 'NET_WIDTH_MIN': self.width,
                    'MINIMIZE_LOOP': self.loop, 'COPPER_AREA': self.copper}
        kind = rule['kind']
        if kind == 'RETURN_PATH':
            return check_return_path(self.board, rule)
        if kind == 'GUARD_RING':
            return check_guard_ring(self.board, rule)
        if kind == 'KELVIN':
            return check_kelvin(self.board, rule, self.intent, self.catalog)
        if kind not in handlers:
            return finding(kind, 'NOT_CHECKABLE', 'Unsupported layout constraint')
        try:
            return handlers[kind](rule)
        except (KeyError, ValueError, TypeError, IndexError) as error:
            return finding(kind, 'NOT_CHECKABLE', 'Missing or unsupported geometry/input: ' + str(error))


def check_layout(board, intent, catalog):
    if intent.get('status') != 'EXPANDED':
        raise ValueError('Layout checks require an expanded intent')
    checks = [identity_check(board, intent, catalog)]
    if checks[0]['result'] == 'PASS':
        checker = LayoutChecks(board, intent, catalog)
        for index, rule in enumerate(intent['layout']):
            checks.append({'index': index, **checker.check(rule)})
        checks.extend(board_requirements(board, intent))
    else:
        checks.append(finding('CONSTRAINTS', 'NOT_CHECKABLE', 'Identity mismatch prevents layout measurement'))
    if board.get('unsupported'):
        checks.append(finding('GEOMETRY', 'NOT_CHECKABLE', '; '.join(board['unsupported'])))
    results = {check['result'] for check in checks}
    result = 'FAIL' if 'FAIL' in results else 'NOT_CHECKABLE' if 'NOT_CHECKABLE' in results else 'PASS'
    return {'schema': 'pcbknowledge.layout-check.v2', 'result': result, 'checks': checks,
            'routing_certified': False,
            'scope': 'Measured constraints only; not routing completeness, fabrication approval or A3-A6 acceptance'}


def check_board(path, intent, catalog):
    from .boardview import parse_board
    return check_layout(parse_board(path), intent, catalog)
