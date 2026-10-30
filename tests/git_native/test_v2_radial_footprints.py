"""Synthetic two-lead radial drawings: axes, selected holes and strict refusals."""
import copy
import unittest

from pcbknowledge.v2.footprints import derive_footprint, export_kicad
from pcbknowledge.v2.schema import validate
from tests.git_native.test_v2_footprints import package


def radial():
    result = package('radial_two_lead', length=4.3, width=4.65, height=2,
                     pitch=5.1, drill=1.2, pad_width=1.8, pad_height=1.8)
    result['mount_type'] = 'THT'
    return result


class RadialFootprintTests(unittest.TestCase):
    def test_two_round_holes_axes_courtyard_and_export(self):
        record = radial()
        original = copy.deepcopy(record)
        validate(record, 'package.schema.json')
        result = derive_footprint(record)
        self.assertEqual(record, original)
        self.assertEqual([(p['number'], p['x'], p['y']) for p in result['pads']],
                         [('1', -2.55, 0), ('2', 2.55, 0)])
        for pad in result['pads']:
            self.assertEqual((pad['kind'], pad['shape'], pad['width'], pad['height'], pad['drill']),
                             ('THROUGH_HOLE', 'ROUND', 1.8, 1.8, 1.2))
        self.assertEqual(result['courtyard'], dict(min_x=-3.7, max_x=3.7, min_y=-2.4, max_y=2.4))
        text = export_kicad(record)
        self.assertIn('(pad "1" thru_hole circle (at -2.55 0 0)', text)
        self.assertIn('(size 1.8 1.8) (drill 1.2)', text)

    def test_pitch_uses_nominal_and_body_uses_maximum(self):
        record = radial()
        record['drawing']['pitch'].pop('value')
        record['drawing']['pitch'].update(min=4.9, typ=5.1, max=5.3)
        self.assertEqual(derive_footprint(record)['pads'][1]['x'], 2.55)
        compact = radial()
        compact['body']['width']['value'] = 3.8
        compact['body']['length']['value'] = 3
        for key, value in [('pitch', 2.54), ('drill', .9), ('pad_width', 1.5), ('pad_height', 1.5)]:
            compact['drawing'][key]['value'] = value
        result = derive_footprint(compact)
        self.assertEqual(result['pads'][0]['x'], -1.27)
        self.assertEqual(result['courtyard'], dict(min_x=-2.27, max_x=2.27, min_y=-1.75, max_y=1.75))

    def test_invalid_and_ambiguous_geometry_is_refused(self):
        mutations = [
            lambda p: p.update(mount_type='SMT'),
            lambda p: p.update(density='COMPACT'),
            lambda p: p['drawing'].update(pin_count=3),
            lambda p: p['drawing'].pop('drill'),
            lambda p: p['drawing']['drill'].update(value=1.8),
            lambda p: p['drawing']['drill'].update(max=1.3),
            lambda p: p['drawing']['pad_height'].update(value=2),
            lambda p: p['drawing']['pad_width'].update(unit='V'),
            lambda p: p['drawing']['pitch'].update(value=1),
            lambda p: p['drawing']['pitch'].update(value=0),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                record = radial()
                mutation(record)
                with self.assertRaises(ValueError):
                    derive_footprint(record)
        record = radial()
        record['drawing']['pitch'].pop('value')
        record['drawing']['pitch'].update(min=4.9, max=5.3)
        with self.assertRaises(ValueError):
            derive_footprint(record)
