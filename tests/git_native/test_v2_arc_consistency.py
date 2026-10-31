"""Arc consistency preserves exhaustive finite solutions and charges propagation work."""
from itertools import product
import math
import random
import unittest

from pcbknowledge.v2.placement import PlacementError
from pcbknowledge.v2.placement_domains import ClusterSearch
from pcbknowledge.v2.placement_search import GridSearch


def owner_domains(points, rules):
    geometry = {ref: {'courtyard': {'min_x': -.2, 'min_y': -.2, 'max_x': .2, 'max_y': .2},
                      'pads': [{'number': '1', 'x': .1, 'y': -.1}]} for ref in points}
    owner = GridSearch(geometry, rules, 30, 30, (), 1, 200000, 500000, 64)
    domains = {ref: [((), point, (point[0] - .2, point[1] - .2, point[0] + .2, point[1] + .2))
                     for point in values] for ref, values in points.items()}
    return owner, domains


def independent_valid(positions):
    for a, b in product(positions, repeat=2):
        if a >= b:
            continue
        left, right = positions[a], positions[b]
        if (left[0] - .2 < right[0] + .2 and right[0] - .2 < left[0] + .2
                and left[1] - .2 < right[1] + .2 and right[1] - .2 < left[1] + .2):
            return False
        if math.hypot(left[0] - right[0], left[1] - right[1]) > 10 + 1e-9:
            return False
    pins = []
    for ref in ('A', 'B'):
        x, y, angle = positions[ref]
        c, s = round(math.cos(math.radians(angle))), round(math.sin(math.radians(angle)))
        pins.append((x + .1 * c - .1 * s, y - .1 * s - .1 * c))
    return math.dist(*pins) <= 2.5 + 1e-9


class ArcConsistencyTests(unittest.TestCase):
    def test_random_finite_solution_sets_equal_independent_exhaustive_oracle(self):
        rules = [{'kind': 'GROUP', 'subjects': list('ABC')},
                 {'kind': 'PLACE_NEAR', 'subject': 'A.pin:1', 'target': 'B.pin:1',
                  'max_distance': {'value': 2.5, 'unit': 'mm'}}]
        for seed in range(6):
            rng = random.Random(seed)
            points = {ref: [(rng.randrange(10, 70) / 10, rng.randrange(10, 70) / 10,
                             rng.choice((0, 90, 180, 270))) for _ in range(5)] for ref in 'ABC'}
            expected = {tuple(sorted(dict(zip('ABC', values)).items())) for values in product(*points.values())
                        if independent_valid(dict(zip('ABC', values)))}
            owner, domains = owner_domains(points, rules)
            actual = list(ClusterSearch(owner, domains).solutions())
            self.assertEqual({tuple(sorted(row.items())) for row in actual}, expected)
            owner2, domains2 = owner_domains(points, list(reversed(rules)))
            self.assertEqual(actual, list(ClusterSearch(owner2, dict(reversed(list(domains2.items())))).solutions()))

    def test_mutually_unsupported_nonempty_domains_fail_before_branching(self):
        owner, domains = owner_domains({'A': [(1, 1, 0)], 'B': [(1.1, 1, 0)], 'C': [(10, 10, 0)]}, [])
        search = ClusterSearch(owner, domains)
        self.assertEqual(list(search.solutions()), [])
        self.assertEqual(owner.states, 1)
        self.assertTrue(all(domain.values for domain in search.domains.values()))

    def test_removed_support_is_not_reused_and_scan_wraps_deterministically(self):
        points = {'A': [(1, 1, 0)], 'B': [(2, 1, 0), (20, 1, 0)], 'C': [(10, 10, 0)]}
        rules = [{'kind': 'GROUP', 'subjects': ['A', 'B']}]
        owner, domains = owner_domains(points, rules)
        search = ClusterSearch(owner, domains)
        self.assertTrue(search.supported('A', 0, 'B', 3))
        self.assertFalse(search.supported('A', 0, 'B', 2))
        search.support_witnesses.clear()
        search.last_support['A', 'B'] = 2
        self.assertTrue(search.supported('A', 0, 'B', 1))

    def test_tiny_work_budget_fails_before_ranking_large_domains(self):
        points = {ref: [(index / 10 + 1, y, 0) for index in range(1000)]
                  for ref, y in zip('ABC', (1, 2, 3))}
        owner, domains = owner_domains(points, [])
        owner.compatibility_limit = 7
        with self.assertRaisesRegex(PlacementError, 'compatibility-work budget exhausted'):
            next(ClusterSearch(owner, domains).solutions())
        self.assertEqual(owner.compatibility_work, 7)
        self.assertEqual(owner.states, 1)

    def test_large_supported_group_yields_without_quadratic_pair_materialization(self):
        points = {ref: [(index + 1, y, 0) for index in range(1000)]
                  for ref, y in zip('ABC', (1, 2, 3))}
        owner, domains = owner_domains(points, [{'kind': 'GROUP', 'subjects': list('ABC')}])
        search = ClusterSearch(owner, domains)
        self.assertEqual(set(next(search.solutions())), set('ABC'))
        self.assertLess(owner.compatibility_work, 100000)
        self.assertLessEqual(len(search.cache), 33)

    def test_group_pair_predicate_preserves_fail_closed_nonfinite_behavior(self):
        points = {'A': [(1, 1, 0)], 'B': [(2, 1, 0)], 'C': [(3, 1, 0)]}
        owner, domains = owner_domains(points, [{'kind': 'GROUP', 'subjects': ['A', 'B']}])
        self.assertFalse(ClusterSearch(owner, domains).pair_ok('A', (float('nan'), 1, 0), 'B', (2, 1, 0)))
