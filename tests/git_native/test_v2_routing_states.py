"""Native unlocked copper gets the installed router's unfixed state token."""
import unittest
from pcbknowledge.v2.routing_states import normalize_native_wire_states
from pcbknowledge.v2.specctra import read_specctra

BOARD = '(kicad_pcb (segment (start 0 0) (end 1 0)) (via (at 1 0)))'
DSN = '''(pcb synthetic (structure (rule (width 150)))
 (wiring (wire (path F.Cu 150 0 0 1000 0) (net N) (type route))
 (via V 1000 0 (net N) (type route))))'''


class WireStateTests(unittest.TestCase):
    def test_only_type_changed_and_idempotent(self):
        text, receipt = normalize_native_wire_states(DSN, BOARD)
        expected = read_specctra(DSN.replace('(type route)', '(type normal)'))
        self.assertEqual(read_specctra(text), expected)
        self.assertEqual(receipt['normalized_route'], 2)
        repeated, second = normalize_native_wire_states(text, BOARD)
        self.assertEqual(repeated, text)
        self.assertEqual(second['normalized_route'], 0)
        self.assertEqual(second['already_normal'], 2)

    def test_explicit_fixed_normal_absent_unchanged(self):
        for state in ('normal', 'protect', 'fix', 'shoveFixed', 'shove_fixed'):
            with self.subTest(state=state):
                source = DSN.replace('type route', 'type ' + state)
                projected, _ = normalize_native_wire_states(source, BOARD)
                self.assertEqual(read_specctra(projected), read_specctra(source))
        source = DSN.replace('(type route)', '')
        projected, receipt = normalize_native_wire_states(source, BOARD)
        self.assertEqual(read_specctra(projected), read_specctra(source))
        self.assertEqual(receipt['implicit_unfixed'], 2)

    def test_unknown_duplicate_empty_quoted_rejected(self):
        tokens = ('(type unknown)', '(type)', '(type route route)',
                  '(type "route")', '(type route)(type normal)')
        for token in tokens:
            with self.subTest(token=token), self.assertRaises(ValueError):
                normalize_native_wire_states(DSN.replace('(type route)', token, 1), BOARD)

    def test_locked_source_rejected(self):
        values = ('locked', '(locked)', '(locked yes)', '(locked maybe)',
                  '(locked no)(locked no)')
        for locked in values:
            with self.subTest(locked=locked), self.assertRaises(ValueError):
                normalize_native_wire_states(DSN, BOARD.replace('(segment', '(segment ' + locked, 1))
        _, receipt = normalize_native_wire_states(DSN, BOARD.replace('(segment', '(segment (locked no)', 1))
        self.assertEqual(receipt['normalized_route'], 2)

    def test_source_groups_fail_closed(self):
        for group in ('(group G)', '(group G (locked yes))', '(group G locked)'):
            with self.subTest(group=group), self.assertRaises(ValueError):
                normalize_native_wire_states(DSN, BOARD[:-1] + group + ')')

    def test_duplicate_wiring_or_wrong_root_rejected(self):
        for text in ('(pcb x (wiring)(wiring))', '(session x)'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                normalize_native_wire_states(text, BOARD)
        with self.assertRaises(ValueError):
            normalize_native_wire_states(DSN, '(footprint synthetic)')


if __name__ == '__main__':
    unittest.main()
