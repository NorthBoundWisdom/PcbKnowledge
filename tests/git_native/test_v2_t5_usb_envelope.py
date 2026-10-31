"""The T5 USB source retains its original voltage envelope."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand

ROOT = Path(__file__).resolve().parents[2]


class T5USBEnvelopeTests(unittest.TestCase):
    def test_actual_graph_voltage_binds_fixed_source_limits(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        graph = read_json((ROOT / 'evals/corpus/themes/t5.block-graph.json').read_bytes())
        usb = next(instance for instance in graph['instances'] if instance['block'] == 'block:t5-usb-input')
        declarations = catalog.get('block:t5-usb-input')['parameters']
        fixed = declarations['output_voltage']['fixed']
        for field in ('min', 'max', 'unit', 'basis', 'conditions'):
            self.assertEqual(fixed[field], usb['parameters']['output_voltage'][field])
        self.assertEqual(usb['parameters']['output_voltage']['min'], 4.75)
        self.assertEqual(usb['parameters']['output_voltage']['max'], 5.25)

    def test_voltage_mutations_refuse_actual_expansion(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        original = read_json((ROOT / 'evals/corpus/themes/t5.block-graph.json').read_bytes())
        brief = read_json((ROOT / 'evals/corpus/themes/t5.brief.json').read_bytes())
        for field, value in (('output_voltage', 12), ('output_voltage', 3.3)):
            with self.subTest(field=field):
                graph = deepcopy(original)
                usb = next(instance for instance in graph['instances'] if instance['block'] == 'block:t5-usb-input')
                previous = usb['parameters'][field]
                usb['parameters'][field] = {key: item for key, item in previous.items()
                                            if key not in ('min', 'max', 'typ', 'value')}
                usb['parameters'][field]['value'] = value
                intent = expand(catalog, graph, brief, bundle_commit='a' * 40)
                self.assertEqual(intent['status'], 'REFUSED')
                self.assertTrue(any(
                    row['code'] == 'CHECK_FAILED' and row['path'] == 'usb.parameters.output_voltage'
                    and row['reason'] == 'Parameter differs from fixed block operating requirement'
                    for row in intent['refusals']))
