"""End-to-end G1 reference and adversarial mutations through production expansion."""
import copy
from pathlib import Path
import unittest
from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand

ROOT = Path(__file__).resolve().parents[2]


class GoldenAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT/'schemas')
        self.graph = read_json((ROOT/'evals/golden-designs/g1.block-graph.json').read_bytes())
        self.brief = read_json((ROOT/'evals/golden-designs/g1.brief.json').read_bytes())

    def expand(self, graph=None):
        # This is a pure algorithm fixture, not a claimed release bundle receipt.
        return expand(self.catalog, graph or self.graph, self.brief, bundle_commit='a'*40)

    def test_reference_is_deterministic_and_passes_all_a2_checks(self):
        one, two = self.expand(), self.expand()
        self.assertEqual(one['status'],'EXPANDED', one['refusals'])
        self.assertTrue(one['checks'])
        self.assertTrue(all(check['result']=='PASS' for check in one['checks']))
        self.assertEqual(canonical_json(one),canonical_json(two))
        self.assertEqual(len(one['components']),46)

    def test_overbudget_and_requirement_spoof_refuse(self):
        changed=copy.deepcopy(self.graph)
        next(i for i in changed['instances'] if i['block']=='block:ldo-fixed')['parameters']['output_current']['value']=.2
        self.assertEqual(self.expand(changed)['status'],'REFUSED')
        changed=copy.deepcopy(self.graph)
        mcu=next(i for i in changed['instances'] if i['block']=='block:mcu-core')
        memory=next(i for i in changed['instances'] if i['block']=='block:i2c-eeprom')
        mcu['requirements'],memory['requirements']=memory['requirements'],mcu['requirements']
        self.assertEqual(self.expand(changed)['status'],'REFUSED')

    def test_floating_boot_and_missing_decoupling_refuse(self):
        block=self.catalog.get('block:mcu-core')
        for net in block['nets']:
            net['connect']=[pin for pin in net['connect'] if pin not in ('U1.pin:BOOT0','U1.pin:44')]
        result=self.expand()
        self.assertEqual(result['status'],'REFUSED')
        self.setUp();block=self.catalog.get('block:mcu-core')
        capacitor_refs={c['ref'] for c in block['components'] if c['ref'].startswith('C')}
        block['components']=[c for c in block['components'] if c['ref'] not in capacitor_refs]
        for net in block['nets']:
            net['connect']=[p for p in net['connect'] if p.split('.pin:')[0] not in capacitor_refs]
        block['layout']=[]
        self.assertEqual(self.expand()['status'],'REFUSED')

    def test_unknown_part_fails_closed(self):
        self.catalog.get('block:mcu-core')['components'][0]['select']={'part':'part:does-not-exist'}
        result=self.expand()
        self.assertEqual(result['status'],'REFUSED')
        self.assertTrue(any(item['code']=='UNSATISFIED_SELECTION' for item in result['refusals']))
