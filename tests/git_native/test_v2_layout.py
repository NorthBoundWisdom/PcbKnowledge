"""Synthetic board measurements and adversarial mutations; never manufactured acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.layout import check_board, check_layout
from tests.git_native.test_v2_record_contracts import fixtures


def q(value, unit='mm'):
    return {'value': value, 'unit': unit}


class FixtureCatalog:
    def get(self, identity, kind):
        assert kind == 'package' and identity == 'package:synthetic'
        return fixtures()['package']


def board_text():
    footprints = []
    for ref, x, y in [('A', 2, 2), ('B', 5, 2), ('C', 5, 5)]:
        footprints.append(f'''(footprint "pcbknowledge:synthetic" (layer "F.Cu") (at {x} {y})
          (property "Reference" "{ref}")
          (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Paste" "F.Mask") (net 1 "N"))
          (fp_rect (start -0.75 -0.75) (end 0.75 0.75) (layer "F.CrtYd")))''')
    return '(kicad_pcb (general (thickness 1.6)) (layers (0 "F.Cu" signal) (2 "B.Cu" signal)) (net 0 "") (net 1 "N") ' + ''.join(footprints) + '''
      (gr_rect (start 0 0) (end 20 20) (layer "Edge.Cuts"))
      (segment (start 2 2) (end 5 2) (width 0.4) (layer "F.Cu") (net 1))
      (zone (net 1) (layer "F.Cu")
        (polygon (pts (xy 0 0) (xy 4 0) (xy 4 4) (xy 0 4)))
        (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 4 0) (xy 4 4) (xy 0 4)))))'''


def intent():
    return {'status': 'EXPANDED',
            'mechanical': {'outline_envelope': {'shape': 'RECTANGLE', 'max_width': q(20), 'max_length': q(20)},
                           'height_limit': {'status': 'UNCONSTRAINED'}},
            'manufacturing': {'layers': 2, 'thickness': q(1.6), 'assembly_side': 'TOP'}, 'components': [{'ref': ref, 'package': 'package:synthetic',
                            'footprint': 'pcbknowledge:synthetic', 'assembly_method': 'SMT_ASSEMBLY'} for ref in ('A', 'B', 'C')],
            'nets': [{'name': 'N', 'pins': [{'ref': ref, 'pin': '1'} for ref in ('A', 'B', 'C')]}],
            'layout': [
                {'kind': 'PLACE_NEAR', 'subject': 'A', 'target': 'B.pin:1', 'max_distance': q(3)},
                {'kind': 'GROUP', 'subjects': ['A', 'B', 'C']},
                {'kind': 'EDGE_PLACEMENT', 'subject': 'A', 'edge': 'LEFT', 'max_distance': q(2)},
                {'kind': 'EDGE_DISTANCE', 'subject': 'A', 'edge': 'TOP', 'distance': q(2)},
                {'kind': 'KEEPOUT', 'subject': 'A', 'margin': q(0)},
                {'kind': 'NET_WIDTH_MIN', 'net': 'N', 'min_width': q(0.3)},
                {'kind': 'MINIMIZE_LOOP', 'path': ['A.pin:1', 'B.pin:1', 'C.pin:1'], 'max_area': q(5, 'mm2')},
                {'kind': 'COPPER_AREA', 'target': 'A.pin:1', 'min_area': q(12, 'mm2')}]}


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.board = board_from_text(board_text())
        self.intent = intent()
        self.catalog = FixtureCatalog()

    def check(self):
        return check_layout(self.board, self.intent, self.catalog)

    def test_supported_measurements_pass_without_claiming_routing(self):
        report = self.check()
        self.assertEqual(report['result'], 'PASS', report)
        self.assertEqual(len(report['checks']), 14)
        self.assertFalse(report['routing_certified'])
        self.assertIn('estimate only', report['checks'][7]['reason'])

    def test_each_measured_constraint_detects_failed_limit(self):
        changes = [('max_distance', q(2)), ('subjects', ['A', 'B', 'C']),
                   ('max_distance', q(1)), ('distance', q(3)), ('margin', q(2)),
                   ('min_width', q(0.5)), ('max_area', q(4, 'mm2')), ('min_area', q(17, 'mm2'))]
        for index, (field, value) in enumerate(changes):
            with self.subTest(kind=self.intent['layout'][index]['kind']):
                self.setUp()
                self.intent['layout'][index][field] = value
                if index == 1:
                    footprint = self.board['footprints']['C']
                    footprint['at'] = [19, 19]
                    footprint['pads']['1'][0]['at'] = [19, 19]
                    footprint['bounds'] = [18.25, 18.25, 19.75, 19.75]
                report = self.check()
                self.assertEqual(report['checks'][index + 1]['result'], 'FAIL', report)
                self.assertEqual(report['result'], 'FAIL')

    def test_identity_mismatches_prevent_constraint_checks(self):
        for mutation in ('ref', 'library', 'pad', 'net', 'duplicate-pad', 'extra-net'):
            with self.subTest(mutation=mutation):
                self.setUp()
                footprint = self.board['footprints']['A']
                if mutation == 'ref':
                    self.board['footprints']['wrong'] = self.board['footprints'].pop('A')
                elif mutation == 'extra-net':
                    self.board['nets']['99'] = 'unexpected'
                elif mutation == 'library':
                    footprint['library'] = 'other:synthetic'
                elif mutation == 'pad':
                    footprint['pads']['2'] = footprint['pads'].pop('1')
                elif mutation == 'duplicate-pad':
                    footprint['pads']['1'].append(copy.deepcopy(footprint['pads']['1'][0]))
                else:
                    footprint['pads']['1'][0]['net'] = ''
                report = self.check()
                self.assertEqual(report['checks'][0]['result'], 'FAIL')
                self.assertEqual(len(report['checks']), 2)

    def test_missing_routing_fills_and_ambiguous_kelvin_are_not_checkable(self):
        self.board['segments'] = []
        self.board['zones'] = []
        self.intent['layout'].append({'kind': 'KELVIN', 'sense_nets': ['N'], 'target': 'A'})
        report = self.check()
        for index in (6, 8, 9):
            self.assertEqual(report['checks'][index]['result'], 'NOT_CHECKABLE', report)
        self.assertEqual(report['result'], 'NOT_CHECKABLE')

    def test_unsupported_geometry_never_reports_complete_pass(self):
        self.board['outline']['rectangular'] = False
        self.board['footprints']['A']['courtyard'] = []
        self.board['footprints']['A']['courtyard_closed'] = False
        self.board['zones'][0]['filled_polygons'].append([[0, 0], [2, 0], [2, 2], [0, 2]])
        self.board['unsupported'] = ['Unsupported synthetic geometry']
        report = self.check()
        for index in (3, 4, 5, 8):
            self.assertEqual(report['checks'][index]['result'], 'NOT_CHECKABLE', report)
        self.assertEqual(report['result'], 'NOT_CHECKABLE')

    def test_copper_requires_direct_layer_contact_and_simple_fill(self):
        for mutation in ('layer', 'position', 'crossing', 'outside'):
            with self.subTest(mutation=mutation):
                self.setUp()
                zone = self.board['zones'][0]
                if mutation == 'layer':
                    zone['layer'] = 'B.Cu'
                elif mutation == 'outside':
                    zone['filled_polygons'] = [[[-5, -5], [4, -5], [4, 4], [-5, 4]]]
                elif mutation == 'position':
                    zone['filled_polygons'] = [[[10, 10], [14, 10], [14, 14], [10, 14]]]
                else:
                    zone['filled_polygons'] = [[[0, 0], [4, 4], [0, 4], [4, 0]]]
                self.assertEqual(self.check()['checks'][8]['result'], 'NOT_CHECKABLE')

    def test_checker_never_writes_board(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.kicad_pcb'
            original = board_text().encode()
            path.write_bytes(original)
            self.assertEqual(check_board(path, self.intent, self.catalog)['result'], 'PASS')
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_unknown_rule_and_invalid_limit_are_not_checkable(self):
        for rule in ({'kind': 'FUTURE_RULE'},
                     {'kind': 'MINIMIZE_LOOP', 'path': ['A.pin:1'], 'max_area': q(float('nan'), 'mm2')}):
            with self.subTest(rule=rule):
                self.intent['layout'] = [rule]
                self.assertEqual(self.check()['checks'][1]['result'], 'NOT_CHECKABLE')

    def test_refused_intent_is_not_checked(self):
        self.intent['status'] = 'REFUSED'
        with self.assertRaisesRegex(ValueError, 'expanded intent'):
            self.check()


class PadGeometryIdentityTests(unittest.TestCase):
    def fixture(self, side='F', angle=0, drilled=False, aliases=False):
        record = fixtures()['package']
        pad = record['explicit_pads'][0]
        pad.update(x=q(2), y=q(3), width=q(1), height=q(2), rotation=q(90, 'deg'))
        if drilled:
            pad.update(kind='THROUGH_HOLE', shape='OVAL', drill_width=q(0.6), drill_height=q(0.9))
        if aliases:
            second = copy.deepcopy(pad)
            second['x'] = q(-2)
            record['explicit_pads'].append(second)
        class Catalog:
            def get(self, identity, kind):
                return record
        drill = '(drill oval 0.6 0.9)' if drilled else ''
        kind, shape = ('thru_hole', 'oval') if drilled else ('smd', 'rect')
        layers = '"*.Cu" "*.Mask"' if drilled else f'"{side}.Cu" "{side}.Paste" "{side}.Mask"'
        y = -3 if side == 'B' else 3
        rotation = angle + (-90 if side == 'B' else 90)
        # Reverse alias order deliberately: ordering is not physical identity.
        pads = ''.join(f'(pad "1" {kind} {shape} (at {x} {y} {rotation}) (size 1 2) '
                       f'{drill} (layers {layers}) (net 1 "N"))' for x in ([-2, 2] if aliases else [2]))
        board = board_from_text(f'(kicad_pcb (net 1 "N") '
                                f'(footprint "pcbknowledge:synthetic" (layer "{side}.Cu") (at 10 20 {angle}) '
                                f'(property "Reference" "A") {pads}))')
        document = {'status': 'EXPANDED', 'components': [{'ref': 'A', 'package': 'package:synthetic',
                                                       'footprint': 'pcbknowledge:synthetic'}],
                    'nets': [{'name': 'N', 'pins': [{'ref': 'A', 'pin': '1'}]}], 'layout': []}
        return board, document, Catalog()

    def test_valid_rotation_translation_back_flip_and_unordered_aliases(self):
        for side in ('F', 'B'):
            for angle in (0, 37, 90, -90):
                for drilled in (False, True):
                    with self.subTest(side=side, angle=angle, drilled=drilled):
                        args = self.fixture(side, angle, drilled, aliases=True)
                        self.assertEqual(check_layout(*args)['checks'][0]['result'], 'PASS')

    def test_geometry_tampering_cannot_preserve_identity(self):
        for field in ('size', 'at', 'drill_size', 'drill_offset', 'rotation', 'shape', 'kind', 'layers'):
            with self.subTest(field=field):
                board, document, catalog = self.fixture(drilled=True)
                pad = board['footprints']['A']['pads']['1'][0]
                if field in ('size', 'at', 'drill_size', 'drill_offset'):
                    pad[field][0] += 0.1
                elif field == 'rotation':
                    pad[field] += 5
                elif field == 'shape':
                    pad[field] = 'rect'
                elif field == 'kind':
                    pad[field] = 'np_thru_hole'
                else:
                    pad[field] = ['F.Cu']
                report = check_layout(board, document, catalog)
                self.assertEqual(report['checks'][0]['result'], 'FAIL', report)

    def test_unsupported_geometry_is_not_exact_identity_pass(self):
        board, document, catalog = self.fixture()
        board['footprints']['A']['pads']['1'][0]['geometry_unsupported'] = True
        report = check_layout(board, document, catalog)
        self.assertEqual(report['checks'][0]['result'], 'NOT_CHECKABLE')
        self.assertEqual(report['result'], 'NOT_CHECKABLE')

    def test_parser_retains_drill_offset_and_missing_angle_is_absolute_zero(self):
        text = '''(kicad_pcb (footprint "x" (layer "F.Cu") (at 10 20 90)
          (property "Reference" "X")
          (pad "1" thru_hole oval (at 2 3) (size 1 2)
            (drill oval 0.6 0.9 (offset 0.1 0.2)) (layers "*.Cu" "*.Mask"))))'''
        pad = board_from_text(text)['footprints']['X']['pads']['1'][0]
        self.assertEqual(pad['rotation'], 0)
        self.assertEqual(pad['drill_size'], [0.6, 0.9])
        self.assertEqual(pad['drill_offset'], [0.1, 0.2])


class BoardRequirementTests(unittest.TestCase):
    def fixture(self):
        return board_from_text(board_text()), intent(), FixtureCatalog()

    def check_kind(self, args, kind):
        report = check_layout(*args)
        return next(item for item in report['checks'] if item['kind'] == kind)['result']

    def test_envelope_thickness_and_copper_layer_mutations(self):
        for kind in ('BOARD_ENVELOPE', 'BOARD_THICKNESS', 'COPPER_LAYER_COUNT'):
            with self.subTest(kind=kind):
                args = self.fixture()
                board = args[0]
                if kind == 'BOARD_ENVELOPE':
                    board['outline']['bounds'][2] = 100
                elif kind == 'BOARD_THICKNESS':
                    board['thickness_mm'] = 0.8
                else:
                    board['copper_layers'] += ['In1.Cu', 'In2.Cu']
                self.assertEqual(self.check_kind(args, kind), 'FAIL')

    def test_absent_board_declarations_and_concrete_height_are_unknown(self):
        args = self.fixture()
        args[0]['thickness_mm'] = None
        args[0]['copper_layers'] = None
        args[1]['mechanical']['height_limit'] = q(5)
        for kind in ('BOARD_THICKNESS', 'COPPER_LAYER_COUNT', 'COMPONENT_HEIGHT'):
            self.assertEqual(self.check_kind(args, kind), 'NOT_CHECKABLE')

    def test_backside_smt_violates_top_assembly_but_hand_solder_does_not(self):
        args = self.fixture()
        footprint = args[0]['footprints']['A']
        footprint['layer'] = 'B.Cu'
        footprint['pads']['1'][0]['layers'] = ['B.Cu', 'B.Mask', 'B.Paste']
        self.assertEqual(self.check_kind(args, 'ASSEMBLY_SIDE'), 'FAIL')
        args[1]['components'][0]['assembly_method'] = 'HAND_SOLDER'
        self.assertEqual(self.check_kind(args, 'ASSEMBLY_SIDE'), 'PASS')

    def test_shrunken_editable_courtyard_cannot_hide_authoritative_collision(self):
        args = self.fixture()
        for ref, x in (('A', 2), ('B', 3)):
            footprint = args[0]['footprints'][ref]
            footprint['at'] = [x, 2]
            footprint['pads']['1'][0]['at'] = [x, 2]
            footprint['bounds'] = [x - 0.01, 1.99, x + 0.01, 2.01]
            footprint['courtyard'] = [[x - 0.01, 1.99], [x + 0.01, 1.99],
                                      [x + 0.01, 2.01], [x - 0.01, 2.01]]
        self.assertEqual(self.check_kind(args, 'KEEPOUT'), 'FAIL')

    def test_parser_projects_real_board_declarations(self):
        board = board_from_text(board_text())
        self.assertEqual(board['thickness_mm'], 1.6)
        self.assertEqual(board['copper_layers'], ['F.Cu', 'B.Cu'])
        minimal = board_from_text('(kicad_pcb)')
        self.assertIsNone(minimal['thickness_mm'])
        self.assertIsNone(minimal['copper_layers'])
