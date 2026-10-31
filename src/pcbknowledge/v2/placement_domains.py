"""Bitset propagation of pairwise courtyard and placement constraints."""
from bisect import bisect_left, bisect_right
from collections import deque
import math
from itertools import combinations

from .placement import EPSILON, GROUP_MAX_DISTANCE_MM, PlacementError, _rule_ok

RANKING_BATCH_SIZE = 16


class BoxDomain:
    def __init__(self, values):
        self.values = values
        self.full = (1 << len(values)) - 1
        self.axes = []
        for axis in range(4):
            groups = {}
            for index, (_, _, box) in enumerate(values):
                groups[box[axis]] = groups.get(box[axis], 0) | (1 << index)
            keys, masks, total = [], [], 0
            for coordinate, mask in sorted(groups.items()):
                keys.append(coordinate)
                total |= mask
                masks.append(total)
            self.axes.append((keys, masks))

    def below(self, axis, value, inclusive):
        keys, masks = self.axes[axis]
        index = (bisect_right(keys, value) if inclusive else bisect_left(keys, value)) - 1
        return masks[index] if index >= 0 else 0

    def separate(self, box, margin):
        xmin, ymin, xmax, ymax = box
        return (self.below(2, xmin - margin, True) | self.below(3, ymin - margin, True)
                | (self.full ^ self.below(0, xmax + margin, False))
                | (self.full ^ self.below(1, ymax + margin, False)))


