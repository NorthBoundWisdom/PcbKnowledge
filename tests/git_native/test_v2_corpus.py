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
        report = coverage_all(self.catalog, {'G1': self.brief}, [])
        self.assertEqual(report['briefs'][0]['screening'], 'ELIGIBLE')
        self.assertEqual(report['briefs'][0]['graph_readiness'], 'NOT_RUN')
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
        report = coverage_all(self.catalog, {'G1': self.brief}, [bad])
        row = report['briefs'][0]
        self.assertEqual(row['screening'], 'ELIGIBLE')
        self.assertEqual(row['graph_readiness'], 'REFUSED')
        self.assertTrue(row['graph_refusals'])
        self.assertIsNone(row['expected_refusal'])

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
                       {'package_family': 'BGA', 'package_role': 'unregistered.role'},
                       {'package_family': 'UNREGISTERED', 'package_role': 'mcu.32-bit'}):
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
                row = coverage_all(self.catalog, {'G1': brief}, [])['briefs'][0]
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
        with patch('pcbknowledge.v2.audit.require_audit'):
            with patch('pcbknowledge.v2.audit.design_inputs', return_value=([], {'G1': brief})):
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

    def test_integrated_briefs_keep_required_functions_and_typed_refusals(self):
        for name in ('g1v1', 'g1v2', 'n1', 'n2', 'n3'):
            brief = read_json((ROOT / f'evals/golden-designs/{name}.brief.json').read_bytes())
            with self.subTest(brief=name):
                self.catalog.structure(brief, 'design-brief.schema.json')
                self.assertTrue(all(row['status'] == 'NOT_RUN' for row in brief['acceptance']))
                self.assertLessEqual(set(brief['mechanical']['edge_interfaces']),
                                     {row['id'] for row in brief['interfaces']})
                supplies = brief['power']['sources'] + brief['power']['rails']
                self.assertEqual({row['function'] for row in supplies},
                                 {'power_input' if name == 'n1' else 'usb_sink', 'regulation'})
                expected = brief.get('expected_refusal')
                refusals = assess_brief(self.catalog, brief)
                if expected:
                    self.assertIn(expected['requirement'], {row['id'] for row in brief['functions']})
                    self.assertIn((expected['code'], 'functions.' + expected['requirement']),
                                  {(row['code'], row['path']) for row in refusals})
                else:
                    self.assertEqual(refusals, [])

    def test_expected_refusal_cannot_be_free_text_or_claim_acceptance(self):
        brief = read_json((ROOT / 'evals/golden-designs/n1.brief.json').read_bytes())
        for value in ('missing part', {'code': 'PASS', 'requirement': 'power_input'},
                      {'code': 'UNSATISFIED_SELECTION'},
                      {'code': 'CHECK_FAILED', 'requirement': 'power_input', 'status': 'PASS'}):
            changed = copy.deepcopy(brief)
            changed['expected_refusal'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.catalog.structure(changed, 'design-brief.schema.json')

    def test_unknown_expected_requirement_fails_audit_without_a_graph(self):
        from pcbknowledge.v2.audit import audit_catalog
        brief = read_json((ROOT / 'evals/golden-designs/n1.brief.json').read_bytes())
        brief['expected_refusal']['requirement'] = 'absent'
        with self.assertRaisesRegex(ValueError, 'required function'):
            audit_catalog(self.catalog, [], {'N1': brief})

    def test_current_variant_decisions_do_not_reuse_remote_decision_numbers(self):
        sensor = read_json((ROOT / 'evals/golden-designs/g1v1.brief.json').read_bytes())
        bridge = read_json((ROOT / 'evals/golden-designs/g1v2.brief.json').read_bytes())
        self.assertIn('D31', sensor['owner_decisions'])
        self.assertTrue({'D32', 'D33'} <= set(bridge['owner_decisions']))
        self.assertNotIn('power_monitor', {row['id'] for row in sensor['functions']})
        self.assertNotIn('monitor_scope', {row['id'] for row in sensor['constraints']})
        self.assertIn('sensor.temperature', {row['category'] for row in sensor['functions']})
        self.assertNotIn('uart_header', {row['id'] for row in bridge['interfaces']})
        self.assertIn('interface.usb-uart', {row['category'] for row in bridge['functions']})

    def test_negative_inputs_do_not_keep_incompatible_original_preferences(self):
        voltage = read_json((ROOT / 'evals/golden-designs/n1.brief.json').read_bytes())
        package = read_json((ROOT / 'evals/golden-designs/n3.brief.json').read_bytes())
        self.assertEqual(voltage['power']['sources'][0]['voltage']['value'], 12)
        self.assertNotIn('D1', package['owner_decisions'])
        mcu = next(row for row in package['functions'] if row['id'] == 'mcu')
        self.assertEqual(mcu['part_preferences'], [])
        self.assertEqual((mcu['package_family'], mcu['package_role']), ('BGA', 'mcu.32-bit'))

    def test_package_vocabulary_is_validated_without_selected_graphs(self):
        from pcbknowledge.v2.audit import audit_catalog
        for family, role in (('UNREGISTERED', 'mcu.32-bit'), ('BGA', 'unregistered.role')):
            brief = copy.deepcopy(self.brief)
            next(row for row in brief['functions'] if row['id'] == 'mcu').update(
                package_family=family, package_role=role)
            self.catalog.structure(brief, 'design-brief.schema.json')
            with self.subTest(family=family, role=role), self.assertRaises(ValueError):
                audit_catalog(self.catalog, [], {'G1': brief})

    def test_empty_package_selector_names_fail_schema(self):
        for family, role in (('', 'mcu.32-bit'), ('BGA', '')):
            brief = copy.deepcopy(self.brief)
            next(row for row in brief['functions'] if row['id'] == 'mcu').update(
                package_family=family, package_role=role)
            with self.subTest(family=family, role=role), self.assertRaises(ValueError):
                self.catalog.structure(brief, 'design-brief.schema.json')
