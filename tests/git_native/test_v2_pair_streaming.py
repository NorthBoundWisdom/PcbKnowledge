"""Final-pair enumeration is deterministic, exact, and yields before full ranking."""
import unittest

from pcbknowledge.v2.placement import PlacementError, _box, _rule_ok
from pcbknowledge.v2.placement_domains import ClusterSearch
from pcbknowledge.v2.placement_search import GridSearch
from pcbknowledge.v2.layout_geometry import overlap


def part():
    return {'courtyard': {'min_x': -.2, 'min_y': -.2, 'max_x': .2, 'max_y': .2}, 'pads': []}


def make_search(count, reverse=False):
    geometry = {'A': part(), 'B': part()}
    rules = [{'kind': 'GROUP', 'subjects': ['A', 'B']}]
    owner = GridSearch(geometry, rules, 100, 100, (), 1, 20000, 500000, 64)
    domains = {ref: [((), (index + 1, y, 0), _box(geometry[ref], (index + 1, y, 0)))
                     for index in range(count)] for ref, y in [('A', 1), ('B', 2)]}
    if reverse:
        domains = dict(reversed(list(domains.items())))
    return owner, ClusterSearch(owner, domains), domains, rules


class PairStreamingTests(unittest.TestCase):
    def test_all_pairs_equal_brute_force_and_order_is_deterministic(self):
        owner, search, domains, rules = make_search(12)
        expected = []
        for _, a, abox in domains['A']:
            for _, b, bbox in domains['B']:
                placed = {'A': a, 'B': b}
                if not overlap(abox, bbox) and all(_rule_ok(rule, owner.geometry, placed, 100, 100)
                                                   for rule in rules):
                    expected.append(placed)
        actual = list(search.solutions())
        self.assertEqual(actual, expected)
        self.assertEqual(actual, list(make_search(12, reverse=True)[1].solutions()))

    def test_first_pair_yielded_before_quadratic_lookahead(self):
        owner, search, _, _ = make_search(1000)
        first = next(search.solutions())
        self.assertEqual(first, {'A': (1, 1, 0), 'B': (1, 2, 0)})
        self.assertLess(owner.compatibility_work, 1100)
        self.assertEqual(len(search.cache), 1)
        self.assertEqual(owner.states, 3)

    def test_terminal_streaming_still_obeys_legal_branch_budget(self):
        owner, search, _, _ = make_search(1000)
        owner.budget = 2
        with self.assertRaisesRegex(PlacementError, 'legal-branch budget exhausted'):
            next(search.solutions())
        self.assertEqual(owner.states, 2)
