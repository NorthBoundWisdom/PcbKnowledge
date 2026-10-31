"""Unprojected conductive drawings cannot silently preserve a layout PASS."""
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.layout import check_layout
from tests.git_native.test_v2_layout import FixtureCatalog, board_text, intent


class CopperGraphicsTests(unittest.TestCase):
    def test_board_copper_shapes_and_text_are_explicitly_unsupported(self):
        objects = [
            '(gr_line (start 2 2) (end 5 5) (width 0.2) (layer "F.Cu"))',
            '(gr_rect (start 2 2) (end 5 5) (fill solid) (layer "B.Cu"))',
            '(gr_poly (pts (xy 2 2) (xy 5 2) (xy 5 5)) (fill solid) (layer "F.Cu"))',
            '(gr_text "conductive" (at 2 2) (layer "F.Cu"))',
            '(gr_text_box "conductive" (start 2 2) (end 5 5) (layer "F.Cu"))',
        ]
        for item in objects:
            with self.subTest(item=item):
                board = board_from_text(board_text()[:-1] + item + ')')
                self.assertTrue(any('unprojected copper object' in reason for reason in board['unsupported']))
                report = check_layout(board, intent(), FixtureCatalog())
                self.assertEqual(report['result'], 'NOT_CHECKABLE', report)

    def test_footprint_copper_graphics_cannot_hide_a_branch(self):
        for item in ('(fp_line (start 0 0) (end 3 3) (layer "F.Cu"))',
                     '(fp_text user "copper" (at 0 0) (layer "F.Cu"))',
                     '(property "Value" "copper" (at 0 0) (layer "B.Cu"))'):
            with self.subTest(item=item):
                text = board_text().replace('(property "Reference" "A")',
                                            '(property "Reference" "A")' + item)
                board = board_from_text(text)
                self.assertTrue(any(reason.startswith('A: unprojected copper object')
                                    for reason in board['unsupported']))
                self.assertEqual(check_layout(board, intent(), FixtureCatalog())['result'], 'NOT_CHECKABLE')

    def test_non_copper_graphics_and_known_copper_keep_existing_measurements(self):
        for layer in ('F.SilkS', 'F.Fab', 'Cmts.User'):
            with self.subTest(layer=layer):
                item = f'(gr_text "annotation" (at 2 2) (layer "{layer}"))'
                board = board_from_text(board_text()[:-1] + item + ')')
                self.assertEqual(board['unsupported'], [])
                self.assertEqual(check_layout(board, intent(), FixtureCatalog())['result'], 'PASS')

    def test_multilayer_unknown_copper_is_not_dropped(self):
        text = board_text()[:-1] + '(future_shape (layers "F.Cu" "B.Cu")))'
        self.assertTrue(board_from_text(text)['unsupported'])
