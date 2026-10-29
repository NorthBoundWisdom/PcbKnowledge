"""CLI snapshot isolation, typed refusals and derived-output boundaries."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.git_native.workspace import initialize_workspace
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


if __name__ == '__main__':
    unittest.main()
