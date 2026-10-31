"""Five-terminal drawings define the shorter row's pitch independently."""
from copy import deepcopy
import unittest

from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.schema import validate
from tests.git_native.test_v2_footprints import package
from tests.git_native.test_v2_record_contracts import quantity


def drawing():
    return package('gullwing_two_side', count=5, length=3.05, width=1.75, height=1.45,
                   lead_span=3, lead_width=.5, lead_length=.6, pitch=.95, opposite_pitch=1.9)


class UnequalRowPitchTests(unittest.TestCase):
    def test_independent_hand_calculated_terminal_coordinates(self):
        value = drawing()
        validate(value, 'package.schema.json')
        pads = {pad['number']: pad for pad in derive_footprint(value)['pads']}
        expected = {'1': -.95, '2': 0, '3': .95, '4': .95, '5': -.95}
        self.assertEqual({number: pad['y'] for number, pad in pads.items()}, expected)
        self.assertTrue(all(pads[number]['x'] < 0 for number in ('1', '2', '3')))
        self.assertTrue(all(pads[number]['x'] > 0 for number in ('4', '5')))

    def test_missing_opposite_row_pitch_never_assumes_half_spacing(self):
        value = drawing()
        del value['drawing']['opposite_pitch']
        with self.assertRaisesRegex(ValueError, 'opposite_pitch'):
            derive_footprint(value)

    def test_mutation_moves_only_the_opposite_row(self):
        value = drawing()
        original = derive_footprint(value)['pads']
        value['drawing']['opposite_pitch'] = quantity(1.6, 'mm')
        changed = derive_footprint(value)['pads']
        self.assertEqual(original[:3], changed[:3])
        self.assertEqual([pad['y'] for pad in changed[3:]], [.8, -.8])

    def test_bad_dimension_and_unsupported_generators_refuse(self):
        for invalid in (quantity(0, 'mm'), quantity(-1, 'mm'), quantity(1.9, 'V'),
                        quantity(float('inf'), 'mm'), {'status': 'UNKNOWN'}):
            value = drawing()
            value['drawing']['opposite_pitch'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                derive_footprint(value)
        for generator, count in [('gullwing_two_side', 3), ('gullwing_two_side', 6),
                                 ('gullwing_four_side', 8), ('chip', 2)]:
            value = deepcopy(drawing())
            value['generator'], value['drawing']['pin_count'] = generator, count
            with self.subTest(generator=generator, count=count), self.assertRaisesRegex(ValueError, 'Opposite'):
                derive_footprint(value)


if __name__ == '__main__':
    unittest.main()
