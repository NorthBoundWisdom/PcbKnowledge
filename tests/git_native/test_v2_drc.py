"""Native DRC wrapper isolation and fail-closed acceptance tests."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.v2.drc import REPORT_SCHEMA, run_drc


class DrcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.board = self.root / 'exported.kicad_pcb'
        self.files = [self.board, self.board.with_suffix('.kicad_pro'), self.board.with_suffix('.kicad_dru')]
        for file in self.files:
            file.write_text('synthetic original')
        self.output = self.root / 'build/drc.json'
        self.report = {'$schema': REPORT_SCHEMA, 'kicad_version': '9.0.2', 'violations': [],
                       'unconnected_items': [], 'schematic_parity': []}

    def fake_process(self, command, **kwargs):
        directory = Path(kwargs['cwd'])
        self.assertNotEqual(Path(command[-1]), self.board)
        self.assertEqual(Path(command[-1]).name, self.board.name)
        self.assertEqual(Path(command[-1]).read_text(), 'synthetic original')
        for file in self.files:
            self.assertEqual((directory / file.name).read_bytes(), file.read_bytes())
        for variable in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
            self.assertTrue(Path(kwargs['env'][variable]).is_relative_to(directory))
        self.assertNotIn('shell', kwargs)
        self.assertIn('--exit-code-violations', command)
        Path(command[command.index('--output') + 1]).write_text(json.dumps(self.report))
        return subprocess.CompletedProcess(command, 0, '', '')

    def invoke(self, layout=None):
        with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
            with patch('pcbknowledge.v2.drc.subprocess.run', side_effect=self.fake_process):
                return run_drc(self.board, self.output, root=self.root, layout_report=layout)

    def test_isolated_success_preserves_inputs_and_separates_a3_from_a4(self):
        result = self.invoke()
        self.assertEqual((result['status'], result['a4'], result['drc_status']), ('NOT_CHECKABLE', 'PASS', 'PASS'))
        self.assertEqual(self.invoke({'status': 'PASS'})['status'], 'PASS')
        self.assertEqual(self.invoke({'status': 'FAIL'})['status'], 'FAIL')
        self.assertEqual(self.invoke({'status': 'NOT_CHECKABLE'})['status'], 'NOT_CHECKABLE')
        self.assertEqual(json.loads(self.output.read_text())['status'], 'NOT_CHECKABLE')
        for file in self.files:
            self.assertEqual(file.read_text(), 'synthetic original')

    def test_absent_tool_is_not_run(self):
        with patch('pcbknowledge.v2.drc.shutil.which', return_value=None):
            result = run_drc(self.board, self.output, root=self.root, layout_report={'status': 'PASS'})
        self.assertEqual((result['status'], result['a4']), ('NOT_RUN', 'NOT_RUN'))

    def test_any_findings_fail_even_with_zero_exit_code(self):
        for key in ('violations', 'unconnected_items', 'schematic_parity'):
            with self.subTest(key=key):
                self.report[key] = [{'type': 'synthetic', 'severity': 'warning'}]
                self.assertEqual(self.invoke({'status': 'PASS'})['status'], 'FAIL')
                self.report[key] = []

    def test_nonzero_exit_timeout_or_malformed_report_cannot_pass(self):
        def nonzero(command, **kwargs):
            self.fake_process(command, **kwargs)
            return subprocess.CompletedProcess(command, 5, '', '')
        with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
            for effect in (nonzero, subprocess.TimeoutExpired('kicad-cli', 120)):
                with patch('pcbknowledge.v2.drc.subprocess.run', side_effect=effect):
                    result = run_drc(self.board, self.output, root=self.root, layout_report={'status': 'PASS'})
                    self.assertEqual(result['status'], 'FAIL')
        for malformed in ({}, {'$schema': 'unknown'}, {**self.report, 'violations': 'not a list'}):
            self.report = malformed
            self.assertEqual(self.invoke({'status': 'PASS'})['status'], 'FAIL')

    def test_paths_and_missing_sidecars_fail_before_execution(self):
        with patch('pcbknowledge.v2.drc.subprocess.run') as process:
            for output in (self.root / 'outside.json', self.root / 'build/../outside.json', self.board):
                with self.assertRaises(ValueError):
                    run_drc(self.board, output, root=self.root)
            self.files[-1].unlink()
            with self.assertRaises(ValueError):
                run_drc(self.board, self.output, root=self.root)
            process.assert_not_called()

    def test_symlink_output_and_input_are_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'build').mkdir()
        (self.root / 'build/link').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            run_drc(self.board, self.root / 'build/link/report.json', root=self.root)
        original = self.board.read_bytes()
        self.board.unlink()
        target = outside / 'board.kicad_pcb'
        target.write_bytes(original)
        self.board.symlink_to(target)
        with self.assertRaises(ValueError):
            run_drc(self.board, self.output, root=self.root)
        self.assertEqual(list(outside.iterdir()), [target])

    def test_missing_native_report_is_failure(self):
        with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
            with patch('pcbknowledge.v2.drc.subprocess.run', return_value=subprocess.CompletedProcess([], 0)):
                result = run_drc(self.board, self.output, root=self.root, layout_report={'status': 'PASS'})
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('Missing', result['reason'])

    def test_generated_local_library_is_copied_but_external_uri_is_rejected(self):
        library = self.root / 'pcbknowledge.pretty'
        library.mkdir()
        (library / 'synthetic.kicad_mod').write_text('(footprint "synthetic")')
        table = self.root / 'fp-lib-table'
        table.write_text('(fp_lib_table (lib (name "pcbknowledge") (type "KiCad") '
                         '(uri "${KIPRJMOD}/pcbknowledge.pretty")))')
        def check(command, **kwargs):
            copied = Path(kwargs['cwd']) / 'pcbknowledge.pretty/synthetic.kicad_mod'
            self.assertEqual(copied.read_text(), '(footprint "synthetic")')
            self.assertEqual((Path(kwargs['cwd']) / 'fp-lib-table').read_bytes(), table.read_bytes())
            return self.fake_process(command, **kwargs)
        with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
            with patch('pcbknowledge.v2.drc.subprocess.run', side_effect=check):
                result = run_drc(self.board, self.output, root=self.root, layout_report={'status': 'PASS'})
                self.assertEqual(result['status'], 'PASS')
        table.write_text('(fp_lib_table (lib (type "KiCad") (uri "/external/library")))')
        with self.assertRaises(ValueError):
            run_drc(self.board, self.output, root=self.root)

    def test_actual_layout_report_shape_integrates_without_false_pass(self):
        from pcbknowledge.v2.boardview import board_from_text
        from pcbknowledge.v2.layout import check_layout
        from tests.git_native.test_v2_layout import FixtureCatalog, board_text, intent
        graph_intent = intent()
        board = board_from_text(board_text())
        passing = check_layout(board, graph_intent, FixtureCatalog())
        self.assertEqual(passing['result'], 'PASS')
        self.assertEqual(self.invoke(passing)['status'], 'PASS')
        graph_intent['layout'][0]['max_distance']['value'] = 0.1
        failing = check_layout(board, graph_intent, FixtureCatalog())
        self.assertEqual(failing['result'], 'FAIL')
        self.assertEqual(self.invoke(failing)['status'], 'FAIL')