def indices(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


class ClusterSearch:
    def __init__(self, owner, domains):
        self.owner = owner
        self.domains = {ref: BoxDomain(values) for ref, values in domains.items()}
        self.cache, self.pair_rules, self.support_witnesses, self.last_support = {}, {}, {}, {}
        for index, rule, refs in owner.rules:
            unresolved = refs & domains.keys()
            if rule['kind'] == 'GROUP':
                for pair in combinations(sorted(unresolved), 2):
                    self.pair_rules.setdefault(frozenset(pair), []).append(rule)
                continue
            if len(unresolved) > 2:
                raise PlacementError('Cluster requires pairwise unresolved constraints', constraints=(index,))
            if len(unresolved) == 2:
                self.pair_rules.setdefault(frozenset(unresolved), []).append(rule)

    def pair_ok(self, ref, position, other, point):
        placed = {**self.owner.positions, ref: position, other: point}
        if self.owner.graphic_conflict(ref, position, other, point):
            return False
        for rule in self.pair_rules.get(frozenset((ref, other)), []):
            if rule['kind'] == 'GROUP':
                distance = math.hypot(position[0] - point[0], position[1] - point[1])
                if not distance <= GROUP_MAX_DISTANCE_MM + EPSILON:
                    return False
            elif not _rule_ok(rule, self.owner.geometry, placed, self.owner.width, self.owner.height):
                return False
        return True

    def separate(self, ref, index, other):
        box = self.domains[ref].values[index][2]
        margin = max(self.owner.margins.get(ref, 0), self.owner.margins.get(other, 0))
        return self.domains[other].separate(box, margin)

    def compatible(self, ref, index, other):
        self.owner.spend_compatibility_work()
        key = ref, index, other
        if key in self.cache:
            return self.cache[key]
        position = self.domains[ref].values[index][1]
        mask = self.separate(ref, index, other)
        rules = self.pair_rules.get(frozenset((ref, other)), [])
        if rules or self.owner.geometry[ref].get('pin1_marker') or self.owner.geometry[other].get('pin1_marker'):
            for candidate in indices(mask):
                self.owner.spend_compatibility_work()
                if not self.pair_ok(ref, position, other, self.domains[other].values[candidate][1]):
                    mask ^= 1 << candidate
        self.cache[key] = mask
        return mask

    def supported(self, ref, index, other, mask):
        """Find one exact witness lazily; never construct a quadratic pair table for AC-3."""
        self.owner.spend_compatibility_work()
        key = ref, index, other
        if self.support_witnesses.get(key, 0) & mask:
            return True
        if key in self.cache:
            candidates = self.cache[key] & mask
            if candidates:
                self.support_witnesses[key] = candidates & -candidates
            return bool(candidates)
        position = self.domains[ref].values[index][1]
        candidates = self.separate(ref, index, other) & mask
        preferred = self.last_support.get((ref, other), 0)
        ordered = (candidates & -(preferred << 1), candidates & ((preferred << 1) - 1)) if preferred else (candidates,)
        if preferred & candidates:
            self.owner.spend_compatibility_work()
            point = self.domains[other].values[preferred.bit_length() - 1][1]
            if self.pair_ok(ref, position, other, point):
                self.support_witnesses[key] = preferred
                return True
        for section in ordered:
            for candidate in indices(section & ~preferred):
                self.owner.spend_compatibility_work()
                if self.pair_ok(ref, position, other, self.domains[other].values[candidate][1]):
                    witness = 1 << candidate
                    self.support_witnesses[key] = witness
                    self.last_support[ref, other] = witness
                    return True
        return False

    def propagate(self, masks):
        """AC-3 removes only values with no compatible witness in another current domain."""
        masks = dict(masks)
        queue, pending = deque(), set()
        for left in sorted(masks):
            for right in sorted(masks):
                self.owner.spend_compatibility_work()
                if left != right:
                    queue.append((left, right))
                    pending.add((left, right))
        while queue:
            self.owner.spend_compatibility_work()
            left, right = queue.popleft()
            pending.remove((left, right))
            revised = masks[left]
            for index in indices(masks[left]):
                if not self.supported(left, index, right, masks[right]):
                    revised ^= 1 << index
            if revised == masks[left]:
                continue
            masks[left] = revised
            if not revised:
                return None
            for other in sorted(masks):
                self.owner.spend_compatibility_work()
                arc = other, left
                if other not in (left, right) and arc not in pending:
                    queue.append(arc)
                    pending.add(arc)
        return masks

    def terminal_solutions(self, masks, chosen):
        """Yield final one/two-variable assignments without quadratic lookahead ranking."""
        ref = min(masks, key=lambda name: (masks[name].bit_count(), name))
        others = {name: mask for name, mask in masks.items() if name != ref}
        for index in indices(masks[ref]):
            if self.owner.states >= self.owner.budget:
                raise PlacementError('Placement legal-branch budget exhausted', states=self.owner.states)
            self.owner.spend_compatibility_work()
            remaining = {other: mask & self.compatible(ref, index, other) for other, mask in others.items()}
            if any(not mask for mask in remaining.values()):
                continue
            self.owner.states += 1
            position = self.domains[ref].values[index][1]
            yield from self.solutions(remaining, {**chosen, ref: position})

    def ranked_candidates(self, ref, masks):
        """Rank finite batches without deleting any candidate from the search domain."""
        others = {name: mask for name, mask in masks.items() if name != ref}
        ranked, inspected = [], 0
        for index in indices(masks[ref]):
            if self.owner.states >= self.owner.budget:
                raise PlacementError('Placement legal-branch budget exhausted', states=self.owner.states)
            self.owner.spend_compatibility_work()
            remaining = {other: mask & self.compatible(ref, index, other) for other, mask in others.items()}
            if all(remaining.values()):
                score = -sum(math.log1p(mask.bit_count()) for mask in remaining.values())
                ranked.append((score, index, remaining))
            inspected += 1
            if inspected == RANKING_BATCH_SIZE:
                yield from sorted(ranked)
                ranked, inspected = [], 0
        yield from sorted(ranked)

    def solutions(self, masks=None, chosen=None):
        masks = {ref: domain.full for ref, domain in self.domains.items()} if masks is None else masks
        chosen = {} if chosen is None else chosen
        if not masks:
            yield chosen
            return
        if len(masks) <= 2:
            yield from self.terminal_solutions(masks, chosen)
            return
        masks = self.propagate(masks)
        if masks is None:
            return
        ref = min(masks, key=lambda name: (masks[name].bit_count(), name))
        for _, index, remaining in self.ranked_candidates(ref, masks):
            if self.owner.states >= self.owner.budget:
                raise PlacementError('Placement legal-branch budget exhausted', states=self.owner.states)
            self.owner.states += 1
            position = self.domains[ref].values[index][1]
            yield from self.solutions(remaining, {**chosen, ref: position})
