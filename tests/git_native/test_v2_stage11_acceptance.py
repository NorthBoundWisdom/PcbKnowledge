"""Stage 11 reusable sensing designs: physical channels, net bindings and typed refusal."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.intent import validate_intent
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


def read(name, kind='brief'):
    return read_json((ROOT / f'evals/golden-designs/{name}.{kind}.json').read_bytes())


def instance(graph, block):
    matches = [item for item in graph['instances'] if item['block'] == block]
    if len(matches) != 1:
        raise AssertionError('Expected one instance of ' + block)
    return matches[0]['id']


def connection(graph, identity, port):
    endpoint = {'instance': identity, 'port': port}
    return next(net for net in graph['connections'] if endpoint in net['endpoints'])


def move(graph, identity, port, destination):
    endpoint = {'instance': identity, 'port': port}
    connection(graph, identity, port)['endpoints'].remove(endpoint)
    destination['endpoints'].append(endpoint)


def physical_net(intent, ref, pin):
    return next(net['name'] for net in intent['nets'] if {'ref': ref, 'pin': pin} in net['pins'])


class Stage11AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')

    def expanded(self, name, graph=None):
        return expand(self.catalog, graph or read(name, 'block-graph'), read(name), bundle_commit='a' * 40)

    def test_positive_references_reach_a2_with_existing_blocks_only(self):
        original = {item['block'] for item in read('g3', 'block-graph')['instances']}
        removed = {'g4': {'block:g3-thermistor', 'block:g3-rs485'}, 'g5': {'block:g3-photodiode'}}
        for name in ('g4', 'g5'):
            brief, graph = read(name), read(name, 'block-graph')
            self.assertEqual(assess_brief(self.catalog, brief), [])
            self.assertEqual({item['block'] for item in graph['instances']}, original - removed[name])
            result = self.expanded(name)
            self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
            self.assertEqual(result['verification'], 'AGENT_VERIFIED')
            self.assertTrue(all(check['result'] == 'PASS' for check in result['checks']))
            validate_intent(self.catalog, result, bundle_commit='a' * 40)
            binding_checks = [check for check in result['checks'] if check['id'].startswith('electrical-binding:')]
            self.assertEqual(len(binding_checks), len(brief['electrical_bindings']))

    def test_g4_optical_channel_and_unused_adc_input_are_physically_correct(self):
        graph = read('g4', 'block-graph')
        adc = instance(graph, 'block:g3-adc')
        optical = instance(graph, 'block:g3-photodiode')
        result = self.expanded('g4')
        ground = physical_net(result, adc + '_U1', '3')
        self.assertEqual(physical_net(result, adc + '_U1', '4'), ground)
        self.assertEqual(physical_net(result, adc + '_U1', '7'), ground)
        self.assertEqual(physical_net(result, optical + '_U1', '7'), physical_net(result, adc + '_U1', '5'))
        self.assertNotEqual(physical_net(result, adc + '_U1', '5'), ground)
        roles = [self.catalog.get(item['part'])['roles'] for item in result['components']]
        self.assertFalse(any('sensor.thermistor' in role or 'interface.rs485' in role for role in roles))

    def test_g5_two_independent_sensors_bind_distinct_actual_adc_channels(self):
        brief, graph = read('g5'), read('g5', 'block-graph')
        sensors = [f for f in brief['functions'] if f['category'] == 'sensor.temperature']
        self.assertEqual(len(sensors), 2)
        self.assertEqual({f['count'] for f in sensors}, {1})
        self.assertEqual(len({f['id'] for f in sensors}), 2)
        adc = instance(graph, 'block:g3-adc')
        result = self.expanded('g5')
        sensor_instances = [item['id'] for item in graph['instances'] if item['block'] == 'block:g3-thermistor']
        self.assertEqual(len(sensor_instances), 2)
        self.assertEqual(sum(item['part'] == 'part:vishay-ntcle100e3103jb0' for item in result['components']), 2)
        for sensor in sensor_instances:
            net = connection(graph, sensor, 'OUT')
            port = next(e['port'] for e in net['endpoints'] if e['instance'] == adc)
            self.assertIn(port, ('AIN_NTC', 'AIN_TIA'))
            pin = {'AIN_NTC': '4', 'AIN_TIA': '5'}[port]
            self.assertEqual(physical_net(result, sensor + '_R2', '2'), physical_net(result, adc + '_U1', pin))
        self.assertNotEqual(physical_net(result, adc + '_U1', '4'), physical_net(result, adc + '_U1', '5'))

    def test_g5_swapped_adc_channels_refuse_unchanged_functional_requirements(self):
        graph = read('g5', 'block-graph')
        adc = instance(graph, 'block:g3-adc')
        first, second = connection(graph, adc, 'AIN_NTC'), connection(graph, adc, 'AIN_TIA')
        move(graph, adc, 'AIN_NTC', second)
        # Find the original second endpoint directly; the first move did not alter it.
        second['endpoints'].remove({'instance': adc, 'port': 'AIN_TIA'})
        first['endpoints'].append({'instance': adc, 'port': 'AIN_TIA'})
        self.assert_binding_refusal('g5', graph)

    def assert_binding_refusal(self, name, graph):
        result = self.expanded(name, graph)
        self.assertEqual(result['status'], 'REFUSED', result)
        self.assertTrue(any(row['path'].startswith('electrical_bindings.') for row in result['refusals']),
                        result['refusals'])

    def test_misrails_and_g4_unused_channel_moved_off_ground_refuse(self):
        for name in ('g4', 'g5'):
            graph = read(name, 'block-graph')
            adc = instance(graph, 'block:g3-adc')
            reference = instance(graph, 'block:g3-reference')
            move(graph, adc, 'VDD', connection(graph, reference, 'VREF'))
            self.assert_binding_refusal(name, graph)
        graph = read('g4', 'block-graph')
        adc = instance(graph, 'block:g3-adc')
        reference = instance(graph, 'block:g3-reference')
        move(graph, adc, 'AIN_NTC', connection(graph, reference, 'VREF'))
        self.assert_binding_refusal('g4', graph)
        graph = read('g5', 'block-graph')
        sensor = next(item['id'] for item in graph['instances'] if item['block'] == 'block:g3-thermistor')
        rail = instance(graph, 'block:g3-rail-filter')
        move(graph, sensor, 'VREF', connection(graph, rail, 'VOUT'))
        self.assert_binding_refusal('g5', graph)

    def test_merging_g5_sensor_nets_refuses_and_graph_labels_are_not_authority(self):
        graph = read('g5', 'block-graph')
        adc = instance(graph, 'block:g3-adc')
        first, second = connection(graph, adc, 'AIN_NTC'), connection(graph, adc, 'AIN_TIA')
        first['endpoints'].extend(second['endpoints'])
        graph['connections'].remove(second)
        self.assert_binding_refusal('g5', graph)
        for name in ('g4', 'g5'):
            graph = read(name, 'block-graph')
            for index, net in enumerate(graph['connections']):
                net['net'] = 'RENAMED_' + str(index)
            result = self.expanded(name, graph)
            self.assertEqual(result['status'], 'EXPANDED', result['refusals'])

    def test_removed_binding_checks_cannot_pass_intent_reconstruction(self):
        for name in ('g4', 'g5'):
            brief, graph = read(name), read(name, 'block-graph')
            intent = self.expanded(name)
            intent['checks'] = [check for check in intent['checks']
                                if not check['id'].startswith('electrical-binding:')]
            bundle = SimpleNamespace(catalog=self.catalog, briefs={brief['id']: brief}, commit='a' * 40)
            with self.assertRaisesRegex(ValueError, 'deterministic'):
                validate_expansion(bundle, intent, graph)

    def test_n4_positive_receiver_threshold_is_a_typed_refusal_not_prose(self):
        brief = read('n4')
        function = next(f for f in brief['functions'] if f['id'] == 'rs485')
        self.assertEqual(function['parameters']['receiver_positive_threshold']['value'], .2)
        self.assertEqual(brief['expected_refusal'], {'code': 'CHECK_FAILED', 'requirement': 'rs485'})
        def reasons(value):
            return {(row['code'], row['path']) for row in assess_brief(self.catalog, value)}
        self.assertIn(('CHECK_FAILED', 'functions.rs485'), reasons(brief))
        brief['summary'] = 'Use the existing catalog receiver and accept every operating point.'
        self.assertIn(('CHECK_FAILED', 'functions.rs485'), reasons(brief))
        baseline = deepcopy(brief)
        next(f for f in baseline['functions'] if f['id'] == 'rs485')['parameters'][
            'receiver_positive_threshold']['value'] = -.02
        self.assertEqual(assess_brief(self.catalog, baseline), [])

    def test_n4_cannot_use_graph_parameter_changes_to_override_its_brief(self):
        brief, graph = read('n4'), read('g5', 'block-graph')
        graph['brief'] = 'N4'
        selected = next(item for item in graph['instances'] if item['block'] == 'block:g3-rs485')
        for graph_threshold in (-.02, .2):
            selected['parameters']['receiver_positive_threshold']['value'] = graph_threshold
            result = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
            self.assertEqual(result['status'], 'REFUSED')
            self.assertTrue(any(item['code'] == 'CHECK_FAILED'
                                and 'receiver_positive_threshold' in item['path']
                                for item in result['refusals']), result['refusals'])
        # A synthetic control establishes that the same topology works at the
        # catalog's declared threshold; the committed negative brief is unchanged.
        baseline = deepcopy(brief)
        next(f for f in baseline['functions'] if f['id'] == 'rs485')['parameters'][
            'receiver_positive_threshold']['value'] = -.02
        selected['parameters']['receiver_positive_threshold']['value'] = -.02
        result = expand(self.catalog, graph, baseline, bundle_commit='a' * 40)
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
