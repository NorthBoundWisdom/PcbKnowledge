"""Synthetic graphic enclosure without rewriting copper or courtyard authority."""
import copy
import unittest
from pcbknowledge.v2.footprints import pin1_marker, occupied_envelope


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

    def test_marker_uses_rotated_physical_pad_bounds(self):
        item = shape()
        item['pads'][0]['rotation'] = 90
        self.assertEqual(pin1_marker(item), {'x': -1.25, 'y': -.75, 'radius': .1, 'stroke': .1})


    def test_oblique_nonsquare_pad_bounds_in_all_component_rotations(self):
        from math import sqrt
        from pcbknowledge.v2.footprints import rotated_pad_size
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
                    self.assertAlmostEqual(item['pin1_marker']['x'], -size[0] / 2 - .25)
                    self.assertAlmostEqual(item['pin1_marker']['y'], -size[1] / 2 - .25)


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
