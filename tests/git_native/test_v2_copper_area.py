"""Original synthetic material, contact and ambiguity regressions; no layout tools."""
from copy import deepcopy
import json
import unittest

from pcbknowledge.v2.layout_copper_area import check_copper_area


def rectangle(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def keyhole():
    return [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0],
            [3, 3], [3, 7], [7, 7], [7, 3], [3, 3]]


def fixture(polygons=None):
    pad = {'net': 'N', 'at': [2, 2], 'size': [1, 1], 'rotation': 0, 'kind': 'smd',
           'shape': 'rect', 'layers': ['F.Cu'], 'drill_size': None, 'geometry_unsupported': False}
    board = {'footprints': {'U': {'pads': {'1': [pad]}}}, 'unsupported': [],
             'outline': {'closed': True, 'rectangular': True, 'bounds': [-100, -100, 100, 100]},
             'zones': [{'net': 'N', 'layer': 'F.Cu', 'layers': [],
                        'filled_polygons': polygons if polygons is not None else [rectangle(0, 0, 4, 4)]}],
             'segments': [], 'arcs': [], 'vias': []}
    rule = {'kind': 'COPPER_AREA', 'target': 'U.pin:1', 'min_area': {'value': 10, 'unit': 'mm2'}}
    return board, rule


class CopperAreaTests(unittest.TestCase):
    def test_exact_area_threshold_survives_diagnostic_rounding(self):
        board, rule = fixture([rectangle(0, 0, .9999999999999998, 1.0000000000000002)])
        board['footprints']['U']['pads']['1'][0].update(at=[.5, .5], size=[.1, .1])
        rule['min_area']['value'] = 1
        result = check_copper_area(board, rule)
        self.assertEqual(result['area_mm2'], 1.0)
        self.assertEqual(result['result'], 'FAIL')
        json.dumps(result, allow_nan=False)

    def test_translated_threshold_and_holes_are_exact(self):
        board, rule = fixture([rectangle(900000, 900000, 900001, 900199.99999)])
        board['outline']['bounds'] = [899999, 899999, 900300, 900300]
        board['footprints']['U']['pads']['1'][0].update(at=[900000.5, 900001], size=[.2, .2])
        rule['min_area']['value'] = 200
        result = check_copper_area(board, rule)
        self.assertEqual(result['result'], 'FAIL', result)
        self.assertAlmostEqual(result['area_mm2'], 199.99999)
        for offset in (0, 900000):
            board, rule = fixture([[[x + offset, y + offset] for x, y in keyhole()]])
            board['outline']['bounds'] = [offset - 1, offset - 1, offset + 20, offset + 20]
            board['footprints']['U']['pads']['1'][0]['at'] = [offset + 2, offset + 2]
            rule['min_area']['value'] = 84.00000000000001
            result = check_copper_area(board, rule)
            self.assertEqual((result['result'], result['area_mm2']), ('FAIL', 84))
            json.dumps(result, allow_nan=False)

    def test_other_same_net_pad_indirect_bridge_is_unproven(self):
        board, rule = fixture([rectangle(0, 0, 4, 4), rectangle(6, 0, 10, 4)])
        other = deepcopy(board['footprints']['U']['pads']['1'][0])
        other.update(at=[5, 2], size=[4, 1])
        board['footprints']['V'] = {'pads': {'1': [other]}}
        rule['min_area']['value'] = 30
        result = check_copper_area(board, rule)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertEqual(result['area_mm2'], 16)
        json.dumps(result, allow_nan=False)
        rule['min_area']['value'] = 10
        self.assertEqual(check_copper_area(board, rule)['result'], 'PASS')

    def test_noncardinal_pad_rotation_is_explicitly_unmeasured(self):
        board, rule = fixture()
        board['footprints']['U']['pads']['1'][0]['rotation'] = 45
        result = check_copper_area(board, rule)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertIn('cardinal', result['reason'])

    def test_single_region_pass_and_too_small(self):
        board, rule = fixture()
        self.assertEqual(check_copper_area(board, rule)['result'], 'PASS')
        rule['min_area']['value'] = 17
        result = check_copper_area(board, rule)
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['area_mm2'], 16)

    def test_plural_disjoint_regions_joined_by_one_pad(self):
        board, rule = fixture([rectangle(0, 4, 4, 6), rectangle(6, 4, 10, 6)])
        board['footprints']['U']['pads']['1'][0].update(at=[5, 5], size=[10, 2])
        before = deepcopy((board, rule))
        result = check_copper_area(board, rule)
        self.assertEqual((result['result'], result['area_mm2'], result['contacting_regions']), ('PASS', 16, 2))
        self.assertEqual((board, rule), before)

    def test_disconnected_large_island_does_not_inflate_small_contact(self):
        board, rule = fixture([rectangle(0, 0, 4, 4), rectangle(20, 20, 60, 60)])
        rule['min_area']['value'] = 100
        result = check_copper_area(board, rule)
        self.assertEqual((result['result'], result['area_mm2'], result['excluded_regions']), ('FAIL', 16, 1))
        board['segments'] = [{'net': 'N', 'start': [2, 2], 'end': [30, 30], 'width': .2, 'layer': 'F.Cu'}]
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')
        rule['min_area']['value'] = 10
        self.assertEqual(check_copper_area(board, rule)['result'], 'PASS')

    def test_hole_subtraction_winding_start_order_and_closure(self):
        points = keyhole()
        for variant in (points, list(reversed(points)), points[3:] + points[:3], points + [points[0]]):
            board, rule = fixture([variant])
            rule['min_area']['value'] = 85
            result = check_copper_area(board, rule)
            self.assertEqual(result['result'], 'FAIL', result)
            self.assertEqual((result['area_mm2'], result['subtracted_holes']), (84, 1))
        board, rule = fixture([keyhole()])
        board['footprints']['U']['pads']['1'][0]['at'] = [5, 5]
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_alternate_keyhole_bridge_and_multiple_holes(self):
        alternate = [[0, 0], [10, 0], [7, 3], [3, 3], [3, 7], [7, 7], [7, 3],
                     [10, 0], [10, 10], [0, 10]]
        board, rule = fixture([alternate])
        self.assertEqual(check_copper_area(board, rule)['area_mm2'], 84)
        two = [[0, 0], [12, 0], [10, 2], [8, 2], [8, 4], [10, 4], [10, 2],
               [12, 0], [12, 10], [0, 10], [0, 0], [3, 3], [3, 5], [5, 5], [5, 3], [3, 3]]
        board, rule = fixture([two])
        result = check_copper_area(board, rule)
        self.assertEqual((result['area_mm2'], result['subtracted_holes']), (112, 2))
        malformed = keyhole()
        malformed[5:] = list(reversed(malformed[5:]))
        # Reversing only the hole makes its winding inconsistent with the exterior.
        board, rule = fixture([malformed])
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_concave_region_contact_clipping(self):
        # C-shaped material intersects the target rectangle in two disjoint strips.
        polygon = [[0, 0], [4, 0], [4, 1], [1, 1], [1, 3], [4, 3], [4, 4], [0, 4]]
        board, rule = fixture([polygon])
        board['footprints']['U']['pads']['1'][0].update(at=[3, 2], size=[1, 4])
        result = check_copper_area(board, rule)
        self.assertEqual((result['result'], result['area_mm2']), ('PASS', 10))

    def test_rotated_rectangular_pad_contact_is_not_axis_aligned_box(self):
        board, rule = fixture([rectangle(-.2, 1.5, .2, 2)])
        pad = board['footprints']['U']['pads']['1'][0]
        pad.update(at=[0, 0], size=[4, .5])
        rule['min_area']['value'] = .1
        for angle, expected in [(0, 'NOT_CHECKABLE'), (90, 'PASS'), (180, 'NOT_CHECKABLE'), (270, 'PASS')]:
            pad['rotation'] = angle
            self.assertEqual(check_copper_area(board, rule)['result'], expected)
        pad['rotation'] = 45
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_tangent_no_contact_wrong_layer_and_boundary_only(self):
        board, rule = fixture()
        pad = board['footprints']['U']['pads']['1'][0]
        for location in ([4.5, 2], [4.5, 4.5], [10, 10]):
            pad['at'] = location
            self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')
        pad['at'] = [2, 2]
        board['zones'][0]['layer'] = 'B.Cu'
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_duplicate_overlap_and_touching_regions_are_not_summed(self):
        for other in [rectangle(0, 0, 4, 4), rectangle(1, 1, 3, 3), rectangle(3, 3, 5, 5),
                      rectangle(4, 0, 6, 2)]:
            board, rule = fixture([rectangle(0, 0, 4, 4), other])
            self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_repeated_physical_target_pads_are_not_pooled(self):
        board, rule = fixture()
        board['footprints']['U']['pads']['1'].append(deepcopy(board['footprints']['U']['pads']['1'][0]))
        result = check_copper_area(board, rule)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertIn('Repeated physical', result['reason'])

    def test_physical_drill_voids_and_slots(self):
        board, rule = fixture([keyhole()])
        board['vias'] = [{'net': 'N', 'at': [5, 5], 'drill': 1}]
        result = check_copper_area(board, rule)
        self.assertEqual((result['result'], result['area_mm2']), ('PASS', 84))
        for center in ([2, 2], [3, 5], [2.8, 5]):
            board['vias'][0]['at'] = center
            self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')
        board['vias'] = []
        board['footprints']['H'] = {'pads': {'': [{'at': [5, 5], 'rotation': 90,
                                                   'drill_size': [1, 2], 'drill_offset': [0, 0]}]}}
        self.assertEqual(check_copper_area(board, rule)['result'], 'PASS')
        board['footprints']['H']['pads'][''][0]['drill_offset'] = [3, 0]
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_wrong_net_and_other_layer_never_add_area(self):
        board, rule = fixture()
        rule['min_area']['value'] = 100
        other = deepcopy(board['zones'][0])
        other.update(net='OTHER', filled_polygons=[rectangle(0, 0, 80, 80)])
        board['zones'].append(other)
        self.assertEqual(check_copper_area(board, rule)['result'], 'FAIL')
        other['net'], other['layer'] = 'N', 'B.Cu'
        self.assertEqual(check_copper_area(board, rule)['result'], 'FAIL')
        board['vias'] = [{'net': 'N', 'at': [90, 90], 'drill': .3}]
        self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_finite_inputs_and_resource_caps(self):
        board, rule = fixture()
        for limits in ({'max_vertices': 3}, {'max_work': 1}, {'max_work': float('inf')}):
            self.assertEqual(check_copper_area(board, rule, **limits)['result'], 'NOT_CHECKABLE')
        for value in (float('nan'), float('inf'), True):
            changed = deepcopy(board)
            changed['zones'][0]['filled_polygons'][0][0][0] = value
            self.assertEqual(check_copper_area(changed, rule)['result'], 'NOT_CHECKABLE')

    def test_malformed_topology_and_outside_board(self):
        bad = [[[0, 0], [4, 4], [0, 4], [4, 0]],
               [[0, 0], [4, 0], [2, 0], [4, 4], [0, 4]],
               [[0, 0], [4, 0], [4, 0], [4, 4], [0, 4]], rectangle(-101, 0, 4, 4)]
        for points in bad:
            board, rule = fixture([points])
            self.assertEqual(check_copper_area(board, rule)['result'], 'NOT_CHECKABLE')

    def test_simple_polygon_partition_area_equivalence_and_order(self):
        board, rule = fixture([rectangle(0, 0, 2, 2), rectangle(3, 0, 5, 2)])
        board['footprints']['U']['pads']['1'][0].update(at=[2.5, 1], size=[6, 2])
        one = check_copper_area(board, rule)
        board['zones'][0]['filled_polygons'].reverse()
        two = check_copper_area(board, rule)
        self.assertEqual(one['area_mm2'], 8)
        self.assertEqual(one['result'], two['result'])
        self.assertEqual(one['area_mm2'], two['area_mm2'])


if __name__ == '__main__':
    unittest.main()
