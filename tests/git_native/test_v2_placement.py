"""Original small synthetic placement cases; no catalog files or external tools."""
import copy
import math
import unittest
from unittest.mock import patch

from pcbknowledge.v2.placement import PlacementError, _points, place_components, place_geometry, validate_positions


def part(width=1, height=1, pads=()):
    return {'courtyard': {'min_x': -width / 2, 'max_x': width / 2,
                          'min_y': -height / 2, 'max_y': height / 2},
            'pads': [{'number': number, 'x': x, 'y': y} for number, x, y in pads]}


def q(value, unit='mm'):
    return {'value': value, 'unit': unit}


def edge(ref, side, value, kind='EDGE_DISTANCE'):
    return {'kind': kind, 'subject': ref, 'edge': side,
            'distance' if kind == 'EDGE_DISTANCE' else 'max_distance': q(value)}


def fixed(ref, x, y):
    return [edge(ref, 'LEFT', x), edge(ref, 'TOP', y)]


class PlacementTests(unittest.TestCase):
    def test_deterministic_shuffled_components_and_constraints(self):
        geometry = {'C': part(), 'U': part(2, 2, [('1', -0.5, 0), ('2', 0, 0), ('3', 0.5, 0)])}
        rules = [{'kind': 'PLACE_NEAR', 'subject': 'C', 'target': 'U.pin:1', 'max_distance': q(2)}]
        before = copy.deepcopy((geometry, rules))
        result = place_geometry(geometry, rules, 6, 6, grid_mm=1)
        self.assertEqual(result, place_geometry(dict(reversed(list(geometry.items()))), rules[::-1], 6, 6, grid_mm=1))
        self.assertEqual(before, (geometry, rules))
        validate_positions(geometry, rules, result, 6, 6)

    def test_off_grid_exact_mechanical_position(self):
        geometry = {'H': part(), 'C': part()}
        rules = fixed('H', 1.23, 2.37)
        result = place_geometry(geometry, rules, 5, 5, mechanical=['H'], grid_mm=1)
        self.assertEqual(result['H'][:2], (1.23, 2.37))

    def test_edges_refer_to_pad_not_footprint_origin(self):
        geometry = {'J': part(3, 1, [('1', -1, 0)])}
        rules = fixed('J.pin:1', 0.5, 2)
        result = place_geometry(geometry, rules, 5, 5, grid_mm=1)
        self.assertEqual(_points('J.pin:1', geometry, result)[0], [0.5, 2.0])
        self.assertNotEqual(result['J'][:2], (0.5, 2.0))

    def test_rotation_required_for_outline_fit(self):
        geometry = {'J': part(4, 1)}
        result = place_geometry(geometry, [], 2, 5, grid_mm=0.5)
        self.assertIn(result['J'][2], (90, 270))
        validate_positions(geometry, [], result, 2, 5)

    def test_global_overlap_and_enclosure_without_rules(self):
        geometry = {'A': part(2, 2), 'B': part(2, 2)}
        with self.assertRaisesRegex(PlacementError, 'collision'):
            validate_positions(geometry, [], {'A': (1, 1, 0), 'B': (1, 1, 0)}, 5, 5)
        with self.assertRaisesRegex(PlacementError, 'outside'):
            validate_positions(geometry, [], {'A': (0, 0, 0), 'B': (3, 3, 0)}, 5, 5)
        result = place_geometry(geometry, [], 4, 4, grid_mm=1)
        validate_positions(geometry, [], result, 4, 4)

    def test_near_constraint_not_relaxed_for_collision(self):
        geometry = {'A': part(2, 2), 'B': part(2, 2)}
        rules = fixed('A', 2, 2) + [{'kind': 'PLACE_NEAR', 'subject': 'B', 'target': 'A',
                                   'max_distance': q(0.1)}]
        with self.assertRaises(PlacementError) as raised:
            place_geometry(geometry, rules, 4, 4, grid_mm=1)
        self.assertIn(2, raised.exception.constraints)

    def test_keepout_applies_to_unconstrained_later_components(self):
        geometry = {'A': part(), 'B': part()}
        rules = fixed('A', 1, 1) + [{'kind': 'KEEPOUT', 'subject': 'A', 'margin': q(1)}]
        result = place_geometry(geometry, rules, 5, 5, grid_mm=1)
        validate_positions(geometry, rules, result, 5, 5)
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, rules, {'A': (1, 1, 0), 'B': (2, 1, 0)}, 5, 5)

    def test_group_means_pairwise_not_centroid(self):
        geometry = {ref: part() for ref in ('A', 'B', 'C')}
        rules = [{'kind': 'GROUP', 'subjects': ['A', 'B', 'C']}]
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, rules, {'A': (1, 1, 0), 'B': (7, 1, 0), 'C': (13, 1, 0)}, 15, 3)

    def test_repeated_pad_alias_nearest_physical_pad(self):
        geometry = {'U': part(4, 1, [('1', -1.5, 0), ('1', 1.5, 0)]), 'C': part(0.5, 0.5)}
        rules = [{'kind': 'PLACE_NEAR', 'subject': 'C', 'target': 'U.pin:1', 'max_distance': q(1)}]
        validate_positions(geometry, rules, {'U': (3, 2, 0), 'C': (5.5, 2, 0)}, 7, 4)
        self.assertEqual(len(_points('U.pin:1', geometry, {'U': (3, 2, 0)})), 2)

    def test_minimize_loop_hull(self):
        geometry = {ref: part() for ref in ('A', 'B', 'C')}
        rules = [{'kind': 'MINIMIZE_LOOP', 'path': ['A', 'B', 'C'], 'max_area': q(1, 'mm2')}]
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, rules, {'A': (1, 1, 0), 'B': (4, 1, 0), 'C': (1, 4, 0)}, 5, 5)

    def test_contradictory_edges_fail_without_movement(self):
        geometry = {'H': part()}
        rules = [edge('H', 'LEFT', 1), edge('H', 'RIGHT', 1)]
        with self.assertRaises(PlacementError):
            place_geometry(geometry, rules, 5, 5, grid_mm=1)

    def test_large_connector_origin_edge_conflict_reports_before_search(self):
        geometry = {'USB': part(18.64, 17.1)}
        rules = [edge('USB', 'LEFT', 1, 'EDGE_PLACEMENT')]
        with self.assertRaisesRegex(PlacementError, 'Empty legal domain for USB') as raised:
            place_geometry(geometry, rules, 50, 50)
        self.assertEqual(raised.exception.constraints, (0,))
        self.assertEqual(raised.exception.states, 0)

    def test_tiny_grid_fails_before_materializing_huge_axis(self):
        with self.assertRaisesRegex(PlacementError, 'budget'):
            place_geometry({'A': part()}, [], 5, 5, grid_mm=1e-30)

    def test_unknown_rules_endpoints_and_nonfinite_fail_closed(self):
        geometry = {'A': part()}
        for rules in ([{'kind': 'MADE_UP'}], [edge('B', 'LEFT', 1)], [edge('A.pin:9', 'LEFT', 1)]):
            with self.assertRaises(PlacementError):
                place_geometry(geometry, rules, 5, 5)
        for grid in (0, -1, True, math.nan, math.inf):
            with self.assertRaises(PlacementError):
                place_geometry(geometry, [], 5, 5, grid_mm=grid)

    def test_search_budget_is_not_infeasibility_claim(self):
        with self.assertRaisesRegex(PlacementError, 'budget'):
            place_geometry({'A': part()}, [], 5, 5, max_states=1)

    def test_copper_rules_deferred_not_reported_as_pass(self):
        rules = [{'kind': 'RETURN_PATH', 'net': 'SIG', 'return_net': 'GND'}]
        result = place_geometry({'A': part()}, rules, 2, 2)
        self.assertEqual(set(result), {'A'})
        self.assertNotIn('PASS', result)

    def test_catalog_adapter_uses_exact_derived_geometry(self):
        intent = {'status': 'EXPANDED', 'manufacturing': {'assembly_side': 'TOP'},
                  'mechanical': {'mounting': [], 'outline_envelope': {'shape': 'RECTANGLE',
                                 'max_width': q(4), 'max_length': q(4)}},
                  'components': [{'ref': 'A', 'package': 'package:synthetic'}], 'layout': []}
        class Catalog:
            def get(self, identifier, kind):
                self.assertion = (identifier, kind)
                return {'synthetic': True}
        catalog = Catalog()
        with patch('pcbknowledge.v2.placement.derive_footprint', return_value=part()) as derive:
            result = place_components(intent, catalog)
        self.assertEqual(catalog.assertion, ('package:synthetic', 'package'))
        derive.assert_called_once_with({'synthetic': True})
        self.assertEqual(set(result), {'A'})


if __name__ == '__main__':
    unittest.main()
