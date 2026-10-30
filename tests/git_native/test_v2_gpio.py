"""Firmware pin requirements remain typed and source-backed through expansion."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.gpio import validate_configurations, validate_configured_drivers, validate_part_functions
from pcbknowledge.v2.synthesis import corpus_topology

ROOT = Path(__file__).resolve().parents[2]


class PinConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.graph = read_json((ROOT / 'evals/golden-designs/g2.block-graph.json').read_bytes())
        self.brief = read_json((ROOT / 'evals/golden-designs/g2.brief.json').read_bytes())

    def config(self, port='UART_TX', **changes):
        return {'instance': 'mcu', 'port': port, 'mode': 'GPIO_PUSH_PULL', 'initial_state': 'LOW', **changes}

    def expand(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def assert_invalid(self, text):
        result = self.expand()
        self.assertTrue(any(text in r['reason'] for r in result['refusals']), result['refusals'])

    def test_three_gpio_requirements_resolve_to_exact_pins(self):
        self.graph['pin_configurations'] = [self.config(p) for p in ('LED1', 'LED2', 'UART_TX')]
        result = self.expand()
        self.assertEqual([(c['ref'], c['pin']) for c in result['pin_configurations']],
                         [('mcu_U1', '10'), ('mcu_U1', '11'), ('mcu_U1', '30')])
        self.assertTrue(all(c['mode'] == 'GPIO_PUSH_PULL' and c['initial_state'] == 'LOW'
                            for c in result['pin_configurations']))
        self.assertTrue(all(c['evidence'] for c in result['pin_configurations']))

    def test_unsupported_pin_and_power_port_are_rejected(self):
        self.graph['pin_configurations'] = [self.config('BUTTON')]
        self.assert_invalid('does not support')
        self.graph['pin_configurations'] = [self.config('VDD')]
        self.assert_invalid('exactly one physical pin')

    def test_duplicate_and_conflicting_configurations_are_rejected(self):
        self.graph['pin_configurations'] = [self.config(), self.config()]
        self.assert_invalid('Duplicate or conflicting')
        self.graph['pin_configurations'] = [self.config()]
        self.graph['port_requirements'] = [{'instance': 'mcu', 'port': 'UART_TX', 'function': 'UART_TX'}]
        self.assert_invalid('conflicts with a required pin function')

    def test_initial_state_and_mode_must_be_supported(self):
        self.graph['pin_configurations'] = [self.config(initial_state='HIGH')]
        self.assert_invalid('Unknown pin-states')
        self.graph['pin_configurations'] = [self.config(mode='UART_TX')]
        self.assert_invalid('Unsupported firmware')
        del self.graph['pin_configurations'][0]['initial_state']
        self.assert_invalid('Missing required')

    def test_active_uart_block_cannot_be_silently_repurposed(self):
        self.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())
        self.brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        self.graph['pin_configurations'] = [self.config()]
        self.assert_invalid('conflicts with a required pin function')

    def test_intent_configuration_evidence_and_duplicates_are_checked(self):
        self.graph['pin_configurations'] = [self.config()]
        configurations = self.expand()['pin_configurations']
        parts = {'mcu_U1': self.catalog.get('part:st-stm32f103c8t6')}
        validate_configurations(self.catalog, parts, configurations)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_configurations(self.catalog, parts, configurations * 2)
        configurations[0]['evidence'][0]['page'] += 1
        with self.assertRaisesRegex(ValueError, 'evidence differs'):
            validate_configurations(self.catalog, parts, configurations)

    def test_configured_output_cannot_share_a_net_with_another_driver(self):
        parts = {'U1': {'pins': [{'number': '1', 'type': 'BIDIRECTIONAL'}]},
                 'U2': {'pins': [{'number': '1', 'type': 'OUTPUT'}]}}
        configurations = [{'ref': 'U1', 'pin': '1'}]
        with self.assertRaisesRegex(ValueError, 'conflicts with another output'):
            validate_configured_drivers(parts, configurations, {('U1', '1'): 'N', ('U2', '1'): 'N'})

    def test_part_cannot_claim_a_gpio_function_on_a_supply_pin(self):
        part = deepcopy(self.catalog.get('part:st-stm32f103c8t6'))
        pin = next(p for p in part['pins'] if p['number'] == '1')
        pin['functions'] = deepcopy(next(p for p in part['pins'] if p['number'] == '30')['functions'])
        with self.assertRaisesRegex(ValueError, 'digital output-capable'):
            validate_part_functions(self.catalog, part)

    def test_absent_capability_registry_fails_closed(self):
        self.catalog.vocabulary.entries.pop('pin-functions')
        self.graph['pin_configurations'] = [self.config()]
        self.assert_invalid('Unknown pin-functions')

    def test_corpus_comparison_includes_configuration_and_requirements(self):
        # G2 repeats three identical load headers, so its structure requires review.
        self.assertIsNone(corpus_topology(self.graph))
        self.graph['instances'] = [i for i in self.graph['instances'] if i['id'] == 'mcu']
        self.graph['connections'] = []
        self.graph.pop('pin_configurations', None)
        other = deepcopy(self.graph)
        other['pin_configurations'] = [self.config()]
        self.assertNotEqual(corpus_topology(other), corpus_topology(self.graph))
        self.graph['pin_configurations'] = [self.config()]
        other['pin_configurations'][0]['initial_state'] = 'HIGH'
        self.assertNotEqual(corpus_topology(other), corpus_topology(self.graph))
        other = deepcopy(self.graph)
        other['port_requirements'] = [{'instance': 'mcu', 'port': 'UART_TX', 'function': 'UART_TX'}]
        self.assertNotEqual(corpus_topology(other), corpus_topology(self.graph))
