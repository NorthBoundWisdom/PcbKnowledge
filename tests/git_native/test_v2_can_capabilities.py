"""Reviewed CAN capability additions preserve the existing physical designs."""
from copy import copy, deepcopy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.gpio import _capability

ROOT = Path(__file__).resolve().parents[2]
FUNCTIONS = {'CAN_RX', 'CAN_TX'}
ADDED_ANCHORS = {('source:st-rm0008', 185), ('source:st-stm32f103', 33)}


class CanCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')

    def test_exact_physical_capabilities_and_wrong_terminal_refusal(self):
        part = self.catalog.records['part:st-stm32f103c8t6']
        for number, function in (('32', 'CAN_RX'), ('33', 'CAN_TX')):
            actual = _capability(self.catalog, {'U1': part}, 'U1', number, function)
            self.assertEqual(actual['name'], function)
            anchors = {(item['source'], item['page']) for item in actual['evidence']}
            self.assertEqual(anchors, ADDED_ANCHORS | {('source:st-stm32f103', 31)})
        with self.assertRaisesRegex(ValueError, 'does not support'):
            _capability(self.catalog, {'U1': part}, 'U1', '32', 'CAN_TX')

    def test_existing_designs_change_only_the_two_reviewed_evidence_anchors(self):
        previous = copy(self.catalog)
        previous.records = deepcopy(self.catalog.records)
        for pin in previous.records['part:st-stm32f103c8t6']['pins']:
            if 'functions' in pin:
                pin['functions'] = [item for item in pin['functions'] if item['name'] not in FUNCTIONS]
                if not pin['functions']:
                    del pin['functions']
        for name in ('g1', 'g1v1', 'g1v2', 'g2', 'g3', 'g4', 'g5', 't5'):
            folder = ROOT / ('evals/corpus/themes' if name == 't5' else 'evals/golden-designs')
            graph = read_json((folder / (name + '.block-graph.json')).read_bytes())
            brief = read_json((folder / (name + '.brief.json')).read_bytes())
            old = expand(previous, graph, brief, bundle_commit='a' * 40)
            new = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
            with self.subTest(brief=name):
                self.assertEqual(new['status'], 'EXPANDED', new['refusals'])
                old_evidence = {(item['source'], item['page']) for item in old.pop('evidence')}
                new_evidence = {(item['source'], item['page']) for item in new.pop('evidence')}
                self.assertEqual(new, old)
                self.assertFalse(old_evidence - new_evidence)
                self.assertEqual(new_evidence - old_evidence,
                                 set() if name in ('g3', 'g4', 'g5') else ADDED_ANCHORS)
