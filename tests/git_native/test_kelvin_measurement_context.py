"""Explicit fixture context uses the production Kelvin geometry without a fake catalog."""
import copy
import unittest

from pcbknowledge.v2.layout_kelvin import check_kelvin, check_kelvin_geometry, terminal_types
from tests.git_native.test_v2_layout_kelvin import Catalog, fixture, track


class KelvinMeasurementContextTests(unittest.TestCase):
    def test_explicit_original_roles_match_production_and_preserve_inputs(self):
        board, rule, intent = fixture()
        roles = terminal_types(intent, Catalog())
        original = copy.deepcopy((board, rule, roles))
        result = check_kelvin_geometry(board, rule, roles)
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(result, check_kelvin(board, rule, intent, Catalog()))
        self.assertEqual((board, rule, roles), original)

    def test_missing_mapped_roles_are_not_checkable(self):
        board, rule, intent = fixture()
        roles = terminal_types(intent, Catalog())
        del roles['R1.pin:1']
        result = check_kelvin_geometry(board, rule, roles)
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertIn('pin type is missing', result['reason'])
        self.assertEqual(check_kelvin_geometry(board, rule, {})['result'], 'NOT_CHECKABLE')

    def test_proven_load_branch_fails_in_both_entry_points(self):
        board, rule, intent = fixture()
        board['segments'][2] = track((-3, 3), (-3, 6))
        board['footprints']['J1']['pads']['1'][0]['at'] = [-3, 6]
        result = check_kelvin_geometry(board, rule, terminal_types(intent, Catalog()))
        self.assertEqual(result['result'], 'FAIL')
        self.assertIn('load terminal', result['reason'])
        self.assertEqual(result, check_kelvin(board, rule, intent, Catalog()))

    def test_exact_positive_area_boundary_is_unchanged(self):
        for x, state in ((-3.900001, 'PASS'), (-3.9, 'NOT_CHECKABLE'), (-3.899999, 'FAIL')):
            board, rule, intent = fixture()
            board['segments'][0]['start'] = [x, 3]
            result = check_kelvin_geometry(board, rule, terminal_types(intent, Catalog()))
            self.assertEqual(result['result'], state)
            self.assertEqual(result, check_kelvin(board, rule, intent, Catalog()))

    def test_unsupported_geometry_and_catalog_errors_remain_not_checkable(self):
        board, rule, intent = fixture()
        board['unsupported'].append('Original unsupported test geometry')
        result = check_kelvin_geometry(board, rule, terminal_types(intent, Catalog()))
        self.assertEqual(result['result'], 'NOT_CHECKABLE')
        self.assertEqual(result, check_kelvin(board, rule, intent, Catalog()))
        self.assertEqual(check_kelvin(board, rule, {}, Catalog())['result'], 'NOT_CHECKABLE')


if __name__ == '__main__':
    unittest.main()
