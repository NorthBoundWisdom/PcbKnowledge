"""Source-reviewed electrical anchors replace impossible origin proxies without wider bounds."""
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.footprints import derive_footprint
from pcbknowledge.v2.placement_feasibility import minimum_separated_distance

ROOT = Path(__file__).resolve().parents[2]
CASES = [('g1v1', 'i2c-temperature-sensor', 'temperature', 'C1', 'U1', '8'),
         ('g1v2', 'usb-uart-bridge', 'bridge', 'C1', 'U1', '4'),
         ('g1v2', 'usb-uart-bridge', 'bridge', 'C2', 'U1', '16'),
         ('g2', 'g2-protected-input', 'protection', 'C2', 'C1', '1'),
         ('g2', 'g2-relay-channels', 'relay', 'RP1', 'U1', '1'),
         ('g2', 'g2-relay-channels', 'relay', 'RP2', 'U1', '2'),
         ('g2', 'g2-low-side-switch', 'switch', 'D1', 'Q1', '3')]


class Stage14AnchorTests(unittest.TestCase):
    def test_electrical_targets_preserve_three_mm_and_remove_isolated_conflict(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        expanded = {}
        for design, block_id, instance, subject, target, pin in CASES:
            with self.subTest(block=block_id, subject=subject):
                if design not in expanded:
                    graph = json.loads((ROOT / f'evals/golden-designs/{design}.block-graph.json').read_text())
                    brief = json.loads((ROOT / f'evals/golden-designs/{design}.brief.json').read_text())
                    intent = expand(catalog, graph, brief, bundle_commit='a' * 40)
                    self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
                    expanded[design] = {c['ref']: derive_footprint(catalog.get(c['package']))
                                        for c in intent['components']}
                block = catalog.get('block:' + block_id)
                rule = next(r for r in block['layout'] if r['kind'] == 'PLACE_NEAR' and r['subject'] == subject)
                self.assertEqual(rule['target'], target + '.pin:' + pin)
                self.assertEqual(rule['max_distance']['value'], 3)
                self.assertTrue(any(rule['target'] in net['connect'] and any(
                    endpoint.startswith(subject + '.pin:') for endpoint in net['connect']) for net in block['nets']))
                geometry = expanded[design]
                a, b = instance + '_' + subject, instance + '_' + target
                self.assertGreater(minimum_separated_distance(geometry, a, b), 3)
                self.assertLessEqual(minimum_separated_distance(geometry, a, b + '.pin:' + pin), 3)
