"""Typed corpus feasibility and actual selected-package enforcement."""
import copy
from pathlib import Path
import unittest

from pcbknowledge.serialization import read_json
from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.coverage import coverage_all
from pcbknowledge.v2.expansion import expand
from pcbknowledge.v2.requirements import assess_brief

ROOT = Path(__file__).resolve().parents[2]


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT, ROOT / 'schemas')
        self.brief = read_json((ROOT / 'evals/golden-designs/g1.brief.json').read_bytes())
        self.graph = read_json((ROOT / 'evals/golden-designs/g1.block-graph.json').read_bytes())

    def test_g1_feasibility_is_not_an_a2_claim(self):
        self.assertEqual(assess_brief(self.catalog, self.brief), [])
        report = coverage_all(self.catalog, {'G1': self.brief}, expectations={'G1': {'outcome': 'SUPPORTED'}})
        self.assertEqual(report['briefs'][0]['screening'], 'ELIGIBLE')
        self.assertEqual(report['briefs'][0]['graph_readiness'], 'NOT_PROVIDED')
        self.assertIn('no new A2', report['scope'])

    def test_negative_voltage_wifi_and_package_are_typed(self):
        brief = copy.deepcopy(self.brief)
        brief['id'] = 'N1'
        brief['power']['sources'][0]['voltage']['value'] = 12
        cases = [(brief, 'CHECK_FAILED', 'functions.usb_sink')]
        brief = copy.deepcopy(self.brief)
        brief['id'] = 'N2'
        wireless = copy.deepcopy(brief['functions'][0])
        wireless.update(id='wifi', category='wireless.wifi', parameters={})
        brief['functions'].append(wireless)
        cases.append((brief, 'UNSATISFIED_SELECTION', 'functions.wifi'))
        brief = copy.deepcopy(self.brief)
        brief['id'] = 'N3'
        next(f for f in brief['functions'] if f['id'] == 'mcu').update(
            package_family='BGA', package_role='mcu.32-bit')
        cases.append((brief, 'UNSATISFIED_SELECTION', 'functions.mcu'))
        for document, code, path in cases:
            with self.subTest(brief=document['id']):
                refusals = assess_brief(self.catalog, document)
                self.assertTrue(any(item['code'] == code and item['path'] == path for item in refusals), refusals)
                self.assertTrue(all(item['reason'] and item['queries'] for item in refusals))

    def test_expansion_checks_selected_component_package_family(self):
        function = next(f for f in self.brief['functions'] if f['id'] == 'mcu')
        function.update(package_family='LQFP-48', package_role='mcu.32-bit')
        self.assertEqual(expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)['status'], 'EXPANDED')
        function['package_family'] = 'BGA'
        result = expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(item['code'] == 'UNSATISFIED_SELECTION' for item in result['refusals']))

    def test_unverified_selected_closure_is_ineligible(self):
        self.catalog.get('block:mcu-core')['verification'] = 'DRAFT'
        refusals = assess_brief(self.catalog, self.brief)
        self.assertTrue(any(item['code'] == 'UNVERIFIED_RECORD' and item['path'] == 'functions.mcu'
                            for item in refusals))

    def test_coverage_reports_graph_readiness_separately(self):
        bad = copy.deepcopy(self.graph)
        bad['connections'] = []
        report = coverage_all(self.catalog, {'G1': self.brief}, {'G1': bad})
        row = report['briefs'][0]
        self.assertEqual(row['screening'], 'ELIGIBLE')
        self.assertEqual(row['graph_readiness'], 'REFUSED')
        self.assertTrue(row['graph_refusals'])
        self.assertEqual(row['expected'], {'outcome': 'UNSPECIFIED'})

    def test_differential_pair_contract_and_dimension_checks(self):
        constraint = {'kind': 'DIFFERENTIAL_PAIR', 'nets': ['P', 'N'],
                      'min_width': {'value': 0.2, 'unit': 'mm'},
                      'gap': {'value': 0.15, 'unit': 'mm'}, 'max_skew': {'value': 1, 'unit': 'mm'}}
        # Schema-only quantities must carry their existing authority envelope.
        template = copy.deepcopy(self.brief['power']['sources'][0]['voltage'])
        for field in ('min_width', 'gap', 'max_skew'):
            constraint[field] = {**template, **constraint[field]}
        self.catalog.structure(constraint, 'layout-constraint.schema.json')
        self.catalog.vocabulary.document({'layout': [constraint]})
        self.catalog._layout_references(constraint, {}, {'P', 'N'})
        with self.assertRaisesRegex(ValueError, 'Dangling layout net'):
            self.catalog._layout_references(constraint, {}, {'P'})
        constraint['gap']['unit'] = 'V'
        with self.assertRaisesRegex(ValueError, 'Wrong canonical unit'):
            self.catalog.vocabulary.document({'layout': [constraint]})


    def test_unrelated_bga_passive_cannot_satisfy_mcu_package_requirement(self):
        from pcbknowledge.v2.requirements import selected_parts
        function = next(f for f in self.brief['functions'] if f['id'] == 'mcu')
        function.update(package_family='BGA', package_role='mcu.32-bit')
        selected = selected_parts(self.catalog, self.catalog.get('block:mcu-core'))
        passive = next(part for part in selected if 'resistor' in part['roles'])
        self.catalog.get(passive['package'])['family'] = 'BGA'
        self.assertTrue(any(self.catalog.get(part['package'])['family'] == 'BGA' for part in selected))
        refusals = assess_brief(self.catalog, self.brief)
        self.assertTrue(any(item['path'] == 'functions.mcu' and item['code'] == 'UNSATISFIED_SELECTION'
                            for item in refusals), refusals)
        result = expand(self.catalog, self.graph, self.brief, bundle_commit='a' * 40)
        self.assertEqual(result['status'], 'REFUSED')
        self.assertTrue(any(item['path'] == 'mcu.requirements' and item['code'] == 'UNSATISFIED_SELECTION'
                            for item in result['refusals']), result['refusals'])

    def test_package_role_family_are_paired_and_role_is_typed(self):
        for fields in ({'package_family': 'BGA'}, {'package_role': 'mcu.32-bit'},
                       {'package_family': 'BGA', 'package_role': 'unregistered.role'}):
            with self.subTest(fields=fields):
                brief = copy.deepcopy(self.brief)
                next(f for f in brief['functions'] if f['id'] == 'mcu').update(fields)
                with self.assertRaises(ValueError):
                    assess_brief(self.catalog, brief)
                self.assertEqual(expand(self.catalog, self.graph, brief, bundle_commit='a' * 40)['status'], 'REFUSED')

    def test_refusal_queries_describe_selection_checks_and_verification(self):
        from pcbknowledge.v2.requirements import refusal
        for code, query in (('UNSATISFIED_SELECTION', 'Q1'), ('CHECK_FAILED', 'Q4'),
                            ('UNVERIFIED_RECORD', 'Q11'), ('UNKNOWN_INPUT', 'Q11')):
            with self.subTest(code=code):
                self.assertEqual(refusal(code, 'test', 'test')['queries'], [query])

    def test_edge_interface_unknown_and_duplicate_references_are_typed(self):
        for mutation in ('unknown', 'duplicate'):
            with self.subTest(mutation=mutation):
                brief = copy.deepcopy(self.brief)
                edges = brief['mechanical']['edge_interfaces']
                edges.append('missing_interface' if mutation == 'unknown' else edges[0])
                refusals = assess_brief(self.catalog, brief)
                self.assertTrue(any(item['code'] == 'INVALID_REFERENCE'
                                    and item['path'] == 'mechanical.edge_interfaces' for item in refusals), refusals)
                row = coverage_all(self.catalog, {'G1': brief})['briefs'][0]
                self.assertEqual(row['screening'], 'REFUSED')
                self.assertEqual(row['refusals'], refusals)

    def test_coverage_all_cli_reports_unknown_edge_label_refusal(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        from pcbknowledge.v2.cli import main
        brief = copy.deepcopy(self.brief)
        brief['mechanical']['edge_interfaces'].append('stale_uart_label')
        output = io.StringIO()
        with patch('pcbknowledge.v2.cli.design_inputs', return_value=(None, {'G1': brief})):
            with contextlib.redirect_stdout(output):
                main(['--repo', str(ROOT), 'v2', 'coverage', '--all', '--json'])
        row = json.loads(output.getvalue())['briefs'][0]
        self.assertEqual(row['screening'], 'REFUSED')
        self.assertTrue(any(item['code'] == 'INVALID_REFERENCE' and item['path'] == 'mechanical.edge_interfaces'
                            for item in row['refusals']))

    def test_additional_bad_edge_does_not_replace_negative_voltage_refusal(self):
        brief = copy.deepcopy(self.brief)
        brief['id'] = 'N1'
        brief['power']['sources'][0]['voltage']['value'] = 12
        brief['mechanical']['edge_interfaces'].append('old_interface_label')
        identities = {(item['code'], item['path']) for item in assess_brief(self.catalog, brief)}
        self.assertIn(('CHECK_FAILED', 'functions.usb_sink'), identities)
        self.assertIn(('INVALID_REFERENCE', 'mechanical.edge_interfaces'), identities)
