"""Synthetic exposed-pad paste apertures and board identity tamper checks."""
import copy
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.footprints import derive_footprint, export_kicad, footprint_name
from pcbknowledge.v2.layout import identity_check
from pcbknowledge.v2.schema import validate
from tests.git_native.test_v2_footprints import package as synthetic_package
from tests.git_native.test_v2_record_contracts import quantity


class PasteMarginTests(unittest.TestCase):
    def package(self, margin=-.15):
        package = synthetic_package('gullwing_two_side', count=8, length=5, width=4,
                                    lead_span=6, lead_length=.6, lead_width=.4, pitch=1.27)
        exposed = {'number': 'EP', 'width': quantity(2.71, 'mm'), 'length': quantity(3.4, 'mm')}
        package['drawing']['exposed_pad'] = exposed
        if margin is not None:
            exposed['paste_margin'] = quantity(margin, 'mm')
        return package

    def identity(self, package, text):
        class Catalog:
            def get(self, *_):
                return package
        intent = {'components': [{'ref': 'U1', 'package': package['id'],
                                  'footprint': footprint_name(package)}], 'nets': []}
        return identity_check(board_from_text(text), intent, Catalog())

    def board(self, package, setup='', footprint_settings=''):
        text = export_kicad(package).replace('(layer "F.Cu")',
                '(layer "F.Cu") (property "Reference" "U1") ' + footprint_settings, 1)
        return '(kicad_pcb (version 20241229) ' + setup + text + ')'

    def test_optional_scalar_margin_preserves_copper_mask_and_perimeter_paste(self):
        package = self.package()
        saved = copy.deepcopy(package)
        validate(package, 'package.schema.json')
        reduced = derive_footprint(package)
        unmodified = derive_footprint(self.package(None))
        self.assertEqual(package, saved)
        self.assertEqual(reduced['pads'][:-1], unmodified['pads'][:-1])
        exposed = reduced['pads'][-1]
        self.assertEqual(exposed['paste_margin'], -.15)
        self.assertEqual((exposed['width'], exposed['height']), (2.71, 3.4))
        aperture = [round(exposed[key] + 2 * exposed['paste_margin'], 6) for key in ('width', 'height')]
        self.assertEqual(aperture, [2.41, 3.1])
        self.assertAlmostEqual(aperture[0] * aperture[1], 7.471)
        text = export_kicad(package)
        self.assertEqual(text.count('(solder_paste_margin -0.15)'), 1)
        self.assertNotIn('solder_mask_margin', text)
        self.assertEqual(self.identity(package, self.board(package))['result'], 'PASS')
        for default in (None, 0):
            original = self.package(default)
            self.assertEqual(self.identity(original, self.board(original))['result'], 'PASS')

    def test_nonfinite_positive_collapsing_ranges_and_wrong_units_refuse(self):
        for margin in (True, float('nan'), float('inf'), .01, -1.355, -2):
            with self.subTest(margin=margin), self.assertRaises(ValueError):
                derive_footprint(self.package(margin))
        for bad in ({'min': -.15, 'max': -.1, 'unit': 'mm'},
                    {'value': -.15, 'max': 0, 'unit': 'mm'}, {'value': -.15, 'unit': 'm'}):
            package = self.package()
            package['drawing']['exposed_pad']['paste_margin'] = bad
            with self.assertRaises(ValueError):
                derive_footprint(package)
        package = self.package(-.0000006)
        package['drawing']['exposed_pad']['width'] = quantity(.000001, 'mm')
        with self.assertRaisesRegex(ValueError, 'collapses'):
            derive_footprint(package)

    def test_pad_margin_deletion_edit_and_ratio_override_fail_identity(self):
        package = self.package()
        original = self.board(package)
        for replacement in ('', '(solder_paste_margin -0.1)',
                            '(solder_paste_margin -0.15) (solder_paste_margin_ratio -0.1)',
                            '(solder_paste_margin -0.15) (solder_paste_margin_ratio 0.0000001)'):
            text = original.replace('(solder_paste_margin -0.15)', replacement)
            self.assertEqual(self.identity(package, text)['result'], 'FAIL')

    def test_inherited_board_and_footprint_settings_cannot_bypass_default_zero(self):
        package = self.package()
        settings = [('(setup (pad_to_paste_clearance -0.1))', ''),
                    ('(setup (pad_to_paste_clearance_ratio -0.1))', ''),
                    ('', '(solder_paste_margin -0.1)'),
                    ('', '(solder_paste_margin_ratio -0.1)'),
                    ('', '(solder_paste_ratio -0.1)')]
        for setup, local in settings:
            with self.subTest(setup=setup, local=local):
                self.assertEqual(self.identity(package, self.board(package, setup, local))['result'], 'FAIL')
        # An explicit zero overrides inherited settings in KiCad 9.
        plain = self.package(0)
        text = self.board(plain, '(setup (pad_to_paste_clearance -0.1))')
        text = text.replace('(size ', '(solder_paste_margin 0) (size ')
        text = text.replace('(solder_paste_margin 0))', ')')
        self.assertEqual(self.identity(plain, text)['result'], 'PASS')

    def test_ambiguous_and_malformed_board_paste_settings_fail_closed(self):
        for setting in ('(solder_paste_margin nan)', '(solder_paste_margin -0.1 2)',
                        '(solder_paste_margin -0.1) (solder_paste_margin -0.2)',
                        '(solder_paste_margin_ratio 0) (solder_paste_ratio -0.2)'):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                board_from_text(self.board(self.package(), footprint_settings=setting))

    def test_unknown_pad_ratio_alias_cannot_override_inherited_ratio(self):
        package = self.package()
        text = self.board(package, footprint_settings='(solder_paste_margin_ratio -0.1)')
        text = text.replace('(solder_paste_margin -0.15)',
                            '(solder_paste_margin -0.15) (solder_paste_ratio 0)')
        with self.assertRaisesRegex(ValueError, 'Unsupported pad'):
            board_from_text(text)

    def test_zero_override_requires_explicit_supported_board_version(self):
        # Native KiCad 9 interprets old-format zeros as inheritance, not overrides.
        package = self.package(0)
        original = self.board(package, '(setup (pad_to_paste_clearance 0.2))')
        for version in ('', '(version 20240108)', '(version 20221018)', '(version 20260101)'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'KiCad 9 board format'):
                board_from_text(original.replace('(version 20241229)', version))

    def test_zero_margin_and_ratio_override_independently_in_kicad9(self):
        # Native 9.0.2: 2x4 mm pad, board .2 mm/.1 ratio, footprint -.1/-.05.
        template = '(kicad_pcb (version 20241229) (setup (pad_to_paste_clearance .2) '
        template += '(pad_to_paste_clearance_ratio .1)) (footprint "P" (layer "F.Cu") '
        template += '(property "Reference" "U1") (solder_paste_margin -.1) '
        template += '(solder_paste_margin_ratio -.05) (pad "1" smd rect (at 0 0) '
        template += '(size 2 4) (layers "F.Cu" "F.Paste") SETTING)))'
        for setting, margin, ratio in [('', -.1, -.05), ('(solder_paste_margin 0)', 0, -.05),
                                       ('(solder_paste_margin_ratio 0)', -.1, 0),
                                       ('(solder_paste_margin 0) (solder_paste_margin_ratio 0)', 0, 0)]:
            with self.subTest(setting=setting):
                board = board_from_text(template.replace('SETTING', setting))
                pad = board['footprints']['U1']['pads']['1'][0]
                self.assertEqual((pad['paste_margin'], pad['paste_ratio']), (margin, ratio))
