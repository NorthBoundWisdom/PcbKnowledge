"""Reference voltage test windows retain existing electrical envelopes and exact pins."""
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.bringup import make_bringup
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand

ROOT = Path(__file__).resolve().parents[2]


class ReferenceBringupTests(unittest.TestCase):
    def test_both_reference_windows_are_conditional_measurements_not_accuracy_claims(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        for name in ('g3', 'g4'):
            with self.subTest(design=name):
                graph = json.loads((ROOT / f'evals/golden-designs/{name}.block-graph.json').read_text())
                brief = json.loads((ROOT / f'evals/golden-designs/{name}.brief.json').read_text())
                intent = expand(catalog, graph, brief, bundle_commit='a' * 40)
                self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
                report = make_bringup(intent, graph, brief, catalog)
                self.assertEqual(report['range_coverage'], 'COMPLETE')
                self.assertEqual(report['prerequisites_status'], 'NOT_RUN')
                rail = next(row for row in report['rails'] if row['net'] == 'VREF')
                reference = next(row for row in graph['instances'] if row['id'] == 'reference')
                original = reference['parameters']['reference_voltage']
                expected = rail['expected_voltage']
                for key in ('min', 'max', 'unit'):
                    self.assertEqual(expected[key], original[key])
                self.assertEqual(expected['conditions_status'], 'NOT_RUN')
                self.assertEqual(rail['result'], 'NOT_RUN')
                declaration = graph['bringup']['rails'][0]
                self.assertEqual(declaration['at'], 'reference_U1.pin:1')
                self.assertEqual(declaration['reference_at'], 'reference_U1.pin:3')
                self.assertEqual(declaration['expected_voltage']['conditions']['regulator_load_max']['value'],
                                 reference['parameters']['load_current']['max'])
