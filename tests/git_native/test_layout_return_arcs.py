"""Arc enclosure proof never treats a chord or sampled points as the curve."""
import copy
from fractions import Fraction
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.layout_return import check_return_path
from pcbknowledge.v2.layout_return_arcs import ceil_radius_nm, circle_box

RULE = {'kind': 'RETURN_PATH', 'net': 'SIGNAL', 'return_net': 'GND'}
TEXT = '''(kicad_pcb (version 20241229)
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
  (net 1 "SIGNAL") (net 2 "GND")
  (gr_rect (start -5 -5) (end 5 5) (layer "Edge.Cuts"))
  (footprint "Test:Return" (layer "B.Cu") (at 0 0)
    (property "Reference" "J1")
    (pad "1" smd rect (at 0 0) (size 0.2 0.2) (layers "B.Cu") (net 2 "GND")))
  (arc (start -1 0) (mid 0 1) (end 1 0) (width 0.2) (layer "F.Cu") (net 1))
  (zone (net 2) (layer "B.Cu")
    (filled_polygon (layer "B.Cu") (pts (xy -2 -2) (xy 2 -2) (xy 2 2) (xy -2 2)))))'''


class ReturnArcTests(unittest.TestCase):
    def test_native_arc_positive_and_read_only(self):
        board = board_from_text(TEXT)
        original = copy.deepcopy(board)
        result = check_return_path(board, RULE)
        self.assertEqual(result['result'], 'PASS', result)
        self.assertEqual(result['arcs'][0]['enclosure_bounds_mm'], [-1, -1, 1, 1])
        self.assertEqual(board, original)

    def test_exact_outward_radius_at_and_above_nm_boundary(self):
        self.assertEqual(ceil_radius_nm(Fraction(1)), 1)
        self.assertEqual(ceil_radius_nm(Fraction(1) + Fraction(1, 10**30)), Fraction(1000001, 1000000))
        self.assertEqual(ceil_radius_nm(Fraction(2)), Fraction(1414214, 1000000))
        self.assertEqual(circle_box({'start': [0, 0], 'mid': [2, 0], 'end': [2, 2]}),
                         (1-Fraction(1414214, 1000000), 1-Fraction(1414214, 1000000),
                          1+Fraction(1414214, 1000000), 1+Fraction(1414214, 1000000)))

    def test_wrong_net_layer_or_missing_contact_is_unknown_not_geometric_failure(self):
        for mutation in (lambda b: b['zones'][0].update(net='OTHER'),
                         lambda b: b['zones'][0].update(layer='F.Cu'),
                         lambda b: b['footprints']['J1']['pads']['1'][0].update(net='OTHER')):
            board = board_from_text(TEXT)
            mutation(board)
            result = check_return_path(board, RULE)
            self.assertEqual(result['result'], 'NOT_CHECKABLE')
            self.assertEqual(result['reason_code'], 'ARC_ENCLOSURE_UNPROVED')

    def test_partial_box_even_if_arc_might_fit_is_not_a_false_failure(self):
        board = board_from_text(TEXT)
        board['zones'][0]['filled_polygons'] = [[[-2, -.2], [2, -.2], [2, 2], [-2, 2]]]
        result = check_return_path(board, RULE)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertEqual(result['reason_code'], 'ARC_ENCLOSURE_UNPROVED')

    def test_concave_interior_gap_and_disjoint_edge_cover_do_not_pass(self):
        for polygons in (
            [[[-2, -2], [2, -2], [2, 2], [.1, 2], [.1, -.1], [-.1, -.1], [-.1, 2], [-2, 2]]],
            [[[-2, -2], [2, -2], [2, -.8], [-2, -.8]],
             [[-2, .8], [2, .8], [2, 2], [-2, 2]],
             [[-2, -2], [-.8, -2], [-.8, 2], [-2, 2]],
             [[.8, -2], [2, -2], [2, 2], [.8, 2]]]):
            board = board_from_text(TEXT)
            board['zones'][0]['filled_polygons'] = polygons
            template = board['footprints']['J1']['pads']['1'][0]
            for index, at in enumerate(([0, -1.5], [0, 1.5], [-1.5, 0], [1.5, 0])):
                pad = copy.deepcopy(template)
                pad['at'] = at
                board['footprints']['J1']['pads'][str(index + 2)] = [pad]
            self.assertEqual(check_return_path(board, RULE)['result'], 'NOT_CHECKABLE')

    def test_interior_hole_cannot_hide_between_enclosure_edges(self):
        board = board_from_text(TEXT)
        board['vias'].append({'net': 'OTHER', 'at': [0, 0], 'drill': .1, 'size': .3})
        result = check_return_path(board, RULE)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertEqual(result['reason_code'], 'ARC_BOX_DRILL_INTERSECTION')
        board['vias'][0]['at'] = [4, 4]
        self.assertEqual(check_return_path(board, RULE)['result'], 'PASS')

    def test_removed_remote_return_anchor_is_not_contact_evidence(self):
        board = board_from_text(TEXT)
        board['footprints']['J1']['pads']['1'][0]['at'] = [1.7, 0]
        board['vias'].append({'net': 'OTHER', 'at': [1.7, 0], 'drill': .4, 'size': .6})
        result = check_return_path(board, RULE)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertEqual(result['reason_code'], 'ARC_ENCLOSURE_UNPROVED')

    def test_width_and_outline_are_part_of_enclosure(self):
        board = board_from_text(TEXT)
        board['outline']['bounds'] = [-1.1, -1.1, 1.1, 1.1]
        self.assertEqual(check_return_path(board, RULE)['result'], 'PASS')
        board['outline']['bounds'][0] = -1.099999
        result = check_return_path(board, RULE)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertEqual(result['reason_code'], 'ARC_BOX_OUTSIDE_OUTLINE')

    def test_degenerate_arcs_signal_vias_and_multilayer_routes_remain_unknown(self):
        for mutation in (lambda b: b['arcs'][0].update(mid=[0, 0]),
                         lambda b: b['arcs'][0].update(end=[-1, 0]),
                         lambda b: b['arcs'][0].update(width=0),
                         lambda b: b['vias'].append({'net': 'SIGNAL'}),
                         lambda b: b['segments'].append({'net': 'SIGNAL', 'layer': 'B.Cu'})):
            board = board_from_text(TEXT)
            mutation(board)
            self.assertEqual(check_return_path(board, RULE)['result'], 'NOT_CHECKABLE')


if __name__ == '__main__':
    unittest.main()
