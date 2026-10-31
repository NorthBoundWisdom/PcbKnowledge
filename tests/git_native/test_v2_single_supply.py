"""Single-supply return qualification does not relabel electrical terminals."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.intent import validate_intent
from tests.git_native.test_v2_record_contracts import fixtures, quantity

ROOT = Path(__file__).resolve().parents[2]


class SingleSupplyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())
        synthetic = fixtures()
        for kind in ('source', 'package', 'part'):
            synthetic[kind]['verification'] = 'AGENT_VERIFIED'
            synthetic[kind]['provenance']['verified_by'] = ['agent:independent-fixture']
        synthetic['source']['license_class'] = 'PUBLIC_REFERENCE'
        part = synthetic['part']
        part['pins'] = [{'number': '1', 'name': 'POS', 'type': 'POWER_IN'},
                        {'number': '2', 'name': 'NEG', 'type': 'POWER_IN'}]
        part['roles'] = ['analog.opamp']
        anchor = {'source': synthetic['source']['id'], 'page': 1}
        cap = quantity(1e-7, 'F')
        cap.update(basis='DATASHEET', evidence=anchor)
        part['single_supply_return'] = {'positive_pin': '1', 'negative_pin': '2',
                                       'capacitance_nominal': cap, 'evidence': [anchor]}
        self.part = part
        for record in (synthetic['source'], synthetic['package'], part):
            self.catalog.records[record['id']] = record
        block = self.catalog.get('block:usb-c-5v-sink')
        block['components'] += [{'ref': 'PAIR', 'select': {'part': part['id']}},
                                {'ref': 'PAIRCAP', 'select': {'part': 'part:kemet-c0603c104k5ractu'}}]
        next(n for n in block['nets'] if n['name'] == 'VBUS')['connect'] += ['PAIR.pin:1', 'PAIRCAP.pin:1']
        next(n for n in block['nets'] if n['name'] == 'GND')['connect'] += ['PAIR.pin:2', 'PAIRCAP.pin:2']
        self.block = block

    def result(self):
        return expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)

    def test_expansion_and_revalidation_preserve_types_and_bind_cap(self):
        result = self.result()
        self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
        self.assertEqual([p['type'] for p in self.part['pins']], ['POWER_IN', 'POWER_IN'])
        receipt = result['single_supply_returns'][0]
        self.assertEqual(receipt['capacitor'], 'usb_PAIRCAP')
        validate_intent(self.catalog, result, bundle_commit='a' * 40)
        near = [r for r in result['layout'] if r.get('subject') == 'usb_PAIRCAP']
        self.assertTrue(any(r.get('target') == 'usb_PAIR.pin:1'
                            and r['max_distance']['value'] == 3 for r in near), near)

    def test_removed_and_forged_receipts_refuse(self):
        original = self.result()
        for mutation in ('remove', 'capacitor', 'return_net'):
            result = deepcopy(original)
            if mutation == 'remove':
                result.pop('single_supply_returns')
            else:
                result['single_supply_returns'][0][mutation] = 'forged'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_intent(self.catalog, result, bundle_commit='a' * 40)

    def test_invalid_descriptor_and_wrong_types_refuse(self):
        from pcbknowledge.v2.single_supply import validate_part
        original = deepcopy(self.part)
        for mutation in ('positive_pin', 'negative_pin', 'type', 'evidence'):
            part = deepcopy(original)
            if mutation == 'type':
                part['pins'][1]['type'] = 'INPUT'
            elif mutation == 'evidence':
                part['single_supply_return']['evidence'] = []
            else:
                part['single_supply_return'][mutation] = 'missing'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_part(part, self.catalog.evidence)

    def test_missing_wrong_cap_and_ordinary_short_refuse(self):
        original = deepcopy(self.block)
        for mutation in ('missing-cap', 'wrong-cap', 'ordinary'):
            self.block.clear()
            self.block.update(deepcopy(original))
            if mutation == 'ordinary':
                self.part.pop('single_supply_return')
            elif mutation == 'wrong-cap':
                next(c for c in self.block['components'] if c['ref'] == 'PAIRCAP')['select']['part'] = (
                    'part:kemet-c0603c220j5gactu')
            else:
                next(n for n in self.block['nets'] if n['name'] == 'VBUS')['connect'].remove('PAIRCAP.pin:1')
            with self.subTest(mutation=mutation):
                self.assertEqual(self.result()['status'], 'REFUSED')

    def test_ground_and_supply_authority_refuse(self):
        original = deepcopy(self.block)
        for mutation in ('missing-return', 'foreign-return', 'unpowered', 'positive-ground', 'both-short'):
            self.block.clear()
            self.block.update(deepcopy(original))
            positive = next(n for n in self.block['nets'] if n['name'] == 'VBUS')['connect']
            negative = next(n for n in self.block['nets'] if n['name'] == 'GND')['connect']
            if mutation == 'missing-return':
                negative.remove('PAIR.pin:2')
            elif mutation == 'foreign-return':
                for pin in ('PAIR.pin:2', 'PAIRCAP.pin:2'):
                    negative.remove(pin)
                self.block['nets'].append({'name': 'FAKE_RETURN', 'connect': ['PAIR.pin:2', 'PAIRCAP.pin:2']})
            elif mutation == 'unpowered':
                for pin in ('PAIR.pin:1', 'PAIRCAP.pin:1'):
                    positive.remove(pin)
                self.block['nets'].append({'name': 'FAKE_POWER', 'connect': ['PAIR.pin:1', 'PAIRCAP.pin:1']})
            else:
                positive.remove('PAIR.pin:1')
                negative.append('PAIR.pin:1')
                if mutation == 'positive-ground':
                    negative.remove('PAIR.pin:2')
                    positive.append('PAIR.pin:2')
            with self.subTest(mutation=mutation):
                self.assertEqual(self.result()['status'], 'REFUSED')
