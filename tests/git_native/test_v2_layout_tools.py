"""Synthetic external-process checks; no KiCad, Java or router installation needed."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.v2.layout_tools import derived_path, locate_tools, resolve_executable, run_bridge, run_process, run_router


class ToolTests(unittest.TestCase):
    def test_missing_tools_are_not_found_and_invalid_explicit_path_does_not_fallback(self):
        with patch('pcbknowledge.v2.layout_tools.shutil.which', return_value=None):
            result = locate_tools()
        self.assertTrue(all(item['status'] == 'NOT_FOUND' for item in result.values()))
        with patch('pcbknowledge.v2.layout_tools.shutil.which', return_value=sys.executable) as lookup:
            self.assertIsNone(resolve_executable('/path/that/does/not/exist', 'java'))
            lookup.assert_not_called()

    def test_process_has_isolated_home_and_failure_is_not_missing_tool(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            directory = root / 'build/process'
            result = run_process([sys.executable, '-c', 'import os; print(os.environ["HOME"])'],
                                 root=root, directory=directory)
            self.assertEqual(result['status'], 'PASS')
            self.assertIn(str(directory / 'home'), Path(result['log']).read_text())
            with self.assertRaisesRegex(ValueError, 'fresh'):
                run_process([sys.executable, '-c', 'pass'], root=root, directory=directory)
            failed = run_process([sys.executable, '-c', 'raise SystemExit(7)'],
                                 root=root, directory=root / 'build/failure')
            self.assertEqual((failed['status'], failed['exit_code']), ('FAIL', 7))
            missing = run_process(['/definitely/missing/executable'], root=root, directory=root / 'build/missing')
            self.assertEqual(missing['status'], 'FAIL')

    def test_timeout_and_output_escape_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            result = run_process([sys.executable, '-c', 'import time; time.sleep(2)'],
                                 root=root, directory=root / 'build/timeout', timeout=.01)
            self.assertEqual(result['status'], 'FAIL')
            with self.assertRaises(ValueError):
                derived_path(root, root / 'build/../../escape')
            with self.assertRaises(ValueError):
                derived_path(root, root / 'output')

    def test_router_command_is_single_thread_and_never_excludes_nets(self):
        tools = {'java': {'status': 'FOUND', 'path': 'java'},
                 'freerouting': {'status': 'FOUND', 'path': 'router.jar'}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            dsn = root / 'build/board.dsn'
            dsn.parent.mkdir()
            dsn.write_text('(pcb test)')
            with patch('pcbknowledge.v2.layout_tools.run_process', return_value={'status': 'PASS'}) as runner:
                result = run_router(dsn, root / 'build/board.ses', tools, root=root, directory=root / 'build/run')
            self.assertEqual(result['status'], 'FAIL')
            argv = runner.call_args.args[0]
            self.assertIn('--router.optimizer.max_threads=1', argv)
            self.assertIn('--router.autorouter.max_threads=1', argv)
            self.assertIn('--router.automatic_neckdown=false', argv)
            self.assertIn('--router.fanout.enabled=false', argv)
            self.assertIn('--router.neck_width_um=0', argv)
            self.assertIn('--router.autorouter.max_passes=100', argv)
            self.assertIn('-da', argv)
            self.assertNotIn('-inc', argv)
            self.assertNotIn('-drc', argv)
            tools['java']['status'] = 'NOT_FOUND'
            self.assertEqual(run_router(dsn, root / 'build/board.ses', tools,
                                        root=root, directory=root / 'build/run')['status'], 'NOT_RUN')

    def test_bridge_is_optional_and_cannot_write_outside_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            board = root / 'build/board.kicad_pcb'
            board.parent.mkdir()
            board.write_text('(kicad_pcb)')
            tools = {'kicad_python': {'status': 'NOT_FOUND'}}
            result = run_bridge('fill', board, root / 'build/filled.kicad_pcb', tools,
                                root=root, directory=root / 'build/fill')
            self.assertEqual(result['status'], 'NOT_RUN')
            with self.assertRaises(ValueError):
                run_bridge('fill', board, root / 'outside.kicad_pcb', tools,
                           root=root, directory=root / 'build/fill')

    def test_process_log_is_capped_and_overflow_fails(self):
        with tempfile.TemporaryDirectory() as folder, patch('pcbknowledge.v2.layout_tools.MAX_LOG_BYTES', 100):
            root = Path(folder).resolve()
            result = run_process([sys.executable, '-c', 'print("x" * 1000)'],
                                 root=root, directory=root / 'build/overflow')
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(Path(result['log']).stat().st_size, 100)


class VersionTests(unittest.TestCase):
    def test_supported_versions_and_bridge_major_are_checked(self):
        from pcbknowledge.v2.layout_tools import validate_versions
        for cli, bridge, java, expected in ((9, 9, 21, 'FOUND'), (10, 10, 25, 'FOUND'),
                                            (8, 8, 21, 'FAIL'), (9, 10, 25, 'FAIL'), (9, 9, 17, 'FAIL')):
            result = {name: {'status': 'FOUND', 'version': f'{version}.0.2'}
                      for name, version in (('kicad', cli), ('kicad_python', bridge), ('java', java))}
            validate_versions(result)
            statuses = {tool['status'] for tool in result.values()}
            self.assertEqual('FAIL' if 'FAIL' in statuses else 'FOUND', expected)
