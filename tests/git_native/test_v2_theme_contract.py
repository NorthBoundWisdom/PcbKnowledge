"""D65 fixed theme and paired-cycle negative identities remain controlled."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.schema import ContractSchemas

ROOT = Path(__file__).resolve().parents[2]


class ThemeContractTests(unittest.TestCase):
    def test_each_fixed_theme_and_five_negative_cycles_accept_structural_templates(self):
        schemas = ContractSchemas()
        for name, field, fixture in [('design-brief.schema.json', 'id', 'g1.brief.json'),
                                     ('block-graph.schema.json', 'brief', 'g1.block-graph.json')]:
            template = json.loads((ROOT / 'evals/golden-designs' / fixture).read_text())
            schema = schemas.load(name)
            for identity in [f'T{i}' for i in range(1, 11)] + [f'N{i}' for i in range(5, 10)]:
                value = deepcopy(template)
                value[field] = identity
                schemas.apply(value, schema, name)
            for identity in ('T0', 'T11', 'N10', 'arbitrary'):
                value = deepcopy(template)
                value[field] = identity
                with self.assertRaises(ValueError):
                    schemas.apply(value, schema, name)
