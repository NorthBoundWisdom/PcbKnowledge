"""Native DRC wrapper isolation and fail-closed acceptance tests."""
import copy
import hashlib
import os
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.v2.drc import REPORT_SCHEMA, run_drc
from pcbknowledge.v2.drc_report_validation import validate_drc_report
from pcbknowledge.v2.schema import ContractSchemas


class DrcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.board = self.root / 'exported.kicad_pcb'
        self.files = [self.board, self.board.with_suffix('.kicad_pro'), self.board.with_suffix('.kicad_dru')]
        for file in self.files:
            file.write_text('synthetic original')
        from tests.git_native.test_v2_layout import board_text
        self.board.write_text(board_text())
        self.originals = {file: file.read_bytes() for file in self.files}
        self.output = self.root / 'build/drc.json'
        self.report = {'$schema': REPORT_SCHEMA, 'kicad_version': '9.0.2', 'violations': [],
                       'unconnected_items': [], 'schematic_parity': []}

    def fake_process(self, command, **kwargs):
        directory = Path(kwargs['cwd'])
        self.assertNotEqual(Path(command[-1]), self.board)
        self.assertEqual(Path(command[-1]).name, self.board.name)
        self.assertEqual(Path(command[-1]).read_bytes(), self.board.read_bytes())
        for file in self.files:
            self.assertEqual((directory / file.name).read_bytes(), file.read_bytes())
        for variable in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
            self.assertTrue(Path(kwargs['env'][variable]).is_relative_to(directory))
        self.assertNotIn('shell', kwargs)
        self.assertIn('--exit-code-violations', command)
        Path(command[command.index('--output') + 1]).write_text(json.dumps(self.report))
        return subprocess.CompletedProcess(command, 0, '', '')

    def layout(self, state='PASS'):
        from pcbknowledge.v2.boardview import board_from_text
        from pcbknowledge.v2.layout import check_layout
        from tests.git_native.test_v2_layout import FixtureCatalog, intent
        graph_intent = intent()
        board = board_from_text(self.board.read_text())
        if state == 'FAIL':
            graph_intent['layout'][0]['max_distance']['value'] = 0.1
        elif state == 'NOT_CHECKABLE':
            board['unsupported'].append('Synthetic unknown geometry')
        report = check_layout(board, graph_intent, FixtureCatalog())
        report['constraints'] = copy.deepcopy(graph_intent['layout'])
        report['status'] = report['result']
        report['identity'] = {'bundle_commit': 'a' * 40, 'block_graph_sha256': 'b' * 64,
                              'intent_sha256': 'c' * 64,
                              'board_sha256': hashlib.sha256(self.board.read_bytes()).hexdigest()}
        return report

    def invoke(self, layout=None):
        with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
            with patch('pcbknowledge.v2.drc.subprocess.run', side_effect=self.fake_process):
                return run_drc(self.board, self.output, root=self.root, layout_report=layout)

    def test_isolated_success_preserves_inputs_and_separates_a3_from_a4(self):
        result = self.invoke()
        self.assertEqual((result['status'], result['a4'], result['drc_status']), ('NOT_CHECKABLE', 'PASS', 'PASS'))
        self.assertEqual(self.invoke(self.layout('PASS'))['status'], 'PASS')
        self.assertEqual(self.invoke(self.layout('FAIL'))['status'], 'FAIL')
        self.assertEqual(self.invoke(self.layout('NOT_CHECKABLE'))['status'], 'NOT_CHECKABLE')
        self.assertEqual(json.loads(self.output.read_text())['status'], 'NOT_CHECKABLE')
        for file in self.files:
            self.assertEqual(file.read_bytes(), self.originals[file])

    def test_absent_tool_is_not_run(self):
        with patch('pcbknowledge.v2.drc.shutil.which', return_value=None):
            result = run_drc(self.board, self.output, root=self.root, layout_report=self.layout('PASS'))
        self.assertEqual((result['status'], result['a4']), ('NOT_RUN', 'NOT_RUN'))

    def test_any_findings_fail_even_with_zero_exit_code(self):
        for key in ('violations', 'unconnected_items', 'schematic_parity'):
            with self.subTest(key=key):
                self.report[key] = [{'type': 'synthetic', 'severity': 'warning'}]
                self.assertEqual(self.invoke(self.layout('PASS'))['status'], 'FAIL')
                self.report[key] = []

    def test_nonzero_exit_timeout_or_malformed_report_cannot_pass(self):
        def nonzero(command, **kwargs):
            self.fake_process(command, **kwargs)
            return subprocess.CompletedProcess(command, 5, '', '')
        with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
            for effect in (nonzero, subprocess.TimeoutExpired('kicad-cli', 120)):
                with patch('pcbknowledge.v2.drc.subprocess.run', side_effect=effect):
                    result = run_drc(self.board, self.output, root=self.root, layout_report=self.layout('PASS'))
                    self.assertEqual(result['status'], 'FAIL')
        for malformed in ({}, {'$schema': 'unknown'}, {**self.report, 'violations': 'not a list'}):
            self.report = malformed
            self.assertEqual(self.invoke(self.layout('PASS'))['status'], 'FAIL')

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
                result = run_drc(self.board, self.output, root=self.root, layout_report=self.layout('PASS'))
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
                result = run_drc(self.board, self.output, root=self.root, layout_report=self.layout('PASS'))
                self.assertEqual(result['status'], 'PASS')
        table.write_text('(fp_lib_table (lib (type "KiCad") (uri "/external/library")))')
        with self.assertRaises(ValueError):
            run_drc(self.board, self.output, root=self.root)

    def test_actual_layout_report_shape_integrates_without_false_pass(self):
        passing = self.layout('PASS')
        result = self.invoke(passing)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['schema'], 'pcbknowledge.drc.v2')
        self.assertEqual(result['identity'], passing['identity'])
        self.assertEqual(result['layout_report'], passing)
        self.assertEqual(self.invoke(self.layout('FAIL'))['status'], 'FAIL')

    def test_forged_partial_or_wrong_board_layout_rejected_before_execution_and_write(self):
        wrong_board = self.layout()
        wrong_board['identity']['board_sha256'] = '0' * 64
        inconsistent = self.layout('FAIL')
        inconsistent.update(result='PASS', status='PASS')
        for report in ({'status': 'PASS'}, wrong_board, inconsistent):
            with self.subTest(report=report):
                with patch('pcbknowledge.v2.drc.subprocess.run') as process:
                    with self.assertRaises(ValueError):
                        run_drc(self.board, self.output, root=self.root, layout_report=report)
                    process.assert_not_called()
                    self.assertFalse(self.output.exists())

    def test_output_hardlink_to_any_input_rejected(self):
        self.output.parent.mkdir()
        for source in self.files:
            os.link(source, self.output)
            with patch('pcbknowledge.v2.drc.subprocess.run') as process:
                with self.assertRaisesRegex(ValueError, 'separate'):
                    run_drc(self.board, self.output, root=self.root)
                process.assert_not_called()
            self.assertEqual(source.read_bytes(), self.originals[source])
            self.output.unlink()

    def test_semantic_native_counts_status_a4_and_identity_reject_tampering(self):
        result = self.invoke(self.layout())
        mutations = (
            lambda r: r.update(finding_count=1),
            lambda r: r.update(a4='FAIL'),
            lambda r: r.update(status='NOT_RUN'),
            lambda r: r.update(exit_code=5),
            lambda r: r.update(drc_status='NOT_RUN'),
            lambda r: r['identity'].update(intent_sha256='d' * 64),
            lambda r: r['report']['violations'].append({'type': 'synthetic'}),
            lambda r: r.update(layout_report=None),
            lambda r: r['input_sha256'].update(
                unrelated=r['input_sha256'].pop(self.board.with_suffix('.kicad_pro').name)),
        )
        for mutation in mutations:
            changed = copy.deepcopy(result)
            mutation(changed)
            with self.assertRaises(ValueError):
                validate_drc_report(changed, ContractSchemas())

    def test_saved_windows_board_path_is_validated_lexically_on_any_host(self):
        result = self.invoke(self.layout())
        for path in (r'C:\exports\exported.kicad_pcb', 'C:/exports/exported.kicad_pcb',
                     r'\\server\share\exported.kicad_pcb'):
            with self.subTest(path=path):
                changed = copy.deepcopy(result)
                changed['board'] = path
                self.assertEqual(validate_drc_report(changed, ContractSchemas()), changed)
                for suffix in ('.kicad_pcb', '.kicad_pro', '.kicad_dru'):
                    missing = copy.deepcopy(changed)
                    missing['input_sha256']['unrelated'] = missing['input_sha256'].pop('exported' + suffix)
                    with self.assertRaisesRegex(ValueError, 'board and both sidecars'):
                        validate_drc_report(missing, ContractSchemas())

    def test_changed_isolated_copy_cannot_run_tool_or_claim_original_digest(self):
        import shutil
        real_copyfile = shutil.copyfile
        for selected in self.files:
            def changed_copy(source, destination):
                result = real_copyfile(source, destination)
                if Path(source) == selected:
                    Path(destination).write_text('Changed after original digest was recorded')
                return result
            with self.subTest(input=selected.name):
                with patch('pcbknowledge.v2.drc.shutil.which', return_value='/tool/kicad-cli'):
                    with patch('pcbknowledge.v2.drc.shutil.copyfile', side_effect=changed_copy):
                        with patch('pcbknowledge.v2.drc.subprocess.run') as process:
                            result = run_drc(self.board, self.output, root=self.root)
                            process.assert_not_called()
                self.assertEqual((result['status'], result['a4']), ('FAIL', 'FAIL'))
                self.assertIn('Copied DRC input differs', result['reason'])
                self.assertEqual(selected.read_bytes(), self.originals[selected])

    def test_explicit_schema_object_is_used_without_workspace_fallback(self):
        schemas = ContractSchemas()
        with patch.object(schemas, 'load', wraps=schemas.load) as load:
            with patch('pcbknowledge.v2.drc.shutil.which', return_value=None):
                result = run_drc(self.board, self.output, root=self.root, schemas=schemas)
        self.assertIn(('envelope.schema.json',), [call.args for call in load.call_args_list])
        self.assertIsNone(result['identity'])
        self.assertIsNone(result['layout_report'])
