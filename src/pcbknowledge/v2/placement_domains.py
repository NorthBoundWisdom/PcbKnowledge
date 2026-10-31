"""Bitset propagation of pairwise courtyard and placement constraints."""
from bisect import bisect_left, bisect_right
import math

from .placement import EPSILON, GROUP_MAX_DISTANCE_MM, PlacementError, _rule_ok


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
        self.cache, self.pair_rules = {}, {}
        for index, rule, refs in owner.rules:
            unresolved = refs & domains.keys()
            if len(unresolved) > 2:
                raise PlacementError('Cluster requires pairwise unresolved constraints', constraints=(index,))
            if len(unresolved) == 2:
                self.pair_rules.setdefault(frozenset(unresolved), []).append(rule)

    def compatible(self, ref, index, other):
        self.owner.spend_compatibility_work()
        key = ref, index, other
        if key in self.cache:
            return self.cache[key]
        _, position, box = self.domains[ref].values[index]
        margin = max(self.owner.margins.get(ref, 0), self.owner.margins.get(other, 0))
        mask = self.domains[other].separate(box, margin)
        rules = self.pair_rules.get(frozenset((ref, other)), [])
        if rules:
            for candidate in indices(mask):
                self.owner.spend_compatibility_work()
                point = self.domains[other].values[candidate][1]
                placed = {**self.owner.positions, ref: position, other: point}
                def passes(rule):
                    if rule['kind'] == 'GROUP':
                        return math.hypot(position[0] - point[0], position[1] - point[1]) <= (
                            GROUP_MAX_DISTANCE_MM + EPSILON)
                    return _rule_ok(rule, self.owner.geometry, placed, self.owner.width, self.owner.height)
                if not all(passes(rule) for rule in rules):
                    mask ^= 1 << candidate
        self.cache[key] = mask
        return mask

    def solutions(self, masks=None, chosen=None):
        masks = {ref: domain.full for ref, domain in self.domains.items()} if masks is None else masks
        chosen = {} if chosen is None else chosen
        if not masks:
            yield chosen
            return
        ref = min(masks, key=lambda name: (masks[name].bit_count(), name))
        others = {name: mask for name, mask in masks.items() if name != ref}
        ranked = []
        for index in indices(masks[ref]):
            if self.owner.states >= self.owner.budget:
                raise PlacementError('Placement legal-branch budget exhausted', states=self.owner.states)
            self.owner.spend_compatibility_work()
            remaining = {other: mask & self.compatible(ref, index, other) for other, mask in others.items()}
            if any(not mask for mask in remaining.values()):
                continue
            score = -sum(math.log1p(mask.bit_count()) for mask in remaining.values())
            ranked.append((score, index, remaining))
        for _, index, remaining in sorted(ranked):
            if self.owner.states >= self.owner.budget:
                raise PlacementError('Placement legal-branch budget exhausted', states=self.owner.states)
            self.owner.states += 1
            position = self.domains[ref].values[index][1]
            yield from self.solutions(remaining, {**chosen, ref: position})
