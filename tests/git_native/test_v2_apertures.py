"""Synthetic independent layer openings retain copper and exact identity."""
from copy import deepcopy
import unittest

from pcbknowledge.v2.apertures import aperture_identity, derive_apertures
from pcbknowledge.v2.boardview import board_from_text, children
from pcbknowledge.v2.footprints import derive_footprint, export_kicad
from pcbknowledge.v2.layout_identity import pad_geometry_result
from pcbknowledge.v2.placement import apply_positions
from pcbknowledge.v2.sexpr import parse, dumps
from pcbknowledge.v2.handoff import _syntax
from tests.git_native.test_v2_footprints import package
from tests.git_native.test_v2_record_contracts import quantity


def opening(identity='a', x=0, y=0, width=.2, height=.2, shape='RECT'):
    return {'id': identity, 'shape': shape, **{key: quantity(value, 'mm') for key, value in
            [('x', x), ('y', y), ('width', width), ('height', height)]}, 'rotation': quantity(0, 'deg')}


def fixture():
    p = package('chip', length=2, width=4, lead_span=4, lead_length=1, lead_width=2)
    p['layer_apertures'] = [{'pad_number': '1', 'mask': [opening('mask', width=.8, height=1.8)],
                            'paste': [opening(str(i), x=x, y=y) for i, (x, y) in
                                      enumerate([(-.2, -.4), (-.2, .4), (.2, -.4), (.2, .4)])]}]
    return p


def board(p):
    fp = parse(export_kicad(p))
    fp.insert(2, ['at', '10', '10', '0'])
    fp.append(['property', 'Reference', 'U1'])
    return ['kicad_pcb', ['version', '20241229'], ['net', '0', ''], fp]


def measured(tree):
    return board_from_text(dumps(_syntax(tree)))['footprints']['U1']


