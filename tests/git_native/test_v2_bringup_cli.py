"""Bring-up CLI consumes a replay-checked immutable G2 bundle."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from pcbknowledge.v2.bundle import build_bundle
from pcbknowledge.v2.cli import main
from pcbknowledge.v2.expansion import expand_bundle

ROOT = Path(__file__).resolve().parents[2]


class BringupCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name) / 'workspace'
        cls.root.mkdir()
        for folder in ('knowledge', 'schemas', 'evals'):
            shutil.copytree(ROOT / folder, cls.root / folder)
        for name in ('.gitignore', 'pcbknowledge.workspace.json'):
            shutil.copyfile(ROOT / name, cls.root / name)
        for args in (('init',), ('config', 'user.name', 'Synthetic'),
                     ('config', 'user.email', 'synthetic@example.invalid'),
                     ('add', '.'), ('commit', '-m', 'Synthetic bring-up CLI fixture')):
            subprocess.run(['git', '-C', str(cls.root), *args], check=True, capture_output=True)
        cls.bundle = build_bundle(cls.root)
        cls.graph = cls.root / 'evals/golden-designs/g2.block-graph.json'
        cls.intent = cls.root / 'build/intent.json'
        graph = json.loads(cls.graph.read_text())
        cls.intent.write_text(json.dumps(expand_bundle(cls.bundle, graph)))

    def run_cli(self, *extra, intent=None):
        output = io.StringIO()
        args = ['--repo', str(self.root), 'bringup', '--bundle', str(self.bundle),
                '--graph', str(self.graph), '--intent', str(intent or self.intent), *map(str, extra)]
        with redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_real_snapshot_json_and_markdown_complete_but_not_observed(self):
        code, report = self.run_cli('--markdown', 'build/bringup-checklist.md')
        self.assertEqual(code, 0, report)
        self.assertEqual(report['range_coverage'], 'COMPLETE')
        self.assertEqual(report['a6'], 'NOT_RUN')
        self.assertTrue(all(row['result'] == 'NOT_RUN' for row in report['rails']))
        self.assertEqual(json.loads((self.root / 'build/bringup-report.json').read_text()), report)
        text = (self.root / 'build/bringup-checklist.md').read_text()
        self.assertIn('WAVEFORM_PROTOCOL', text)
        self.assertIn('not measured compliance', text)
        self.assertNotIn('- [x]', text)

    def test_mismatched_intent_writes_neither_output(self):
        document = json.loads(self.intent.read_text())
        document['bundle_commit'] = 'f' * 40
        intent = self.root / 'build/mismatched.json'
        intent.write_text(json.dumps(document))
        code, report = self.run_cli('--output', 'build/rejected.json',
                                    '--markdown', 'build/rejected.md', intent=intent)
        self.assertEqual(code, 2)
        self.assertIn('deterministic', report['message'])
        self.assertFalse((self.root / 'build/rejected.json').exists())
        self.assertFalse((self.root / 'build/rejected.md').exists())

    def test_unsafe_alias_and_input_overwrite_destinations_rejected(self):
        before = self.intent.read_bytes()
        for args in (('--output', 'knowledge/report.json'), ('--markdown', '../outside.md'),
                     ('--output', 'build/shared', '--markdown', 'build/shared'),
                     ('--output', str(self.intent)), ('--markdown', str(self.intent))):
            with self.subTest(args=args):
                code, report = self.run_cli(*args)
                self.assertEqual(code, 2, report)
        self.assertEqual(self.intent.read_bytes(), before)
        self.assertFalse((self.root / 'knowledge/report.json').exists())
        self.assertFalse((self.root.parent / 'outside.md').exists())

    def test_hardlinked_outputs_cannot_overwrite_inputs_or_each_other(self):
        before = self.intent.read_bytes()
        alias = self.root / 'build/aliased-input.json'
        os.link(self.intent, alias)
        for flag in ('--output', '--markdown'):
            code, report = self.run_cli(flag, str(alias))
            self.assertEqual(code, 2, report)
            self.assertEqual(self.intent.read_bytes(), before)
        first, second = self.root / 'build/pair.json', self.root / 'build/pair.md'
        first.write_text('Retain both destinations')
        os.link(first, second)
        code, report = self.run_cli('--output', str(first), '--markdown', str(second))
        self.assertEqual(code, 2, report)
        self.assertEqual(first.read_text(), 'Retain both destinations')
        self.assertEqual(second.read_text(), 'Retain both destinations')
