"""Continuous necessary bounds detect crowded anchors without a grid search."""
import unittest

from pcbknowledge.v2.placement import PlacementError
from pcbknowledge.v2.placement_joint_feasibility import shared_anchor_pair_possible, check_shared_anchor_pairs


def geometry():
    return {'U': {'courtyard': {'min_x': -3.55, 'min_y': -2.7, 'max_x': 3.55, 'max_y': 2.7},
                  'pads': [{'number': '1', 'x': 2.465, 'y': .635}]},
            **{ref: {'courtyard': {'min_x': -1.325, 'min_y': -.775, 'max_x': 1.325, 'max_y': .775},
                     'pads': [{'number': '1', 'x': -.625, 'y': 0}]} for ref in ('A', 'B')}}


def rule(ref, radius=2):
    return {'kind': 'PLACE_NEAR', 'subject': ref, 'target': 'U.pin:1',
            'max_distance': {'value': radius, 'unit': 'mm'}}


class JointFeasibilityTests(unittest.TestCase):
    def test_search_rejects_joint_contradiction_before_grid_enumeration(self):
        from pcbknowledge.v2.placement_search import GridSearch
        with self.assertRaisesRegex(PlacementError, "continuous courtyard domains"):
            GridSearch(geometry(), [rule("A"), rule("B")], 100, 100, (), .1, 20000, 500000, 64)

    def test_two_individually_possible_parts_cannot_share_tight_anchor(self):
        self.assertFalse(shared_anchor_pair_possible(geometry(), rule('A'), rule('B')))
        with self.assertRaises(PlacementError) as caught:
            check_shared_anchor_pairs(geometry(), [(3, rule('A')), (8, rule('B'))])
        self.assertEqual(caught.exception.constraints, (3, 8))

    def test_larger_domain_does_not_get_false_infeasibility(self):
        self.assertTrue(shared_anchor_pair_possible(geometry(), rule('A', 5), rule('B', 5)))

    def test_same_component_repeated_rules_do_not_require_two_bodies(self):
        check_shared_anchor_pairs(geometry(), [(3, rule('A')), (8, rule('A'))])

    def test_repeated_anchor_pin_aliases_keep_alternative_regions(self):
        shapes = geometry()
        shapes['U']['pads'].append({'number': '1', 'x': -2.465, 'y': -.635})
        self.assertTrue(shared_anchor_pair_possible(shapes, rule('A'), rule('B')))

    def test_four_terminal_anchored_parts_exceed_common_slice_capacity(self):
        from copy import deepcopy
        from pcbknowledge.v2.placement_joint_feasibility import shared_anchor_packing_possible
        shapes = geometry()
        for ref in ('C', 'D'):
            shapes[ref] = deepcopy(shapes['A'])
        rules = [rule(ref + '.pin:1') for ref in ('A', 'B', 'C', 'D')]
        self.assertTrue(shared_anchor_pair_possible(shapes, rules[0], rules[1]))
        self.assertTrue(shared_anchor_packing_possible(shapes, rules[:2]))
        self.assertFalse(shared_anchor_packing_possible(shapes, rules))
