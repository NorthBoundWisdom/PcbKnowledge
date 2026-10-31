"""Preserve the observed USB2 locator conflict without changing its geometry."""
import math
from pathlib import Path
import unittest

from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.footprints import derive_footprint

ROOT = Path(__file__).resolve().parents[2]
# D68 retains the KiCad hole-to-copper floor observed in native KiCad 9 reports.
# This is not the separately named annular_ring_min or copper clearance_min.
D68_HOLE_COPPER_FLOOR_MM = .25


class USB2FabConflictTests(unittest.TestCase):
    def test_exact_usb2_lands_reproduce_four_locator_conflicts(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        block = catalog.get('block:usb-c-usb2-sink', 'block')
        part = catalog.get(block['components'][0]['select']['part'], 'part')
        package = catalog.get(part['package'], 'package')
        self.assertEqual(package['id'], 'package:gct-usb4110-gf-a')
        pads = derive_footprint(package)['pads']
        conflicts = {}
        for hole in (pad for pad in pads if pad['kind'] == 'MECHANICAL'):
            self.assertEqual(hole['shape'], 'ROUND')
            for pad in (pad for pad in pads if pad['kind'] == 'SMD'):
                self.assertEqual(pad['shape'], 'RECT')
                self.assertEqual(pad['rotation'], 0)
                dx = max(abs(pad['x'] - hole['x']) - pad['width'] / 2, 0)
                dy = max(abs(pad['y'] - hole['y']) - pad['height'] / 2, 0)
                clearance = math.hypot(dx, dy) - hole['drill'] / 2
                if clearance < D68_HOLE_COPPER_FLOOR_MM:
                    conflicts[pad['number'], hole['number']] = clearance
        self.assertEqual(set(conflicts), {('A1_B12', 'NC1'), ('A4_B9', 'NC1'),
                                          ('B4_A9', 'NC2'), ('B1_A12', 'NC2')})
        for (pad, _hole), clearance in conflicts.items():
            expected = .17509999000199966 if pad in ('A1_B12', 'B1_A12') else .2098831648126535
            self.assertAlmostEqual(clearance, expected, places=10)
        fab = catalog.get('fab_profile:generic-two-layer-default', 'fab_profile')
        self.assertEqual(fab['clearance_min']['value'], .15)
        self.assertEqual(fab['annular_ring_min']['value'], .25)



if __name__ == '__main__':
    unittest.main()
