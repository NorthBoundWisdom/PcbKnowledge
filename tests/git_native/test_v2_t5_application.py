"""Mutation tests against actual selected T5 records and reconstructed expansion."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion

ROOT = Path(__file__).resolve().parents[2]


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = Catalog(ROOT, ROOT / 'schemas')
        cls.brief_template = json.loads((ROOT / 'evals/corpus/themes/t5.brief.json').read_text(encoding='utf-8'))
        cls.graph_template = json.loads((ROOT / 'evals/corpus/themes/t5.block-graph.json').read_text(encoding='utf-8'))

    def setUp(self):
        self.catalog = deepcopy(self.template)
        self.brief = deepcopy(self.brief_template)
        self.graph = deepcopy(self.graph_template)

    def run_expansion(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def failed(self, path):
        result = self.run_expansion()
        return any(r['code'] != 'UNVERIFIED_RECORD' and path in r['path'] for r in result['refusals'])

    def record(self, identity):
        return self.catalog.records[identity]

    def component(self, block, ref):
        return next(c for c in self.record('block:' + block)['components'] if c['ref'] == ref)

    def change_binding(self, identity, value):
        binding = next(b for b in self.brief['parameter_bindings'] if b['id'] == identity)
        binding['value'] = value
        for endpoint in binding['endpoints']:
            instance = next(i for i in self.graph['instances'] if endpoint['function'] in i['requirements'])
            instance['parameters'][endpoint['parameter']] = deepcopy(value)

    def test_reviewed_application_expands_with_all_checks_pass(self):
        result = self.run_expansion()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        self.assertEqual(result['refusals'], [])
        self.assertTrue(result['checks'])
        self.assertTrue(all(c.get('result') == 'PASS' for c in result['checks']))

    def test_active_low_sync_starts_high_on_exact_pin_and_replay_rejects_tampering(self):
        result = self.run_expansion()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        config = result['pin_configurations'][0]
        self.assertEqual((config['ref'], config['pin'], config['initial_state']), ('mcu_U1', '14', 'HIGH'))
        bundle = SimpleNamespace(catalog=self.catalog, briefs={'T5': self.brief}, commit='a' * 40)
        validate_expansion(bundle, result, self.graph)
        config['initial_state'] = 'LOW'
        with self.assertRaisesRegex(ValueError, 'differs from deterministic'):
            validate_expansion(bundle, result, self.graph)

    def test_mounting_requirement_cannot_be_omitted(self):
        self.graph['instances'] = [instance for instance in self.graph['instances']
                                   if instance['block'] != 'block:mounting-holes']
        result = self.run_expansion()
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(result['refusals'])

    def test_selected_isolation_resistor_binds_offset(self):
        self.component('t5-output-stage', 'R3')['select']['part'] = 'part:yageo-rc0603fr-07120rl'
        self.assertTrue(self.failed('analog.checks'))

    def test_each_producer_pull_load_binds(self):
        for block, ref, instance in [('t5-controller', 'R1', 'mcu'), ('t5-dac', 'RCS', 'dac')]:
            original = deepcopy(self.component(block, ref))
            self.component(block, ref)['select']['part'] = 'part:yageo-rc0603fr-071kl'
            self.assertTrue(self.failed(instance + '.checks'))
            self.component(block, ref).update(original)

    def test_actual_fourth_reference_cap_is_required(self):
        self.component('t5-dac', 'CR4')['select']['part'] = 'part:kemet-c0603c103k5ractu'
        self.assertTrue(self.failed('dac.checks'))

    def test_retention_not_nominal_only(self):
        checks = self.record('block:t5-dac')['checks']
        target = next(c for c in checks if c['calculator'] == 'quad_parallel_capacitance')
        target['inputs']['retained_lower_factor']['value'] = .4
        self.assertTrue(self.failed('dac.checks'))

    def test_physical_preload_not_consumer_minimum(self):
        self.component('t5-control-rail', 'RLOAD1')['select']['part'] = 'part:yageo-rc0603fr-0710kl'
        self.assertTrue(self.failed('ldo.checks'))

    def test_actual_ptc_resistance_binds(self):
        self.record('part:eaton-pts120615v050')['parameters']['resistance']['max'] = 5
        self.assertTrue(self.failed('protection.checks'))

    def test_actual_ptc_hold_rating_binds(self):
        self.record('part:eaton-pts120615v050')['parameters']['hold_current']['value'] = .05
        self.assertTrue(self.failed('protection.checks'))

    def test_actual_opa_minimum_supply_binds(self):
        self.record('part:ti-opa197idr')['parameters']['input_voltage']['min'] = 5
        self.assertTrue(self.failed('analog.checks'))

    def test_shared_sample_rate_cannot_drift(self):
        instance = next(i for i in self.graph['instances'] if i['id'] == 'analog')
        instance['parameters']['sample_rate']['min'] = 50000
        self.assertTrue(self.failed('parameter_bindings.t5_sample_rate'))

    def test_actual_frequency_includes_clock_and_rounding(self):
        binding = next(b for b in self.brief['parameter_bindings'] if b['id'] == 't5_frequency')
        value = deepcopy(binding['value'])
        value.update(min=1, max=1000)
        self.change_binding('t5_frequency', value)
        self.assertTrue(self.failed('mcu.checks'))

    def test_both_host_allocations_are_counted(self):
        for host in ('swd', 'uart'):
            identity = 't5_' + host + '_budget'
            binding = next(b for b in self.brief['parameter_bindings'] if b['id'] == identity)
            original = deepcopy(binding['value'])
            value = deepcopy(original)
            value['value'] = .01
            self.change_binding(identity, value)
            self.assertTrue(self.failed('ldo.checks'))
            self.change_binding(identity, original)

    def test_hot_ambient_cannot_keep_unqualified_ptc_factor(self):
        binding = next(b for b in self.brief['parameter_bindings'] if b['id'] == 't5_bench_temperature')
        value = deepcopy(binding['value'])
        value['value'] = 40
        self.change_binding('t5_bench_temperature', value)
        self.assertTrue(self.failed('protection.parameters.temperature'))

    def test_distinct_residual_predicates_bind(self):
        for key in ('pointwise_residual_error', 'cycle_mean_residual_error'):
            checks = self.record('block:t5-output-stage')['checks']
            originals = deepcopy(checks)
            for check in checks:
                if check['calculator'] == 'sampled_waveform_envelope':
                    check['inputs'][key]['max'] = .03
            self.assertTrue(self.failed('analog.checks'))
            self.record('block:t5-output-stage')['checks'] = originals


if __name__ == '__main__':
    unittest.main()
