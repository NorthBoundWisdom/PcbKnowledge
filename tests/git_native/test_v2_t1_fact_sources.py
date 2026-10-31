"""Reviewed T1 facts retain exact part applicability and useful refusal states."""
from fractions import Fraction
from pathlib import Path
import unittest

from pcbknowledge.v2.catalog import Catalog

ROOT = Path(__file__).resolve().parents[2]


class T1FactSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')

    def test_tps3700_geometry_uses_exact_part_selected_manufacturer_drawing(self):
        package = self.catalog.get('package:ti-tps3700ddcr')
        drawing = 'source:ti-ddc0006a-mpds124i'
        selector = 'source:ti-tps3700ddcr-package-selection'
        self.assertEqual(package['scope']['mpns'], ['TPS3700DDCR'])
        self.assertIn(selector, {item['source'] for item in package['scope']['evidence']})
        self.assertIn(drawing, {item['source'] for item in package['scope']['evidence']})
        self.assertTrue(self.catalog.get(selector)['url'].endswith('/part-details/TPS3700DDCR'))
        for group in ('body', 'drawing'):
            for value in package[group].values():
                if isinstance(value, dict) and value.get('basis') == 'DATASHEET':
                    self.assertEqual(value['evidence'], {'source': drawing, 'page': 1})

    def test_precision_resistor_bounds_preserve_exact_decimal_tolerance(self):
        for name, nominal in [('yageo-rt0603brd0710kl', 10000), ('yageo-rt0603brd0768k1l', 68100)]:
            with self.subTest(part=name):
                value = self.catalog.get('part:' + name)['parameters']['resistance']
                self.assertEqual(Fraction(str(value['min'])), Fraction(nominal) * Fraction(999, 1000))
                self.assertEqual(Fraction(str(value['max'])), Fraction(nominal) * Fraction(1001, 1000))

    def test_fact_verification_does_not_promote_application_blocks(self):
        blocks = [record for identity, record in self.catalog.records.items() if identity.startswith('block:t1-')]
        self.assertEqual(len(blocks), 9)
        self.assertTrue(all(block['verification'] == 'DRAFT' for block in blocks))
        for identity in ('source:ti-ddc0006a-mpds124i', 'source:ti-tps3700ddcr-package-selection',
                         'package:ti-tps3700ddcr', 'package:wurth-74437349047'):
            record = self.catalog.get(identity)
            self.assertEqual(record['verification'], 'AGENT_VERIFIED')
            provenance = record['provenance']
            self.assertTrue(provenance['verified_by'])
            self.assertNotIn(provenance['created_by'], provenance['verified_by'])


if __name__ == '__main__':
    unittest.main()
