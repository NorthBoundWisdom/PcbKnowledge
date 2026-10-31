"""Keep independent measurement/audio requirements while implementation remains unqualified."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.coverage import brief_coverage
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class Cycle5BriefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')
        cls.briefs = {name.upper(): read_json((ROOT / f'evals/corpus/themes/{name}.brief.json').read_bytes())
                      for name in ('t9', 't10', 'n9')}

    def parameters(self, brief, function):
        return next(row['parameters'] for row in self.briefs[brief]['functions'] if row['id'] == function)

    def test_contracts_keep_real_function_and_net_references_without_observed_acceptance(self):
        missing = {'T9': 'thermocouple_measurement', 'T10': 'class_d_amplifier', 'N9': 'stereo_audio_adc'}
        for name, brief in self.briefs.items():
            with self.subTest(brief=name):
                self.catalog.structure(brief, 'design-brief.schema.json')
                self.assertTrue(all(row['status'] == 'NOT_RUN' for row in brief['acceptance']))
                functions = {row['id'] for row in brief['functions']}
                for row in brief['power']['sources'] + brief['power']['rails']:
                    self.assertIn(row['function'], functions)
                endpoints = [(row['function'], row['port']) for group in brief['electrical_bindings']
                             for row in group['endpoints']]
                self.assertEqual(len(endpoints), len(set(endpoints)))
                self.assertTrue(all(function in functions for function, _ in endpoints))
                row = brief_coverage(self.catalog, name, brief, [])
                self.assertEqual((row['status'], row['graph_readiness']), ('NOT_RUN', 'NOT_RUN'))
                self.assertIn(('UNSATISFIED_SELECTION', 'functions.' + missing[name]),
                              {(item['code'], item['path']) for item in row['refusals']})

    def test_thermocouple_error_and_freshness_and_stereo_clock_domains_stay_distinct(self):
        thermocouple = self.parameters('T9', 'thermocouple_measurement')
        self.assertEqual((thermocouple['hot_junction_temperature']['min'],
                          thermocouple['hot_junction_temperature']['max']), (0, 300))
        self.assertEqual(thermocouple['absolute_temperature_error']['max'], 3)
        self.assertEqual(thermocouple['fixture_expanded_uncertainty']['max'], 0.5)
        self.assertEqual(thermocouple['uncertainty_coverage_factor']['value'], 2)
        self.assertEqual(thermocouple['sample_pair_skew']['max'], 0.1)
        self.assertEqual(thermocouple['maximum_fresh_acquisition_interval']['max'], 0.25)
        audio = self.parameters('N9', 'stereo_audio_adc')
        self.assertEqual((audio['sample_word_bits']['value'], audio['slot_width_bits']['value']), (24, 32))
        self.assertEqual((audio['sinad']['min'], audio['sinad']['unit']), (70, 'dB'))
        clocks = self.parameters('N9', 'pcm_host_link')
        frame = clocks['frame_clock']['value']
        self.assertEqual(frame, 48000)
        self.assertEqual(clocks['bit_clock']['value'], frame * 2 * audio['slot_width_bits']['value'])
        self.assertEqual(clocks['master_clock']['value'], frame * 256)
        self.assertEqual(clocks['clock_frequency_tolerance']['max'], 0.00005)
        bindings = {row['id'] for row in self.briefs['N9']['electrical_bindings']}
        self.assertTrue({'i2s_mclk', 'i2s_bclk', 'i2s_lrclk', 'i2s_sdout'} <= bindings)

    def test_audio_thermal_inputs_are_configured_thresholds_not_observations(self):
        inputs = self.parameters('T10', 'audio_input')
        self.assertEqual((inputs['input_voltage_rms']['max'], inputs['input_voltage_rms']['unit']), (0.25, 'V'))
        amplifier = self.parameters('T10', 'class_d_amplifier')
        self.assertEqual((amplifier['gain']['min'], amplifier['gain']['max']), (9, 11))
        self.assertEqual(amplifier['output_power']['min'], 0.5)
        self.assertEqual(amplifier['full_ambient_output_power']['min'], 0.25)
        self.assertEqual(amplifier['thd_plus_noise']['max'], 0.01)
        self.assertEqual(amplifier['minimum_continuous_test_duration']['value'], 600)
        self.assertEqual(amplifier['thermal_equilibrium_window']['value'], 300)
        self.assertEqual(amplifier['thermal_equilibrium_change_threshold']['max'], 1)
        self.assertTrue(all(row['status'] == 'NOT_RUN' for row in self.briefs['T10']['acceptance']))

    def test_wrong_dimension_refuses_and_negative_hypothesis_has_an_actual_screening_result(self):
        bad = deepcopy(self.briefs['T9'])
        function = next(row for row in bad['functions'] if row['id'] == 'thermocouple_measurement')
        function['parameters']['sample_pair_skew']['unit'] = 'V'
        with self.assertRaisesRegex(ValueError, 'Wrong canonical unit'):
            self.catalog.structure(bad, 'design-brief.schema.json')
        brief = self.briefs['N9']
        self.assertEqual(brief['expected_refusal'],
                         {'code': 'UNSATISFIED_SELECTION', 'requirement': 'stereo_audio_adc'})
        self.assertIn(('UNSATISFIED_SELECTION', 'functions.stereo_audio_adc'),
                      {(row['code'], row['path']) for row in assess_brief(self.catalog, brief)})
        self.assertEqual(set(brief['owner_decisions']), {'D65', 'D113'})