class ApertureTests(unittest.TestCase):
    def test_four_windows_and_independent_mask_do_not_change_copper(self):
        p = fixture()
        plain = deepcopy(p)
        del plain['layer_apertures']
        derived = derive_footprint(p)
        for actual, original in zip(derived['pads'], derive_footprint(plain)['pads']):
            self.assertEqual({k: v for k, v in actual.items() if k != 'independent_layers'}, original)
        actual = measured(board(p))
        self.assertEqual(len(actual['apertures']), 5)
        self.assertEqual(set(actual['pads']), {'1', '2'})
        self.assertEqual(actual['pads']['1'][0]['layers'], ['F.Cu'])
        self.assertTrue(aperture_identity(actual, derived))
        self.assertEqual(pad_geometry_result(actual, derived)[0], 'PASS')

    def test_rigid_rotations_preserve_all_openings(self):
        p = fixture()
        for angle in (0, 90, 180, 270):
            result = apply_positions(board(p), {'U1': (12, 13, angle)})
            self.assertTrue(aperture_identity(measured(result), derive_footprint(p)))

    def test_missing_extra_moved_and_layer_substitution_fail(self):
        p = fixture()
        for kind in ('missing', 'extra', 'moved', 'layer'):
            actual = measured(board(p))
            if kind == 'missing':
                actual['apertures'].pop()
            elif kind == 'extra':
                actual['apertures'].append(deepcopy(actual['apertures'][0]))
            elif kind == 'moved':
                actual['apertures'][0]['at'][0] += .1
            else:
                actual['apertures'][0]['layers'] = ['B.Mask']
            self.assertFalse(aperture_identity(actual, derive_footprint(p)))

    def test_round_and_oval_shapes(self):
        for shape in ('ROUND', 'OVAL'):
            p = fixture()
            p['layer_apertures'][0]['paste'] = [opening(shape=shape)]
            self.assertTrue(aperture_identity(measured(board(p)), derive_footprint(p)))

    def test_bad_geometry(self):
        for key, value in [('width', 0), ('x', float('nan')), ('height', 1e-9), ('rotation', 45)]:
            p = fixture()
            p['layer_apertures'][0]['paste'][0][key]['value'] = value
            with self.assertRaises(ValueError):
                derive_footprint(p)
        p = fixture()
        p['layer_apertures'][0]['paste'][0]['x']['unit'] = 'V'
        with self.assertRaises(ValueError):
            derive_footprint(p)

    def test_bad_binding_or_pattern(self):
        for action in ('missing', 'duplicate', 'empty', 'overlap', 'id', 'net', 'unknown'):
            p = fixture()
            binding = p['layer_apertures'][0]
            if action == 'missing':
                binding['pad_number'] = 'absent'
            elif action == 'duplicate':
                p['layer_apertures'].append(deepcopy(binding))
            elif action == 'empty':
                binding['paste'] = []
            elif action == 'overlap':
                binding['paste'][1]['x'] = deepcopy(binding['paste'][0]['x'])
                binding['paste'][1]['y'] = deepcopy(binding['paste'][0]['y'])
            elif action == 'id':
                binding['paste'][1]['id'] = binding['paste'][0]['id']
            elif action == 'net':
                binding['paste'][0]['net'] = 'GND'
            else:
                binding['paste'][0]['shape'] = 'CUSTOM'
            with self.assertRaises(ValueError):
                derive_footprint(p)

    def test_ambiguous_physical_binding_and_scalar_conflict(self):
        p = fixture()
        pads = derive_footprint(p)['pads']
        with self.assertRaises(ValueError):
            derive_apertures(p, pads + [deepcopy(pads[0])])
        pads[0]['paste_margin'] = -.01
        with self.assertRaises(ValueError):
            derive_apertures(p, pads)

    def test_malformed_native_apertures_are_rejected(self):
        for mutation in ('number', 'net', 'drill', 'margin', 'mixed'):
            tree = board(fixture())
            pad = children(children(tree, 'footprint')[0], 'pad')[-1]
            if mutation == 'number':
                pad[1] = '1'
            elif mutation == 'mixed':
                children(pad, 'layers')[0].append('F.Mask')
            else:
                pad.append({'net': ['net', '0', ''], 'drill': ['drill', '.1'],
                            'margin': ['solder_paste_margin', '.1']}[mutation])
            with self.assertRaises(ValueError):
                measured(tree)

    def test_inherited_margin_guard(self):
        for scope, field in [('board', 'pad_to_paste_clearance'), ('board', 'pad_to_mask_clearance'),
                             ('footprint', 'solder_paste_margin'), ('footprint', 'solder_mask_margin')]:
            tree = board(fixture())
            if scope == 'board':
                tree.append(['setup', [field, '.1']])
            else:
                children(tree, 'footprint')[0].append([field, '.1'])
            with self.assertRaises(ValueError):
                measured(tree)

    def test_back_side_rigid_identity(self):
        p = fixture()
        tree = board(p)
        fp = children(tree, 'footprint')[0]
        children(fp, 'layer')[0][1] = 'B.Cu'
        for pad in children(fp, 'pad'):
            at = children(pad, 'at')[0]
            at[2] = str(-float(at[2]))
            at[3] = str(-float(at[3]))
            layers = children(pad, 'layers')[0]
            layers[1:] = [layer.replace('F.', 'B.') for layer in layers[1:]]
        for angle in (0, 90, 180, 270):
            transformed = apply_positions(tree, {'U1': (12, 13, angle)})
            actual = measured(transformed)
            self.assertTrue(aperture_identity(actual, derive_footprint(p)))
            self.assertEqual(pad_geometry_result(actual, derive_footprint(p))[0], 'PASS')

    def test_mechanical_hole_not_classified_as_aperture(self):
        p = package('mechanical_hole', count=1, drill=2, pad_width=2, pad_height=2)
        actual = measured(board(p))
        self.assertEqual(actual['apertures'], [])
        self.assertEqual(set(actual['pads']), {''})

    def test_catalog_schema_and_source_closure(self):
        from pathlib import Path
        from pcbknowledge.v2.catalog import Catalog
        from tests.git_native.test_v2_record_contracts import fixtures
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        source = fixtures()['source']
        source['license_class'] = 'PUBLIC_REFERENCE'
        catalog.records[source['id']] = source
        p = fixture()
        catalog.structure(p, 'package.schema.json')
        q = p['layer_apertures'][0]['paste'][0]['x']
        q.update(basis='DATASHEET', evidence={'source': 'source:synthetic', 'page': 1})
        q.pop('note')
        catalog._anchors(p)
        q['evidence']['source'] = 'source:absent'
        with self.assertRaises(ValueError):
            catalog._anchors(p)

    def test_false_calculated_coordinate_rejected(self):
        from pathlib import Path
        from pcbknowledge.v2.catalog import Catalog
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        from tests.git_native.test_v2_record_contracts import fixtures
        source = fixtures()['source']
        source['license_class'] = 'PUBLIC_REFERENCE'
        catalog.records[source['id']] = source
        p = fixture()
        p['layer_apertures'][0]['paste'][0]['x'] = {
            'value': 99, 'unit': 'mm', 'basis': 'CALCULATED', 'calculator': 'geometry_affine',
            'inputs': {'offset': quantity(0, 'mm'), 'dimension': {
                'value': 1, 'unit': 'mm', 'basis': 'DATASHEET', 'conditions': {},
                'evidence': {'source': 'source:synthetic', 'page': 1}},
                       'factor': quantity(1, '1')}}
        with self.assertRaisesRegex(ValueError, 'Calculated quantity'):
            catalog._anchors(p)

    def test_through_hole_mask_refused_but_paste_preserves_both_mask_sides(self):
        p = package('pin_header', count=2, pitch=2.54, lead_width=.6, lead_length=.6)
        p['layer_apertures'] = [{'pad_number': '1', 'paste': [opening()]}]
        actual = measured(board(p))
        self.assertEqual(set(actual['pads']['1'][0]['layers']), {'*.Cu', '*.Mask'})
        p['layer_apertures'][0]['mask'] = [opening()]
        with self.assertRaisesRegex(ValueError, 'requires an SMD'):
            derive_footprint(p)

    def test_cross_binding_overlapping_windows_refused(self):
        p = fixture()
        pads = derive_footprint(p)['pads']
        dx = pads[0]['x'] - pads[1]['x']
        p['layer_apertures'].append({'pad_number': '2', 'paste': [opening(x=dx - .2, y=-.4)]})
        with self.assertRaisesRegex(ValueError, 'Overlapping aperture'):
            derive_footprint(p)

    def test_aperture_multiset_is_order_independent_but_preserves_duplicates(self):
        from pcbknowledge.v2.routing import _canonical_geometry
        a = measured(board(fixture()))
        b = deepcopy(a)
        b['apertures'].reverse()
        self.assertEqual(_canonical_geometry(a), _canonical_geometry(b))
        b['apertures'].append(deepcopy(b['apertures'][0]))
        self.assertNotEqual(_canonical_geometry(a), _canonical_geometry(b))

    def test_handoff_never_assigns_aperture_net(self):
        from pcbknowledge.v2.handoff import _footprint
        p = fixture()
        class Catalog:
            def get(self, *args):
                return p
        fp = _footprint({'id': 'synthetic', 'brief_id': 'test', 'bundle_commit': 'a' * 40},
                        {'ref': 'U1', 'package': p['id'], 'footprint': 'synthetic'}, Catalog(), (10, 10),
                        {('U1', '1'): (1, 'GND'), ('U1', ''): (1, 'GND')})
        pads = children(fp, 'pad')
        self.assertEqual(len([pad for pad in pads if not pad[1]]), 5)
        self.assertTrue(all(not children(pad, 'net') for pad in pads if not pad[1]))
        self.assertEqual(children(next(pad for pad in pads if pad[1] == '1'), 'net'), [['net', '1', 'GND']])

    def test_full_identity_rejects_additional_copper_or_apertures(self):
        from pcbknowledge.v2.layout import identity_check
        p = fixture()
        tree = board(p)
        parsed = board_from_text(dumps(_syntax(tree)))
        fp = parsed['footprints']['U1']
        intent = {'components': [{'ref': 'U1', 'package': p['id'], 'footprint': fp['library']}], 'nets': []}
        class Catalog:
            def get(self, *args):
                return p
        self.assertEqual(identity_check(parsed, intent, Catalog())['result'], 'PASS')
        for collection in ('apertures', 'pads'):
            changed = deepcopy(parsed)
            footprint = changed['footprints']['U1']
            if collection == 'apertures':
                footprint['apertures'].append(deepcopy(footprint['apertures'][0]))
            else:
                footprint['pads']['extra'] = [deepcopy(footprint['pads']['1'][0])]
            self.assertEqual(identity_check(changed, intent, Catalog())['result'], 'FAIL')

    def test_schema_rejects_electrical_aperture_fields(self):
        from pathlib import Path
        from pcbknowledge.v2.schema import validate
        schema_dir = Path(__file__).resolve().parents[2] / 'schemas'
        p = fixture()
        p['layer_apertures'][0]['paste'][0]['number'] = '9'
        with self.assertRaises(ValueError):
            validate(p, 'package.schema.json', schema_dir)
