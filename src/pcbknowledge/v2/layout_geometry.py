"""Small conservative planar measurements for read-only layout checks."""
import math


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def polygon_area(points):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))) / 2


def convex_hull(points):
    points = sorted(set(tuple(point) for point in points))
    if len(points) < 3:
        return points
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def contains(point, polygon):
    """Ray crossing, treating boundary points as inside."""
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(cross(a, b, point)) < 1e-9 and min(a[0], b[0]) <= point[0] <= max(a[0], b[0]):
            if min(a[1], b[1]) <= point[1] <= max(a[1], b[1]):
                return True
        if (a[1] > point[1]) != (b[1] > point[1]):
            x = a[0] + (point[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if point[0] < x:
                inside = not inside
    return inside


def simple_polygon(points):
    """Reject degenerate, touching or intersecting non-adjacent polygon edges."""
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3 or len({tuple(p) for p in points}) != len(points):
        return False
    edges = list(zip(points, points[1:] + points[:1]))
    for index, (a, b) in enumerate(edges):
        for other, (c, d) in enumerate(edges[index + 1:], index + 1):
            if other == index + 1 or (index == 0 and other == len(edges) - 1):
                continue
            if cross(a, b, c) * cross(a, b, d) <= 0 and cross(c, d, a) * cross(c, d, b) <= 0:
                if max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0])):
                    if max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1])):
                        return False
    return polygon_area(points) > 0


def overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])
