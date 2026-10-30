"""Corpus input contracts and honest coverage for missing or refused graphs."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pcbknowledge.v2.audit import audit_catalog
from pcbknowledge.v2.cli import main
from pcbknowledge.v2.coverage import coverage_all
from tests.git_native.test_v2_record_contracts import validate

ROOT = Path(__file__).resolve().parents[2]


class CorpusTests(unittest.TestCase):
    def test_variant_requirements_are_machine_distinguishable(self):
        def read(name):
            return json.loads((ROOT / f'evals/golden-designs/{name}.brief.json').read_text())
        sensor = read('g1v1')
        self.assertNotIn('power_monitor', {row['id'] for row in sensor['functions']})
        self.assertNotIn('monitor_scope', {row['id'] for row in sensor['constraints']})
        self.assertIn('sensor.temperature', {row['category'] for row in sensor['functions']})
        bridge = read('g1v2')
        self.assertNotIn('uart_header', {row['id'] for row in bridge['interfaces']})
        self.assertIn('interface.usb_uart', {row['category'] for row in bridge['functions']})
        for name, category in [('n1', 'power.input.dc'), ('n2', 'communication.wifi'),
                               ('n3', 'digital.mcu.bga')]:
            brief = read(name)
            function = next(row for row in brief['functions']
                            if row['id'] == brief['expected_refusal']['requirement'])
            self.assertEqual(function['category'], category)
            self.assertEqual({row['function'] for row in brief['power']['sources']}
                             | {row['function'] for row in brief['power']['rails']},
                             {'dc_input' if name == 'n1' else 'usb_sink', 'regulation'})
            self.assertTrue(set(brief['mechanical']['edge_interfaces'])
                            <= {row['id'] for row in brief['interfaces']})
        self.assertEqual(read('n1')['power']['sources'][0]['voltage']['value'], 12)

    def test_all_corpus_briefs_are_typed_and_unexecuted(self):
        for name in ('g1v1', 'g1v2', 'n1', 'n2', 'n3'):
            with self.subTest(name=name):
                brief = json.loads((ROOT / f'evals/golden-designs/{name}.brief.json').read_text())
                validate(brief, 'design-brief.schema.json')
                self.assertEqual(brief['id'], name.upper())
                self.assertTrue(all(row['status'] == 'NOT_RUN' for row in brief['acceptance']))
                if name.startswith('n'):
                    self.assertEqual(brief['expected_refusal']['code'], 'UNSATISFIED_SELECTION')
                    self.assertIn(brief['expected_refusal']['requirement'],
                                  {row['id'] for row in brief['functions']})

    def test_expected_refusal_is_not_free_text_or_an_acceptance_receipt(self):
        brief = json.loads((ROOT / 'evals/golden-designs/n1.brief.json').read_text())
        for value in ('missing part', {'code': 'PASS', 'requirement': 'input'},
                      {'code': 'UNSATISFIED_SELECTION'},
                      {'code': 'UNSATISFIED_SELECTION', 'requirement': 'input', 'status': 'PASS'}):
            changed = copy.deepcopy(brief)
            changed['expected_refusal'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(changed, 'design-brief.schema.json')

    def test_unknown_expected_requirement_fails_audit_without_a_graph(self):
        catalog = SimpleNamespace(structure=lambda *_: None, records={})
        brief = {'functions': [{'id': 'input'}],
                 'expected_refusal': {'code': 'UNSATISFIED_SELECTION', 'requirement': 'absent'}}
        with self.assertRaisesRegex(ValueError, 'required function'):
            audit_catalog(catalog, [], {'N1': brief})

    @patch('pcbknowledge.v2.audit.require_audit')
    @patch('pcbknowledge.v2.audit.design_inputs', return_value=([{'brief': 'MISSING'}], {'G1': {}}))
    def test_all_rejects_graphs_without_briefs(self, _inputs, _audit):
        with self.assertRaisesRegex(ValueError, 'missing brief'):
            coverage_all(SimpleNamespace(root=ROOT))

    @patch('pcbknowledge.v2.audit.require_audit')
    @patch('pcbknowledge.v2.audit.design_inputs')
    @patch('pcbknowledge.v2.expansion.expand')
    @patch('pcbknowledge.v2.coverage.coverage')
    def test_all_does_not_hide_failed_attempts_or_promote_missing_graphs(self, ready, expand, inputs, _audit):
        ready.return_value = {'ready': 1, 'total': 1}
        refusal = {'code': 'CHECK_FAILED', 'path': 'power', 'reason': 'Synthetic overvoltage'}
        expand.side_effect = [{'status': 'EXPANDED', 'refusals': []},
                              {'status': 'REFUSED', 'refusals': [refusal]}]
        inputs.return_value = ([{'brief': 'G1', 'id': 'first'}, {'brief': 'G1', 'id': 'second'}],
                               {'G1': {}, 'N1': {'expected_refusal': {'code': 'UNSATISFIED_SELECTION'}}})
        report = coverage_all(SimpleNamespace(root=ROOT))
        self.assertEqual(report['status'], 'INCOMPLETE')
        first, missing = report['briefs']
        self.assertEqual(first['status'], 'INCOMPLETE')
        self.assertEqual(len(first['graphs']), 2)
        self.assertEqual(first['graphs'][1]['refusals'], [refusal])
        self.assertEqual(missing['status'], 'NOT_RUN')
        self.assertEqual(missing['graphs'], [])
        self.assertNotIn('a2', missing)

    @patch('pcbknowledge.v2.cli.validate_workspace', return_value=SimpleNamespace(root=ROOT))
    @patch('pcbknowledge.v2.cli.dispatch')
    def test_cli_emits_one_json_line_per_brief_and_nonzero_for_incomplete(self, dispatch, _workspace):
        rows = [{'brief': 'G1', 'status': 'READY'}, {'brief': 'N1', 'status': 'NOT_RUN'}]
        dispatch.return_value = {'status': 'INCOMPLETE', 'briefs': rows}
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(['--repo', str(ROOT), 'v2', 'coverage', '--all'])
        self.assertEqual(status, 2)
        self.assertEqual([json.loads(line) for line in output.getvalue().splitlines()], rows)


if __name__ == '__main__':
    unittest.main()
