"""Ordered Kelvin mappings survive expansion without inventing a physical PASS."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand, validate_expansion
from pcbknowledge.v2.intent import validate_intent
from pcbknowledge.v2.kelvin_contract import validate_kelvin, block_connections
from pcbknowledge.v2.layout import LayoutChecks

ROOT = Path(__file__).resolve().parents[2]


def fixture():
    parts = {'U': [{'pins': [{'number': '1', 'name': 'IN+', 'type': 'ANALOG'},
                             {'number': '2', 'name': 'IN-', 'type': 'ANALOG'}]}],
             'R': [{'pins': [{'number': '1', 'name': '1'}, {'number': '2', 'name': '2'}]}]}
    rule = {'kind': 'KELVIN', 'sense_nets': ['A', 'B'], 'target': 'R', 'branches': [
        {'sense': 'U.pin:' + n, 'target': 'R.pin:' + n,
         'evidence': {'source': 'source:synthetic', 'page': 1}} for n in ('1', '2')]}
    connections = {(ref, pin): net for ref in ('U', 'R') for pin, net in [('1', 'A'), ('2', 'B')]}
    return parts, rule, connections


class KelvinContractTests(unittest.TestCase):
    def test_valid_ordered_mapping_and_unmapped_legacy(self):
        parts, rule, connections = fixture()
        validate_kelvin(rule, parts, connections)
        del rule['branches']
        validate_kelvin(rule, parts, connections)
        self.assertEqual(LayoutChecks({'footprints': {}}, {'components': []}, None).check(rule)['result'],
                         'NOT_CHECKABLE')

    def test_wrong_missing_named_and_duplicate_pins_rejected(self):
        parts, rule, connections = fixture()
        for endpoint in ('U.pin:IN+', 'U.pin:3', 'MISSING.pin:1', 'U'):
            changed = deepcopy(rule)
            changed['branches'][0]['sense'] = endpoint
            with self.assertRaises(ValueError):
                validate_kelvin(changed, parts, connections)
        for field in ('sense', 'target'):
            changed = deepcopy(rule)
            changed['branches'][1][field] = changed['branches'][0][field]
            with self.assertRaises(ValueError):
                validate_kelvin(changed, parts, connections)

    def test_branch_order_and_merged_nets_rejected(self):
        parts, rule, connections = fixture()
        rule['branches'].reverse()
        with self.assertRaisesRegex(ValueError, 'ordered branch'):
            validate_kelvin(rule, parts, connections)
        rule['sense_nets'] = ['A', 'A']
        with self.assertRaisesRegex(ValueError, 'distinct'):
            validate_kelvin(rule, parts, connections)

    def test_partial_mapping_and_missing_evidence_rejected(self):
        parts, rule, connections = fixture()
        for branches in ([], [rule['branches'][0]], [None, rule['branches'][1]]):
            with self.assertRaises(ValueError):
                validate_kelvin(dict(rule, branches=branches), parts, connections)
        for value in ({}, {'source': 'source:synthetic', 'page': 0}):
            changed = deepcopy(rule)
            changed['branches'][0]['evidence'] = value
            with self.assertRaises(ValueError):
                validate_kelvin(changed, parts, connections)

    def test_block_named_connections_resolve_to_numbered_authority(self):
        parts, rule, connections = fixture()
        block = {'nets': [{'name': 'A', 'connect': ['U.pin:IN+', 'R.pin:1']},
                          {'name': 'B', 'connect': ['U.pin:IN-', 'R.pin:2']}]}
        self.assertEqual(block_connections(block, parts), connections)
        block['nets'][1]['connect'].append('U.pin:1')
        with self.assertRaises(ValueError):
            block_connections(block, parts)


class KelvinExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')
        cls.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())
        cls.brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        cls.intent = expand(cls.catalog, cls.graph, cls.brief, bundle_commit='a' * 40)
        cls.bundle = SimpleNamespace(catalog=cls.catalog, commit='a' * 40, briefs={'G1': cls.brief})

    def test_expanded_mapping_is_prefixed_and_reconstructed(self):
        self.assertEqual(self.intent['status'], 'EXPANDED')
        rule = next(row for row in self.intent['layout'] if row['kind'] == 'KELVIN')
        self.assertEqual(rule['branches'][0]['sense'], 'monitor_U1.pin:1')
        self.assertEqual(rule['branches'][1]['target'], 'monitor_R1.pin:2')
        self.assertIn('source:ti-ina219', self.intent['dependencies'])
        self.assertIn({'source': 'source:ti-ina219', 'page': 27}, self.intent['evidence'])
        validate_expansion(self.bundle, self.intent, self.graph)
        for mutation in ('missing', 'swapped', 'evidence'):
            changed = deepcopy(self.intent)
            row = next(x for x in changed['layout'] if x['kind'] == 'KELVIN')
            if mutation == 'missing':
                del row['branches']
            elif mutation == 'swapped':
                row['branches'].reverse()
            else:
                row['branches'][0]['evidence']['page'] = 3
            with self.assertRaises(ValueError):
                validate_expansion(self.bundle, changed, self.graph)

    def test_intent_same_net_mapping_and_source_closure_are_validated(self):
        for mutation in ('pin', 'net', 'source', 'closure'):
            changed = deepcopy(self.intent)
            row = next(x for x in changed['layout'] if x['kind'] == 'KELVIN')
            if mutation == 'pin':
                row['branches'][0]['sense'] = 'monitor_U1.pin:4'
            elif mutation == 'net':
                row['sense_nets'][1] = row['sense_nets'][0]
            elif mutation == 'source':
                row['branches'][0]['evidence']['source'] = 'source:missing'
            else:
                changed['evidence'].remove({'source': 'source:ti-ina219', 'page': 27})
            with self.assertRaises(ValueError):
                validate_intent(self.catalog, changed, bundle_commit='a' * 40)

    def test_all_three_blocks_declare_exact_current_endpoints_without_promotion(self):
        for name in ('ina219-monitor', 'g2-input-monitor', 't1-readback'):
            block = self.catalog.get('block:' + name)
            rule = next(row for row in block['layout'] if row['kind'] == 'KELVIN')
            self.assertEqual([(b['sense'], b['target']) for b in rule['branches']],
                             [('U1.pin:1', 'R1.pin:1'), ('U1.pin:2', 'R1.pin:2')])
            self.assertTrue(all(b['evidence'] == {'source': 'source:ti-ina219', 'page': 27}
                                for b in rule['branches']))
        self.assertEqual(self.catalog.get('block:t1-readback')['verification'], 'DRAFT')
