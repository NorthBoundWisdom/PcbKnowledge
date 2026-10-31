"""G3 physical topology, declared bench models and adversarial A2 acceptance."""
import copy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.audit import audit_catalog
from pcbknowledge.v2.calculators import calculate
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.intent import validate_intent

ROOT = Path(__file__).resolve().parents[2]


def limits(quantity):
    if 'value' in quantity:
        return quantity['value'], quantity['value']
    return quantity['min'], quantity['max']


class G3AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/golden-designs/g3.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g3.block-graph.json').read_bytes())

    def block(self, name):
        return self.catalog.get('block:g3-' + name)

    def part(self, block, component):
        item = next(c for c in block['components'] if c['ref'] == component)
        return self.catalog.get(item['select']['part'])

    def fixed(self, block, parameter):
        return block['parameters'][parameter]['fixed']

    def resolve(self, block, check):
        result = {}
        for name, value in check['inputs'].items():
            if 'component' in value:
                quantity = copy.deepcopy(self.part(block, value['component'])['parameters'][value['parameter']])
                if 'bound' in value:
                    number = quantity[value['bound']]
                    quantity = {k: v for k, v in quantity.items() if k not in ('min', 'max', 'typ')}
                    quantity['value'] = number
            elif set(value) == {'parameter'}:
                quantity = self.fixed(block, value['parameter'])
            else:
                quantity = value
            result[name] = quantity
        return result

    def model(self, block, calculator):
        check = next(c for c in block['checks'] if c['calculator'] == calculator)
        return calculate(calculator, self.resolve(block, check))

    def expand(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def test_reference_reaches_a2_with_reachable_catalog(self):
        result = self.expand()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        self.assertEqual(result['verification'], 'AGENT_VERIFIED')
        self.assertTrue(result['checks'])
        self.assertTrue(all(check['result'] == 'PASS' for check in result['checks']))
        validate_intent(self.catalog, result, bundle_commit='a' * 40)
        self.assertEqual(audit_catalog(self.catalog)['unreachable'], [])

    def test_unknown_model_input_missing_power_and_shorted_output_refuse(self):
        photodiode = next(i for i in self.graph['instances'] if i['id'] == 'photodiode')
        photodiode['parameters']['photocurrent'] = {
            'status': 'UNKNOWN', 'reason': 'Synthetic absent light-current budget.', 'blocks': ['Q10']}
        self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        self.graph['connections'] = [n for n in self.graph['connections'] if n['net'] != 'ANALOG_3V3']
        self.assertEqual(self.expand()['status'], 'REFUSED')
        self.setUp()
        ground = next(n for n in self.graph['connections'] if n['net'] == 'GND')
        ground['endpoints'].append({'instance': 'photodiode', 'port': 'OUT'})
        self.assertEqual(self.expand()['status'], 'REFUSED')

    def test_tia_polarity_bias_tolerance_error_and_feedback_capacitors(self):
        block = self.block('photodiode')
        nets = {n['name']: set(n['connect']) for n in block['nets']}
        self.assertIn('D1.pin:1', nets['SUMMING'])
        self.assertIn('D1.pin:2', nets['GND'])
        self.assertIn('C2.pin:1', nets['SUMMING'])
        self.assertIn('C2.pin:2', nets['OUT'])
        self.assertFalse({'C3', 'C4', 'C5'} & {item['ref'] for item in block['components']})
        low, high = limits(self.part(block, 'C2')['parameters']['capacitance'])
        self.assertAlmostEqual(low, 95e-12, delta=1e-24)
        self.assertAlmostEqual(high, 105e-12, delta=1e-24)
        loop = self.model(block, 'tia_loop_total_capacitance')
        self.assertGreaterEqual(loop['phase_margin']['min'], 45)
        self.assertGreaterEqual(loop['feedback_pole']['min'], 1)
        near = {row['subject']: row for row in block['layout'] if row['kind'] == 'PLACE_NEAR'}
        for subject in ('C2.pin:1', 'R3.pin:1'):
            self.assertEqual(near[subject]['target'], 'U1.pin:6')
            self.assertEqual(near[subject]['max_distance']['value'], 2)
        model = self.model(block, 'tia_frontend')
        self.assertAlmostEqual(model['bias_voltage']['min'], 1.16325)
        self.assertAlmostEqual(model['bias_voltage']['max'], 1.33825)
        self.assertAlmostEqual(model['output_voltage']['min'], 1.11325)
        self.assertAlmostEqual(model['output_voltage']['max'], 1.89325)
        self.assertGreater(model['low_headroom_margin']['min'], 0)
        self.assertGreater(model['high_headroom_margin']['min'], 0)
        check = next(c for c in block['checks'] if c['calculator'] == 'tia_frontend')
        self.assertEqual(check['inputs']['total_error']['basis'], 'ENGINEERING_DEFAULT')

    def test_ntc_range_power_and_modeled_filter_are_not_accuracy_claims(self):
        block = self.block('thermistor')
        model = self.model(block, 'ntc_divider')
        self.assertAlmostEqual(model['output_voltage']['min'], .8886783024150604)
        self.assertAlmostEqual(model['output_voltage']['max'], 1.6651792001401697)
        self.assertLess(model['max_sensor_power']['max'], .005)
        self.assertGreater(model['pole_frequency']['min'], 80)
        self.assertLess(model['pole_frequency']['max'], 140)
        check = next(c for c in block['checks'] if c['calculator'] == 'ntc_divider')
        self.assertEqual(check['inputs']['capacitance']['basis'], 'ENGINEERING_DEFAULT')
        self.assertEqual(limits(self.fixed(block, 'temperature')), (15, 35))

    def test_parallel_reference_bank_matches_actual_parts_and_nets(self):
        block = self.block('reference')
        nets = {n['name']: set(n['connect']) for n in block['nets']}
        resistances = []
        for ref in ('R1', 'R2', 'R3'):
            self.assertIn(ref + '.pin:1', nets['VIN'])
            self.assertIn(ref + '.pin:2', nets['VREF'])
            resistances.append(limits(self.part(block, ref)['parameters']['resistance']))
        equivalent = tuple(1 / sum(1 / r[i] for r in resistances) for i in (0, 1))
        for check in block['checks']:
            if check['calculator'] == 'reference_load':
                for actual, expected in zip(limits(check['inputs']['series_resistance']), equivalent):
                    self.assertAlmostEqual(actual, expected)
        self.assertGreaterEqual(self.model(block, 'reference_load')['cathode_current']['min'], .001)

    def test_rs485_bias_series_chains_and_individual_termination_power(self):
        block = self.block('rs485')
        nets = {n['name']: set(n['connect']) for n in block['nets']}
        for pair, middle, start, end in [('RU', 'BIAS_UP', 'VDD', 'A'), ('RL', 'BIAS_DOWN', 'B', 'GND')]:
            self.assertIn(pair + '1.pin:1', nets[start])
            self.assertEqual(nets[middle], {pair + '1.pin:2', pair + '2.pin:1'})
            self.assertIn(pair + '2.pin:2', nets[end])
        check = next(c for c in block['checks'] if c['calculator'] == 'rs485_termination')
        for prefix, key in [('RU', 'bias_up'), ('RL', 'bias_down')]:
            rs = [limits(self.part(block, prefix + str(i))['parameters']['resistance']) for i in (1, 2)]
            self.assertEqual(limits(check['inputs'][key]), tuple(sum(r[i] for r in rs) for i in (0, 1)))
        local = self.part(block, 'RT')['parameters']
        voltage = limits(check['inputs']['driver_voltage'])[1]
        local_power = voltage**2 / limits(local['resistance'])[0]
        remote_power = voltage**2 / limits(check['inputs']['termination_b'])[0]
        self.assertLessEqual(local_power, local['power_rating']['max'])
        self.assertLessEqual(remote_power, .1)
        model = self.model(block, 'rs485_termination')
        source = self.part(block, 'U1')['parameters']
        self.assertGreaterEqual(model['equivalent_load']['min'], source['differential_load_resistance']['min'])
        self.assertLessEqual(model['driver_current']['max'], source['output_current']['max'])
        self.assertGreaterEqual(model['idle_differential']['min'], source['receiver_positive_threshold']['max'])

    def test_external_host_logic_levels_match_source_requirements(self):
        for name in ('adc', 'rs485'):
            block = self.block(name)
            source = self.part(block, 'U1')['parameters']
            high = self.fixed(block, 'input_high_voltage')['value']
            low = self.fixed(block, 'input_low_voltage')['value']
            if name == 'adc':
                vlo, vhi = limits(self.fixed(block, 'input_voltage'))
                self.assertGreaterEqual(high, source['input_high_ratio']['min'] * vhi)
                self.assertLessEqual(low, source['input_low_ratio']['max'] * vlo)
                self.assertGreaterEqual(vlo, self.fixed(block, 'output_high_voltage')['value'])
            else:
                self.assertGreaterEqual(high, source['input_high_voltage']['min'])
                self.assertLessEqual(low, source['input_low_voltage']['max'])
                self.assertGreaterEqual(source['output_high_voltage']['min'],
                                        self.fixed(block, 'output_high_voltage')['value'])
            self.assertLessEqual(source['output_low_voltage']['max'],
                                 self.fixed(block, 'output_low_voltage')['value'])

    def test_shared_reference_and_analog_rail_operating_budgets(self):
        reference, tia, ntc, adc = (self.block(n) for n in ('reference', 'photodiode', 'thermistor', 'adc'))
        vref_max = limits(self.fixed(reference, 'reference_voltage'))[1]
        bias_resistance = sum(limits(self.part(tia, r)['parameters']['resistance'])[0] for r in ('R1', 'R2'))
        ntc_min = self.model(ntc, 'ntc_divider')['sensor_resistance']['min']
        upper_min = limits(self.part(ntc, 'R1')['parameters']['resistance'])[0]
        adc_reference = self.fixed(adc, 'load_current')
        self.assertEqual(adc_reference['basis'], 'ENGINEERING_DEFAULT')
        load = vref_max / bias_resistance + vref_max / (upper_min + ntc_min) + limits(adc_reference)[1]
        self.assertLessEqual(load, limits(self.fixed(reference, 'load_current'))[1])
        reference_check = next(c for c in reference['checks'] if c['calculator'] == 'reference_load')
        rmin = limits(reference_check['inputs']['series_resistance'])[0]
        source_max = limits(self.fixed(reference, 'input_voltage'))[1]
        ref_min = limits(self.fixed(reference, 'reference_voltage'))[0]
        reference_supply = (source_max - ref_min) / rmin
        analog_total = reference_supply + limits(self.fixed(tia, 'input_current'))[1]
        analog_total += limits(self.fixed(adc, 'input_current'))[1]
        rail_budget = limits(self.fixed(self.block('rail-filter'), 'output_current'))[1]
        self.assertLessEqual(analog_total, rail_budget)
        self.assertEqual(self.fixed(adc, 'input_current')['basis'], 'ENGINEERING_DEFAULT')
        pullup_current = sum(source_max / limits(self.part(adc, r)['parameters']['resistance'])[0]
                             for r in ('R1', 'R2', 'R3'))
        self.assertLessEqual(pullup_current + .0008, limits(self.fixed(adc, 'input_current'))[1])

    def test_external_source_budget_covers_modeled_dc_consumption(self):
        block = self.block('rs485')
        driver = self.model(block, 'rs485_termination')['driver_current']['max']
        source = self.part(block, 'U1')['parameters']
        quiescent = source['quiescent_current']['max']
        voltage = limits(self.fixed(block, 'input_voltage'))[1]
        control = voltage / limits(self.part(block, 'RD')['parameters']['resistance'])[0]
        analog = limits(self.fixed(self.block('rail-filter'), 'output_current'))[1]
        budget = limits(self.brief['power']['sources'][0]['current_budget'])[1]
        # This is the declared DC scenario; remaining headroom is not a transient-current guarantee.
        self.assertLessEqual(driver + quiescent + control + analog, budget)

    def test_guard_and_continuous_ground_constraints_survive_expansion(self):
        block = self.block('photodiode')
        guard = next(c for c in block['layout'] if c['kind'] == 'GUARD_RING')
        self.assertEqual((guard['net'], guard['guard_net']), ('SUMMING', 'BIAS'))
        self.assertGreaterEqual(guard['min_clearance']['value'], .2)
        self.assertGreaterEqual(guard['min_width']['value'], .25)
        for name in ('photodiode', 'thermistor'):
            block = self.block(name)
            self.assertIn({'kind': 'RETURN_PATH', 'net': 'OUT', 'return_net': 'GND'}, block['layout'])

    def test_input_connector_budget_and_no_host_power_export(self):
        block = self.block('power-input-header')
        connector = self.part(block, 'J1')['parameters']
        self.assertLessEqual(limits(self.fixed(block, 'output_current'))[1], limits(connector['current_rating'])[1])
        self.assertEqual(limits(self.fixed(block, 'output_voltage')), (3.2, 3.4))
        adc_ground = next(n for n in self.block('adc')['nets'] if n['name'] == 'GND')
        self.assertTrue({'J1.pin:1', 'J1.pin:2'} <= set(adc_ground['connect']))
        adc_supply = next(n for n in self.block('adc')['nets'] if n['name'] == 'VDD')
        self.assertFalse(any(endpoint.startswith('J1.') for endpoint in adc_supply['connect']))
