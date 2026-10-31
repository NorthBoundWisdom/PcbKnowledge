"""G1 constraint semantics plus synthetic physical-anchor counterexamples."""
import copy
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.placement import PlacementError, validate_positions
from tests.git_native.test_v2_placement import part, q

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
        geometry = {'U': part(6, 4, [('8', 3, 0)]), 'C': part(1, 1)}
        positions = {'U': (5, 5, 0), 'C': (9, 5, 0)}
        original = {'kind': 'PLACE_NEAR', 'subject': 'C', 'target': 'U', 'max_distance': q(3)}
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, [original], positions, 15, 10)
        corrected = dict(original, target='U.pin:8')
        validate_positions(geometry, [corrected], positions, 15, 10)
        too_far = dict(positions, C=(12, 5, 0))
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, [corrected], too_far, 15, 10)
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
        geometry = {r: part(.5, .5) for r in group['subjects']}
        positions = {'U1': (1, 1, 0), 'Y1': (11, 1, 0), 'C8': (5, 1, 0), 'C9': (8, 1, 0)}
        validate_positions(geometry, [group], positions, 15, 5)
        positions['Y1'] = (11.01, 1, 0)
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, [group], positions, 15, 5)

    def test_usb_mating_face_datum_preserves_one_mm_edge_rule(self):
        package = record('packages', 'gct-usb4110-gf-a')
        geometry = {'J1': derive_footprint(package)}
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
        validate_positions(geometry, [rule], {'J1': (10, .5, 0)}, 25, 20)
        with self.assertRaisesRegex(PlacementError, 'unsatisfied'):
            validate_positions(geometry, [rule], {'J1': (10, 1.01, 0)}, 25, 20)
        centered = copy.deepcopy(geometry)
        for pad in centered['J1']['pads']:
            pad['y'] -= 3.85
        centered['J1']['courtyard']['min_y'] -= 3.85
        centered['J1']['courtyard']['max_y'] -= 3.85
        with self.assertRaisesRegex(PlacementError, 'outside'):
            validate_positions(centered, [rule], {'J1': (10, .5, 0)}, 25, 20)

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
