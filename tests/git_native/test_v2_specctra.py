"""Handwritten original DSN and SES fixtures test interchange without native tools."""
import unittest
from unittest.mock import patch

from pcbknowledge.v2.specctra import configure_dsn, read_specctra, validate_session, verify_native_vias

DSN = '''(pcb "board.dsn" (parser (string_quote ")) (unit mm) (resolution mm 1000)
(structure (layer F.Cu (type signal)) (layer B.Cu (type signal))
 (via VIA) (rule (width .1) (clearance .1)))
(placement (component "chip" (place U1 5 -6 front 90)))
(library (padstack VIA (shape (circle F.Cu .8)) (shape (circle B.Cu .8))))
(network (net GND (pins U1-1)) (net VCC (pins U1-2)) (class old GND VCC (rule (width .1)))))'''
SES = '''(session "board.ses" (base_design "board.dsn")
(placement (resolution um 1000) (component "chip" (place U1 5000000 -6000000 front 90)))
(routes (resolution um 1000)
(library_out (padstack VIA (shape (circle F.Cu 800000)) (shape (circle B.Cu 800000))))
(network_out (net GND (wire (path F.Cu 150000 5000000 -6000000 6000000 -6000000) (type route))
(via VIA 6000000 -6000000)))))'''


class SpecctraTests(unittest.TestCase):
    def test_native_quote_delimiter_and_units(self):
        self.assertEqual(read_specctra(DSN)[0], 'pcb')
        report = validate_session(SES, DSN, {'GND': .15, 'VCC': .3}, dsn_name='board.dsn')
        self.assertEqual((report['wire_count'], report['via_count']), (1, 1))
        self.assertEqual(report['wires'][0]['points_mm'], [(5, -6), (6, -6)])
        self.assertAlmostEqual(report['wires'][0]['width_mm'], .15)
        stem = SES.replace('(base_design "board.dsn")', '(base_design board)')
        self.assertEqual(validate_session(stem, DSN, {'GND': .15}, dsn_name='board.dsn')['wire_count'], 1)

    def test_unknown_identity_layer_net_and_moved_placement_fail(self):
        for old, new in [('board.dsn', 'other.dsn'), ('path F.Cu', 'path In1.Cu'),
                         ('net GND', 'net UNKNOWN'), ('5000000 -6000000 front', '5000001 -6000000 front'),
                         ('via VIA ', 'via UNKNOWN '), ('150000 ', '149000 ')]:
            with self.subTest(mutation=new), self.assertRaises(ValueError):
                validate_session(SES.replace(old, new), DSN, {'GND': .15, 'VCC': .3}, dsn_name='board.dsn')

    def test_malformed_nonfinite_and_negative_width_fail(self):
        for text in (SES[:-1], SES.replace('150000 ', '-150000 '), SES.replace('150000 ', 'nan '),
                     SES.replace('6000000)', 'inf)'), SES.replace('resolution um 1000', 'resolution um 0')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_session(text, DSN, {'GND': .15, 'VCC': .3}, dsn_name='board.dsn')

    def test_dsn_classes_use_shared_authority_and_preserve_net_set(self):
        class Catalog:
            def get(self, identity, kind):
                return {'clearance_min': {'unit': 'mm', 'value': .15},
                        'trace_width_min': {'unit': 'mm', 'value': .15}}
        intent = {'fab_profile': 'fab:test', 'nets': [{'name': 'GND'}, {'name': 'VCC'}]}
        with patch('pcbknowledge.v2.specctra.net_widths', return_value={'GND': .15, 'VCC': .3}, dsn_name='board.dsn'):
            output = configure_dsn(DSN, intent, Catalog())
            self.assertIn('(width 0.3)', output)
            self.assertIn('(clearance 0.15)', output)
            self.assertNotIn('class old', output)
            with self.assertRaises(ValueError):
                configure_dsn(DSN.replace('net VCC', 'net WRONG'), intent, Catalog())

    def test_changed_or_unknown_via_geometry_is_rejected(self):
        for text in (SES.replace('800000', '700000'), SES.replace('padstack VIA', 'padstack UNKNOWN'),
                     SES.replace('circle F.Cu 800000', 'rect F.Cu 0 0 800000 800000')):
            with self.assertRaises(ValueError):
                validate_session(text, DSN, {'GND': .15, 'VCC': .3}, dsn_name='board.dsn')

    def test_native_via_geometry_must_meet_fab_drill_and_annulus(self):
        fab = {'drill_min': {'unit': 'mm', 'value': .3},
               'annular_ring_min': {'unit': 'mm', 'value': .15}}
        text = DSN.replace('VIA', 'Via[0-1]_800:300_um')
        verify_native_vias(text, fab)
        for bad in (text.replace('800:300', '800:200'), text.replace('.8)', '.6)'),
                    text.replace('800:300', '500:300')):
            with self.assertRaises(ValueError):
                verify_native_vias(bad, fab)
