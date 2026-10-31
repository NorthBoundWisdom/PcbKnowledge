"""Synthetic graphic enclosure without rewriting copper or courtyard authority."""
import copy
import unittest
from pcbknowledge.v2.footprints import pin1_marker, occupied_envelope
from pcbknowledge.v2.placement import PlacementError, _box, place_geometry, validate_positions


def shape():
    item = {'pads': [{'number': '1', 'x': 0, 'y': 0, 'width': 1, 'height': 2, 'rotation': 0}],
            'pin1': '1', 'courtyard': {'min_x': -.75, 'max_x': .75, 'min_y': -1.25, 'max_y': 1.25}}
    item['pin1_marker'] = pin1_marker(item)
    return item


class SilkEnvelopeTests(unittest.TestCase):
    def test_circle_extent_includes_half_stroke_and_preserves_authority(self):
        item = shape()
        before = copy.deepcopy(item)
        envelope = occupied_envelope(item)
        self.assertAlmostEqual(envelope['min_x'], -.9)
        self.assertAlmostEqual(envelope['min_y'], -1.4)
        self.assertEqual(item, before)
        self.assertEqual(_box(item, (0, 0, 0)), [-.75, -1.25, .75, 1.25])

    def test_marker_uses_rotated_physical_pad_bounds(self):
        item = shape()
        item['pads'][0]['rotation'] = 90
        self.assertEqual(pin1_marker(item), {'x': -1.25, 'y': -.75, 'radius': .1, 'stroke': .1})

    def test_previous_legal_courtyard_collision_is_now_rejected(self):
        items = {'A': shape(), 'B': shape()}
        with self.assertRaisesRegex(PlacementError, 'Graphic collision'):
            validate_positions(items, [], {'A': (5, 5, 0), 'B': (3.5, 2.5, 180)}, 8, 8)

    def test_empty_union_corner_is_not_a_graphic_obstacle(self):
        items = {'A': shape(), 'B': shape()}
        positions = {'A': (2, 2, 0), 'B': (3.5, 2, 0)}
        from pcbknowledge.v2.layout_geometry import overlap
        self.assertTrue(overlap(_box(items['A'], positions['A'], occupied=True),
                                _box(items['B'], positions['B'], occupied=True)))
        validate_positions(items, [], positions, 8, 8)

    def test_circle_to_pad_and_circle_to_circle_not_bounding_boxes(self):
        from pcbknowledge.v2.placement_graphics import conflicts
        ink = ((0, 0, .15), [], (-.15, -.15, .15, .15))
        copper = (None, [(-.1, -.1, .1, .1)], (-.1, -.1, .1, .1))
        self.assertTrue(conflicts(ink, (0, 0), copper, (.2, 0)))
        self.assertTrue(conflicts(copper, (.2, 0), ink, (0, 0)))
        self.assertFalse(conflicts(ink, (0, 0), copper, (.3, 0)))
        self.assertTrue(conflicts(ink, (0, 0), ink, (.29, 0)))
        self.assertFalse(conflicts(ink, (0, 0), ink, (.3, 0)))

    def test_cluster_prunes_ink_collision_without_pair_rules(self):
        from types import SimpleNamespace
        from pcbknowledge.v2.placement_domains import ClusterSearch
        from pcbknowledge.v2.placement_graphics import conflicts, graphics
        items = {'A': shape(), 'B': shape()}
        a, b = (5, 5, 0), (3.5, 2.5, 180)
        owner = SimpleNamespace(rules=[], margins={}, geometry=items, positions={},
                                spend_compatibility_work=lambda: None)
        owner.graphic_conflict = lambda ref, pos, other, point: conflicts(
            graphics(items[ref], pos[2]), pos, graphics(items[other], point[2]), point)
        domains = {'A': [(0, a, _box(items['A'], a))], 'B': [(0, b, _box(items['B'], b))]}
        self.assertEqual(ClusterSearch(owner, domains).compatible('A', 0, 'B'), 0)

    def test_outline_includes_graphic_under_all_rotations(self):
        for angle in (0, 90, 180, 270):
            item = shape()
            box = _box(item, (0, 0, angle))
            position = (-box[0], -box[1], angle)
            # The marker protrudes either at the low or high edge after rotation.
            with self.subTest(angle=angle), self.assertRaisesRegex(PlacementError, 'outside'):
                validate_positions({'A': item}, [], {'A': position}, box[2] - box[0], box[3] - box[1])

    def test_search_and_final_verifier_share_enclosure(self):
        items = {'A': shape(), 'B': shape()}
        before = copy.deepcopy(items)
        positions = place_geometry(items, [], 8, 8, grid_mm=.1)
        validate_positions(items, [], positions, 8, 8)
        self.assertEqual(items, before)

    def test_malformed_markers_fail_closed_before_search(self):
        mutations = [None, {}, {'extra': 1}]
        for key in ('x', 'y', 'radius', 'stroke'):
            for value in (float('nan'), float('inf'), -float('inf'), True, '1'):
                mutations.append({**shape()['pin1_marker'], key: value})
            marker = shape()['pin1_marker']
            del marker[key]
            mutations.append(marker)
        mutations.extend({**shape()['pin1_marker'], key: value}
                         for key, value in [('radius', 0), ('radius', -.1), ('stroke', -.1)])
        for marker in mutations:
            item = shape()
            item['pin1_marker'] = marker
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                place_geometry({'A': item}, [], 8, 8)

    def test_oblique_nonsquare_pad_bounds_in_all_component_rotations(self):
        from math import sqrt
        from pcbknowledge.v2.footprints import rotated_pad_size
        from pcbknowledge.v2.placement_graphics import graphics
        expected = {30: (sqrt(3) / 2 + 1, .5 + sqrt(3)),
                    45: (3 / sqrt(2), 3 / sqrt(2))}
        for local, size in expected.items():
            for angle in (0, 90, 180, 270):
                item = shape()
                item['pads'][0]['rotation'] = local
                item['pin1_marker'] = pin1_marker(item)
                width, height = size if angle % 180 == 0 else size[::-1]
                with self.subTest(local=local, angle=angle):
                    observed = rotated_pad_size(item['pads'][0], angle)
                    self.assertAlmostEqual(observed[0], width)
                    self.assertAlmostEqual(observed[1], height)
                    pad = graphics(item, angle)[1][0]
                    self.assertAlmostEqual(pad[2] - pad[0], width)
                    self.assertAlmostEqual(pad[3] - pad[1], height)
                    self.assertAlmostEqual(item['pin1_marker']['x'], -size[0] / 2 - .25)
                    self.assertAlmostEqual(item['pin1_marker']['y'], -size[1] / 2 - .25)

    def test_existing_near_constraint_is_not_relaxed(self):
        items = {'A': shape(), 'B': shape()}
        rule = {'kind': 'PLACE_NEAR', 'subject': 'A', 'target': 'B',
                'max_distance': {'value': .1, 'unit': 'mm'}}
        with self.assertRaises(PlacementError):
            place_geometry(items, [rule], 4, 4, grid_mm=.5, max_states=100)
        self.assertEqual(rule['max_distance']['value'], .1)


if __name__ == '__main__':
    unittest.main()


class ExportSyntaxTests(unittest.TestCase):
    def test_all_catalog_marker_exports_parse_with_typed_stroke(self):
        from pathlib import Path
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.footprints import export_kicad
        from pcbknowledge.v2.boardview import children
        from pcbknowledge.v2.sexpr import parse
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        for package in catalog.records.values():
            if package['schema'] != 'pcbknowledge.package.v2':
                continue
            tree = parse(export_kicad(package))
            marker = children(tree, 'fp_circle')[0]
            stroke = children(marker, 'stroke')[0]
            self.assertEqual(children(stroke, 'width'), [['width', '0.1']])
            self.assertEqual(children(stroke, 'type'), [['type', 'default']])
