"""Power-return topology is tied to catalog declarations and physical terminals."""
import copy
import unittest

from pcbknowledge.v2.expansion import _Expansion
from pcbknowledge.v2.intent import electrical_checks
from pcbknowledge.v2.netlist import KICAD_PIN_TYPES
from pcbknowledge.v2.power_sinks import derive_loads, validate_block_loads, validate_loads


def pin(number, kind='PASSIVE'):
    return {'number': number, 'name': number, 'type': kind}


def fixture():
    parts = {'load_J1': {'id': 'part:header', 'roles': ['connector.header'], 'pins': [pin('1'), pin('2')]},
             'source_R1': {'id': 'part:resistor', 'roles': ['resistor'], 'pins': [pin('1'), pin('2')]},
             'driver_U1': {'id': 'part:driver', 'roles': ['driver.darlington-array'],
                           'pins': [pin('1', 'POWER_SINK'), pin('2', 'POWER_SINK'), pin('3', 'GROUND')]}}
    blocks = {'block:header': {'id': 'block:header', 'components': [{'ref': 'J1', 'select': {'part': 'part:header'}}],
               'ports': [{'name': 'P', 'kind': 'POWER_IN'}, {'name': 'R', 'kind': 'PASSIVE'}],
               'nets': [{'name': 'P', 'connect': ['port:P', 'J1.pin:1']},
                        {'name': 'R', 'connect': ['port:R', 'J1.pin:2']}],
               'external_loads': [{'connector': 'J1', 'supply_pin': '1', 'return_pin': '2'}]},
              'block:source': {'id': 'block:source',
               'components': [{'ref': 'R1', 'select': {'part': 'part:resistor'}}],
               'ports': [{'name': 'O', 'kind': 'POWER_OUT'}],
               'nets': [{'name': 'OUT', 'connect': ['port:O', 'R1.pin:2']}]}}
    nets = [{'name': 'INPUT', 'pins': [{'ref': 'source_R1', 'pin': '1'}]},
            {'name': 'SUPPLY', 'pins': [{'ref': 'source_R1', 'pin': '2'}, {'ref': 'load_J1', 'pin': '1'}]},
            {'name': 'RETURN', 'pins': [{'ref': 'driver_U1', 'pin': '1'}, {'ref': 'load_J1', 'pin': '2'}]},
            {'name': 'GROUND', 'pins': [{'ref': 'driver_U1', 'pin': '3'}]}]
    loads = [{'block': 'block:header', 'connector': 'load_J1', 'local_connector': 'J1',
              'supply_pin': '1', 'return_pin': '2', 'provider': {'block': 'block:source',
                'local_component': 'R1', 'ref': 'source_R1', 'pin': '2', 'port': 'O'}}]
    class Catalog:
        def get(self, identity, kind=None):
            return blocks[identity]

        def _candidates(self, selection):
            return [p for p in parts.values() if p['id'] == selection['part']]
    return Catalog(), parts, blocks, nets, loads


