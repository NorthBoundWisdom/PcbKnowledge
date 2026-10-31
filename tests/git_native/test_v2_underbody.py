"""Synthetic package-local conductor exclusions and deterministic projections."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import pcbknowledge
from pcbknowledge.serialization import read_json
from pcbknowledge.v2.conductor_keepouts import project_keepouts, validate_projection, validate_region, validate_regions
from pcbknowledge.v2.conductor_keepout_export import keepout_nodes
from pcbknowledge.v2.layout_conductor_keepout import check_conductor_keepout
from pcbknowledge.v2.boardview import board_from_text, children, field
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.footprints import export_kicad
from pcbknowledge.v2.handoff import _footprint, _syntax
from pcbknowledge.v2.schema import ContractSchemas
from pcbknowledge.v2.sexpr import dumps, parse
from tests.git_native.test_v2_footprints import package
from tests.git_native.test_v2_record_contracts import quantity

ROOT = Path(pcbknowledge.__file__).resolve().parents[2]
SCHEMAS, REGISTRY = ROOT/'schemas', ROOT/'knowledge/registry'


def region():
    return {'id': 'underbody', 'rectangle': {k: quantity(v, 'mm') for k, v in
            [('xmin', -1.25), ('ymin', -3.45), ('xmax', 1.25), ('ymax', 3.45)]},
            'forbid': ['TRACK', 'VIA'], 'layer_scope': 'ALL_COPPER', 'scope_basis': 'ENGINEERING_DEFAULT',
            'scope_note': 'Synthetic all-layer scope fixture, not a manufacturer claim.',
            'evidence': {'source': 'source:synthetic', 'page': 1}}


def fixture(angle=0, side='F.Cu'):
    board = {'footprints': {'L1': {'at': [10, 10], 'rotation': angle, 'layer': side, 'pads': {}}},
             'copper_layers': ['F.Cu', 'In1.Cu', 'B.Cu'], 'segments': [], 'arcs': [], 'vias': [],
             'zones': [], 'unsupported': []}
    return board, {'kind': 'CONDUCTOR_KEEPOUT', 'subject': 'L1', 'region': region()}


class UnderbodyTests(unittest.TestCase):
    def test_empty_region_and_pad_zone_copper_are_not_forbidden(self):
        board, rule = fixture()
        board['footprints']['L1']['pads'] = {'1': [{'at': [10, 10], 'size': [10, 10]}]}
        board['zones'] = [{'filled_polygons': [[[0, 0], [20, 0], [20, 20], [0, 20]]]}]
        self.assertEqual(check_conductor_keepout(board, rule)['result'], 'PASS')

    def test_track_full_width_and_tangent_all_layers(self):
        for layer in ('F.Cu', 'In1.Cu', 'B.Cu'):
            board, rule = fixture()
            board['segments'] = [{'start': [11.5, 8], 'end': [11.5, 12], 'width': .5, 'layer': layer}]
            self.assertEqual(check_conductor_keepout(board, rule)['result'], 'FAIL')
            board['segments'][0]['width'] = .499
            self.assertEqual(check_conductor_keepout(board, rule)['result'], 'PASS')

    def test_crossing_segment_and_corner_disk_are_not_endpoint_or_bbox_tests(self):
        board, rule = fixture()
        board['segments'] = [{'start': [0, 10], 'end': [20, 10], 'width': .1, 'layer': 'F.Cu'}]
        self.assertEqual(check_conductor_keepout(board, rule)['result'], 'FAIL')
        board['segments'] = []
        board['vias'] = [{'at': [11.55, 13.75], 'size': .8, 'drill': .3, 'layers': ['F.Cu', 'B.Cu']}]
        self.assertEqual(check_conductor_keepout(board, rule)['result'], 'PASS')
        board['vias'][0]['size'] = .9
        self.assertEqual(check_conductor_keepout(board, rule)['result'], 'FAIL')

    def test_pose_rotation_and_back_mirror_use_actual_component(self):
        for angle, location in [(0, [10, 13]), (90, [13, 10]), (180, [10, 7]), (270, [7, 10])]:
            for side in ('F.Cu', 'B.Cu'):
                board, rule = fixture(angle, side)
                board['vias'] = [{'at': location, 'size': .2, 'layers': ['F.Cu', 'B.Cu']}]
                self.assertEqual(check_conductor_keepout(board, rule)['result'], 'FAIL')
        board, rule = fixture(0, 'B.Cu')
        rule['region']['rectangle']['ymin'] = quantity(1, 'mm')
        rule['region']['rectangle']['ymax'] = quantity(3, 'mm')
        board['vias'] = [{'at': [10, 8], 'size': .2, 'layers': ['F.Cu', 'B.Cu']}]
        self.assertEqual(check_conductor_keepout(board, rule)['result'], 'FAIL')
        board['vias'][0]['at'] = [10, 12]
        self.assertEqual(check_conductor_keepout(board, rule)['result'], 'PASS')

    def test_unsupported_geometry_and_limits_are_explicit(self):
        for mutation in ('angle', 'arc', 'layer', 'unknown'):
            board, rule = fixture()
            if mutation == 'angle':
                board['footprints']['L1']['rotation'] = 45
            elif mutation == 'arc':
                board['arcs'] = [{'layer': 'F.Cu'}]
            elif mutation == 'layer':
                board['copper_layers'] = None
            else:
                board['unsupported'] = ['Unparsed conductive shape']
            self.assertEqual(check_conductor_keepout(board, rule)['result'], 'NOT_CHECKABLE')
        board, rule = fixture()
        self.assertEqual(check_conductor_keepout(board, rule, max_items=float('inf'))['result'], 'NOT_CHECKABLE')
        board['vias'] = [{'at': [0, 0], 'size': .5, 'layers': ['F.Cu', 'B.Cu']}] * 2
        self.assertEqual(check_conductor_keepout(board, rule, max_items=1)['result'], 'NOT_CHECKABLE')

    def test_contract_rejects_widening_fields_and_invalid_numeric_values(self):
        schemas = ContractSchemas(SCHEMAS)
        for mutation in ('nan', 'zero', 'scope', 'pads', 'extra', 'missing'):
            value = region()
            if mutation == 'nan':
                value['rectangle']['xmin']['value'] = float('nan')
            elif mutation == 'zero':
                value['rectangle']['xmax']['value'] = -1.25
            elif mutation == 'scope':
                value['layer_scope'] = 'F.Cu'
            elif mutation == 'pads':
                value['forbid'].append('PAD')
            elif mutation == 'extra':
                value['copper'] = True
            else:
                del value['evidence']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_region(value)
        schemas.apply(region(), schemas.load('layout-constraint.schema.json')['$defs']['conductor_keepout'],
                      'layout-constraint.schema.json')
        with self.assertRaises(ValueError):
            validate_regions({'conductor_keepouts': [region(), region()]})

    def test_projection_is_automatic_exact_and_immutable(self):
        p = {'conductor_keepouts': [region()]}
        catalog = SimpleNamespace(get=lambda *args: p)
        components = [{'ref': 'L1', 'package': 'package:test'}]
        before = deepcopy(p)
        projected = project_keepouts(components, catalog)
        self.assertEqual(p, before)
        intent = {'components': components, 'layout': projected}
        validate_projection(intent, catalog)
        for change in ('drop', 'widen', 'duplicate'):
            altered = deepcopy(intent)
            if change == 'drop':
                altered['layout'] = []
            elif change == 'widen':
                altered['layout'][0]['region']['rectangle']['xmax']['value'] += .1
            else:
                altered['layout'].append(deepcopy(altered['layout'][0]))
            with self.assertRaises(ValueError):
                validate_projection(altered, catalog)

    def test_native_keepout_flags_local_and_handoff_coordinates(self):
        p = package('chip', lead_span=1.6, lead_width=.8, lead_length=.3)
        p['conductor_keepouts'] = [region()]
        tree = parse(export_kicad(p))
        zone = children(tree, 'zone')[0]
        self.assertEqual(field(zone, 'layers'), ['*.Cu'])
        flags = children(zone, 'keepout')[0]
        self.assertEqual(field(flags, 'tracks'), ['not_allowed'])
        self.assertEqual(field(flags, 'vias'), ['not_allowed'])
        for allowed in ('pads', 'copperpour', 'footprints'):
            self.assertEqual(field(flags, allowed), ['allowed'])
        fp = _footprint({'id': 'test', 'brief_id': 'G', 'bundle_commit': 'a' * 40},
                        {'ref': 'L1', 'package': p['id'], 'footprint': 'test'},
                        SimpleNamespace(get=lambda *args: p), (10, 20), {})
        zone = children(fp, 'zone')[0]
        points = children(children(zone, 'polygon')[0], 'pts')[0][1:]
        self.assertEqual([[float(v) for v in pt[1:]] for pt in points],
                         [[8.75, 16.55], [11.25, 16.55], [11.25, 23.45], [8.75, 23.45]])
        text = dumps(_syntax(['kicad_pcb', ['net', '0', ''], fp]))
        self.assertIn('(tracks not_allowed)', text)
        self.assertEqual(len(board_from_text(text)['footprints']), 1)

    def test_selected_package_projection_and_source_closure_in_expansion(self):
        catalog = Catalog(ROOT, ROOT/'schemas')
        catalog.schemas = ContractSchemas(SCHEMAS)
        entries = read_json((REGISTRY/'layout-constraints.json').read_bytes())['entries']
        catalog.vocabulary.entries['layout-constraints'].update(entries)
        graph = read_json((ROOT/'evals/golden-designs/g1.block-graph.json').read_bytes())
        brief = read_json((ROOT/'evals/golden-designs/g1.brief.json').read_bytes())
        p = catalog.get('package:lqfp-48-stm32')
        value = region()
        value['evidence'] = deepcopy(p['evidence'][0])
        p['conductor_keepouts'] = [value]
        intent = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
        projected = [r for r in intent['layout'] if r['kind'] == 'CONDUCTOR_KEEPOUT']
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]['region'], value)
        self.assertIn(value['evidence']['source'], intent['dependencies'])
        self.assertIn(value['evidence'], intent['evidence'])
        value['evidence'] = {'source': 'source:wurth-74437349047', 'page': 1}
        catalog.get(value['evidence']['source'])['verification'] = 'DRAFT'
        refused = expand(catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(refused['status'], 'REFUSED')
        self.assertTrue(any(r['code'] == 'UNVERIFIED_RECORD' and r['path'] == value['evidence']['source']
                            for r in refused['refusals']), refused['refusals'])

    def test_native_roundtrip_rule_area_is_not_copper(self):
        p = package('chip', lead_span=1.6, lead_width=.8, lead_length=.3)
        p['conductor_keepouts'] = [region()]
        fp = _footprint({'id': 'test', 'brief_id': 'G', 'bundle_commit': 'a' * 40},
                        {'ref': 'L1', 'package': p['id'], 'footprint': 'test'},
                        SimpleNamespace(get=lambda *args: p), (10, 20), {})
        root = ['kicad_pcb', ['net', '0', ''], ['layers', ['0', 'F.Cu', 'signal'],
                ['2', 'B.Cu', 'signal']], fp]
        rule = {'kind': 'CONDUCTOR_KEEPOUT', 'subject': 'L1', 'region': region()}
        def check(tree):
            return check_conductor_keepout(board_from_text(dumps(_syntax(tree))), rule)['result']
        self.assertEqual(check(root), 'PASS')
        crossed = deepcopy(root)
        crossed.append(['segment', ['start', '8', '20'], ['end', '12', '20'],
                        ['width', '0.2'], ['layer', 'F.Cu'], ['net', '0']])
        self.assertEqual(check(crossed), 'FAIL')
        for mutation in ('filled_polygon', 'unknown', 'malformed'):
            changed = deepcopy(root)
            zone = children(changed[-1], 'zone')[0]
            if mutation == 'malformed':
                children(zone, 'keepout')[0].append(['tracks', 'allowed'])
            else:
                zone.append([mutation, ['pts', ['xy', '10', '20']]])
            self.assertEqual(check(changed), 'NOT_CHECKABLE')

    def test_real_workspace_schema_snapshot_and_handoff(self):
        import shutil
        import tempfile
        from pcbknowledge.workspace import initialize_workspace, validate_workspace, SCHEMA_PATHS
        from pcbknowledge.v2.handoff import board_tree
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'workspace'
            initialize_workspace(target, schema_source_root=SCHEMAS.parent, init_git=True)
            shutil.copytree(ROOT/'knowledge', target/'knowledge', dirs_exist_ok=True)
            shutil.copy(REGISTRY/'layout-constraints.json', target/'knowledge/registry/layout-constraints.json')
            validation = validate_workspace(target)
            self.assertTrue(validation.manifest.schema_digest)
            self.assertEqual(len(list((target/'schemas').glob('*.json'))), len(SCHEMA_PATHS))
            catalog = Catalog(target, target/'schemas')
            p = catalog.get('package:lqfp-48-stm32')
            value = region()
            value['evidence'] = deepcopy(p['evidence'][0])
            p['conductor_keepouts'] = [value]
            catalog.structure(p, 'package.schema.json')
            graph = read_json((ROOT/'evals/golden-designs/g1.block-graph.json').read_bytes())
            brief = read_json((ROOT/'evals/golden-designs/g1.brief.json').read_bytes())
            intent = expand(catalog, graph, brief, bundle_commit='a'*40)
            self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
            tree = board_tree(intent, catalog)
            board = board_from_text(dumps(tree))
            rule = next(rule for rule in intent['layout'] if rule['kind'] == 'CONDUCTOR_KEEPOUT')
            self.assertEqual(check_conductor_keepout(board, rule)['result'], 'PASS')

    def test_native_bounds_never_rounded_and_negative_origin_is_exact(self):
        p = package('chip', lead_span=1.6, lead_width=.8, lead_length=.3)
        p['conductor_keepouts'] = [region()]
        zone = keepout_nodes(p, position=(-10.125, -20.25))[0]
        points = children(children(zone, 'polygon')[0], 'pts')[0][1:]
        self.assertEqual([[float(v) for v in pt[1:]] for pt in points],
                         [[-11.375, -23.7], [-8.875, -23.7], [-8.875, -16.8], [-11.375, -16.8]])
        p['conductor_keepouts'][0]['rectangle']['xmin']['value'] = -1.25000001
        with self.assertRaisesRegex(ValueError, 'nanometer'):
            keepout_nodes(p)
