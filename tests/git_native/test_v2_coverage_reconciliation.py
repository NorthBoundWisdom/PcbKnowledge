"""Preserve remote corpus diagnostics while adding feasibility screening."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pcbknowledge.v2.audit import audit_catalog
from pcbknowledge.v2.cli import main, coverage_lines
from pcbknowledge.v2.coverage import coverage_all

ROOT = Path(__file__).resolve().parents[2]


class CoverageReconciliationTests(unittest.TestCase):
    def test_audit_validates_briefs_without_graphs(self):
        calls = []
        catalog = SimpleNamespace(structure=lambda *args: calls.append(args), records={})
        brief = {'functions': [{'id': 'input'}]}
        self.assertEqual(audit_catalog(catalog, [], {'N1': brief})['status'], 'VALID')
        self.assertEqual(calls, [(brief, 'design-brief.schema.json')])

    def test_audit_rejects_graph_without_brief(self):
        catalog = SimpleNamespace(structure=lambda *_: None, records={})
        with self.assertRaisesRegex(ValueError, 'missing brief'):
            audit_catalog(catalog, [{'brief': 'MISSING'}], {})

    def test_expected_refusal_must_bind_existing_function_without_graph(self):
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

    @patch('pcbknowledge.v2.requirements.assess_brief', return_value=[])
    @patch('pcbknowledge.v2.expansion.expand')
    @patch('pcbknowledge.v2.coverage.coverage', return_value={'ready': 1, 'total': 1})
    def test_all_preserves_failed_attempt_and_not_run(self, _coverage, expand, _screen):
        refusal = {'code': 'CHECK_FAILED', 'path': 'power', 'reason': 'Synthetic overvoltage'}
        expand.side_effect = [{'status': 'EXPANDED', 'refusals': []},
                              {'status': 'REFUSED', 'refusals': [refusal]}]
        graphs = [{'brief': 'G1', 'id': 'first'}, {'brief': 'G1', 'id': 'second'}]
        expectation = {'code': 'UNSATISFIED_SELECTION', 'requirement': 'input'}
        briefs = {'G1': {}, 'N1': {'functions': [{'id': 'input'}], 'expected_refusal': expectation}}
        report = coverage_all(SimpleNamespace(), briefs, graphs)
        first, missing = report['briefs']
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(first['status'], 'INCOMPLETE')
        self.assertEqual(len(first['graphs']), 2)
        self.assertEqual(first['graphs'][1]['refusals'], [refusal])
        self.assertEqual(first['graph_refusals'], [refusal])
        self.assertEqual((first['blocks_ready'], first['blocks_total']), (2, 2))
        self.assertEqual(missing['status'], 'NOT_RUN')
        self.assertEqual(missing['graphs'], [])
        self.assertEqual(missing['expected_refusal'], expectation)
        self.assertNotIn('a2', missing)
        self.assertIn('blocks ready=NOT_RUN', coverage_lines(report))

    @patch('pcbknowledge.v2.requirements.assess_brief')
    @patch('pcbknowledge.v2.expansion.expand', return_value={'status': 'EXPANDED', 'refusals': []})
    @patch('pcbknowledge.v2.coverage.coverage', return_value={'ready': 1, 'total': 1})
    def test_graph_success_does_not_hide_failed_screening(self, _coverage, _expand, screen):
        refusal = {'code': 'CHECK_FAILED', 'path': 'functions.input', 'reason': 'Budget'}
        screen.return_value = [refusal]
        report = coverage_all(SimpleNamespace(), {'G1': {}}, [{'brief': 'G1', 'id': 'g'}])
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertEqual(report['briefs'][0]['refusals'], [refusal])
        self.assertEqual(report['briefs'][0]['graph_readiness'], 'EXPANDED')

    @patch('pcbknowledge.v2.requirements.assess_brief', return_value=[])
    @patch('pcbknowledge.v2.coverage.coverage', side_effect=ValueError('Invalid graph schema'))
    def test_invalid_graph_is_retained_as_typed_failure(self, _coverage, _screen):
        report = coverage_all(SimpleNamespace(), {'G1': {}}, [{'brief': 'G1', 'id': 'bad', 'instances': []}])
        row = report['briefs'][0]
        self.assertEqual(row['status'], 'INCOMPLETE')
        self.assertEqual(row['graphs'][0]['graph'], 'bad')
        self.assertEqual(row['graphs'][0]['refusals'][0]['code'], 'INVALID_REFERENCE')
        self.assertEqual(row['blocks_ready'], 0)

    @patch('pcbknowledge.v2.cli.validate_workspace', return_value=SimpleNamespace(root=ROOT))
    @patch('pcbknowledge.v2.cli.dispatch')
    def test_cli_default_json_lines_and_aggregate_both_nonzero_when_incomplete(self, dispatch, _workspace):
        rows = [{'brief': 'G1', 'status': 'READY'}, {'brief': 'N1', 'status': 'NOT_RUN'}]
        report = {'status': 'INCOMPLETE', 'briefs': rows}
        dispatch.return_value = report
        for options, expected in (([], rows), (['--json'], [report])):
            with self.subTest(options=options):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = main(['--repo', str(ROOT), 'v2', 'coverage', '--all', *options])
                self.assertEqual(status, 2)
                self.assertEqual([json.loads(line) for line in output.getvalue().splitlines()], expected)


if __name__ == '__main__':
    unittest.main()
