"""Deterministic finite-domain placement with constrained-cluster propagation."""
from collections import Counter
import heapq
import math

from .placement import (EPSILON, GROUP_MAX_DISTANCE_MM, PlacementError, _box, _domain, _finite,
                        _local_points, _prepare_rules, _priority, _ref, _refs, _rule_ok, _score,
                        _validate_geometry, validate_positions)
from .layout_geometry import overlap
from .placement_graphics import graphics, conflicts

MAX_DOMAIN_CANDIDATES = 500000
BEAM_WIDTH = 64
MAX_COMPATIBILITY_WORK = 20000000
COMPATIBILITY_WORK_PER_BRANCH = 10000


class GridSearch:
    def __init__(self, geometry, rules, width, height, mechanical, grid, budget, domain_budget, beam):
        self.geometry, self.width, self.height = geometry, width, height
        self.rules = [(index, rule, _refs(rule)) for index, rule in _prepare_rules(rules, geometry)]
        self.prepared = [(index, rule) for index, rule, _ in self.rules]
        from .placement_feasibility import check_isolated_near_bounds
        check_isolated_near_bounds(geometry, self.prepared)
        from .placement_joint_feasibility import check_shared_anchor_pairs
        check_shared_anchor_pairs(geometry, self.prepared)
        self.local_rules = {ref: [(index, rule, refs) for index, rule, refs in self.rules if ref in refs]
                            for ref in geometry}
        self.mechanical, self.grid, self.budget = set(mechanical), grid, budget
        self.beam, self.states, self.examined = beam, 1, 0
        self.compatibility_work = 0
        self.compatibility_limit = min(MAX_COMPATIBILITY_WORK, budget * COMPATIBILITY_WORK_PER_BRANCH)
        self.failed, self.positions, self.boxes, self.best = set(), {}, {}, {}
        self.local_boxes, self.domains, self.points, self.margins = {}, {}, {}, {}
        self.graphics = {}
        for _, rule, _ in self.rules:
            if rule['kind'] == 'KEEPOUT':
                ref = rule['subject']
                self.margins[ref] = max(self.margins.get(ref, 0), rule['margin']['value'])
        self.edge = {ref for ref in geometry if any(rule['kind'].startswith('EDGE_')
                                                   for _, rule, _ in self.local_rules[ref])}
        self.domain_budget = domain_budget
        for ref in sorted(geometry):
            available = 0
            for angle in (0, 90, 180, 270):
                self.local_boxes[ref, angle] = _box(geometry[ref], (0, 0, angle))
                self.graphics[ref, angle] = graphics(geometry[ref], angle)
                xs, ys = _domain(ref, angle, geometry, self.prepared, width, height, grid)
                if max(len(xs), len(ys)) > domain_budget:
                    raise PlacementError('Axis candidate domain exceeds deterministic budget')
                self.domains[ref, angle] = xs, ys
                available += len(xs) * len(ys)
            if not available:
                raise PlacementError('Empty legal domain for ' + ref,
                                     constraints=[index for index, _, _ in self.local_rules[ref]])

    def spend_compatibility_work(self):
        if self.compatibility_work >= self.compatibility_limit:
            raise PlacementError('Placement compatibility-work budget exhausted', states=self.states)
        self.compatibility_work += 1

    def local_points(self, endpoint, angle):
        key = endpoint, angle
        if key not in self.points:
            self.points[key] = _local_points(endpoint, self.geometry, angle)
        return self.points[key]

    def physical_points(self, endpoint, ref, candidate):
        x, y, angle = candidate if _ref(endpoint) == ref else self.positions[_ref(endpoint)]
        return [(x + p[0], y + p[1]) for p in self.local_points(endpoint, angle)]

    def bounds(self, ref, angle):
        xs, ys = self.domains[ref, angle]
        if not xs or not ys:
            return [], []
        xmin, xmax, ymin, ymax = xs[0], xs[-1], ys[0], ys[-1]
        for _, rule, refs in self.local_rules[ref]:
            if rule['kind'] == 'PLACE_NEAR':
                left, right = rule['subject'], rule['target']
                local, remote = (left, right) if _ref(left) == ref else (right, left)
                if _ref(remote) not in self.positions:
                    continue
                r = rule['max_distance']['value']
                centers = [(a[0] - b[0], a[1] - b[1])
                           for a in self.physical_points(remote, ref, (0, 0, angle))
                           for b in self.local_points(local, angle)]
                xmin, xmax = max(xmin, min(p[0] for p in centers) - r), min(xmax, max(p[0] for p in centers) + r)
                ymin, ymax = max(ymin, min(p[1] for p in centers) - r), min(ymax, max(p[1] for p in centers) + r)
            elif rule['kind'] == 'GROUP':
                for other in sorted((refs - {ref}) & self.positions.keys()):
                    x, y = self.positions[other][:2]
                    r = GROUP_MAX_DISTANCE_MM
                    xmin, xmax, ymin, ymax = max(xmin, x - r), min(xmax, x + r), max(ymin, y - r), min(ymax, y + r)
        return ([x for x in xs if xmin - EPSILON <= x <= xmax + EPSILON],
                [y for y in ys if ymin - EPSILON <= y <= ymax + EPSILON])

    def rule_ok(self, ref, position, rule, refs):
        kind = rule['kind']
        if kind == 'GROUP':
            x, y = position[:2]
            return all(math.hypot(x - self.positions[o][0], y - self.positions[o][1])
                       <= GROUP_MAX_DISTANCE_MM + EPSILON for o in (refs - {ref}) & self.positions.keys())
        if not (refs - {ref}) <= self.positions.keys():
            return True
        if kind == 'PLACE_NEAR':
            left = self.physical_points(rule['subject'], ref, position)
            right = self.physical_points(rule['target'], ref, position)
            return any(math.hypot(a[0] - b[0], a[1] - b[1]) <= rule['max_distance']['value'] + EPSILON
                       for a in left for b in right)
        if kind == 'MINIMIZE_LOOP':
            return _rule_ok(rule, self.geometry, {**self.positions, ref: position}, self.width, self.height)
        return True

    def graphic_conflict(self, ref, position, other, point):
        return conflicts(self.graphics[ref, position[2]], position, self.graphics[other, point[2]], point)

    def legal(self, ref, position):
        x, y, angle = position
        local = self.local_boxes[ref, angle]
        box = (local[0] + x, local[1] + y, local[2] + x, local[3] + y)
        for other, previous in self.boxes.items():
            margin = max(self.margins.get(ref, 0), self.margins.get(other, 0))
            if overlap((box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin), previous):
                return None
        if any(self.graphic_conflict(ref, position, other, point)
               for other, point in self.positions.items()):
            return None
        for index, rule, refs in self.local_rules[ref]:
            if not self.rule_ok(ref, position, rule, refs):
                self.failed.add(index)
                return None
        return box

    def candidates(self, ref):
        values, seen = [], set()
        endpoints = {endpoint for _, rule, _ in self.local_rules[ref]
                     for endpoint in [*rule.get('path', []), *rule.get('subjects', []),
                                      *[rule[key] for key in ('subject', 'target') if key in rule]]
                     if _ref(endpoint) == ref}
        for angle in (0, 90, 180, 270):
            xs, ys = self.bounds(ref, angle)
            if len(xs) * len(ys) > self.domain_budget:
                raise PlacementError('Bounded candidate scan exceeds deterministic domain limit')
            self.examined += len(xs) * len(ys)
            for y in ys:
                for x in xs:
                    position = x, y, angle
                    box = self.legal(ref, position)
                    if box is None:
                        continue
                    signature = (tuple(round(v, 12) for v in box), tuple(
                        tuple(sorted((round(x + p[0], 12), round(y + p[1], 12))
                                     for p in self.local_points(endpoint, angle))) for endpoint in sorted(endpoints)))
                    if signature in seen:
                        continue
                    seen.add(signature)
                    score = _score(ref, position, self.positions, self.geometry,
                                   self.prepared, self.width, self.height)
                    values.append((score, position, box))
        if not values:
            self.failed.update(index for index, _, _ in self.local_rules[ref])
        return sorted(values)

    def anchor_candidates(self, ref):
        values = []
        quota = max(1, self.beam // 4)
        for angle in (0, 90, 180, 270):
            xs, ys = self.bounds(ref, angle)
            xs = sorted(xs, key=lambda x: ((x - self.width / 2) ** 2, x))
            ys = sorted(ys, key=lambda y: ((y - self.height / 2) ** 2, y))
            if not xs or not ys:
                continue
            def item(i, j):
                x, y = xs[i], ys[j]
                return ((x - self.width / 2) ** 2 + (y - self.height / 2) ** 2, y, x, i, j)
            pending, visited, count, examined = [item(0, 0)], {(0, 0)}, 0, 0
            while pending and count < quota:
                if examined >= self.domain_budget:
                    raise PlacementError('Lazy candidate traversal exceeds deterministic domain limit')
                examined += 1
                distance, y, x, i, j = heapq.heappop(pending)
                self.examined += 1
                position = x, y, angle
                box = self.legal(ref, position)
                if box is not None:
                    values.append(((distance, angle, y, x), position, box))
                    count += 1
                for a, b in ((i + 1, j), (i, j + 1)):
                    if a < len(xs) and b < len(ys) and (a, b) not in visited:
                        visited.add((a, b))
                        heapq.heappush(pending, item(a, b))
        if not values:
            self.failed.update(index for index, _, _ in self.local_rules[ref])
        return sorted(values)

    def next_candidates(self):
        unplaced = set(self.geometry) - self.positions.keys()
        fixed, edges = unplaced & self.mechanical, unplaced & self.edge
        neighbors = {ref for ref in unplaced if any((refs - {ref}) & self.positions.keys()
                                                    for _, _, refs in self.local_rules[ref])}
        choices = fixed or edges or neighbors
        anchors = {ref for ref in choices if len({p['number'] for p in self.geometry[ref]['pads']}) > 2}
        if not fixed and not edges and anchors:
            choices = anchors
        if not choices:
            ref = min(unplaced, key=lambda r: _priority(r, self.positions, self.geometry,
                                                       self.prepared, self.mechanical))
            return ref, self.anchor_candidates(ref)
        best = None
        for ref in sorted(choices | neighbors):
            values = self.candidates(ref)
            priority = len(values), _priority(ref, self.positions, self.geometry, self.prepared, self.mechanical)
            if ref in choices and (best is None or priority < best[0]):
                best = priority, ref, values
            if not values:
                return ref, values
        return best[1], best[2]

    def connected_ready(self, ready):
        """Choose one deterministic rule-connected near cluster, without batching unrelated groups."""
        linked = {}
        for ref in sorted(ready):
            for _, _, refs in self.local_rules[ref]:
                for endpoint in refs:
                    linked.setdefault(endpoint, set()).add(ref)
        remaining, components = set(ready), []
        while remaining:
            component, pending = set(), {min(remaining)}
            while pending:
                ref = min(pending)
                pending.remove(ref)
                component.add(ref)
                remaining.discard(ref)
                for _, _, refs in self.local_rules[ref]:
                    for endpoint in refs:
                        pending.update(linked.get(endpoint, set()) - component)
            components.append(component)
        candidates = [component for component in components if len(component) >= 2]
        if not candidates:
            return set()
        return min(candidates, key=lambda component: min(
            _priority(ref, self.positions, self.geometry, self.prepared, self.mechanical)
            for ref in component))

    def cluster(self):
        if (self.edge | self.mechanical) - self.positions.keys():
            return None
        ready = {ref for ref in self.geometry.keys() - self.positions.keys() if ref not in self.edge
                 and any(rule['kind'] == 'PLACE_NEAR' and (refs - {ref}) <= self.positions.keys()
                         for _, rule, refs in self.local_rules[ref])}
        near_attached = bool(ready)
        if near_attached:
            ready = self.connected_ready(ready)
        if not near_attached:
            ready = {ref for ref in self.geometry.keys() - self.positions.keys() if ref not in self.edge
                     and any(rule['kind'] == 'GROUP' and (refs - {ref}) & self.positions.keys()
                             for _, rule, refs in self.local_rules[ref])}
        if len(ready) < 2 or any(len(refs & ready) > 2 and (not near_attached or rule['kind'] != 'GROUP')
                                 for _, rule, refs in self.rules):
            return None
        return {ref: self.candidates(ref) for ref in sorted(ready)}

    def solve_cluster(self, domains):
        from .placement_domains import ClusterSearch
        if any(not values for values in domains.values()):
            return False
        for solution in ClusterSearch(self, domains).solutions():
            self.positions.update(solution)
            self.boxes.update({ref: _box(self.geometry[ref], position)
                               for ref, position in solution.items()})
            valid = all(_rule_ok(rule, self.geometry, self.positions, self.width, self.height)
                        for _, rule, _ in self.rules)
            if valid and self.solve():
                return True
            for ref in solution:
                self.positions.pop(ref)
                self.boxes.pop(ref)
        return False

    def solve(self):
        if len(self.positions) > len(self.best):
            self.best = dict(self.positions)
        if len(self.positions) == len(self.geometry):
            return True
        cluster = self.cluster()
        if cluster is not None:
            return self.solve_cluster(cluster)
        ref, candidates = self.next_candidates()
        selected, counts = [], Counter()
        for item in candidates:
            angle = item[1][2]
            if counts[angle] < max(1, self.beam // 4):
                counts[angle] += 1
                selected.append(item)
        for _, position, box in selected:
            if self.states >= self.budget:
                raise PlacementError('Placement legal-branch budget exhausted',
                                     constraints=sorted(self.failed), states=self.states)
            self.states += 1
            self.positions[ref], self.boxes[ref] = position, box
            if self.solve():
                return True
            self.positions.pop(ref)
            self.boxes.pop(ref)
        return False


def solve_geometry(geometry, rules, width, height, *, mechanical=(), grid_mm=.5, max_states=200000,
                   max_domain_candidates=MAX_DOMAIN_CANDIDATES, beam_width=BEAM_WIDTH):
    width, height = _finite(width, 'width', positive=True), _finite(height, 'height', positive=True)
    grid = _finite(grid_mm, 'grid', positive=True)
    for value in (max_states, max_domain_candidates, beam_width):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise PlacementError('Invalid deterministic search limit')
    if len(geometry) > 256 or not set(mechanical) <= geometry.keys():
        raise PlacementError('Invalid component or mechanical domain')
    if width / grid > max_domain_candidates or height / grid > max_domain_candidates:
        raise PlacementError('Axis candidate domain exceeds deterministic budget')
    _validate_geometry(geometry)
    search = GridSearch(geometry, rules, width, height, mechanical, grid, max_states,
                        max_domain_candidates, beam_width)
    if not search.solve():
        raise PlacementError('Finite heuristic placement search exhausted',
                             constraints=sorted(search.failed), states=search.states)
    validate_positions(geometry, rules, search.positions, width, height)
    return {ref: search.positions[ref] for ref in sorted(search.positions)}
