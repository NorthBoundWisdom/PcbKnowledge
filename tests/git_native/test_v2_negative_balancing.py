"""Two-cell balancing absence is a catalog screening result, not physical impossibility."""
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class NegativeBalancingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/corpus/themes/n5.brief.json').read_bytes())

    def test_schema_and_exact_missing_balancing_function(self):
        self.catalog.structure(self.brief, 'design-brief.schema.json')
        self.assertEqual(self.brief['expected_refusal'],
                         {'code': 'UNSATISFIED_SELECTION', 'requirement': 'cell_balance'})
        result = assess_brief(self.catalog, self.brief)
        self.assertEqual([(row['code'], row['path']) for row in result],
                         [('UNSATISFIED_SELECTION', 'functions.cell_balance')])
        self.assertTrue(result[0]['reason'])
        self.assertEqual(result[0]['queries'], ['Q1'])

    def test_synthetic_eligible_contract_removes_absence_refusal(self):
        # This is an abstract screening fixture, not a circuit or a promoted knowledge record.
        # assess_brief establishes eligibility only; expansion still has to prove any real circuit.
        block = {'id': 'block:synthetic-two-cell-balancer', 'category': 'power.cell-balancing',
                 'verification': 'AGENT_VERIFIED', 'parameters': {}, 'components': [],
                 'ports': [{'name': name} for name in ('PACK_NEG', 'CELL_MID', 'PACK_POS')]}
        self.catalog.records[block['id']] = block
        self.assertEqual(assess_brief(self.catalog, self.brief), [])
        block['verification'] = 'DRAFT'
        result = assess_brief(self.catalog, self.brief)
        self.assertEqual([(row['code'], row['path']) for row in result],
                         [('UNVERIFIED_RECORD', 'functions.cell_balance')])
