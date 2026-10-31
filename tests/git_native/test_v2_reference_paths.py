"""Guard and continuous-reference requirements survive expansion without copper claims."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import _Expansion
from pcbknowledge.v2.handoff_rules import export_rules, project_settings
from pcbknowledge.v2.layout import LayoutChecks
from pcbknowledge.v2.reference_paths import validate_reference_paths
from pcbknowledge.v2.schema import SCHEMA_DIR, validate
from pcbknowledge.v2.vocabulary import Vocabulary
from tests.git_native.test_v2_record_contracts import quantity

ROOT = Path(__file__).resolve().parents[2]


def fixture():
    guard = {'kind': 'GUARD_RING', 'net': 'SUM', 'guard_net': 'BIAS',
             'min_width': quantity(.25, 'mm'), 'min_clearance': quantity(.2, 'mm')}
    path = {'kind': 'RETURN_PATH', 'net': 'SUM', 'return_net': 'GND'}
    fab = {key: quantity(value, 'mm') for key, value in
           [('trace_width_min', .15), ('clearance_min', .15), ('drill_min', .3), ('annular_ring_min', .125)]}
    intent = {'layout': [guard, path], 'nets': [{'name': net} for net in ('SUM', 'BIAS', 'GND')],
              'fab_profile': 'fab_profile:synthetic', 'components': [], 'mechanical': {'mounting': []}}
    return intent, fab


class ReferencePathTests(unittest.TestCase):
    def test_structure_registry_and_exact_fields(self):
        intent, _ = fixture()
        vocabulary = Vocabulary.load(ROOT / 'knowledge/registry', SCHEMA_DIR)
        for item in intent['layout']:
            validate(item, 'layout-constraint.schema.json')
            vocabulary.document({'layout': [item]})
            for field in set(item) - {'kind'}:
                broken = {key: value for key, value in item.items() if key != field}
                with self.subTest(field=field), self.assertRaises(ValueError):
                    vocabulary.document({'layout': [broken]})
            with self.assertRaises(ValueError):
                vocabulary.document({'layout': [{**item, 'subjects': ['U1', 'U2']}]})
        with self.assertRaises(ValueError):
            validate({**intent['layout'][0], 'guard_net': []}, 'layout-constraint.schema.json')

    def test_catalog_references_dimensions_and_merged_net_short(self):
        intent, fab = fixture()
        nets = {'SUM', 'BIAS', 'GND'}
        for item in intent['layout']:
            Catalog._layout_references(item, {}, nets)
            other = 'guard_net' if item['kind'] == 'GUARD_RING' else 'return_net'
            for value in ('UNKNOWN_NET', 'SUM'):
                with self.subTest(kind=item['kind'], value=value), self.assertRaises(ValueError):
                    Catalog._layout_references({**item, other: value}, {}, nets)
        guard = intent['layout'][0]
        for field in ('min_width', 'min_clearance'):
            for value in (quantity(0, 'mm'), quantity(-1, 'mm'), quantity(float('inf'), 'mm'),
                          quantity(.25, 'V'), {'status': 'UNKNOWN'}, {'min': .2, 'max': .3, 'unit': 'mm'}):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    Catalog._layout_references({**guard, field: value}, {}, nets)
            with self.assertRaisesRegex(ValueError, 'fab minimum'):
                validate_reference_paths([{**guard, field: quantity(.1, 'mm')}], nets, fab)

    def test_expansion_resolves_both_net_fields_and_preserves_requirements(self):
        intent, _ = fixture()
        block = {'layout': intent['layout']}
        state = SimpleNamespace(blocks={'sense': block}, resolved={
            'sense:SUM': 'sense_SUM', 'sense:BIAS': 'sense_BIAS', 'sense:GND': 'common_ground'},
            intent={'layout': [], 'nets': [], 'mechanical': {'edge_interfaces': []}}, parts={}, used=set(),
            catalog=SimpleNamespace(search=lambda _: []))
        _Expansion.apply_layout_rules(state)
        guard, path = state.intent['layout']
        self.assertEqual((guard['net'], guard['guard_net']), ('sense_SUM', 'sense_BIAS'))
        self.assertEqual((path['net'], path['return_net']), ('sense_SUM', 'common_ground'))
        self.assertEqual(guard['min_width'], block['layout'][0]['min_width'])
        state.resolved['sense:BIAS'] = 'sense_SUM'
        state.intent['layout'] = []
        _Expansion.apply_layout_rules(state)
        with self.assertRaisesRegex(ValueError, 'remain distinct'):
            validate_reference_paths(state.intent['layout'], {'sense_SUM', 'common_ground'})

    def test_export_width_clearance_and_unproven_complete_requirements(self):
        intent, fab = fixture()
        catalog = SimpleNamespace(get=lambda *_: fab)
        text = export_rules(intent, catalog)
        self.assertIn('constraint clearance (min 0.200000mm)', text)
        self.assertIn("A.NetName == 'SUM' && B.NetName == 'BIAS'", text)
        self.assertIn('constraint track_width (min 0.250000mm)', text)
        self.assertIn('"return_net": "GND"', text)
        self.assertIn('"guard_net": "BIAS"', text)
        self.assertEqual(export_rules(deepcopy(intent), catalog), text)
        project = project_settings(intent, catalog)
        pattern = next(p for p in project['net_settings']['netclass_patterns'] if p['pattern'] == 'BIAS')
        netclass = next(c for c in project['net_settings']['classes'] if c['name'] == pattern['netclass'])
        self.assertEqual(netclass['track_width'], .25)
        intent['layout'][0]['guard_net'] = 'SUM'
        with self.assertRaises(ValueError):
            export_rules(intent, catalog)

    def test_layout_without_projected_copper_remains_not_checkable(self):
        intent, _ = fixture()
        checker = LayoutChecks.__new__(LayoutChecks)
        checker.board = {}
        for item in intent['layout']:
            result = checker.check(item)
            self.assertEqual(result['result'], 'NOT_CHECKABLE')
            expected = 'required' if item['kind'] == 'RETURN_PATH' else 'not proven'
            self.assertIn(expected, result['reason'])
