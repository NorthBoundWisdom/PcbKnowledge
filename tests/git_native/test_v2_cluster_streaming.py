"""Pairwise GROUP propagation and batched lookahead preserve complete finite domains."""
from itertools import product
import unittest

from pcbknowledge.v2.placement import _box, _rule_ok
from pcbknowledge.v2.placement_domains import ClusterSearch
from pcbknowledge.v2.placement_search import GridSearch
from pcbknowledge.v2.layout_geometry import overlap


def part():
    return {'courtyard': {'min_x': -.2, 'min_y': -.2, 'max_x': .2, 'max_y': .2}, 'pads': []}


def setup(count):
    geometry = {ref: part() for ref in ('A', 'B', 'C')}
    rules = [{'kind': 'GROUP', 'subjects': ['A', 'B', 'C']}]
    owner = GridSearch(geometry, rules, 100, 100, (), 1, 20000, 500000, 64)
    domains = {ref: [((), (x + 1, y, 0), _box(geometry[ref], (x + 1, y, 0)))
                     for x in range(count)] for ref, y in [('A', 1), ('B', 2), ('C', 3)]}
    return owner, domains, rules


class ClusterStreamingTests(unittest.TestCase):
    def test_group_pair_expansion_matches_exhaustive_all_assignments(self):
        owner, domains, rules = setup(4)
        expected = set()
        for a, b, c in product(domains['A'], domains['B'], domains['C']):
            placed = {'A': a[1], 'B': b[1], 'C': c[1]}
            boxes = [a[2], b[2], c[2]]
            if any(overlap(x, y) for n, x in enumerate(boxes) for y in boxes[n + 1:]):
                continue
            if all(_rule_ok(rule, owner.geometry, placed, 100, 100) for rule in rules):
                expected.add(tuple(sorted(placed.items())))
        result = list(ClusterSearch(owner, domains).solutions())
        self.assertEqual({tuple(sorted(value.items())) for value in result}, expected)
        owner2, domains2, _ = setup(4)
        self.assertEqual(result, list(ClusterSearch(owner2, dict(reversed(list(domains2.items())))).solutions()))

    def test_batch_bound_yields_before_all_nonterminal_candidates_ranked(self):
        owner, domains, _ = setup(1000)
        search = ClusterSearch(owner, domains)
        self.assertEqual(set(next(search.solutions())), {'A', 'B', 'C'})
        self.assertLess(owner.compatibility_work, 40000)
        self.assertLessEqual(len(search.cache), 33)

    def test_batch_iteration_keeps_candidates_beyond_first_batch(self):
        owner, domains, _ = setup(20)
        owner.rules = []
        search = ClusterSearch(owner, domains)
        masks = {ref: domain.full for ref, domain in search.domains.items()}
        ranked = list(search.ranked_candidates('A', masks))
        self.assertEqual({index for _, index, _ in ranked}, set(range(20)))

    def test_near_clusters_are_separate_and_selection_is_order_independent(self):
        geometry = {ref: part() for ref in ('U', 'A', 'B', 'V', 'C', 'D')}
        rules = [{'kind': 'GROUP', 'subjects': group} for group in (['U', 'A', 'B'], ['V', 'C', 'D'])]
        rules += [{'kind': 'PLACE_NEAR', 'subject': ref, 'target': anchor,
                   'max_distance': {'value': 2, 'unit': 'mm'}}
                  for ref, anchor in [('A', 'U'), ('B', 'U'), ('C', 'V'), ('D', 'V')]]
        selections = []
        for source in (rules, list(reversed(rules))):
            owner = GridSearch(geometry, source, 100, 100, (), 1, 20000, 500000, 64)
            owner.positions = {'U': (5, 5, 0), 'V': (25, 25, 0)}
            selections.append(owner.connected_ready({'A', 'B', 'C', 'D'}))
        self.assertEqual(selections, [{'A', 'B'}, {'A', 'B'}])

    def test_group_only_fallback_does_not_enable_large_group_batching(self):
        owner, _, _ = setup(3)
        owner.positions = {'A': (5, 5, 0)}
        owner.geometry['D'] = part()
        owner.rules = [(0, {'kind': 'GROUP', 'subjects': list('ABCD')}, set('ABCD'))]
        owner.local_rules['D'] = owner.rules
        for ref in 'ABC':
            owner.local_rules[ref] = owner.rules
        self.assertIsNone(owner.cluster())

    def test_shared_placed_anchor_keeps_decoupler_domains_together(self):
        geometry = {ref: part() for ref in ('U', 'A', 'B', 'C')}
        rules = [{'kind': 'PLACE_NEAR', 'subject': ref, 'target': 'U',
                  'max_distance': {'value': 2, 'unit': 'mm'}} for ref in 'ABC']
        owner = GridSearch(geometry, rules, 100, 100, (), 1, 20000, 500000, 64)
        owner.positions = {'U': (5, 5, 0)}
        self.assertEqual(owner.connected_ready(set('ABC')), set('ABC'))
