"""Synthetic necessary-bound checks; no catalog or external tools."""
import unittest

from pcbknowledge.v2.placement import PlacementError
from pcbknowledge.v2.placement_feasibility import check_isolated_near_bounds, minimum_separated_distance


def rectangle(x, y, pads=()):
    return {'courtyard': {'min_x': -x, 'min_y': -y, 'max_x': x, 'max_y': y},
            'pads': [{'number': number, 'x': px, 'y': py} for number, px, py in pads]}


class FeasibilityTests(unittest.TestCase):
    def test_origin_bound_considers_all_rotations(self):
        geometry = {'A': rectangle(4, 3), 'B': rectangle(1, .5)}
        self.assertEqual(minimum_separated_distance(geometry, 'A', 'B'), 3.5)
        rule = {'kind': 'PLACE_NEAR', 'subject': 'A', 'target': 'B',
                'max_distance': {'value': 3, 'unit': 'mm'}}
        with self.assertRaises(PlacementError) as caught:
            check_isolated_near_bounds(geometry, [(12, rule)])
        self.assertEqual(caught.exception.constraints, (12,))
        rule['max_distance']['value'] = 3.5
        check_isolated_near_bounds(geometry, [(12, rule)])

    def test_physical_pin_offset_changes_bound_without_changing_rule_limit(self):
        geometry = {'A': rectangle(4, 3, [('1', 4, 0)]), 'B': rectangle(1, .5)}
        self.assertEqual(minimum_separated_distance(geometry, 'A.pin:1', 'B'), .5)

    def test_repeated_pin_alias_uses_nearest_possible_physical_pad(self):
        geometry = {'A': rectangle(4, 3, [('1', 0, 0), ('1', 4, 0)]), 'B': rectangle(1, .5)}
        self.assertEqual(minimum_separated_distance(geometry, 'A.pin:1', 'B'), .5)

    def test_asymmetric_authoritative_datum_is_not_assumed_body_center(self):
        a = rectangle(1, 1)
        a['courtyard'] = {'min_x': 2, 'min_y': -1, 'max_x': 4, 'max_y': 1}
        self.assertEqual(minimum_separated_distance({'A': a, 'B': rectangle(.5, .5)}, 'A', 'B'), 0)

    def test_pin_pair_can_coincide_without_courtyard_overlap(self):
        geometry = {'A': rectangle(1, 1, [('1', 1, 0)]),
                    'B': rectangle(1, 1, [('1', -1, 0)])}
        self.assertEqual(minimum_separated_distance(geometry, 'A.pin:1', 'B.pin:1'), 0)
