"""Whole-corridor return-copper measurements, including interior gaps."""
import copy
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.layout import LayoutChecks
from pcbknowledge.v2.layout_return import check_return_path, contains, point


def board():
    return {'unsupported': [], 'copper_layers': ['F.Cu', 'B.Cu'], 'arcs': [], 'vias': [],
            'outline': {'closed': True, 'rectangular': True},
            'segments': [{'net': 'SIGNAL', 'layer': 'F.Cu', 'width': .2, 'start': [1, 1], 'end': [9, 1]}],
            'zones': [{'net': 'GND', 'layer': 'B.Cu', 'layers': [],
                       'filled_polygons': [[[0, 0], [10, 0], [10, 2], [0, 2]]]}],
            'footprints': {'J1': {'pads': {'1': [{'at': [.5, 1], 'net': 'GND', 'kind': 'smd',
                                               'layers': ['B.Cu'], 'size': [.2, .2], 'geometry_unsupported': False}]}}}}


RULE = {'kind': 'RETURN_PATH', 'net': 'SIGNAL', 'return_net': 'GND'}


class ReturnPathTests(unittest.TestCase):
    def test_exported_board_projection_is_measured_without_mutation(self):
        text = '''(kicad_pcb (version 20241229)
          (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
          (net 1 "SIGNAL") (net 2 "GND")
          (gr_rect (start 0 0) (end 10 2) (layer "Edge.Cuts"))
          (footprint "Test:Return" (layer "B.Cu") (at 0.5 1)
            (property "Reference" "J1")
            (pad "1" smd rect (at 0 0) (size 0.2 0.2) (layers "B.Cu") (net 2 "GND")))
          (segment (start 1 1) (end 9 1) (width 0.2) (layer "F.Cu") (net 1))
          (zone (net 2) (layer "B.Cu")
            (filled_polygon (layer "B.Cu") (pts (xy 0 0) (xy 10 0) (xy 10 2) (xy 0 2)))))'''
        sample = board_from_text(text)
        original = copy.deepcopy(sample)
        self.assertEqual(check_return_path(sample, RULE)['result'], 'PASS')
        self.assertEqual(sample, original)
        slotted = text[:-1] + '(gr_rect (start 4 0.5) (end 6 1.5) (layer "Edge.Cuts")))'
        self.assertEqual(check_return_path(board_from_text(slotted), RULE)['result'], 'NOT_CHECKABLE')

    def test_supported_corridor_and_minimal_layout_registration(self):
        sample = board()
        result = check_return_path(sample, RULE)
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(result['segments'][0]['observed_boundary_distance_squared_mm2'], 1)
        checker = LayoutChecks.__new__(LayoutChecks)
        checker.board = sample
        self.assertEqual(checker.check(RULE), result)

    def test_interior_slot_is_not_hidden_by_covered_endpoints(self):
        sample = board()
        sample['zones'][0]['filled_polygons'] = [
            [[0, 0], [10, 0], [10, 2], [5.01, 2], [5.01, .5], [5, .5], [5, 2], [0, 2]]]
        result = check_return_path(sample, RULE)
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['failed_segments'], [0])

    def test_entire_track_width_not_only_centerline_is_required(self):
        sample = board()
        sample['segments'][0]['start'][1] = .1
        sample['segments'][0]['end'][1] = .1
        self.assertEqual(check_return_path(sample, RULE)['result'], 'PASS')
        sample['segments'][0]['end'][1] = .099999
        self.assertEqual(check_return_path(sample, RULE)['result'], 'FAIL')

    def test_wrong_net_layer_and_unconnected_island_fail(self):
        for mutation in (lambda b: b['zones'][0].update(net='OTHER'),
                         lambda b: b['zones'][0].update(layer='F.Cu'),
                         lambda b: b['footprints']['J1']['pads']['1'][0].update(at=[20, 20]),
                         lambda b: b['zones'][0].update(filled_polygons=[])):
            sample = board()
            mutation(sample)
            self.assertEqual(check_return_path(sample, RULE)['result'], 'FAIL')

    def test_every_segment_is_checked(self):
        sample = board()
        outside = copy.deepcopy(sample['segments'][0])
        outside.update(start=[1, 4], end=[9, 4])
        sample['segments'].append(outside)
        result = check_return_path(sample, RULE)
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['failed_segments'], [1])

    def test_unsupported_and_empty_routes_never_pass(self):
        for mutation in (lambda b: b.update(unsupported=['zone hole']),
                         lambda b: b.update(copper_layers=['F.Cu', 'In1.Cu', 'B.Cu']),
                         lambda b: b.update(segments=[]),
                         lambda b: b['arcs'].append({'net': 'SIGNAL'}),
                         lambda b: b['vias'].append({'net': 'SIGNAL'}),
                         lambda b: b['zones'][0].update(filled_polygons=[[[0, 0], [1, 1], [0, 1], [1, 0]]])):
            sample = board()
            mutation(sample)
            self.assertEqual(check_return_path(sample, RULE)['result'], 'NOT_CHECKABLE')

    def test_pad_hole_cannot_count_as_return_contact(self):
        sample = board()
        sample['footprints']['J1']['pads']['1'][0].update(kind='np_thru_hole', drill=2)
        self.assertEqual(check_return_path(sample, RULE)['result'], 'NOT_CHECKABLE')

    def test_pad_edge_and_via_only_possible_contact_are_not_false_failures(self):
        sample = board()
        sample['footprints']['J1']['pads']['1'][0]['at'] = [-.05, 1]
        self.assertEqual(check_return_path(sample, RULE)['result'], 'NOT_CHECKABLE')
        sample['footprints']['J1']['pads']['1'][0]['at'] = [20, 20]
        sample['vias'].append({'net': 'GND', 'at': [.5, 1], 'size': .6, 'drill': .3})
        self.assertEqual(check_return_path(sample, RULE)['result'], 'NOT_CHECKABLE')

    def test_near_diagonal_boundary_has_no_epsilon_inside_fallback(self):
        polygon = [point(p) for p in [[0, 0], [10, 10], [0, 10]]]
        self.assertTrue(contains(point([1, 1]), polygon))
        self.assertFalse(contains(point([1, .99999999999]), polygon))

    def test_outline_slots_and_intersecting_physical_drills_remain_unknown(self):
        sample = board()
        sample['outline']['closed'] = False
        self.assertEqual(check_return_path(sample, RULE)['result'], 'NOT_CHECKABLE')
        sample = board()
        sample['footprints']['H1'] = {'pads': {'': [{'at': [5, 1], 'drill': 1, 'drill_size': [1, 1]}]}}
        self.assertEqual(check_return_path(sample, RULE)['result'], 'NOT_CHECKABLE')
        sample['footprints']['H1']['pads'][''][0]['at'] = [5, 5]
        self.assertEqual(check_return_path(sample, RULE)['result'], 'PASS')