class PowerSinkTests(unittest.TestCase):
    def test_sink_return_receives_power_routing_class(self):
        _, parts, _, nets, _ = fixture()
        class State:
            pass
        state = State()
        state.parts, state.blocks, state.port_nodes = parts, {}, {}
        state.pin_nodes = {(p['ref'], p['pin']): n['name'] for n in nets for p in n['pins']}
        state.resolved = {n['name']: n['name'] for n in nets}
        state.intent = {'nets': []}
        failures = []
        state.refuse = lambda *args: failures.append(args)
        _Expansion.assemble_nets(state)
        classes = {n['name']: n['class'] for n in state.intent['nets']}
        self.assertEqual(classes['RETURN'], 'POWER')
        self.assertEqual(classes['GROUND'], 'GROUND')
        self.assertEqual(failures, [])

    def test_catalog_backed_supplied_return_passes_without_a_digital_pullup(self):
        catalog, parts, blocks, nets, loads = fixture()
        validate_block_loads(catalog, blocks['block:header'], {'J1': [parts['load_J1']]})
        validate_loads(catalog, parts, nets, loads, set(blocks))
        checks = electrical_checks(parts, nets, loads)
        self.assertTrue(all(check['result'] == 'PASS' for check in checks), checks)
        self.assertTrue(any(check['id'] == 'power_sink:driver_U1:1' for check in checks))
        self.assertFalse(any('driver_U1:2' in check['id'] for check in checks))
        self.assertFalse(any(check['id'].startswith('pullup:') for check in checks))
        self.assertEqual(KICAD_PIN_TYPES['POWER_SINK'], 'open_collector')

    def test_a_header_or_named_net_without_a_declared_load_is_not_enough(self):
        _, parts, _, nets, _ = fixture()
        checks = electrical_checks(parts, nets)
        self.assertTrue(any(check['id'].startswith('power_sink:') and check['result'] == 'FAIL' for check in checks))

    def test_active_pin_and_ground_shorts_fail_even_with_real_load_connector(self):
        for kind in ('GROUND', 'POWER_OUT', 'OUTPUT', 'OPEN_DRAIN', 'BIDIRECTIONAL', 'POWER_SINK'):
            _, parts, _, nets, loads = fixture()
            parts['bad'] = {'id': 'part:bad', 'roles': [], 'pins': [pin('1', kind)]}
            nets[2]['pins'].append({'ref': 'bad', 'pin': '1'})
            checks = electrical_checks(parts, nets, loads)
            with self.subTest(kind=kind):
                self.assertTrue(any(c['id'] == 'power_sink:driver_U1:1' and c['result'] == 'FAIL' for c in checks))

    def test_declared_load_cannot_be_left_unimplemented(self):
        _, parts, _, nets, loads = fixture()
        nets[2]['pins'].remove({'ref': 'driver_U1', 'pin': '1'})
        checks = electrical_checks(parts, nets, loads)
        self.assertTrue(any(c['id'] == 'external_load:load_J1:2' and c['result'] == 'FAIL' for c in checks))
        # A disconnected spare collector is allowed, but not a required off-board load.
        self.assertFalse(any(c['id'].startswith('power_sink:') for c in checks))

    def test_ordinary_open_drain_still_requires_its_resistive_pullup(self):
        _, parts, _, nets, loads = fixture()
        parts['driver_U1']['pins'][0]['type'] = 'OPEN_DRAIN'
        checks = electrical_checks(parts, nets, loads)
        self.assertTrue(any(c['id'] == 'pullup:driver_U1:1' and c['result'] == 'FAIL' for c in checks))

    def test_wrong_catalog_mapping_role_or_provider_is_rejected(self):
        mutations = [
            lambda p, b, n, l: p['load_J1'].update(roles=['resistor']),
            lambda p, b, n, l: b['block:header'].pop('external_loads'),
            lambda p, b, n, l: l[0].update(return_pin='1'),
            lambda p, b, n, l: l[0]['provider'].update(pin='1'),
            lambda p, b, n, l: l[0]['provider'].update(port='missing'),
            lambda p, b, n, l: b['block:source']['ports'][0].update(kind='GROUND'),
            lambda p, b, n, l: p['source_R1']['pins'][1].update(type='GROUND'),
            lambda p, b, n, l: l[0].update(local_connector='not-J1'),
        ]
        for mutate in mutations:
            catalog, parts, blocks, nets, loads = fixture()
            mutate(parts, blocks, nets, loads)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_loads(catalog, parts, nets, loads, set(blocks))

    def test_provider_wrong_net_and_missing_dependency_are_rejected(self):
        catalog, parts, blocks, nets, loads = fixture()
        with self.assertRaises(ValueError):
            validate_loads(catalog, parts, nets, loads, {'block:header'})
        nets[1]['pins'].remove({'ref': 'source_R1', 'pin': '2'})
        nets[0]['pins'].append({'ref': 'source_R1', 'pin': '2'})
        with self.assertRaises(ValueError):
            validate_loads(catalog, parts, nets, loads, set(blocks))

    def test_supply_must_be_distinct_and_not_ground(self):
        for destination in ('GROUND', 'RETURN'):
            catalog, parts, blocks, nets, loads = fixture()
            moving = list(nets[1]['pins'])
            nets[1]['pins'] = []
            next(net for net in nets if net['name'] == destination)['pins'].extend(moving)
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                validate_loads(catalog, parts, nets, loads, set(blocks))

    def test_projection_uses_typed_ports_and_actual_physical_nets(self):
        catalog, parts, blocks, nets, expected = fixture()
        class Expansion:
            def find(self, node):
                return {'source:OUT': 'SUPPLY', 'load:P': 'SUPPLY', 'load:R': 'RETURN'}[node]
        expansion = Expansion()
        expansion.catalog, expansion.parts = catalog, parts
        expansion.blocks = {'source': blocks['block:source'], 'load': blocks['block:header']}
        expansion.local_parts = {'source': {'R1': parts['source_R1']}, 'load': {'J1': parts['load_J1']}}
        expansion.port_nodes = {('source', 'O'): 'source:OUT', ('load', 'P'): 'load:P', ('load', 'R'): 'load:R'}
        expansion.pin_nodes = {('source_R1', '2'): 'source:OUT', ('load_J1', '1'): 'load:P',
                               ('load_J1', '2'): 'load:R'}
        expansion.intent = {'nets': nets, 'dependencies': sorted(blocks)}
        expansion.resolved = {'source:OUT': 'SUPPLY', 'load:P': 'SUPPLY', 'load:R': 'RETURN'}
        expansion.powered = {'SUPPLY'}
        derive_loads(expansion)
        self.assertEqual(expansion.intent['external_loads'], expected)
        expansion.powered.add('RETURN')
        with self.assertRaises(ValueError):
            derive_loads(expansion)
        expansion.powered.remove('RETURN')
        original = expansion.port_nodes['source', 'O']
        expansion.port_nodes['source', 'O'] = 'load:R'
        with self.assertRaises(ValueError):
            derive_loads(expansion)
        expansion.port_nodes['source', 'O'] = original
        expansion.blocks['source']['ports'][0]['kind'] = 'PASSIVE'
        with self.assertRaises(ValueError):
            derive_loads(expansion)
