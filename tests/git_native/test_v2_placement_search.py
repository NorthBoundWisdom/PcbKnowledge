"""Synthetic finite-domain propagation and actual-work budget regressions."""
import unittest

from pcbknowledge.v2.placement import PlacementError, validate_positions
from pcbknowledge.v2.placement_search import GridSearch, solve_geometry
from pcbknowledge.v2.placement_domains import BoxDomain, indices
from pcbknowledge.v2.layout_geometry import overlap


def part(size=.2):
    return {'courtyard': {'min_x': -size / 2, 'min_y': -size / 2,
                          'max_x': size / 2, 'max_y': size / 2}, 'pads': []}


def near(ref, target, distance):
    return {'kind': 'PLACE_NEAR', 'subject': ref, 'target': target,
            'max_distance': {'value': distance, 'unit': 'mm'}}


def fixed(ref, x, y):
    return [{'kind': 'EDGE_DISTANCE', 'subject': ref, 'edge': side,
             'distance': {'value': value, 'unit': 'mm'}} for side, value in [('LEFT', x), ('TOP', y)]]


class DomainTests(unittest.TestCase):
    def test_bitset_matches_pairwise_courtyard_check(self):
        boxes = [(x, y, x + .5, y + .7) for x in (0, .5, 1, 2) for y in (0, .7, 2)]
        domain = BoxDomain([((), (0, 0, 0), box) for box in boxes])
        for box in boxes:
            for margin in (0, .1, .5):
                inflated = (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)
                expected = {index for index, other in enumerate(boxes) if not overlap(inflated, other)}
                self.assertEqual(set(indices(domain.separate(box, margin))), expected)

    def test_fine_grid_finds_cluster_without_changing_constraint(self):
        geometry = {ref: part() for ref in ('A', 'B', 'C')}
        rules = fixed('A', .3, .3) + [near('B', 'A', .21), near('C', 'A', .21)]
        with self.assertRaises(PlacementError):
            solve_geometry(geometry, rules, .7, .7, grid_mm=.5)
        result = solve_geometry(geometry, rules, .7, .7, grid_mm=.1)
        validate_positions(geometry, rules, result, .7, .7)
        self.assertEqual(rules[2]['max_distance']['value'], .21)
        reordered = solve_geometry(dict(reversed(list(geometry.items()))), rules[::-1], .7, .7, grid_mm=.1)
        self.assertEqual(result, reordered)

    def test_impossible_isolated_pair_is_rejected_before_search(self):
        geometry = {ref: part(1) for ref in ('A', 'B', 'C')}
        rules = fixed('A', 2, 2) + [near('B', 'A', .2), near('C', 'A', .2)]
        with self.assertRaisesRegex(PlacementError, 'Near constraint incompatible') as caught:
            solve_geometry(geometry, rules, 4, 4, grid_mm=.1)
        self.assertEqual(caught.exception.constraints, (2,))

    def test_joint_packing_exhaustion_remains_heuristic(self):
        geometry = {ref: part(1) for ref in ('A', 'B', 'C')}
        with self.assertRaisesRegex(PlacementError, 'Finite heuristic placement search exhausted'):
            solve_geometry(geometry, [], 2, 1, grid_mm=.5)

    def test_group_bound_preserved_in_cluster(self):
        geometry = {ref: part(1) for ref in ('A', 'B', 'C')}
        rules = fixed('A', 3, 3) + [near('B', 'A', 2), near('C', 'A', 2),
                                   {'kind': 'GROUP', 'subjects': ['A', 'B', 'C']}]
        result = solve_geometry(geometry, rules, 7, 7, grid_mm=.5)
        validate_positions(geometry, rules, result, 7, 7)

    def test_large_unmaterialized_domain_uses_lazy_search(self):
        result = solve_geometry({'A': part()}, [], 80, 100, grid_mm=.1, max_domain_candidates=500000)
        self.assertEqual(result['A'][:2], (40, 50))

    def test_actual_attached_cartesian_scan_remains_bounded(self):
        geometry = {'A': part(), 'B': part()}
        rules = fixed('A', 5, 5) + [near('B', 'A', 20)]
        with self.assertRaisesRegex(PlacementError, 'Bounded candidate scan'):
            solve_geometry(geometry, rules, 10, 10, grid_mm=.1, max_domain_candidates=101)

    def test_lazy_exhaustion_remains_bounded(self):
        search = GridSearch({'A': part(), 'B': part()}, [], 10, 10, (), .1, 1000, 101, 64)
        search.positions['B'] = (5, 5, 0)
        search.boxes['B'] = (0, 0, 10, 10)
        with self.assertRaisesRegex(PlacementError, 'Lazy candidate traversal'):
            search.anchor_candidates('A')

    def test_legal_branch_budget_remains_separate(self):
        with self.assertRaisesRegex(PlacementError, 'legal-branch budget'):
            solve_geometry({'A': part()}, [], 2, 2, max_states=1)

    def test_lazy_anchor_beam_matches_exhaustive_order(self):
        search = GridSearch({'A': part(), 'B': part()}, [], 3, 4, (), .1, 100, 10000, 16)
        search.positions['B'] = (1.5, 2, 0)
        search.boxes['B'] = (1.4, 1.9, 1.6, 2.1)
        expected = []
        for angle in (0, 90, 180, 270):
            xs, ys = search.bounds('A', angle)
            legal = []
            for x in xs:
                for y in ys:
                    position = x, y, angle
                    box = search.legal('A', position)
                    if box is not None:
                        score = ((x - 1.5) ** 2 + (y - 2) ** 2, angle, y, x)
                        legal.append((score, position, box))
            expected.extend(sorted(legal)[:4])
        self.assertEqual(search.anchor_candidates('A'), sorted(expected))

    def test_multiple_keepouts_retain_strongest_regardless_order(self):
        geometry = {'A': part(1), 'B': part(1)}
        rules = fixed('A', 2, 2) + [{'kind': 'KEEPOUT', 'subject': 'A',
                                    'margin': {'value': value, 'unit': 'mm'}} for value in (2, .1)]
        result = solve_geometry(geometry, rules, 8, 8)
        self.assertEqual(result, solve_geometry(geometry, rules[::-1], 8, 8))
        validate_positions(geometry, rules, result, 8, 8)

    def test_near_epsilon_matches_independent_validator(self):
        geometry = {'A': part(), 'B': part()}
        rules = [near('B', 'A', 1)]
        search = GridSearch(geometry, rules, 5, 5, (), .1, 1000, 500000, 64)
        search.positions['A'] = (2, 2, 0)
        search.boxes['A'] = (1.9, 1.9, 2.1, 2.1)
        accepted = (3 + .5e-9, 2, 0)
        self.assertIsNotNone(search.legal('B', accepted))
        validate_positions(geometry, rules, {'A': (2, 2, 0), 'B': accepted}, 5, 5)
        self.assertIsNone(search.legal('B', (3 + 2e-9, 2, 0)))

    def test_cluster_ranking_resource_budget_precedes_branch_selection(self):
        from pcbknowledge.v2.placement_domains import ClusterSearch
        geometry = {'A': part(), 'B': part(), 'C': part()}
        rules = [{'kind': 'GROUP', 'subjects': ['A', 'B']}]
        owner = GridSearch(geometry, rules, 100, 100, (), 1, 2, 500000, 64)
        values = [((), (index / 10, 1, 0), (index / 10, 0, index / 10 + .1, .1))
                  for index in range(1000)]
        search = ClusterSearch(owner, {'A': values, 'B': values, 'C': values})
        with self.assertRaisesRegex(PlacementError, 'compatibility-work budget exhausted'):
            next(search.solutions())
        self.assertEqual(owner.compatibility_work, owner.compatibility_limit)
        self.assertEqual(owner.states, 1)

    def test_cluster_no_branch_budget_rejects_before_ranking(self):
        from pcbknowledge.v2.placement_domains import ClusterSearch
        owner = GridSearch({'A': part(), 'B': part()}, [], 10, 10, (), 1, 1, 500000, 64)
        values = [((), (1, 1, 0), (0, 0, 1, 1))]
        with self.assertRaisesRegex(PlacementError, 'legal-branch budget exhausted'):
            next(ClusterSearch(owner, {'A': values, 'B': values}).solutions())
        self.assertEqual(owner.compatibility_work, 0)
