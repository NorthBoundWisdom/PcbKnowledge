"""Original motor requirements remain explicit while unimplemented designs stay refused."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.coverage import brief_coverage
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class Cycle2BriefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')
        cls.briefs = {name.upper(): read_json((ROOT / f'evals/corpus/themes/{name}.brief.json').read_bytes())
                      for name in ('t3', 't4', 'n6')}

    def test_semantic_contracts_preserve_unobserved_acceptance_and_unimplemented_functions(self):
        missing = {'T3': 'h_bridge', 'T4': 'stepper_driver', 'N6': 'three_phase_drive'}
        for identity, brief in self.briefs.items():
            with self.subTest(brief=identity):
                self.catalog.structure(brief, 'design-brief.schema.json')
                self.assertTrue(all(item['status'] == 'NOT_RUN' for item in brief['acceptance']))
                row = brief_coverage(self.catalog, identity, brief, [])
                self.assertEqual((row['status'], row['graph_readiness']), ('NOT_RUN', 'NOT_RUN'))
                self.assertIn(('UNSATISFIED_SELECTION', 'functions.' + missing[identity]),
                              {(r['code'], r['path']) for r in row['refusals']})

    def test_distinct_motor_current_and_timing_budgets_are_not_collapsed(self):
        functions = {f['id']: f for f in self.briefs['T3']['functions']}
        brushed = functions['h_bridge']['parameters']
        self.assertEqual(brushed['load_current']['value'], 0.25)
        self.assertEqual(brushed['winding_peak_current']['value'], 0.6)
        self.assertEqual(brushed['peak_duration']['value'], 0.1)
        self.assertEqual(brushed['differential_load_resistance']['min'], 10)
        functions = {f['id']: f for f in self.briefs['T4']['functions']}
        stepper = functions['stepper_driver']['parameters']
        self.assertEqual(stepper['trip_current']['value'], 0.25)
        self.assertEqual((stepper['hold_current']['min'], stepper['hold_current']['max']), (0.15, 0.3))
        self.assertEqual(stepper['winding_peak_current']['max'], 0.35)
        for field in ('step_high_time', 'step_low_time', 'direction_setup_time', 'direction_hold_time'):
            self.assertEqual(stepper[field]['unit'], 's')
            self.assertGreater(stepper[field]['min'], 0)

    def test_new_inputs_reject_wrong_dimensions_and_negative_case_is_reproduced(self):
        bad = deepcopy(self.briefs['T4'])
        function = next(f for f in bad['functions'] if f['id'] == 'stepper_driver')
        function['parameters']['winding_peak_current']['unit'] = 'V'
        with self.assertRaisesRegex(ValueError, 'Wrong canonical unit'):
            self.catalog.structure(bad, 'design-brief.schema.json')
        negative = self.briefs['N6']
        expected = negative['expected_refusal']
        self.assertEqual(expected, {'code': 'UNSATISFIED_SELECTION', 'requirement': 'three_phase_drive'})
        self.assertIn((expected['code'], 'functions.' + expected['requirement']),
                      {(r['code'], r['path']) for r in assess_brief(self.catalog, negative)})
        self.assertEqual(set(negative['owner_decisions']), {'D65', 'D111'})
