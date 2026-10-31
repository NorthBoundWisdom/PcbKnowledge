"""Physical reference data fixes preserve electrical identity and manufacturing geometry."""
import copy
import unittest

from pcbknowledge.v2.footprints import derive_footprint, export_kicad
from pcbknowledge.v2.sexpr import parse
from pcbknowledge.v2.boardview import children, field
from tests.git_native.test_v2_footprints import package
from tests.git_native.test_v2_record_contracts import quantity


class GeometryExportTests(unittest.TestCase):
    def test_body_center_is_typed_and_moves_only_courtyard(self):
        original = package('chip', lead_span=1.6, lead_width=.8, lead_length=.3)
        shifted = copy.deepcopy(original)
        shifted['body']['center'] = {'x': quantity(0, 'mm'), 'y': quantity(4, 'mm')}
        before, after = derive_footprint(original), derive_footprint(shifted)
        self.assertEqual(before['pads'], after['pads'])
        self.assertGreater(after['courtyard']['max_y'], before['courtyard']['max_y'])
        shifted['body']['center']['x'] = quantity(1, 'V')
        with self.assertRaises(ValueError):
            derive_footprint(shifted)

    def test_native_npth_number_is_blank_but_geometry_and_count_remain(self):
        hole = package('mechanical_hole', count=1, drill=3.2)
        hole['drawing']['pin_count'] = 1
        hole['pin1'] = '1'
        tree = parse(export_kicad(hole))
        pads = children(tree, 'pad')
        self.assertEqual(len(pads), 1)
        self.assertEqual(pads[0][1:4], ['', 'np_thru_hole', 'circle'])
        self.assertEqual(field(pads[0], 'drill'), ['3.2'])

    def test_smt_attribute_and_local_pad_angles_are_exported(self):
        part = package('chip', lead_span=1.6, lead_width=.8, lead_length=.3)
        fp = parse(export_kicad(part))
        self.assertEqual(field(fp, 'attr'), ['smd'])
        self.assertTrue(all(float(field(p, 'at')[2]) == 0 for p in children(fp, 'pad')))

    def test_manufacturer_land_numbered_map_does_not_move_copper(self):
        part = package('manufacturer_two_side_land', count=4, pitch=2.5, row_pitch=4.35,
                       pad_width=1.95, pad_height=1.4)
        before = derive_footprint(part)
        part['drawing']['pad_numbers'] = ['4', '1', '2', '3']
        after = derive_footprint(part)
        self.assertEqual([p['number'] for p in after['pads']], ['4', '1', '2', '3'])
        for a, b in zip(before['pads'], after['pads']):
            self.assertEqual({k: v for k, v in a.items() if k != 'number'},
                             {k: v for k, v in b.items() if k != 'number'})
        part['drawing']['pad_numbers'] = ['1', '1', '2', '3']
        with self.assertRaises(ValueError):
            derive_footprint(part)

    def test_nonconductive_locator_holes_are_not_electrical_terminals(self):
        from tests.git_native.test_v2_catalog import CatalogTests
        case = CatalogTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        pad = copy.deepcopy(case.documents['package']['explicit_pads'][0])
        pad.update(number='LOCATOR', kind='MECHANICAL', shape='ROUND', x=quantity(5, 'mm'),
                   width=quantity(.65, 'mm'), height=quantity(.65, 'mm'), drill=quantity(.65, 'mm'))
        case.documents['package']['explicit_pads'].append(pad)
        case.save()
        self.assertEqual(len(case.load().records), 4)
        case.documents['part']['pins'].append({'number': 'LOCATOR', 'name': 'FAKE', 'type': 'PASSIVE'})
        case.save()
        with self.assertRaisesRegex(ValueError, 'Pin/pad coverage'):
            case.load()
