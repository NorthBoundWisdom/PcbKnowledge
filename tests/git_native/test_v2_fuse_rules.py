"""Fuse/header rule binding uses connectivity, never names or geometric guesses."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest

from pcbknowledge.v2.fuse_rules import fuse_entry_bindings
from pcbknowledge.v2.rules import apply_rules


def fixture():
    parts = {
        'F': {'id': 'part:fuse', 'roles': ['protection.fuse'], 'pins': [
            {'number': '1', 'type': 'PASSIVE'}, {'number': '2', 'type': 'PASSIVE'}]},
        'J': {'id': 'part:header', 'roles': ['connector.header'], 'pins': [
            {'number': '1', 'type': 'PASSIVE'}, {'number': '2', 'type': 'GROUND'}]},
    }
    nets = [{'name': 'ENTRY', 'class': 'POWER', 'pins': [{'ref': 'F', 'pin': '1'}, {'ref': 'J', 'pin': '1'}]},
            {'name': 'GND', 'class': 'GROUND', 'pins': [{'ref': 'J', 'pin': '2'}]}]
    rule = {'id': 'rule:synthetic-fuse-entry', 'applies_to': {'role': 'protection.fuse'}, 'layout': [
        {'kind': 'PLACE_NEAR', 'subject': 'fuse_pin', 'target': 'connected_connector_pin',
         'max_distance': {'value': 5, 'unit': 'mm'}}]}
    return parts, nets, SimpleNamespace(search=lambda kind: [rule])


class FuseRuleTests(unittest.TestCase):
    def test_unique_pair_is_deterministic_and_tracks_dependency(self):
        parts, nets, catalog = fixture()
        constraints, used = apply_rules(catalog, parts, nets)
        self.assertEqual(used, {'rule:synthetic-fuse-entry'})
        self.assertEqual((constraints[0]['subject'], constraints[0]['target']), ('F.pin:1', 'J.pin:1'))
        self.assertEqual(apply_rules(catalog, parts, list(reversed(nets))), (constraints, used))

    def test_exact_part_selector_is_conjunctive_and_excludes_other_fuses(self):
        parts, nets, catalog = fixture()
        rule = catalog.search('rule')[0]
        rule['applies_to']['part'] = 'part:other-fuse'
        self.assertEqual(apply_rules(catalog, parts, nets), ([], set()))
        rule['applies_to']['part'] = 'part:fuse'
        self.assertEqual(len(apply_rules(catalog, parts, nets)[0]), 1)
        rule['applies_to']['role'] = 'resistor'
        self.assertEqual(apply_rules(catalog, parts, nets), ([], set()))
        rule['applies_to']['role'] = 'protection.fuse'
        rule['applies_to']['pin_type'] = 'INPUT'
        self.assertEqual(apply_rules(catalog, parts, nets), ([], set()))

    def test_part_selector_structure_and_catalog_reference_are_checked(self):
        from pcbknowledge.v2.catalog import Catalog
        from tests.git_native.test_v2_record_contracts import fixtures
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        rule = fixtures()['rule']
        for selector in ('', None, 'source:synthetic', 'package:synthetic'):
            with self.subTest(selector=selector):
                rule['applies_to']['part'] = selector
                with self.assertRaises(ValueError):
                    catalog.structure(rule, 'rule.schema.json')
        rule['applies_to']['part'] = 'part:nonexistent-fuse'
        catalog.structure(rule, 'rule.schema.json')
        catalog.records[rule['id']] = rule
        with self.assertRaisesRegex(ValueError, 'Missing part: part:nonexistent-fuse'):
            catalog.validate()

    def test_absent_wrong_role_wrong_pin_type_and_wrong_net_refuse(self):
        for mutation in ('disconnected', 'role', 'connector_type', 'fuse_type', 'wrong_net', 'ground'):
            with self.subTest(mutation=mutation):
                parts, nets, catalog = fixture()
                if mutation == 'disconnected':
                    nets[0]['pins'].pop()
                elif mutation == 'role':
                    parts['J']['roles'] = ['resistor']
                elif mutation == 'connector_type':
                    parts['J']['pins'][0]['type'] = 'INPUT'
                elif mutation == 'fuse_type':
                    parts['F']['pins'][0]['type'] = 'POWER_IN'
                elif mutation == 'wrong_net':
                    nets.append({'name': 'UNRELATED', 'class': 'POWER', 'pins': [nets[0]['pins'].pop()]})
                elif mutation == 'ground':
                    nets[0]['class'] = 'GROUND'
                with self.assertRaisesRegex(ValueError, 'one unique directly connected header pin pair'):
                    apply_rules(catalog, parts, nets)
        parts['F']['roles'] = ['resistor']
        with self.assertRaisesRegex(ValueError, 'protection.fuse'):
            fuse_entry_bindings('F', parts, nets)

    def test_multiple_headers_or_physical_pin_pairs_refuse(self):
        for mutation in ('header', 'fuse_pin', 'connector_pin'):
            with self.subTest(mutation=mutation):
                parts, nets, catalog = fixture()
                if mutation == 'header':
                    parts['J2'] = copy.deepcopy(parts['J'])
                    nets[0]['pins'].append({'ref': 'J2', 'pin': '1'})
                elif mutation == 'fuse_pin':
                    nets[0]['pins'].append({'ref': 'F', 'pin': '2'})
                else:
                    parts['J']['pins'][1]['type'] = 'PASSIVE'
                    nets[0]['pins'].append(nets[1]['pins'].pop())
                with self.assertRaisesRegex(ValueError, 'one unique directly connected header pin pair'):
                    apply_rules(catalog, parts, nets)

    def test_unrelated_headers_and_ground_return_do_not_bind(self):
        parts, nets, catalog = fixture()
        parts['UNRELATED'] = copy.deepcopy(parts['J'])
        nets.append({'name': 'OTHER', 'class': 'POWER', 'pins': [{'ref': 'UNRELATED', 'pin': '1'}]})
        nets[1]['pins'].append({'ref': 'F', 'pin': '2'})
        constraints, _ = apply_rules(catalog, parts, nets)
        self.assertEqual(constraints[0]['target'], 'J.pin:1')
        # Even a mislabeled net cannot make a declared ground pin a supply entry.
        nets[1]['class'] = 'POWER'
        self.assertEqual(apply_rules(catalog, parts, nets)[0], constraints)

    def test_resolved_pin_distance_is_measured(self):
        from pcbknowledge.v2.layout import LayoutChecks
        parts, nets, catalog = fixture()
        constraint = apply_rules(catalog, parts, nets)[0][0]
        board = {'footprints': {
            'F': {'pads': {'1': [{'at': (0, 0)}]}}, 'J': {'pads': {'1': [{'at': (3, 4)}]}}}}
        checker = LayoutChecks(board, {'components': []}, None)
        self.assertEqual(checker.check(constraint)['result'], 'PASS')
        board['footprints']['J']['pads']['1'][0]['at'] = (3, 4.001)
        self.assertEqual(checker.check(constraint)['result'], 'FAIL')

    def test_g2_and_renamed_graphs_bind_exact_physical_entry_pins(self):
        from pcbknowledge.serialization import read_json
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.expansion import expand
        root = Path(__file__).resolve().parents[2]
        catalog = Catalog(root, root / 'schemas')
        brief = read_json((root / 'evals/golden-designs/g2.brief.json').read_bytes())
        original = read_json((root / 'evals/golden-designs/g2.block-graph.json').read_bytes())
        for prefix in ('', 'first_', 'second_', 'third_'):
            with self.subTest(prefix=prefix):
                graph = copy.deepcopy(original)
                for instance in graph['instances']:
                    instance['id'] = prefix + instance['id']
                for rail in graph.get('bringup', {}).get('rails', []):
                    for key in ('at', 'reference_at'):
                        if key in rail:
                            rail[key] = prefix + rail[key]
                for configuration in graph.get('pin_configurations', []):
                    configuration['instance'] = prefix + configuration['instance']
                for net in graph['connections']:
                    for endpoint in net['endpoints']:
                        endpoint['instance'] = prefix + endpoint['instance']
                intent = expand(catalog, graph, brief, bundle_commit='a' * 40)
                self.assertEqual(intent['status'], 'EXPANDED', intent['refusals'])
                constraints = [r for r in intent['layout'] if r['kind'] == 'PLACE_NEAR'
                               and r['subject'] == prefix + 'protection_F1.pin:1']
                self.assertEqual(len(constraints), 1, intent['refusals'])
                self.assertEqual(constraints[0]['target'], prefix + 'input_J1.pin:1')
                self.assertEqual(constraints[0]['max_distance']['value'], 5)
                self.assertIn('rule:fuse-connector-proximity', intent['dependencies'])
