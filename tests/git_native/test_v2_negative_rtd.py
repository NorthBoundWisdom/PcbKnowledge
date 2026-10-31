"""Four-wire RTD absence is a catalog result, never a physical impossibility claim."""
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class NegativeRtdTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/corpus/themes/n7.brief.json').read_bytes())

    def test_exact_missing_excitation_and_four_wire_conversion_function(self):
        self.catalog.structure(self.brief, 'design-brief.schema.json')
        self.assertEqual(self.brief['expected_refusal'],
                         {'code': 'UNSATISFIED_SELECTION', 'requirement': 'rtd_interface'})
        result = assess_brief(self.catalog, self.brief)
        self.assertEqual([(row['code'], row['path']) for row in result],
                         [('UNSATISFIED_SELECTION', 'functions.rtd_interface')])
        self.assertEqual(result[0]['queries'], ['Q1'])

    def test_synthetic_eligible_contract_removes_absence_without_claiming_a2(self):
        # Abstract screening fixture only: no invented physical circuit or promoted source.
        function = next(row for row in self.brief['functions'] if row['id'] == 'rtd_interface')
        quantities = {'drive_current': 'current', 'sample_rate': 'frequency',
                      'temperature': 'temperature', 'io_voltage': 'voltage'}
        parameters = {name: {'quantity': quantities[name], 'required': True, 'fixed': value}
                      for name, value in function['parameters'].items()}
        block = {'id': 'block:synthetic-four-wire-rtd', 'category': 'sensor.rtd',
                 'verification': 'AGENT_VERIFIED', 'components': [], 'parameters': parameters,
                 'provenance': {'notes': 'Abstract excitation, independent sensing and UART conversion contract.'},
                 'ports': [{'name': name} for name in
                           ('FORCE_POS', 'SENSE_POS', 'SENSE_NEG', 'FORCE_NEG', 'TX', 'RX', 'GND')]}
        self.catalog.records[block['id']] = block
        self.assertEqual(assess_brief(self.catalog, self.brief), [])
        from copy import deepcopy
        block['parameters'] = deepcopy(parameters)
        block['parameters']['drive_current']['fixed']['value'] = .001
        wrong = assess_brief(self.catalog, self.brief)
        self.assertEqual([(row['code'], row['path']) for row in wrong],
                         [('CHECK_FAILED', 'functions.rtd_interface')])
        block['parameters'] = parameters
        block['verification'] = 'DRAFT'
        result = assess_brief(self.catalog, self.brief)
        self.assertEqual([(row['code'], row['path']) for row in result],
                         [('UNVERIFIED_RECORD', 'functions.rtd_interface')])
