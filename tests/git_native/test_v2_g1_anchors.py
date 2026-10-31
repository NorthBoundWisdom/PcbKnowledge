"""G1 constraint semantics plus synthetic physical-anchor counterexamples."""
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.layout import LayoutChecks


def q(value):
    return {"value": value, "unit": "mm"}

# Resolve the installed source tree, not the temporary draft's directory.
import pcbknowledge
ROOT = Path(pcbknowledge.__file__).resolve().parents[2]


def record(kind, name):
    return json.loads((ROOT / 'knowledge' / kind / (name + '.json')).read_text())


def near(block, subject):
    return next(r for r in block['layout'] if r['kind'] == 'PLACE_NEAR' and r['subject'] == subject)


class PhysicalAnchorTests(unittest.TestCase):
    def test_supply_and_protection_anchors_are_on_the_intended_net(self):
        cases = [('i2c-eeprom', 'C1', 'U1.pin:8'),
                 ('input-protection', 'D1.pin:1', 'F1.pin:2')]
        for name, subject, target in cases:
            with self.subTest(block=name):
                block = record('blocks', name)
                rule = near(block, subject)
                self.assertEqual(rule['target'], target)
                self.assertEqual(rule['max_distance']['value'], 3)
                physical_subject = subject if '.pin:' in subject else subject + '.pin:1'
                self.assertTrue(any({physical_subject, target} <= set(n['connect']) for n in block['nets']))

    def test_pad_anchor_corrects_origin_proxy_without_increasing_limit(self):
        board = {'footprints': {'U': {'at': [5, 5], 'pads': {'8': [{'at': [8, 5]}]}},
                                'C': {'at': [9, 5], 'pads': {}}}}
        checker = LayoutChecks(board, {'components': []}, None)
        original = {'kind': 'PLACE_NEAR', 'subject': 'C', 'target': 'U', 'max_distance': q(3)}
        self.assertEqual(checker.check(original)['result'], 'FAIL')
        corrected = dict(original, target='U.pin:8')
        self.assertEqual(checker.check(corrected)['result'], 'PASS')
        board['footprints']['C']['at'] = [12, 5]
        self.assertEqual(checker.check(corrected)['result'], 'FAIL')
        self.assertEqual(original['max_distance'], corrected['max_distance'])

    def test_oscillator_keeps_proximity_group_loop_and_numbered_wiring(self):
        block = record('blocks', 'mcu-core')
        rule = near(block, 'Y1')
        self.assertEqual((rule['target'], rule['max_distance']['value']), ('U1.pin:5', 5))
        group = next(r for r in block['layout'] if r['kind'] == 'GROUP' and 'Y1' in r['subjects'])
        self.assertEqual(set(group['subjects']), {'U1', 'Y1', 'C8', 'C9'})
        # GROUP's ten millimetre bound is the checker contract, not a mutable block value.
        loop = next(r for r in block['layout'] if r['kind'] == 'MINIMIZE_LOOP')
        self.assertEqual(loop['max_area']['value'], 25)
        self.assertEqual(loop['path'], ['U1.pin:5', 'Y1.pin:1', 'Y1.pin:3', 'U1.pin:6'])
        nets = {n['name']: set(n['connect']) for n in block['nets']}
        self.assertTrue({'Y1.pin:2', 'Y1.pin:4'} <= nets['GND'])
        self.assertIn('Y1.pin:1', nets['OSC_IN'])
        self.assertIn('Y1.pin:3', nets['OSC_OUT'])
        board = {'footprints': {ref: {'at': point, 'pads': {}} for ref, point in
                                [('U1', [1, 1]), ('Y1', [11, 1]), ('C8', [5, 1]), ('C9', [8, 1])]}}
        checker = LayoutChecks(board, {'components': []}, None)
        self.assertEqual(checker.check(group)['result'], 'PASS')
        board['footprints']['Y1']['at'] = [11.01, 1]
        self.assertEqual(checker.check(group)['result'], 'FAIL')

    def test_usb_mating_face_datum_preserves_one_mm_edge_rule(self):
        package = record('packages', 'gct-usb4110-gf-a')
        self.assertEqual(package['body']['center']['y']['value'], 3.85)
        for name in ('usb-c-5v-sink', 'usb-c-usb2-sink'):
            block = record('blocks', name)
            edge = next(r for r in block['layout'] if r['kind'] == 'EDGE_PLACEMENT')
            self.assertEqual(edge['max_distance']['value'], 1)
            self.assertEqual(near(block, 'R1')['target'], 'J1.pin:A5')
            self.assertEqual(near(block, 'R2')['target'], 'J1.pin:B5')
            self.assertEqual(near(block, 'R1')['max_distance']['value'], 3)
            self.assertEqual(near(block, 'R2')['max_distance']['value'], 3)
        # A synthetic top-edge rule isolates datum behavior from connector side choice.
        rule = {'kind': 'EDGE_PLACEMENT', 'subject': 'J1', 'edge': 'TOP', 'max_distance': q(1)}
        board = {'footprints': {'J1': {'at': [10, .5], 'pads': {}}},
                 'outline': {'closed': True, 'rectangular': True, 'bounds': [0, 0, 25, 20]}}
        checker = LayoutChecks(board, {'components': []}, None)
        self.assertEqual(checker.check(rule)['result'], 'PASS')
        board['footprints']['J1']['at'] = [10, 1.01]
        self.assertEqual(checker.check(rule)['result'], 'FAIL')

    def test_usb_manufacturer_lands_and_nonconductive_locators(self):
        package = record('packages', 'gct-usb4110-gf-a')
        pads = derive_footprint(package)['pads']
        electrical = {p['number']: p for p in pads if p['kind'] != 'MECHANICAL'}
        terminals = {p['number'] for p in record('parts', 'gct-usb4110-gf-a')['pins']}
        self.assertEqual(set(electrical), terminals)
        self.assertEqual(len(terminals), 16)
        self.assertEqual(len(pads), 18)
        signal = [p for p in electrical.values() if not p['number'].startswith('SHELL')]
        self.assertEqual({p['y'] for p in signal}, {7.355})
        self.assertEqual({p['height'] for p in signal}, {1.15})
        narrow = sorted((p for p in signal if p['width'] == .3), key=lambda p: p['x'])
        self.assertEqual(len(narrow), 8)
        for a, b in zip(narrow, narrow[1:]):
            self.assertAlmostEqual(b['x'] - a['x'], .5)
            self.assertAlmostEqual(b['x'] - a['x'] - .3, .2)
        self.assertEqual({p['drill'] for p in pads if p['kind'] == 'MECHANICAL'}, {.65})


if __name__ == '__main__':
    unittest.main()
