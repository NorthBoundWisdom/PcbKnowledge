"""D102 preserves G2 proximity bounds while its distance datum is escalated."""
from pathlib import Path
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.layout import LayoutChecks

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = [(0, 'C2', 'U1.pin:7', 1, 1.96), (1, 'C3', 'U1.pin:1', 2, 1.62),
            (2, 'D1', 'U1.pin:8', 2, 2.51), (3, 'C4', 'L1.pin:2', 3, 5.95),
            (4, 'RF1', 'U1.pin:4', 3, 1.595), (8, 'C5', 'U1.pin:7', 1, 2.21),
            (9, 'C6', 'U1.pin:7', 1, 2.21), (10, 'C2', 'U1.pin:6', 1, 1.96),
            (11, 'C5', 'U1.pin:6', 1, 2.21), (12, 'C6', 'U1.pin:6', 1, 2.21)]


class BuckDistanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.block = self.catalog.get('block:g2-buck')
        self.packages = {item['ref']: self.catalog.get(item['select']['part'])['package']
                         for item in self.block['components']}
        self.geometry = {ref: derive_footprint(self.catalog.get(package))
                         for ref, package in self.packages.items()}

    def test_all_ten_rules_and_eight_isolated_courtyard_conflicts_remain(self):
        rules = [(i, rule['subject'], rule['target'], rule['max_distance']['value'])
                 for i, rule in enumerate(self.block['layout']) if rule['kind'] == 'PLACE_NEAR']
        self.assertEqual(rules, [row[:4] for row in EXPECTED])
        conflicts = []
        for index, subject, target, limit, expected_bound in EXPECTED:
            ref, _, pin = target.partition('.pin:')
            source_box, target_box = self.geometry[subject]['courtyard'], self.geometry[ref]['courtyard']
            source_margin = min(-source_box['min_x'], source_box['max_x'],
                                -source_box['min_y'], source_box['max_y'])
            target_margin = min(min(pad['x'] - target_box['min_x'], target_box['max_x'] - pad['x'],
                                    pad['y'] - target_box['min_y'], target_box['max_y'] - pad['y'])
                                for pad in self.geometry[ref]['pads'] if pad['number'] == pin)
            # Disjoint same-surface courtyards imply disjoint inscribed discs.
            # Their radius sum is necessary, not a jointly achievable layout.
            self.assertGreaterEqual(source_margin, 0)
            self.assertGreaterEqual(target_margin, 0)
            bound = source_margin + target_margin
            self.assertAlmostEqual(bound, expected_bound)
            self.assertEqual(self.block['layout'][index]['max_distance']['unit'], 'mm')
            if bound > limit:
                conflicts.append(index)
        self.assertEqual(conflicts, [0, 2, 3, 8, 9, 10, 11, 12])

    def test_exported_synthetic_pairs_keep_center_distance_failures(self):
        for index, subject, target, limit, bound in EXPECTED:
            if bound <= limit:
                continue
            ref, _, pin = target.partition('.pin:')
            for distance, expected in ((bound, 'FAIL'), (limit, 'PASS'), (limit + .000001, 'FAIL')):
                with self.subTest(index=index, distance=distance):
                    text = f'''(kicad_pcb (version 20241229)
                      (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
                      (footprint "Test:Pair" (layer "F.Cu") (at {distance} 0)
                        (property "Reference" "{subject}"))
                      (footprint "Test:Pair" (layer "F.Cu") (at 0 0)
                        (property "Reference" "{ref}")
                        (pad "{pin}" smd rect (at 0 0) (size 0.2 0.2) (layers "F.Cu"))))'''
                    board = board_from_text(text)
                    intent = {'components': [{'ref': name, 'package': self.packages[name]}
                                             for name in (subject, ref)]}
                    report = LayoutChecks(board, intent, self.catalog).check(self.block['layout'][index])
                    self.assertEqual(report['result'], expected)
                    self.assertAlmostEqual(report['distance_mm'], distance)
