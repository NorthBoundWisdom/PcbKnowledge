"""Native variant normalization preserves electrical and placement identity."""
from copy import deepcopy
import unittest
from pcbknowledge.v2.specctra import _validate_placements


def fixture():
    electrical = [['pin', 'rect', '1', '2', '3'], ['keepout', '', ['circle', 'F.Cu', '1', '0', '0']]]
    dsn = ['pcb', 'x', ['library', ['image', 'chip', *deepcopy(electrical), ['outline', 'a']],
                      ['image', 'chip::1', *deepcopy(electrical), ['outline', 'b']]]]
    return dsn, {'R1': ('chip', 2, 3, 'front', 90)}, {'R1': ('chip::1', 2, 3, 'front', 90)}


class AliasTests(unittest.TestCase):
    def test_only_outline_variant_is_accepted(self):
        _validate_placements(*fixture())

    def test_arbitrary_rename_missing_image_and_changed_pin_or_keepout_are_rejected(self):
        for kind in ('rename', 'missing', 'pin', 'keepout', 'extra', 'duplicate'):
            dsn, actual, original = fixture()
            if kind == 'rename':
                actual['R1'] = ('other', 2, 3, 'front', 90)
            elif kind == 'missing':
                dsn[2].pop(1)
            elif kind == 'pin':
                dsn[2][2][2][3] = '99'
            elif kind == 'keepout':
                dsn[2][2][3][2][2] = '99'
            elif kind == 'extra':
                dsn[2][2].append(['pin', 'rect', '2', '2', '3'])
            else:
                dsn[2].append(deepcopy(dsn[2][1]))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                _validate_placements(dsn, actual, original)

    def test_reference_position_rotation_and_side_remain_exact(self):
        for index, value in ((1, 2.1), (2, 3.1), (3, 'back'), (4, 180)):
            dsn, actual, original = fixture()
            row = list(actual['R1'])
            row[index] = value
            actual['R1'] = tuple(row)
            with self.assertRaises(ValueError):
                _validate_placements(dsn, actual, original)
        dsn, actual, original = fixture()
        actual['R2'] = actual.pop('R1')
        with self.assertRaises(ValueError):
            _validate_placements(dsn, actual, original)

    def test_exact_names_need_no_alias_and_non_native_suffix_is_rejected(self):
        dsn, actual, original = fixture()
        actual['R1'] = original['R1']
        _validate_placements(dsn, actual, original)
        for name in ('chip:1', 'chip::0', 'chip::abc'):
            dsn, actual, original = fixture()
            original['R1'] = (name, 2, 3, 'front', 90)
            with self.assertRaises(ValueError):
                _validate_placements(dsn, actual, original)

    def test_missing_session_placement_is_rejected(self):
        dsn, actual, original = fixture()
        with self.assertRaises(ValueError):
            _validate_placements(dsn, {}, original)
        _validate_placements(dsn, {}, {})

    def test_electrical_image_elements_and_counts_are_never_normalized(self):
        for kind in ('place_keepout', 'via_keepout', 'side', 'padstack', 'duplicate', 'missing-variant', 'malformed'):
            dsn, actual, original = fixture()
            variant = dsn[2][2]
            if kind in ('place_keepout', 'via_keepout', 'side'):
                variant.append([kind, 'different'])
            elif kind == 'padstack':
                variant[2][1] = 'other-stack'
            elif kind == 'duplicate':
                variant.append(deepcopy(variant[2]))
            elif kind == 'missing-variant':
                dsn[2].pop(2)
            else:
                dsn[2].append(['image'])
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                _validate_placements(dsn, actual, original)

    def test_added_missing_reference_and_small_physical_changes_fail(self):
        for kind in ('added', 'missing', 'micrometer', 'degree'):
            dsn, actual, original = fixture()
            if kind == 'added':
                actual['R2'] = actual['R1']
            elif kind == 'missing':
                actual.clear()
            elif kind == 'micrometer':
                actual['R1'] = ('chip', 2.001, 3, 'front', 90)
            else:
                actual['R1'] = ('chip', 2, 3, 'front', 91)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                _validate_placements(dsn, actual, original)

    def test_full_session_preflight_accepts_only_electrically_identical_alias(self):
        from pcbknowledge.v2.specctra import validate_session
        dsn = """(pcb board (unit mm) (resolution mm 1000)
         (structure (layer F.Cu) (layer B.Cu) (via VIA))
         (placement (component chip::1 (place R1 2 3 front 90)))
         (library (image chip (pin PAD 1 0 0)) (image chip::1 (pin PAD 1 0 0))
          (padstack VIA (shape (circle F.Cu .8)) (shape (circle B.Cu .8))))
         (network (net GND (pins R1-1))))"""
        ses = """(session board (base_design board)
         (placement (resolution mm 1000) (component chip (place R1 2000 3000 front 90)))
         (routes (resolution mm 1000) (library_out
           (padstack VIA (shape (circle F.Cu 800)) (shape (circle B.Cu 800))))
          (network_out (net GND (wire (path F.Cu 150 2000 3000 4000 3000))))))"""
        self.assertEqual(validate_session(ses, dsn, {'GND': .15}, dsn_name='board.dsn')['wire_count'], 1)
        with self.assertRaises(ValueError):
            validate_session(ses.replace('2000 3000 front', '2001 3000 front'), dsn,
                             {'GND': .15}, dsn_name='board.dsn')
        with self.assertRaises(ValueError):
            validate_session(ses, dsn.replace('image chip::1 (pin PAD', 'image chip::1 (pin OTHER'),
                             {'GND': .15}, dsn_name='board.dsn')

    def test_equally_malformed_image_children_cannot_enable_aliases(self):
        for child in ('unexpected-atom', [], [[]]):
            dsn, actual, original = fixture()
            for image in dsn[2][1:]:
                image.append(deepcopy(child))
            with self.subTest(child=child), self.assertRaisesRegex(ValueError, 'Malformed DSN image child'):
                _validate_placements(dsn, actual, original)
