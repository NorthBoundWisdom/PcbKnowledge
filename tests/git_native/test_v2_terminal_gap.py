"""Hand-derived chip lands from terminal span and a separately cited inner gap."""
import copy
import unittest

from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.schema import validate
from tests.git_native.test_v2_footprints import package
from tests.git_native.test_v2_record_contracts import quantity


class TerminalGapTests(unittest.TestCase):
    def package(self):
        item = package('chip', length=6.8, width=6.8, lead_span=7.3, lead_width=.8, terminal_gap=2.1)
        item['drawing']['lead_span'] = {**quantity(7.3, 'mm'), 'min': 7.1, 'typ': 7.3, 'max': 7.5}
        del item['drawing']['lead_span']['value']
        item['drawing']['terminal_gap'] = {**quantity(2.1, 'mm'), 'typ': 2.1}
        del item['drawing']['terminal_gap']['value']
        return item

    def test_reference_gap_and_span_tolerances_have_correlated_inner_edges(self):
        for span, gap, lead_width, expected in (([7.1, 7.3, 7.5], 2.1, .8, (2.475, 2.95, .9)),
                                               ([8.8, 9, 9.2], 3.2, 1.1, (3.175, 3.25, 1.2))):
            item = self.package()
            drawing = item['drawing']
            drawing['lead_span'].update(zip(('min', 'typ', 'max'), span))
            drawing['terminal_gap']['typ'] = gap
            drawing['lead_width']['value'] = lead_width
            original = copy.deepcopy(item)
            validate(item, 'package.schema.json')
            pads = derive_footprint(item)['pads']
            self.assertEqual(item, original)
            self.assertEqual((pads[1]['x'], pads[1]['width'], pads[1]['height']), expected)
            self.assertEqual(pads[0]['x'], -expected[0])
            self.assertNotIn('lead_length', item['drawing'])

    def test_scalar_and_bounded_gap_are_supported_without_extra_fillet(self):
        item = self.package()
        item['drawing']['terminal_gap'] = quantity(2.1, 'mm')
        self.assertEqual(derive_footprint(item)['pads'][1]['width'], 2.95)
        item['drawing']['terminal_gap'] = {'min': 2, 'max': 2.2, 'unit': 'mm'}
        self.assertEqual(derive_footprint(item)['pads'][1]['width'], 3)

    def test_missing_competing_or_unsupported_authorities_refuse(self):
        for change in ('missing', 'both', 'opposite', 'generator'):
            item = self.package()
            if change == 'missing':
                del item['drawing']['terminal_gap']
            elif change == 'both':
                item['drawing']['lead_length'] = quantity(2.6, 'mm')
            elif change == 'opposite':
                item['drawing']['opposite_lead_length'] = quantity(2.6, 'mm')
            else:
                item['generator'] = 'molded_diode'
            with self.subTest(change=change), self.assertRaises(ValueError):
                derive_footprint(item)

    def test_invalid_gap_and_span_ranges_refuse(self):
        gaps = [quantity(value, 'mm') for value in (0, -1, 7.1, 8, True, float('inf'))]
        gaps += [{'min': 3, 'max': 2, 'unit': 'mm'}, {'min': 2, 'typ': 4, 'max': 3, 'unit': 'mm'},
                 {'value': 2, 'typ': 2, 'unit': 'mm'}, {'value': 2, 'unit': 'm'},
                 {'min': 2, 'unit': 'mm'}, {'status': 'UNKNOWN'}]
        for gap in gaps:
            item = self.package()
            item['drawing']['terminal_gap'] = gap
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                derive_footprint(item)
        item = self.package()
        item['drawing']['lead_span'].update(min=8, max=7)
        with self.assertRaises(ValueError):
            derive_footprint(item)
