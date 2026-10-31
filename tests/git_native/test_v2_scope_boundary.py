"""D78 keeps knowledge handoff and checks without layout orchestration."""
from contextlib import redirect_stderr
import io
import unittest

from pcbknowledge.v2.cli import parser


class ScopeBoundaryTests(unittest.TestCase):
    def test_retired_commands_are_not_available(self):
        for command in ('tools', 'run'):
            with self.subTest(command=command), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    parser().parse_args(['layout', command])
                self.assertEqual(error.exception.code, 2)

    def test_handoff_and_read_only_checks_remain_available(self):
        common = ['--bundle', 'bundle.json', '--graph', 'graph.json']
        export = parser().parse_args(['layout', 'export', '--intent', 'intent.json', *common])
        check = parser().parse_args(['layout', 'check', 'intent.json', 'board.kicad_pcb', *common])
        drc = parser().parse_args(['drc', 'board.kicad_pcb'])
        self.assertEqual((export.action, check.action, drc.group), ('export', 'check', 'drc'))
