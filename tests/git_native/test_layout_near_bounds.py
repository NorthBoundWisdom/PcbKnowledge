"""Necessary geometric bounds never substitute for searching or placing a board."""
import copy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pcbknowledge.v2.layout_near_bounds import isolated_near_bounds, validate_near_bounds


def fixture():
    part = {'id': 'part:test', 'package': 'package:test', 'pins': [{'number': '1', 'name': 'IN'}]}
    package = {'id': 'package:test', 'mount_type': 'SMT'}
    records = {part['id']: part, package['id']: package}
    catalog = SimpleNamespace(get=lambda name, _kind: records[name])
    footprint = {'courtyard': {'min_x': -1.25, 'min_y': -1.25, 'max_x': 1.25, 'max_y': 1.25},
                 'pads': [{'number': '1', 'x': 0, 'y': 0}]}
    intent = {'status': 'EXPANDED', 'manufacturing': {'assembly_side': 'TOP'},
              'components': [{'ref': ref, 'part': part['id'], 'package': package['id'],
                              'assembly_method': 'SMT_ASSEMBLY'} for ref in ('R1', 'RT1')],
              'layout': [{'kind': 'PLACE_NEAR', 'subject': 'R1', 'target': 'RT1',
                          'max_distance': {'unit': 'mm', 'value': 4.499999}},
                         {'kind': 'KEEPOUT', 'subject': 'RT1', 'margin': {'unit': 'mm', 'value': 2}}]}
    return catalog, intent, footprint


class NearBoundTests(unittest.TestCase):
    def test_impossible_pair_names_both_references_and_keeps_input(self):
        catalog, intent, footprint = fixture()
        original = copy.deepcopy(intent)
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            self.assertEqual(isolated_near_bounds(catalog, intent)[0]['lower_bound_mm'], Fraction(9, 2))
            with self.assertRaisesRegex(ValueError, 'R1 -> RT1.*9/2'):
                validate_near_bounds(catalog, intent)
        self.assertEqual(intent, original)

    def test_equality_is_not_an_impossibility_proof(self):
        catalog, intent, footprint = fixture()
        intent['layout'][0]['max_distance']['value'] = 4.5
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            validate_near_bounds(catalog, intent)
            self.assertFalse(isolated_near_bounds(catalog, intent)[0]['impossible'])

    def test_projected_keepout_applies_across_faces_and_mount_types(self):
        catalog, intent, footprint = fixture()
        intent['manufacturing']['assembly_side'] = 'BOTH'
        intent['components'][1]['assembly_method'] = 'HAND_SOLDER'
        catalog.get('package:test', 'package')['mount_type'] = 'THT'
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            with self.assertRaisesRegex(ValueError, 'R1 -> RT1.*projected'):
                validate_near_bounds(catalog, intent)

    def test_no_explicit_exclusion_has_no_nonzero_proof(self):
        catalog, intent, footprint = fixture()
        intent['layout'].pop()
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            self.assertEqual(isolated_near_bounds(catalog, intent), [])

    def test_pad_center_is_not_replaced_by_footprint_origin(self):
        catalog, intent, footprint = fixture()
        intent['layout'][0].update(target='RT1.pin:IN', max_distance={'unit': 'mm', 'value': 3.75})
        footprint['pads'][0]['x'] = 0.75
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            bound = isolated_near_bounds(catalog, intent)[0]
            self.assertEqual(bound['lower_bound_mm'], Fraction(15, 4))
            self.assertFalse(bound['impossible'])

    def test_duplicate_physical_pads_use_smallest_radius(self):
        catalog, intent, footprint = fixture()
        intent['layout'][0].update(target='RT1.pin:1', max_distance={'unit': 'mm', 'value': 3.5})
        footprint['pads'].append({'number': '1', 'x': 1, 'y': 0})
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            bound = isolated_near_bounds(catalog, intent)[0]
            self.assertEqual(bound['lower_bound_mm'], Fraction(7, 2))
            self.assertFalse(bound['impossible'])
        footprint['pads'][1]['x'] = 2
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            self.assertEqual(isolated_near_bounds(catalog, intent), [])

    def test_off_center_courtyard_uses_actual_origin(self):
        catalog, intent, footprint = fixture()
        footprint['courtyard']['min_x'] = -0.25
        intent['layout'][0]['max_distance']['value'] = 2.5
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            bound = isolated_near_bounds(catalog, intent)[0]
            self.assertEqual(bound['lower_bound_mm'], Fraction(5, 2))
            self.assertFalse(bound['impossible'])

    def test_real_audit_reports_checked_occurrences_not_feasibility(self):
        from pcbknowledge.v2.audit import design_inputs, require_audit
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.expansion import expand
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        result = require_audit(catalog)
        graphs, briefs = design_inputs(root)
        count = sum(len(isolated_near_bounds(catalog, expand(
            catalog, graph, briefs[graph['brief']], bundle_commit='0' * 40))) for graph in graphs)
        self.assertIsInstance(result['near_bounds_checked'], int)
        self.assertGreaterEqual(result['near_bounds_checked'], 0)
        self.assertEqual(result['near_bounds_checked'], count)

    def test_real_audit_rejects_impossible_expanded_pair(self):
        from pcbknowledge.v2.audit import require_audit
        from pcbknowledge.v2.catalog import Catalog
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        block = catalog.records['block:mcu-core']
        near = next(rule for rule in block['layout'] if rule['kind'] == 'PLACE_NEAR')
        near['max_distance']['value'] = 0
        block['layout'].append({'kind': 'KEEPOUT', 'subject': near['subject'],
                                'margin': {'unit': 'mm', 'value': 1, 'basis': 'ENGINEERING_DEFAULT',
                                           'conditions': {}, 'note': 'Synthetic contradiction test.'}})
        with self.assertRaisesRegex(ValueError, r'mcu_C1 -> mcu_U1\.pin:1.*explicit KEEPOUT'):
            require_audit(catalog)

    def test_copper_edge_no_same_net_cannot_inherit_center_bound(self):
        catalog, intent, footprint = fixture()
        intent['layout'][0].update(datum='COPPER_EDGE', target='RT1.pin:1',
                                   max_distance={'unit': 'mm', 'value': 0})
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            self.assertEqual(isolated_near_bounds(catalog, intent), [])

    def test_unproved_or_unsupported_context_is_not_rejected_as_impossible(self):
        catalog, intent, footprint = fixture()
        intent['layout'][0].update(target='RT1.pin:absent')
        with patch('pcbknowledge.v2.layout_near_bounds.derive_footprint', return_value=footprint):
            self.assertEqual(isolated_near_bounds(catalog, intent), [])
        intent['status'] = 'REFUSED'
        self.assertEqual(isolated_near_bounds(catalog, intent), [])


if __name__ == '__main__':
    unittest.main()
