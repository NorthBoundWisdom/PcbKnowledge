"""Current-input variant reference regressions, not new synthesis provenance."""
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.intent import validate_intent

ROOT = Path(__file__).resolve().parents[2]


class VariantAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')

    def expand_reference(self, name):
        base = ROOT / 'evals/golden-designs'
        brief = read_json((base / (name + '.brief.json')).read_bytes())
        graph = read_json((base / (name + '.block-graph.json')).read_bytes())
        # Fixed algorithm input, not an authenticated release-bundle receipt.
        return expand(self.catalog, graph, brief, bundle_commit='a' * 40)

    def nets(self, intent):
        return {(pin['ref'], pin['pin']): net['name'] for net in intent['nets'] for pin in net['pins']}

    def test_both_reference_variants_expand_and_validate(self):
        for name in ('g1v1', 'g1v2'):
            with self.subTest(brief=name):
                intent = self.expand_reference(name)
                self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
                self.assertTrue(intent['checks'])
                self.assertTrue(all(check['result'] == 'PASS' for check in intent['checks']))
                validate_intent(self.catalog, intent, bundle_commit='a' * 40)

    def test_temperature_variant_has_no_monitor_or_shunt_and_uses_logger_rail(self):
        intent = self.expand_reference('g1v1')
        excluded = {item['select']['part'] for item in self.catalog.get('block:ina219-monitor')['components']
                    if item['ref'] in ('U1', 'R1')}
        self.assertFalse(excluded & {item['part'] for item in intent['components']})
        nets = self.nets(intent)
        for endpoint in (('temperature_U1', '8'), ('temperature_R1', '1'), ('ldo_U1', '2'), ('mcu_U1', '24')):
            self.assertEqual(nets[endpoint], 'LOGGER_3V3')
        self.assertEqual(nets['temperature_U1', '1'], 'I2C_SDA')
        self.assertEqual(nets['temperature_U1', '2'], 'I2C_SCL')
        self.assertEqual(nets['temperature_U1', '3'], nets['temperature_R1', '2'])

    def test_usb_uart_pair_direction_and_monitor_supply_boundaries(self):
        intent = self.expand_reference('g1v2')
        nets = self.nets(intent)
        for name, endpoints in {
            'USB_DP': [('usb_J1', 'A6'), ('usb_J1', 'B6'), ('bridge_U1', '5')],
            'USB_DN': [('usb_J1', 'A7'), ('usb_J1', 'B7'), ('bridge_U1', '6')],
            'UART_TX': [('mcu_U1', '30'), ('bridge_U1', '3')],
            'UART_RX': [('mcu_U1', '31'), ('bridge_U1', '2')],
            'REGULATED_3V3': [('monitor_U1', '4'), ('monitor_R1', '1'), ('ldo_U1', '2')],
            'LOGGER_3V3': [('monitor_R1', '2'), ('bridge_U1', '16'), ('mcu_U1', '24')],
        }.items():
            for endpoint in endpoints:
                self.assertEqual(nets[endpoint], name)
        pairs = [rule['nets'] for rule in intent['layout'] if rule['kind'] == 'DIFFERENTIAL_PAIR']
        self.assertTrue(any(set(pair) == {'USB_DP', 'USB_DN'} for pair in pairs))

    def test_temperature_os_missing_bias_fails_existing_pullup_check(self):
        block = self.catalog.get('block:i2c-temperature-sensor')
        for net in block['nets']:
            net['connect'] = [endpoint for endpoint in net['connect'] if endpoint != 'R1.pin:2']
        intent = self.expand_reference('g1v1')
        self.assertEqual(intent['status'], 'REFUSED')
        self.assertTrue(any(check['id'] == 'pullup:temperature_U1:3' and check['result'] == 'FAIL'
                            for check in intent['checks']), intent['checks'])

    def test_usb_uart_floating_required_input_fails_connection_check(self):
        block = self.catalog.get('block:usb-uart-bridge')
        for net in block['nets']:
            net['connect'] = [endpoint for endpoint in net['connect'] if endpoint != 'U1.pin:9']
        intent = self.expand_reference('g1v2')
        self.assertEqual(intent['status'], 'REFUSED')
        self.assertTrue(any(check['id'] == 'connection:bridge_U1:9' and check['result'] == 'FAIL'
                            for check in intent['checks']), intent['checks'])
