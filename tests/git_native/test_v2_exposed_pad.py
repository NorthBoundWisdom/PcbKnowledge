"""Synthetic perimeter packages retain a distinct cited exposed thermal terminal."""
import copy
import unittest

from pcbknowledge.v2.footprints import derive_footprint
from tests.git_native.test_v2_footprints import package
from tests.git_native.test_v2_record_contracts import quantity


class ExposedPadTests(unittest.TestCase):
    def drawing(self):
        item = package('gullwing_two_side', count=8, length=5, width=4,
                       lead_span=6, lead_length=.6, lead_width=.4, pitch=1.27)
        item['drawing']['exposed_pad'] = {'number': 'EP', 'width': quantity(2.4, 'mm'),
                                          'length': quantity(3.2, 'mm')}
        return item

    def test_exposed_pad_is_centered_original_derived_geometry(self):
        original = self.drawing()
        saved = copy.deepcopy(original)
        pads = derive_footprint(original)['pads']
        self.assertEqual(original, saved)
        self.assertEqual(len(pads), 9)
        self.assertEqual(pads[-1], {'number': 'EP', 'kind': 'SMD', 'shape': 'RECT',
                                   'x': 0.0, 'y': 0.0, 'width': 2.4, 'height': 3.2, 'rotation': 0.0})

    def test_alias_collision_body_overflow_and_unsupported_generator_refuse(self):
        for change in ('alias', 'width', 'generator'):
            item = self.drawing()
            if change == 'alias':
                item['drawing']['exposed_pad']['number'] = '1'
            elif change == 'width':
                item['drawing']['exposed_pad']['width'] = quantity(4.1, 'mm')
            else:
                item['generator'] = 'chip'
                item['drawing']['pin_count'] = 2
            with self.subTest(change=change), self.assertRaises(ValueError):
                derive_footprint(item)

    def test_manufacturer_two_side_land_repeats_cited_dimensions(self):
        item = package('manufacturer_two_side_land', count=6, length=3, width=1.6,
                       pitch=.95, row_pitch=2.4, pad_width=1, pad_height=.6)
        pads = derive_footprint(item)['pads']
        self.assertEqual([(p['number'], p['x'], p['y']) for p in pads],
                         [('1', -1.2, -.95), ('2', -1.2, 0), ('3', -1.2, .95),
                          ('4', 1.2, .95), ('5', 1.2, 0), ('6', 1.2, -.95)])
        self.assertTrue(all((p['width'], p['height']) == (1, .6) for p in pads))

    def test_four_side_land_keeps_corner_clearance_without_changing_collision_guard(self):
        item = package('manufacturer_four_side_land', count=16, length=3, width=3,
                       pitch=.5, row_pitch=2.8, pad_width=.8, pad_height=.27)
        item['drawing']['exposed_pad'] = {'number': 'EXP-PAD', 'width': quantity(1, 'mm'),
                                          'length': quantity(1, 'mm')}
        pads = derive_footprint(item)['pads']
        self.assertEqual(len(pads), 17)
        self.assertEqual([(p['number'], p['x'], p['y']) for p in (pads[0], pads[4], pads[8], pads[12])],
                         [('1', -1.4, -.75), ('5', -.75, 1.4), ('9', 1.4, .75), ('13', .75, -1.4)])
        item['drawing']['row_pitch'] = quantity(2.4, 'mm')
        with self.assertRaisesRegex(ValueError, 'Overlapping physical pads'):
            derive_footprint(item)

    def test_manufacturer_land_rejects_unequal_sides_or_extra_fillets(self):
        for count, density in ((7, 'NOMINAL'), (8, 'ROBUST')):
            item = package('manufacturer_four_side_land', count=count, length=3, width=3,
                           pitch=.5, row_pitch=2.8, pad_width=.8, pad_height=.27)
            item['density'] = density
            with self.assertRaises(ValueError):
                derive_footprint(item)
