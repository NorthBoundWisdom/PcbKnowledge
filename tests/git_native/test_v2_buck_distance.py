"""D90 nearest same-net pad copper keeps all ten original G2 limits."""
import copy
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.boardview import board_from_text, parse_board
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.layout import LayoutChecks, check_layout

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = [(0, 'C2', 'U1.pin:7', 1), (1, 'C3', 'U1.pin:1', 2),
            (2, 'D1', 'U1.pin:8', 2), (3, 'C4', 'L1.pin:2', 3),
            (4, 'RF1', 'U1.pin:4', 3), (8, 'C5', 'U1.pin:7', 1),
            (9, 'C6', 'U1.pin:7', 1), (10, 'C2', 'U1.pin:6', 1),
            (11, 'C5', 'U1.pin:6', 1), (12, 'C6', 'U1.pin:6', 1)]


def pair_board(subject, target, distance):
    ref, _, pin = target.partition('.pin:')
    return board_from_text(f'''(kicad_pcb (version 20241229)
      (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) (net 1 "TEST")
      (footprint "Test:Pair" (layer "F.Cu") (at {distance} 0) (property "Reference" "{subject}")
        (pad "1" smd rect (at 0 0) (size 0.2 0.2) (layers "F.Cu") (net 1 "TEST")))
      (footprint "Test:Pair" (layer "F.Cu") (at 0 0) (property "Reference" "{ref}")
        (pad "{pin}" smd rect (at 0 0) (size 0.2 0.2) (layers "F.Cu") (net 1 "TEST"))))''')


class BuckDistanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT, ROOT / 'schemas')
        cls.block = cls.catalog.get('block:g2-buck')

    def test_all_ten_limits_preserved_and_other_blocks_keep_default(self):
        rules = [(i, r['subject'], r['target'], r['max_distance']['value'])
                 for i, r in enumerate(self.block['layout']) if r['kind'] == 'PLACE_NEAR']
        self.assertEqual(rules, EXPECTED)
        for record in self.catalog.search('block'):
            for rule in record['layout']:
                if rule['kind'] == 'PLACE_NEAR':
                    self.assertEqual(rule.get('datum', 'ORIGIN_PAD_CENTER'),
                                     'COPPER_EDGE' if record['id'] == self.block['id'] else 'ORIGIN_PAD_CENTER')

    def test_every_original_limit_has_a_copper_edge_boundary_and_failure(self):
        # Contract-only pair coupons are not a claim that the full G2 board fits.
        for index, subject, target, limit in EXPECTED:
            for distance, expected in ((limit + .2, 'PASS'), (limit + .200001, 'FAIL')):
                with self.subTest(index=index, distance=distance):
                    board = pair_board(subject, target, distance)
                    report = LayoutChecks(board, {'components': []}, None).check(self.block['layout'][index])
                    self.assertEqual(report['result'], expected)
                    self.assertAlmostEqual(report['distance_mm'], distance - .2)
                    self.assertEqual(report['datum'], 'COPPER_EDGE')
                    self.assertEqual(report['subject_pad'], subject + '.pin:1')

    def test_omitted_datum_keeps_origin_distance_and_explicit_default_matches(self):
        board = pair_board('C', 'U.pin:1', 1.2)
        checker = LayoutChecks(board, {'components': []}, None)
        rule = {'kind': 'PLACE_NEAR', 'subject': 'C', 'target': 'U.pin:1',
                'max_distance': {'value': 1, 'unit': 'mm'}}
        self.assertEqual(checker.check(rule)['result'], 'FAIL')
        self.assertEqual(checker.check(rule), checker.check({**rule, 'datum': 'ORIGIN_PAD_CENTER'}))
        self.assertEqual(checker.check({**rule, 'datum': 'COPPER_EDGE'})['result'], 'PASS')

    def test_g2_cap_output_is_not_silently_treated_as_the_inductor_output_net(self):
        nets = {endpoint: net['name'] for net in self.block['nets'] for endpoint in net['connect']}
        self.assertEqual(nets['C4.pin:1'], 'CAP_OUT')
        self.assertEqual(nets['L1.pin:2'], 'VOUT')
        board = pair_board('C4', 'L1.pin:2', .3)
        board['footprints']['C4']['pads']['1'][0]['net'] = nets['C4.pin:1']
        board['footprints']['L1']['pads']['2'][0]['net'] = nets['L1.pin:2']
        report = LayoutChecks(board, {'components': []}, None).check(self.block['layout'][3])
        self.assertEqual(report['result'], 'NOT_CHECKABLE')
        self.assertEqual(report['reason_code'], 'NO_SAME_NET_PAD')

    def test_unknown_datum_wrong_kind_and_nonpin_target_are_rejected(self):
        for mutation in ('datum', 'kind', 'target', 'alias'):
            block = copy.deepcopy(self.block)
            rule = block['layout'][0]
            if mutation == 'datum':
                rule['datum'] = 'BODY_EDGE'
            elif mutation == 'kind':
                rule['kind'] = 'TEST_POINT'
            elif mutation == 'alias':
                rule['target'] = 'U1.pin:VIN'
            else:
                rule['target'] = 'U1'
            with self.assertRaises(ValueError):
                self.catalog.structure(block, 'block.schema.json')
                self.catalog._block(block)

    def test_expansion_retains_copper_edge_without_new_reference_aliases(self):
        graph = json.loads((ROOT / 'evals/golden-designs/g2.block-graph.json').read_text())
        brief = json.loads((ROOT / 'evals/golden-designs/g2.brief.json').read_text())
        intent = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
        self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
        rules = [r for r in intent['layout'] if r.get('datum') == 'COPPER_EDGE']
        self.assertEqual(len(rules), 10)
        self.assertTrue(all(r['subject'].startswith('buck_') and r['target'].startswith('buck_') for r in rules))

    def test_joint_original_board_keeps_failed_and_unmeasurable_rules_visible(self):
        graph = json.loads((ROOT / 'evals/golden-designs/g2.block-graph.json').read_text())
        brief = json.loads((ROOT / 'evals/golden-designs/g2.brief.json').read_text())
        intent = expand(self.catalog, graph, brief, bundle_commit='a' * 40)
        board = parse_board(ROOT / 'tests/fixtures/layout/g2-buck-copper-edge.kicad_pcb')
        report = check_layout(board, intent, self.catalog)
        self.assertEqual(report['checks'][0]['result'], 'PASS')
        rows = [row for row in report['checks'] if row.get('datum') == 'COPPER_EDGE']
        self.assertEqual(len(rows), 10)
        self.assertEqual(sum(row['result'] == 'PASS' for row in rows), 7)
        self.assertEqual(sum(row['result'] == 'FAIL' for row in rows), 2)
        self.assertEqual([row['reason_code'] for row in rows if row['result'] == 'NOT_CHECKABLE'],
                         ['NO_SAME_NET_PAD'])
        self.assertEqual(report['result'], 'FAIL')
        self.assertFalse(report['routing_certified'])
