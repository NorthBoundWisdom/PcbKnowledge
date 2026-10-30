"""CLI snapshot isolation, typed refusals and derived-output boundaries."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.workspace import initialize_workspace
from pcbknowledge.v2.cli import main

ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / 'workspace'
        initialize_workspace(self.root, schema_source_root=ROOT, init_git=True)
        for args in [('config', 'user.name', 'Synthetic'),
                     ('config', 'user.email', 'synthetic@example.invalid'),
                     ('add', '.'), ('commit', '-m', 'Synthetic authority')]:
            subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)

    def run_cli(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(['--repo', str(self.root), *map(str, args)])
        return status, json.loads(output.getvalue())

    def bundle(self):
        code, result = self.run_cli('bundle', 'build')
        self.assertEqual(code, 0, result)
        path = Path(result['bundle'])
        self.assertEqual(path.parent, self.root / 'build/bundle')
        self.assertEqual(path.stem, result['commit'])
        return path

    def document(self, name, value):
        path = self.root / 'build' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def test_bundle_queries_use_snapshot_not_dirty_catalog(self):
        bundle = self.bundle()
        (self.root / 'knowledge/parts/invalid.json').write_text('{}')
        code, result = self.run_cli('part', 'search', '--bundle', bundle)
        self.assertEqual((code, result), (0, []))
        code, result = self.run_cli('registry', 'show', 'registry:roles', '--bundle', bundle)
        self.assertEqual(code, 0)
        self.assertEqual(result['id'], 'registry:roles')
        code, result = self.run_cli('v2', 'validate')
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'ERROR')

    def test_bundle_requires_clean_committed_authority(self):
        (self.root / 'dirty.txt').write_text('synthetic dirty state')
        code, result = self.run_cli('bundle', 'build')
        self.assertEqual(code, 2)
        self.assertIn('clean committed', result['message'])
        self.assertFalse((self.root / 'build/bundle').exists())

    def test_build_output_escape_and_symlink_rejected(self):
        for output in ('knowledge/derived', '../outside', 'build/../../outside', 'build'):
            with self.subTest(output=output):
                code, result = self.run_cli('bundle', 'build', '--output', output)
                self.assertEqual(code, 2)
                self.assertIn('below build', result['message'])
        outside = Path(self.temporary.name).resolve() / 'outside'
        outside.mkdir()
        (self.root / 'build').symlink_to(outside, target_is_directory=True)
        code, result = self.run_cli('bundle', 'build')
        self.assertEqual(code, 2)
        self.assertIn('symlink', result['message'])
        self.assertEqual(list(outside.iterdir()), [])

    def test_expand_emits_typed_refusal_and_preserves_it_in_build(self):
        graph = self.document('graph.json', {'id': 'synthetic'})
        refusal = {'status': 'REFUSED', 'refusals': [{'code': 'MISSING_PART'}]}
        with patch('pcbknowledge.v2.cli.expand_bundle', return_value=refusal) as expand:
            code, result = self.run_cli('expand', graph, '--bundle', 'snapshot.json',
                                        '--output', 'build/refused.json')
            self.assertEqual((code, result), (2, refusal))
            expand.assert_called_once_with(Path('snapshot.json'), {'id': 'synthetic'})
        self.assertEqual(json.loads((self.root / 'build/refused.json').read_text()), refusal)
        self.assertNotIn(b'\r', (self.root / 'build/refused.json').read_bytes())
        with patch('pcbknowledge.v2.cli.expand_bundle') as expand:
            code, result = self.run_cli('expand', graph, '--bundle', 'snapshot.json',
                                        '--output', 'knowledge/not-derived.json')
            self.assertEqual(code, 2)
            expand.assert_not_called()

    def test_nested_symlink_escape_and_invalid_json_write_nothing(self):
        outside = Path(self.temporary.name).resolve() / 'outside'
        outside.mkdir()
        (self.root / 'build').mkdir()
        (self.root / 'build/link').symlink_to(outside, target_is_directory=True)
        graph = self.document('bad.json', {'id': 'synthetic'})
        with patch('pcbknowledge.v2.cli.expand_bundle') as expand:
            code, _ = self.run_cli('expand', graph, '--bundle', 'snapshot.json',
                                   '--output', 'build/link/intent.json')
            self.assertEqual(code, 2)
            expand.assert_not_called()
        graph.write_text('{"id":"a","id":"b"}')
        code, result = self.run_cli('expand', graph, '--bundle', 'snapshot.json',
                                    '--output', 'build/intent.json')
        self.assertEqual(code, 2)
        self.assertIn('Duplicate JSON key', result['message'])
        self.assertFalse((self.root / 'build/intent.json').exists())

    def test_coverage_snapshot_and_export_replay_dispatch(self):
        bundle = self.bundle()
        graph = self.document('graph.json', {'id': 'synthetic'})
        intent = self.document('intent.json', {'status': 'EXPANDED'})
        with patch('pcbknowledge.v2.cli.coverage', return_value={'status': 'INCOMPLETE'}) as check:
            code, result = self.run_cli('v2', 'coverage', graph, '--bundle', bundle)
            self.assertEqual((code, result['status']), (2, 'INCOMPLETE'))
            self.assertEqual(check.call_args.args[1], {'id': 'synthetic'})
        with patch('pcbknowledge.v2.cli.export_design', return_value=self.root / 'build/result') as export:
            code, result = self.run_cli('export', '--bundle', bundle, '--graph', graph,
                                        '--intent', intent, '--output', 'build/result')
            self.assertEqual((code, result['status']), (0, 'EXPORTED'))
            values = export.call_args.args
            self.assertEqual(values[0], {'status': 'EXPANDED'})
            self.assertEqual(values[2], {'id': 'synthetic'})
            self.assertEqual(values[3], self.root / 'build/result')
        with patch('pcbknowledge.v2.cli.export_design', side_effect=ValueError('Replay mismatch')):
            code, result = self.run_cli('export', '--bundle', bundle, '--graph', graph, '--intent', intent)
            self.assertEqual(code, 2)
            self.assertIn('Replay mismatch', result['message'])
        self.assertFalse((self.root / 'build/design').exists())

    def test_audit_returns_orphans_and_validate_requires_audit(self):
        invalid = {'status': 'INVALID', 'unreachable': ['part:unused']}
        with patch('pcbknowledge.v2.cli.audit_catalog', return_value=invalid) as audit:
            code, result = self.run_cli('v2', 'audit')
            self.assertEqual((code, result), (2, invalid))
            audit.assert_called_once()
        with patch('pcbknowledge.v2.cli.require_audit', side_effect=ValueError('Unreachable part:unused')):
            code, result = self.run_cli('v2', 'validate')
            self.assertEqual(code, 2)
            self.assertIn('Unreachable', result['message'])
        code, result = self.run_cli('v2', 'audit')
        self.assertEqual((code, result['status'], result['unreachable']), (0, 'VALID', []))
        code, result = self.run_cli('v2', 'validate')
        self.assertEqual((code, result['status']), (0, 'VALID'))
        self.assertEqual(result['audit']['unreachable'], [])

    def test_evidence_fetch_dispatch_and_nonzero_failure_results(self):
        for status, expected in (('MATCH', 0), ('DIFFERENT_BYTES', 2), ('FAILED', 2)):
            payload = {'status': status, 'results': []}
            with self.subTest(status=status):
                with patch('pcbknowledge.v2.cli.fetch_evidence', return_value=payload) as fetch:
                    code, result = self.run_cli('evidence', 'fetch', '--source', 'source:synthetic')
                    self.assertEqual((code, result), (expected, payload))
                    self.assertEqual(fetch.call_args.args[1], 'source:synthetic')
        with patch('pcbknowledge.v2.cli.fetch_evidence', return_value={'status': 'MATCH'}) as fetch:
            self.assertEqual(self.run_cli('evidence', 'fetch')[0], 0)
            self.assertIsNone(fetch.call_args.args[1])

    def test_evidence_add_dispatch_and_file_error(self):
        file = self.root / 'manual.pdf'
        with patch('pcbknowledge.v2.cli.add_evidence', return_value={'status': 'MATCH'}) as add:
            code, result = self.run_cli('evidence', 'add', file)
            self.assertEqual((code, result['status']), (0, 'MATCH'))
            self.assertEqual(add.call_args.args[1], file)
        code, result = self.run_cli('evidence', 'add', file)
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'ERROR')

    def test_layout_export_and_check_require_snapshot_replay(self):
        bundle = self.bundle()
        graph = self.document('graph.json', {'id': 'synthetic'})
        intent = self.document('intent.json', {'status': 'EXPANDED'})
        board = self.root / 'build/board.kicad_pcb'
        with patch('pcbknowledge.v2.cli.export_handoff', return_value=self.root / 'build/handoff') as export:
            code, result = self.run_cli('layout', 'export', '--bundle', bundle, '--graph', graph, '--intent', intent)
            self.assertEqual((code, result['status']), (0, 'EXPORTED'))
            self.assertEqual(export.call_args.args[0], {'status': 'EXPANDED'})
        report = {'result': 'NOT_CHECKABLE', 'checks': []}
        with patch('pcbknowledge.v2.cli.validate_expansion') as replay:
            with patch('pcbknowledge.v2.cli.check_board', return_value=report) as check:
                code, result = self.run_cli('layout', 'check', intent, board, '--bundle', bundle, '--graph', graph)
                self.assertEqual((code, result['status']), (2, 'NOT_CHECKABLE'))
                replay.assert_called_once()
                check.assert_called_once()
        with patch('pcbknowledge.v2.cli.validate_expansion', side_effect=ValueError('Replay mismatch')):
            with patch('pcbknowledge.v2.cli.check_board') as check:
                code, result = self.run_cli('layout', 'check', intent, board, '--bundle', bundle, '--graph', graph)
                self.assertEqual(code, 2)
                check.assert_not_called()

    def test_drc_context_all_or_none_and_missing_layout_not_accepted(self):
        board = self.root / 'build/board.kicad_pcb'
        with patch('pcbknowledge.v2.cli.run_drc', return_value={'status': 'NOT_CHECKABLE', 'a4': 'PASS'}) as drc:
            code, result = self.run_cli('drc', board)
            self.assertEqual((code, result['status']), (2, 'NOT_CHECKABLE'))
            self.assertIsNone(drc.call_args.kwargs['layout_report'])
        with patch('pcbknowledge.v2.cli.run_drc') as drc:
            code, result = self.run_cli('drc', board, '--intent', 'intent.json')
            self.assertEqual(code, 2)
            self.assertIn('together', result['message'])
            drc.assert_not_called()
        with patch('pcbknowledge.v2.cli.run_drc', return_value={'status': 'NOT_RUN'}):
            self.assertEqual(self.run_cli('drc', board)[0], 2)

    def test_coverage_all_and_graph_mode_are_exclusive(self):
        with patch('pcbknowledge.v2.cli.coverage_all', return_value={'briefs': []}) as coverage:
            self.assertEqual(self.run_cli('v2', 'coverage', '--all', '--json')[0], 0)
            coverage.assert_called_once()
        for args in (('v2', 'coverage'), ('v2', 'coverage', 'graph.json', '--all')):
            self.assertEqual(self.run_cli(*args)[0], 2)

    def test_coverage_all_defaults_to_one_line_per_brief_and_retains_json(self):
        rows = [
            {'brief': 'G1', 'blocks_ready': 2, 'blocks_total': 3, 'screening': 'ELIGIBLE',
             'graph_readiness': 'REFUSED', 'refusals': [],
             'graph_refusals': [{'code': 'MISSING_PART', 'path': 'instances.u'}]},
            {'brief': 'N1', 'screening': 'REFUSED', 'graph_readiness': 'NOT_PROVIDED',
             'refusals': [{'code': 'CHECK_FAILED', 'path': 'power'}], 'graph_refusals': []},
        ]
        payload = {'briefs': rows}
        with patch('pcbknowledge.v2.cli.corpus_coverage', return_value=payload):
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['--repo', str(self.root), 'v2', 'coverage', '--all'])
            self.assertEqual(code, 0)
            self.assertEqual(output.getvalue().splitlines(), [
                'G1: blocks ready=2/3; screening=ELIGIBLE; graph=REFUSED; '
                'refusals=MISSING_PART@instances.u',
                'N1: blocks ready=NOT_PROVIDED; screening=REFUSED; graph=NOT_PROVIDED; '
                'refusals=CHECK_FAILED@power',
            ])
            self.assertEqual(self.run_cli('v2', 'coverage', '--all', '--json'), (0, payload))

    def test_corpus_cli_hashes_actual_bundle_and_preserves_legacy_mode(self):
        import hashlib
        bundle = self.bundle()
        attempt = self.document('attempt.json', {'receipt': {}})
        reference = self.document('reference.json', {'id': 'reference'})
        skill = self.root / 'skill.md'
        skill.write_bytes(b'Exact skill\r\n')
        expected = self.document('expected.json', {'code': 'CHECK_FAILED', 'path': 'functions.usb_sink'})
        with patch('pcbknowledge.v2.synthesis.evaluate_corpus', return_value={'status': 'PASS'}) as evaluator:
            code, _ = self.run_cli('eval-synthesis', '--bundle', bundle, '--brief', 'N1', '--attempt', attempt,
                                   '--skill', skill, '--orchestrator', 'agent:coordinator',
                                   '--expected-refusal', expected)
            self.assertEqual(code, 0)
            self.assertEqual(evaluator.call_args.kwargs['bundle_sha256'], hashlib.sha256(bundle.read_bytes()).hexdigest())
            self.assertEqual(evaluator.call_args.kwargs['skill_text'], 'Exact skill\r\n')
        with patch('pcbknowledge.v2.synthesis.evaluate', return_value={'status': 'PASS'}) as legacy:
            self.assertEqual(self.run_cli('eval-synthesis', '--bundle', bundle, '--reference', reference,
                                          '--attempt', attempt)[0], 0)
            legacy.assert_called_once()
        self.assertEqual(self.run_cli('eval-synthesis', '--bundle', bundle, '--brief', 'N1', '--attempt', attempt)[0], 2)


if __name__ == '__main__':
    unittest.main()
