"""Copper-edge distances use complete pads and exact threshold comparisons."""
import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from pcbknowledge.v2.layout_distance import check_copper_edge, distance_leq
from pcbknowledge.v2.boardview import board_from_text


def pad(at, size=(2, 2), *, net='VIN', layer='F.Cu', shape='rect', rotation=0):
    return {'at': list(at), 'size': list(size), 'net': net, 'layers': [layer],
            'shape': shape, 'rotation': rotation, 'kind': 'smd', 'drill': None}


def fixture():
    board = {'copper_layers': ['F.Cu', 'B.Cu'], 'footprints': {
        'C1': {'pads': {'1': [pad((0, 0))], '2': [pad((1, 0), net='GND')]}},
        'U1': {'pads': {'7': [pad((3, 0))]}}}}
    rule = {'kind': 'PLACE_NEAR', 'subject': 'C1', 'target': 'U1.pin:7',
            'datum': 'COPPER_EDGE', 'max_distance': {'value': 1, 'unit': 'mm'}}
    return board, rule


class CopperDistanceTests(unittest.TestCase):
    def test_rect_edge_exact_limit_and_one_nanometre_excess(self):
        board, rule = fixture()
        original = copy.deepcopy((board, rule))
        result = check_copper_edge(board, rule)
        self.assertEqual((result['result'], result['distance_mm']), ('PASS', 1))
        self.assertEqual((result['subject_pad'], result['target_pad']), ('C1.pin:1', 'U1.pin:7'))
        self.assertEqual(result['common_layers'], ['F.Cu'])
        self.assertEqual((board, rule), original)
        board['footprints']['U1']['pads']['7'][0]['at'][0] = 3.000001
        self.assertEqual(check_copper_edge(board, rule)['result'], 'FAIL')

    def test_nearest_same_net_pad_not_nearest_other_net(self):
        board, rule = fixture()
        board['footprints']['C1']['pads']['2'][0]['at'] = [3, 0]
        result = check_copper_edge(board, rule)
        self.assertEqual(result['subject_pad'], 'C1.pin:1')
        self.assertEqual(result['distance_mm'], 1)
        board['footprints']['C1']['pads']['1'][0]['net'] = 'OTHER'
        result = check_copper_edge(board, rule)
        self.assertEqual((result['result'], result['reason_code']), ('NOT_CHECKABLE', 'NO_SAME_NET_PAD'))

    def test_cardinal_rotation_changes_edges_not_centers(self):
        board, rule = fixture()
        board['footprints']['C1']['pads']['1'] = [pad((0, 0), (4, 1), rotation=90)]
        board['footprints']['U1']['pads']['7'] = [pad((3, 0), (1, 1))]
        self.assertEqual(check_copper_edge(board, rule)['distance_mm'], 2)
        self.assertEqual(check_copper_edge(board, rule)['result'], 'FAIL')
        board['footprints']['C1']['pads']['1'][0]['rotation'] = 0
        self.assertEqual(check_copper_edge(board, rule)['distance_mm'], 0.5)
        self.assertEqual(check_copper_edge(board, rule)['result'], 'PASS')

    def test_circle_and_oval_capsule_edges(self):
        for shape, at, size in [('circle', (3, 0), (2, 2)), ('oval', (4, 0), (4, 2))]:
            board, rule = fixture()
            board['footprints']['U1']['pads']['7'] = [pad(at, size, shape=shape)]
            result = check_copper_edge(board, rule)
            self.assertEqual((result['result'], result['distance_mm']), ('PASS', 1))
        board['footprints']['C1']['pads']['1'] = [pad((0, 0), shape='circle')]
        board['footprints']['U1']['pads']['7'] = [pad((3, 4), shape='circle')]
        rule['max_distance']['value'] = 3
        self.assertEqual(check_copper_edge(board, rule)['distance_mm'], 3)
        self.assertEqual(check_copper_edge(board, rule)['result'], 'PASS')

    def test_layer_mismatch_and_missing_selection_are_typed(self):
        board, rule = fixture()
        board['footprints']['U1']['pads']['7'][0]['layers'] = ['B.Cu']
        result = check_copper_edge(board, rule)
        self.assertEqual(result['reason_code'], 'NO_COMMON_COPPER_LAYER')
        board['footprints']['C1']['pads']['1'][0]['layers'] = ['B.Cu']
        self.assertEqual(check_copper_edge(board, rule)['result'], 'PASS')
        board['copper_layers'] = ['F.Cu']
        self.assertEqual(check_copper_edge(board, rule)['reason_code'], 'NO_COMMON_COPPER_LAYER')
        board['footprints']['U1']['pads']['7'] = []
        self.assertEqual(check_copper_edge(board, rule)['reason_code'], 'MISSING_PAD')
        del board['footprints']['U1']
        self.assertEqual(check_copper_edge(board, rule)['reason_code'], 'MISSING_COMPONENT')

    def test_all_eligible_geometry_is_checked_even_if_one_pair_passes(self):
        for change in ({'shape': 'roundrect'}, {'rotation': 45}, {'drill': 0.3}, {'geometry_unsupported': True}):
            board, rule = fixture()
            extra = copy.deepcopy(board['footprints']['U1']['pads']['7'][0])
            extra.update(change)
            board['footprints']['U1']['pads']['7'].append(extra)
            result = check_copper_edge(board, rule)
            code = 'DRILL_INTERSECTION' if 'drill' in change else 'UNSUPPORTED_GEOMETRY'
            self.assertEqual((result['result'], result['reason_code']), ('NOT_CHECKABLE', code))

    def test_duplicate_physical_pads_and_overlap_choose_measured_pair(self):
        board, rule = fixture()
        board['footprints']['U1']['pads']['7'].append(pad((1.5, 0)))
        rule['max_distance']['value'] = 0
        result = check_copper_edge(board, rule)
        self.assertEqual((result['result'], result['distance_mm'], result['target_pad_index']), ('PASS', 0, 1))

    def test_invalid_datum_limit_and_target_do_not_fallback_to_centers(self):
        for change in ({'datum': 'ORIGIN_PAD_CENTER'}, {'target': 'U1'},
                       {'max_distance': {'value': -1, 'unit': 'mm'}},
                       {'max_distance': {'value': True, 'unit': 'mm'}}):
            board, rule = fixture()
            rule.update(change)
            self.assertEqual(check_copper_edge(board, rule)['reason_code'], 'INVALID_RULE')

    def test_projected_rotated_export_has_hand_checked_world_coordinates(self):
        board = board_from_text('''(kicad_pcb (version 20241229)
          (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) (net 1 "VIN")
          (footprint "TEST:C" (layer "F.Cu") (at 10 10 90)
            (property "Reference" "C1")
            (pad "1" smd rect (at 1 0 90) (size 4 1) (layers "F.Cu") (net 1 "VIN")))
          (footprint "TEST:U" (layer "F.Cu") (at 12 9)
            (property "Reference" "U1")
            (pad "7" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "VIN"))))''')
        _, rule = fixture()
        self.assertEqual(board['footprints']['C1']['pads']['1'][0]['at'], [10, 9])
        result = check_copper_edge(board, rule)
        self.assertEqual((result['result'], result['distance_mm']), ('PASS', 1))

    def test_unrelated_hole_removing_selected_pad_copper_is_not_checkable(self):
        for at in ([0, 0], [3, 0]):
            board, rule = fixture()
            hole = pad(at, (4, 4), net='', shape='circle')
            hole.update(kind='np_thru_hole', drill=4, drill_size=[4, 4], layers=['*.Cu'])
            board['footprints']['H1'] = {'pads': {'': [hole]}}
            result = check_copper_edge(board, rule)
            self.assertEqual((result['result'], result['reason_code']), ('NOT_CHECKABLE', 'DRILL_INTERSECTION'))
        board, rule = fixture()
        board['vias'] = [{'at': [0, 0], 'size': 0.6, 'drill': 0.3, 'net': 'OTHER'}]
        self.assertEqual(check_copper_edge(board, rule)['reason_code'], 'DRILL_INTERSECTION')

    def test_unprojected_board_geometry_cannot_produce_pass(self):
        board, rule = fixture()
        board['unsupported'] = ['Unsupported copper primitive']
        result = check_copper_edge(board, rule)
        self.assertEqual((result['result'], result['reason_code']), ('NOT_CHECKABLE', 'UNSUPPORTED_GEOMETRY'))

    def test_exact_radical_ordering(self):
        with localcontext() as context:
            context.prec = 60
            for a in range(1, 12):
                for b in range(1, 12):
                    for r, s in [(0, 0), (1, 2), (2, 1), (Fraction(1, 3), Fraction(2, 3))]:
                        dr, ds = Decimal(r.numerator) / Decimal(r.denominator), Decimal(s.numerator) / Decimal(s.denominator)
                        expected = max(Decimal(0), Decimal(a).sqrt() - dr) <= max(Decimal(0), Decimal(b).sqrt() - ds)
                        self.assertEqual(distance_leq(Fraction(a), r, Fraction(b), s), expected)


if __name__ == '__main__':
    unittest.main()
