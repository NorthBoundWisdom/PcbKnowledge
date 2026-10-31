"""Read-only filled-region topology and rectangular-pad area measurements."""
from collections import Counter
from fractions import Fraction
import math

EPS = Fraction('0.000000001')


class Unsupported(ValueError):
    """Geometry cannot be measured safely by this checker."""


class Budget:
    def __init__(self, max_vertices=5000, max_work=2000000):
        if any(type(v) is not int or v <= 0 for v in (max_vertices, max_work)):
            raise Unsupported('Positive integer geometry limits required')
        self.max_vertices, self.max_work = max_vertices, max_work
        self.vertices = self.work = 0

    def spend(self, count=1):
        self.work += count
        if self.work > self.max_work:
            raise Unsupported('Filled-region comparison budget exhausted')

    def points(self, values):
        if not isinstance(values, list):
            raise Unsupported('Polygon points must be a list')
        self.vertices += len(values)
        if self.vertices > self.max_vertices:
            raise Unsupported('Filled-region vertex budget exhausted')
        return [point(v) for v in values]


def scalar(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1000000:
        raise Unsupported('Nonfinite or excessive geometry coordinate')
    return Fraction(str(value))


def point(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise Unsupported('Expected coordinate pair')
    return tuple(scalar(v) for v in value)


def edges(ring):
    return zip(ring, ring[1:] + ring[:1])


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def signed_area(ring):
    ring = [tuple(v if isinstance(v, Fraction) else scalar(v) for v in p) for p in ring]
    return sum((a[0] * b[1] - b[0] * a[1] for a, b in edges(ring)), Fraction(0)) / 2


def intersects(a, b, c, d):
    if max(min(a[0], b[0]), min(c[0], d[0])) > min(max(a[0], b[0]), max(c[0], d[0])) + EPS:
        return False
    if max(min(a[1], b[1]), min(c[1], d[1])) > min(max(a[1], b[1]), max(c[1], d[1])) + EPS:
        return False
    signs = [cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)]
    return not ((signs[0] > EPS and signs[1] > EPS) or (signs[0] < -EPS and signs[1] < -EPS)
                or (signs[2] > EPS and signs[3] > EPS) or (signs[2] < -EPS and signs[3] < -EPS))


def location(p, ring, budget):
    """Return 1 inside, 0 on/near boundary, -1 outside."""
    inside = False
    for a, b in edges(ring):
        budget.spend()
        if abs(cross(a, b, p)) <= EPS and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS:
            if min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS:
                return 0
        if (a[1] > p[1]) != (b[1] > p[1]):
            if p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
    return 1 if inside else -1


def simple(ring, budget):
    if len(ring) < 3 or len(set(ring)) != len(ring) or abs(signed_area(ring)) <= EPS:
        raise Unsupported('Degenerate filled ring')
    lines = list(edges(ring))
    for i, (a, b) in enumerate(lines):
        for j in range(i + 1, len(lines)):
            budget.spend()
            c, d = lines[j]
            if j == i + 1 or (i == 0 and j == len(lines) - 1):
                # Adjacent collinear reversal would hide a zero-width spur.
                shared, left, right = (b, a, d) if j == i + 1 else (a, b, c)
                if abs(cross(left, shared, right)) <= EPS:
                    dot = sum((left[k] - shared[k]) * (right[k] - shared[k]) for k in (0, 1))
                    if dot >= 0:
                        raise Unsupported('Backtracking filled boundary')
            elif intersects(a, b, c, d):
                raise Unsupported('Crossing or touching filled ring')


def ring_contacts(left, right, budget):
    for a, b in edges(left):
        for c, d in edges(right):
            budget.spend()
            if intersects(a, b, c, d):
                return True
    return False


def material(p, region, budget):
    outer = location(p, region['outer'], budget)
    if outer != 1:
        return outer
    for hole in region['holes']:
        loc = location(p, hole, budget)
        if loc >= 0:
            return -loc
    return 1


def _split_walk(points, budget):
    counts = Counter(edges(points))
    if any(a == b or count != 1 for (a, b), count in counts.items()):
        raise Unsupported('Duplicate or zero-length filled edge')
    bridges = sorted((a, b) for a, b in counts if (b, a) in counts and a < b)
    remaining = {(a, b) for a, b in counts if (b, a) not in counts}
    outgoing, incoming = {}, Counter()
    for a, b in remaining:
        if a in outgoing:
            raise Unsupported('Ambiguous keyhole branch')
        outgoing[a] = b
        incoming[b] += 1
    if set(outgoing) != set(incoming) or any(v != 1 for v in incoming.values()):
        raise Unsupported('Open keyhole ring')
    rings = []
    while outgoing:
        start = min(outgoing)
        ring, current = [], start
        while current in outgoing:
            budget.spend()
            ring.append(current)
            current = outgoing.pop(current)
        if current != start:
            raise Unsupported('Malformed keyhole cycle')
        simple(ring, budget)
        rings.append(ring)
    if not rings or len(bridges) != len(rings) - 1:
        raise Unsupported('Keyhole bridges must form a ring tree')
    return rings, bridges


def normalize(values, budget):
    points = budget.points(values)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    rings, bridges = _split_walk(points, budget)
    for i, ring in enumerate(rings):
        if any(ring_contacts(ring, other, budget) for other in rings[i + 1:]):
            raise Unsupported('Touching or intersecting keyhole rings')
    parents = [[j for j, other in enumerate(rings) if j != i and location(ring[0], other, budget) == 1]
               for i, ring in enumerate(rings)]
    outer = [i for i, parent in enumerate(parents) if not parent]
    if len(outer) != 1 or any(len(parent) > 1 for parent in parents):
        raise Unsupported('Only one exterior with nonnested holes is supported per filled polygon')
    exterior = rings[outer[0]]
    holes = [ring for i, ring in enumerate(rings) if i != outer[0]]
    if any(signed_area(h) * signed_area(exterior) >= 0 for h in holes):
        raise Unsupported('Keyhole hole winding disagrees with exterior')
    region = {'outer': exterior, 'holes': holes,
              'area': abs(signed_area(exterior)) - sum((abs(signed_area(h)) for h in holes), Fraction(0))}
    _bridges(bridges, rings, region, budget)
    if region['area'] <= EPS:
        raise Unsupported('Nonpositive filled material area')
    return region


def _bridges(bridges, rings, region, budget):
    memberships = {p: i for i, ring in enumerate(rings) for p in ring}
    joined = set()
    for a, b in bridges:
        if a not in memberships or b not in memberships or memberships[a] == memberships[b]:
            raise Unsupported('Bridge endpoints must join distinct ring vertices')
        pair = tuple(sorted((memberships[a], memberships[b])))
        if pair in joined:
            raise Unsupported('Duplicate bridge connection')
        joined.add(pair)
        for ring in rings:
            for c, d in edges(ring):
                budget.spend()
                if a in (c, d) or b in (c, d):
                    continue
                if intersects(a, b, c, d):
                    raise Unsupported('Keyhole bridge crosses boundary')
        midpoint = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if material(midpoint, region, budget) != 1:
            raise Unsupported('Keyhole bridge leaves filled material')
    for i, (a, b) in enumerate(bridges):
        for c, d in bridges[i + 1:]:
            budget.spend()
            if not {a, b}.intersection((c, d)) and intersects(a, b, c, d):
                raise Unsupported('Crossing keyhole bridges')


def clip_area(ring, pad, budget):
    """Clip a simple ring to the convex rectangular pad; retain signed winding."""
    x, y = point(pad['at'])
    width, height = point(pad['size'])
    if min(width, height) <= 0:
        raise Unsupported('Nonpositive target pad dimensions')
    angle = scalar(pad['rotation']) % 360
    if angle not in (0, 90, 180, 270):
        raise Unsupported('Exact contact measurement supports cardinal rectangular pad rotations only')
    cosine, sine = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[angle]
    points = [((p[0] - x) * cosine - (p[1] - y) * sine,
               (p[0] - x) * sine + (p[1] - y) * cosine) for p in ring]
    for axis, limit, direction in ((0, width / 2, 1), (0, -width / 2, -1),
                                    (1, height / 2, 1), (1, -height / 2, -1)):
        output = []
        for a, b in edges(points):
            budget.spend()
            av, bv = direction * (a[axis] - limit), direction * (b[axis] - limit)
            if (av <= 0) != (bv <= 0):
                fraction = av / (av - bv)
                output.append(tuple(a[k] + fraction * (b[k] - a[k]) for k in (0, 1)))
            if bv <= 0:
                output.append(b)
        points = output
        if not points:
            return Fraction(0)
    return abs(signed_area(points))


def contact_area(region, pad, budget):
    holes = sum((clip_area(h, pad, budget) for h in region['holes']), Fraction(0))
    area = clip_area(region['outer'], pad, budget) - holes
    if area < -EPS:
        raise Unsupported('Inconsistent clipped hole area')
    return max(Fraction(0), area)


def disjoint(regions, budget):
    for i, left in enumerate(regions):
        for right in regions[i + 1:]:
            for a in [left['outer'], *left['holes']]:
                for b in [right['outer'], *right['holes']]:
                    if ring_contacts(a, b, budget):
                        raise Unsupported('Filled regions overlap or touch; exact union is unsupported')
            if material(left['outer'][0], right, budget) == 1 or material(right['outer'][0], left, budget) == 1:
                raise Unsupported('Filled regions overlap; duplicate area cannot be counted')
