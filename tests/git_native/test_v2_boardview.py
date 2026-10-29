"""Original small board fixtures for the read-only KiCad projection."""
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.sexpr import Atom, dumps, parse

BOARD = '''(kicad_pcb (version 20241229) (net 0 "") (net 1 "VCC")
(gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts"))
(footprint "test:part" (layer "F.Cu") (at 10 20 90)
(property "Reference" "U1")
(fp_rect (start -2 -3) (end 2 3) (layer "F.CrtYd"))
(pad "1" smd rect (at 2 3 90) (size 1 2) (layers "F.Cu") (net 1 "VCC"))
(pad "1" smd rect (at 2 -3 90) (size 1 2) (layers "F.Cu") (net 1 "VCC")))
(segment (start 13 18) (end 20 18) (width 0.3) (layer "F.Cu") (net 1))
(arc (start 20 18) (mid 21 19) (end 22 18) (width 0.3) (layer "F.Cu") (net 1))
(via (at 20 18) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1))
(zone (net 1) (layer "F.Cu")
(polygon (pts (xy 1 1) (xy 5 1) (xy 5 5)))
(filled_polygon (layer "F.Cu") (pts (xy 1 1) (xy 5 1) (xy 5 5)))))'''


class SExpressionTests(unittest.TestCase):
    def test_quotes_comments_and_roundtrip(self):
        text = '(root ; comment\n (name "quote\\\" and \\\\slash") (value 1.2))'
        result = parse(text)
        self.assertIsInstance(result[0], Atom)
        self.assertEqual(parse(dumps(result)), result)
        self.assertEqual(result[1][1], 'quote" and \\slash')

    def test_malformed_and_depth_are_rejected(self):
        for text in ('', 'atom', '(', ')', '(a)(b)', '("unterminated)', '(' * 129 + ')' * 129):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)


class BoardViewTests(unittest.TestCase):
    def test_rotation_aliases_outline_and_routing(self):
        board = board_from_text(BOARD)
        component = board['footprints']['U1']
        self.assertEqual(component['library'], 'test:part')
        self.assertEqual(component['pads']['1'][0]['at'], [13.0, 18.0])
        self.assertEqual(component['pads']['1'][1]['at'], [7.0, 18.0])
        self.assertEqual(component['bounds'], [7.0, 18.0, 13.0, 22.0])
        self.assertTrue(board['outline']['rectangular'])
        self.assertTrue(board['outline']['closed'])
        self.assertEqual(board['outline']['bounds'], [0, 0, 40, 30])
        for kind in ('segments', 'arcs', 'vias', 'zones'):
            self.assertEqual(len(board[kind]), 1)
            self.assertEqual(board[kind][0]['net'], 'VCC')
        self.assertEqual(len(board['zones'][0]['filled_polygons'][0]), 3)

    def test_bottom_uses_already_flipped_file_local_coordinates(self):
        # KiCad 9.0.2 SaveBoard after Flip stores local (2,-3), angle90,
        # world (7,18); do not reflect these saved coordinates a second time.
        changed = BOARD.replace('(layer "F.Cu") (at 10 20 90)', '(layer "B.Cu") (at 10 20 90)')
        board = board_from_text(changed)
        self.assertEqual(board['footprints']['U1']['pads']['1'][1]['at'], [7.0, 18.0])

    def test_duplicate_reference_and_net_and_nonfinite_rejected(self):
        root = parse(BOARD)
        footprint = next(item for item in root if isinstance(item, list) and item[0] == 'footprint')
        with self.assertRaisesRegex(ValueError, 'Duplicate footprint'):
            board_from_text(dumps(root + [footprint]))
        for changed in (BOARD.replace('(at 10 20 90)', '(at nan 20 90)'),
                        BOARD.replace('(net 1 "VCC")', '(net 1 "VCC") (net 1 "VCC")', 1),
                        BOARD.replace('(net 1 "VCC")', '(net 9 "VCC")', 1),
                        BOARD.replace('(size 1 2)', '(size -1 2)', 1)):
            with self.assertRaises(ValueError):
                board_from_text(changed)

    def test_unsupported_curved_outline_is_explicit(self):
        changed = BOARD.replace('(gr_rect (start 0 0) (end 40 30) (layer "Edge.Cuts"))',
                                '(gr_circle (center 0 0) (end 40 30) (layer "Edge.Cuts"))')
        board = board_from_text(changed)
        self.assertFalse(board['outline']['closed'])
        self.assertFalse(board['outline']['rectangular'])
        self.assertTrue(board['unsupported'])

    def test_ambiguous_filled_zone_layer_is_not_silently_accepted(self):
        changed = BOARD.replace('(filled_polygon (layer "F.Cu")', '(filled_polygon (layer "B.Cu")')
        self.assertTrue(board_from_text(changed)['unsupported'])

    def test_nonpositive_route_dimensions_rejected(self):
        for value in ('0', '-0.3', 'nan'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                board_from_text(BOARD.replace('(width 0.3)', '(width ' + value + ')'))

    def test_open_courtyard_is_not_an_enclosure(self):
        board = board_from_text(BOARD.replace('fp_rect', 'fp_line'))
        self.assertFalse(board['footprints']['U1']['courtyard_closed'])
        self.assertTrue(board['unsupported'])

    def test_open_outline_does_not_claim_closed(self):
        changed = BOARD.replace('gr_rect', 'gr_line')
        self.assertFalse(board_from_text(changed)['outline']['closed'])
