"""Reject contradictory saved scalar summaries without rerunning geometry."""
from .layout import EDGE_EQUALITY_TOLERANCE_MM, GROUP_MAX_DISTANCE_MM


def _state(check, passed, *, rounded_boundary=False):
    if check['result'] == 'NOT_CHECKABLE' or rounded_boundary:
        return
    if check['result'] != ('PASS' if passed else 'FAIL'):
        raise ValueError('Report result contradicts ' + check['kind'] + ' measurements')


def scalar_consistency(check, rule=None):
    kind = check['kind']
    if check['result'] == 'NOT_CHECKABLE':
        return
    if kind in ('KEEPOUT', 'CONDUCTOR_KEEPOUT'):
        _state(check, not check['collisions'])
    elif kind == 'ASSEMBLY_SIDE':
        _state(check, not check['misplaced'])
    elif kind == 'COPPER_LAYER_COUNT':
        _state(check, len(check['layers']) == check['expected_count'])
    elif kind == 'BOARD_THICKNESS':
        _state(check, abs(check['thickness_mm'] - check['expected_mm']) <= .000002)
    elif kind == 'BOARD_ENVELOPE':
        passed = (0 < check['width_mm'] <= check['max_width_mm'] + .000002
                  and 0 < check['length_mm'] <= check['max_length_mm'] + .000002)
        _state(check, passed)
    elif kind == 'COPPER_AREA':
        area, limit = check['area_mm2'], check['min_area_mm2']
        _state(check, area >= limit, rounded_boundary=area == limit)
    elif kind == 'GROUP':
        if check['limit_mm'] != GROUP_MAX_DISTANCE_MM:
            raise ValueError('Report group limit differs from the checker contract')
        _state(check, check['distance_mm'] <= check['limit_mm'])
    if rule is not None:
        _rule_consistency(check, rule)


def _rule_consistency(check, rule):
    kind = check['kind']
    if kind == 'PLACE_NEAR':
        datum = rule.get('datum', 'ORIGIN_PAD_CENTER')
        if check.get('datum', 'ORIGIN_PAD_CENTER') != datum:
            raise ValueError('Report distance datum differs from the copied input rule')
    if kind == 'GUARD_RING':
        _guard_limits(check, rule)
    fields = {'PLACE_NEAR': ('distance_mm', 'max_distance', 'mm'),
              'EDGE_PLACEMENT': ('distance_mm', 'max_distance', 'mm'),
              'EDGE_DISTANCE': ('distance_mm', 'distance', 'mm'),
              'NET_WIDTH_MIN': ('min_width_mm', 'min_width', 'mm'),
              'MINIMIZE_LOOP': ('estimated_area_mm2', 'max_area', 'mm2'),
              'COPPER_AREA': ('area_mm2', 'min_area', 'mm2')}
    if kind not in fields:
        return
    measurement, field, unit = fields[kind]
    quantity = rule.get(field, {})
    if quantity.get('unit') != unit or 'value' not in quantity:
        raise ValueError('Measured report rule requires its resolved scalar limit')
    limit, value = quantity['value'], check[measurement]
    if kind == 'PLACE_NEAR' and 'limit_mm' in check and check['limit_mm'] != limit:
        raise ValueError('Reported copper-edge limit differs from the input rule')
    if kind == 'COPPER_AREA' and check['min_area_mm2'] != limit:
        raise ValueError('Reported copper-area limit differs from the input rule')
    if kind == 'EDGE_DISTANCE':
        passed = abs(value - limit) <= EDGE_EQUALITY_TOLERANCE_MM + 1e-9
    else:
        passed = value >= limit if kind in ('NET_WIDTH_MIN', 'COPPER_AREA') else value <= limit
    # Edge findings additionally depend on the unreported orthogonal coordinate.
    if kind.startswith('EDGE_'):
        if check['result'] == 'PASS' and (value < 0 or not passed):
            raise ValueError('Passing edge report contradicts measured distance')
        return
    exact_geometry = kind == 'COPPER_AREA' or rule.get('datum') == 'COPPER_EDGE'
    _state(check, passed, rounded_boundary=exact_geometry and value == limit)


def _guard_limits(check, rule):
    for surface in check.get('surfaces', [check]):
        if 'required_width_mm' not in surface:
            continue
        for observed, field in (('required_width_mm', 'min_width'), ('required_clearance_mm', 'min_clearance')):
            quantity = rule.get(field, {})
            if quantity.get('unit') != 'mm' or surface[observed] != quantity.get('value'):
                raise ValueError('Reported guard limit differs from copied input rule')
        if surface['result'] == 'PASS' and (surface['closed_segments'] < 3 or surface['max_gap_mm'] != 0
                                         or surface['min_clearance_mm'] < 0):
            raise ValueError('Passing guard report contradicts closed-ring measurements')
