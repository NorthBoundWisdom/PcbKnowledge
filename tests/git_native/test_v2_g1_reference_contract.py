"""Reviewed G1 power-connector substitution and conditional hardware test plan."""
import json
import math
from pathlib import Path
import unittest

from pcbknowledge.v2.bringup import make_bringup
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.footprints import derive_footprint

ROOT = Path(__file__).resolve().parents[2]


class ReferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')

    def test_power_only_connector_preserves_usb_data_block_and_hole_rules(self):
        power = self.catalog.get('block:usb-c-5v-sink')
        data = self.catalog.get('block:usb-c-usb2-sink')
        self.assertEqual(power['components'][0]['select']['part'], 'part:gct-usb4125-gf-a-0190')
        self.assertEqual(data['components'][0]['select']['part'], 'part:gct-usb4110-gf-a')
        package = self.catalog.get('package:gct-usb4125-gf-a-0190')
        pads = derive_footprint(package)['pads']
        self.assertEqual(len(pads), 10)
        self.assertFalse(any(p['kind'] == 'MECHANICAL' for p in pads))
        holes = [p for p in pads if p['kind'] == 'THROUGH_HOLE']
        contacts = [p for p in pads if p['kind'] == 'SMD']
        self.assertEqual(len(holes), 4)
        self.assertEqual({p['number'] for p in contacts}, {'A5', 'B5', 'B12', 'B9', 'A9', 'A12'})
        for hole in holes:
            for axis in ('width', 'height'):
                self.assertAlmostEqual((hole[axis] - hole['drill_' + axis]) / 2, .25)
            for contact in contacts:
                dx = max(abs(contact['x'] - hole['x']) - contact['width'] / 2, 0)
                segment = (hole['drill_height'] - hole['drill_width']) / 2
                dy = max(abs(contact['y'] - hole['y']) - contact['height'] / 2 - segment, 0)
                self.assertGreaterEqual(math.hypot(dx, dy) - hole['drill_width'] / 2, .25)

    def test_every_rail_has_an_independent_conditional_window_and_no_observation(self):
        graph = json.loads((ROOT / 'evals/golden-designs/g1.block-graph.json').read_text())
        brief = json.loads((ROOT / 'evals/golden-designs/g1.brief.json').read_text())
        intent = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'EXPANDED')
        report = make_bringup(intent, graph, brief, self.catalog)
        self.assertEqual(report['range_coverage'], 'COMPLETE')
        self.assertEqual(report['a6'], 'NOT_RUN')
        self.assertEqual(report['prerequisites_status'], 'NOT_RUN')
        expected = {'USB_VBUS': (4.75, 5.25), 'PROTECTED_5V': (4.62, 5.25),
                    'REGULATED_3V3': (3.18, 3.42), 'LOGGER_3V3': (3.16, 3.42), 'MCU_VDDA': (3.04, 3.42)}
        self.assertEqual({row['net'] for row in report['rails']}, set(expected))
        for row in report['rails']:
            window = row['expected_voltage']
            self.assertEqual((window['min'], window['max']), expected[row['net']])
            self.assertEqual(window['acceptance_type'], 'ENGINEERING_TEST_WINDOW')
            self.assertEqual(window['conditions_status'], 'NOT_RUN')
            self.assertTrue(window['conditions'])
            self.assertIn('contextual_expectation', window)
            self.assertEqual(row['declared_reference_location']['ref'], 'ldo_U1')
            self.assertEqual(row['declared_reference_location']['pin'], '1')
