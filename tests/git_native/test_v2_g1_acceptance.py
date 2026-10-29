"""End-to-end G1 reference and adversarial mutations through production expansion."""
import copy
import hashlib
from pathlib import Path
import unittest
from pcbknowledge.serialization import canonical_json, read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.assembly import validate_assembly
from pcbknowledge.v2.intent import validate_intent

ROOT = Path(__file__).resolve().parents[2]
# Intentional Stage 6 package identity and assembly-contract migration baseline.
G1_CANONICAL_SHA256 = '10fbd1fad48855e011e58c0043176306ba3877666a861633e7c1cb095cfc6b9f'


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
        self.assertEqual(hashlib.sha256(canonical_json(one).encode()).hexdigest(), G1_CANONICAL_SHA256)

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

    def test_preserved_synthesis_graphs_replay_against_current_inputs(self):
        # Historical receipts remain untouched: this checks current replay only,
        # not a fresh independent synthesis or a replacement provenance claim.
        for name in ('one', 'two', 'three'):
            with self.subTest(attempt=name):
                attempt = read_json((ROOT / 'evals/synthesis/g1' / (name + '.json')).read_bytes())
                result = self.expand(attempt['graph'])
                self.assertEqual(result['status'], 'EXPANDED', result['refusals'])
                self.assertTrue(result['checks'])
                self.assertTrue(all(check['result'] == 'PASS' for check in result['checks']))
                validate_intent(self.catalog, result, bundle_commit='a' * 40)

    def test_expanded_requires_authentic_assembly_metadata(self):
        original = self.expand()
        for collection in ('components', 'bom'):
            for field in ('mount_type', 'assembly_method'):
                for mutation in ('missing', 'tampered'):
                    with self.subTest(collection=collection, field=field, mutation=mutation):
                        intent = copy.deepcopy(original)
                        item = intent[collection][0]
                        if mutation == 'missing':
                            del item[field]
                        elif field == 'mount_type':
                            item[field] = 'THT' if item[field] != 'THT' else 'SMT'
                        else:
                            item[field] = 'HAND_SOLDER' if item[field] != 'HAND_SOLDER' else 'SMT_ASSEMBLY'
                        with self.assertRaises(ValueError):
                            validate_intent(self.catalog, intent, bundle_commit='a' * 40)

    def test_early_refusal_can_omit_but_not_forge_assembly_metadata(self):
        graph = copy.deepcopy(self.graph)
        graph['connections'][1]['endpoints'].append(copy.deepcopy(graph['connections'][0]['endpoints'][0]))
        intent = self.expand(graph)
        self.assertEqual(intent['status'], 'REFUSED')
        self.assertTrue(intent['components'])
        self.assertTrue(any(item['code'] == 'INVALID_REFERENCE' for item in intent['refusals']))
        for item in intent['components']:
            self.assertNotIn('mount_type', item)
            self.assertNotIn('assembly_method', item)
        self.catalog.structure(intent, 'design-intent.schema.json')
        validate_assembly(self.catalog, intent)
        intent['components'][0]['mount_type'] = 'SMT'
        with self.assertRaisesRegex(ValueError, 'Assembly metadata'):
            validate_assembly(self.catalog, intent)
