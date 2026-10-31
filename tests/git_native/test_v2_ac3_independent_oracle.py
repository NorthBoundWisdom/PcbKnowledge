"""Independent finite oracle: original synthetic geometry, no production predicates."""
import copy
import itertools
import math
import random
import unittest

from pcbknowledge.v2.placement_domains import ClusterSearch
from pcbknowledge.v2.placement_search import GridSearch


def world(position, x, y):
    for _ in range(position[2] // 90):
        x, y = y, -x
    return position[0] + x, position[1] + y


def valid(positions):
    for left, right in itertools.combinations('ABC', 2):
        margin = .125 if 'A' in (left, right) else 0
        a, b = positions[left], positions[right]
        if abs(a[0] - b[0]) < .5 + margin and abs(a[1] - b[1]) < .5 + margin:
            return False
        if math.dist(a[:2], b[:2]) > 10 + 1e-9:
            return False
        ca, cb = world(a, .48, 0), world(b, .48, 0)
        if math.dist(ca, cb) < .26 - 1e-9:
            return False
        for circle, other in ((ca, b), (cb, a)):
            pad = world(other, .1, -.1)
            distance_squared = sum(max(abs(circle[i] - pad[i]) - .1, 0) ** 2 for i in (0, 1))
            if distance_squared < .13 ** 2 - 1e-12:
                return False
    if math.dist(world(positions['A'], .1, -.1), world(positions['B'], .1, -.1)) > 2.5 + 1e-9:
        return False
    a, b = positions['A'][:2], positions['B'][:2]
    area = abs((b[0] - a[0]) * (8 - a[1]) - (b[1] - a[1]) * (8 - a[0])) / 2
    return area <= 3 + 1e-9


def fixture(seed):
    rng = random.Random(seed)
    geometry = {ref: {
        'courtyard': {'min_x': -.25, 'min_y': -.25, 'max_x': .25, 'max_y': .25},
        'pads': [{'number': '1', 'x': .1, 'y': -.1, 'width': .2, 'height': .2, 'rotation': 0}],
        'pin1_marker': {'x': .48, 'y': 0, 'radius': .1, 'stroke': .06}} for ref in 'ABCZ'}
    rules = [
        {'kind': 'GROUP', 'subjects': list('ABC')},
        {'kind': 'PLACE_NEAR', 'subject': 'A.pin:1', 'target': 'B.pin:1',
         'max_distance': {'value': 2.5, 'unit': 'mm'}},
        {'kind': 'KEEPOUT', 'subject': 'A', 'margin': {'value': .125, 'unit': 'mm'}},
        {'kind': 'MINIMIZE_LOOP', 'path': ['A', 'B', 'Z'], 'max_area': {'value': 3, 'unit': 'mm2'}}]
    owner = GridSearch(geometry, rules, 30, 30, (), 1, 200000, 500000, 64)
    owner.positions = {'Z': (8, 8, 0)}
    # Binary-exact box boundaries avoid making a decimal-rounding policy part of this oracle.
    points = {ref: [(rng.randrange(8, 48) / 8, rng.randrange(8, 48) / 8,
                     rng.choice((0, 90, 180, 270))) for _ in range(5)] for ref in 'ABC'}
    domains = {ref: [((), point, (point[0] - .25, point[1] - .25,
                                  point[0] + .25, point[1] + .25)) for point in values]
               for ref, values in points.items()}
    return owner, points, domains


class IndependentArcOracleTests(unittest.TestCase):
    def test_markers_keepout_pin_rotations_and_fixed_anchor_loop(self):
        total = 0
        for seed in range(250):
            with self.subTest(seed=seed):
                owner, points, domains = fixture(seed)
                expected = set()
                for values in itertools.product(*points.values()):
                    positions = dict(zip('ABC', values))
                    if valid(positions):
                        expected.add(tuple(sorted(positions.items())))
                original = copy.deepcopy(domains)
                actual = {tuple(sorted(row.items())) for row in ClusterSearch(owner, domains).solutions()}
                self.assertEqual(actual, expected)
                self.assertEqual(domains, original)
                self.assertEqual(owner.positions, {'Z': (8, 8, 0)})
                total += len(actual)
        self.assertEqual(total, 5659)
