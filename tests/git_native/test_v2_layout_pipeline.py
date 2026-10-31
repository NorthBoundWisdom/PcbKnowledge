"""Synthetic end-to-end coordinator tests; native tools are always mocked."""
from contextlib import ExitStack
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from pcbknowledge.v2.layout_pipeline import run_layout
from pcbknowledge.v2.placement import PlacementError

MODULE = 'pcbknowledge.v2.layout_pipeline.'


class PipelineFixture:
    def __init__(self, root):
        self.root = root
        self.output = root / 'build/attempt'
        self.intent = {'brief_id': 'B', 'block_graph_sha256': 'graph-hash'}
        self.bundle = SimpleNamespace(commit='commit-hash', catalog=object(), briefs={'B': {}})
        self.graph = {'brief': 'B'}
        self.tools = {name: {'status': 'FOUND', 'path': '/tool/' + name}
                      for name in ('kicad', 'kicad_python', 'java', 'freerouting')}
        self.layout = {'result': 'PASS', 'checks': [{'kind': 'IDENTITY', 'result': 'PASS'}]}
        self.drc = {'a4': 'PASS', 'status': 'PASS', 'report': {
            'violations': [], 'unconnected_items': [], 'schematic_parity': []}}
        self.bringup = {'range_coverage': 'COMPLETE', 'unresolved_rail_ranges': []}
        self.mocks = {}

    def handoff(self, intent, bundle, graph, output):
        output.mkdir(parents=True)
        (output / 'design.kicad_pcb').write_text('(kicad_pcb)')
        (output / 'fp-lib-table').write_text('(fp_lib_table)')
        (output / 'pcbknowledge.pretty').mkdir()
        (output / 'assembly.csv').write_text('references\nU1\n')
        return output

    def route(self, board, output, *args, **kwargs):
        output.mkdir()
        final = output / 'routed.kicad_pcb'
        final.write_text('(kicad_pcb (filled yes))')
        return {'status': 'PASS', 'board': str(final), 'router': {'status': 'PASS', 'runtime_seconds': 1.25}}

    def fabrication(self, board, output, *args, **kwargs):
        output.mkdir()
        (output / 'top.svg').write_text('<svg/>')
        return {'status': 'PASS', 'reread': {'status': 'PASS'}}

    def install(self, stack):
        values = {'validate_expansion': None, 'place_components': {}, 'apply_positions': ['kicad_pcb'],
                  '_syntax': ['kicad_pcb'], 'check_board': self.layout, 'run_drc': self.drc,
                  'parse_board': {}, 'make_bringup': self.bringup, 'render_bringup': '# Checklist\n'}
        for name, value in values.items():
            self.mocks[name] = stack.enter_context(patch(MODULE + name, return_value=value))
        for name, function in (('export_handoff', self.handoff), ('route_board', self.route),
                               ('export_outputs', self.fabrication)):
            self.mocks[name] = stack.enter_context(patch(MODULE + name, side_effect=function))
        stack.enter_context(patch('pcbknowledge.v2.layout_copper.add_copper', return_value=['kicad_pcb']))
        return self

    def run(self):
        return run_layout(self.intent, self.bundle, self.graph, self.output, self.tools, root=self.root)


class PipelineTests(unittest.TestCase):
    def test_success_checks_filled_board_copies_bom_and_summarizes_measured_counts(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            report = fixture.run()
            final = fixture.output / 'routing/routed.kicad_pcb'
            self.assertEqual((report['a3'], report['a4'], report['a5']), ('PASS', 'PASS', 'PASS'))
            self.assertEqual(fixture.mocks['check_board'].call_args.args[0], final)
            self.assertEqual(fixture.mocks['run_drc'].call_args.args[0], final)
            self.assertEqual(fixture.mocks['export_outputs'].call_args.args[0], final)
            self.assertEqual(fixture.mocks['run_drc'].call_args.kwargs['kicad'], '/tool/kicad')
            self.assertEqual(report['router']['runtime_seconds'], 1.25)
            self.assertEqual(report['counts']['layout'], {'PASS': 1, 'FAIL': 0, 'NOT_CHECKABLE': 0})
            self.assertEqual(report['counts']['drc']['unconnected_items'], 0)
            self.assertTrue((final.parent / 'fp-lib-table').is_file())
            self.assertTrue((fixture.output / 'fabrication/assembly.csv').is_file())
            self.assertEqual(len(report['svg_paths']), 1)
            saved = json.loads((fixture.output / 'report.json').read_text())
            self.assertEqual(saved['board'], str(final))

    def test_fresh_directory_and_build_boundary_are_checked_before_authority_or_tools(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.output.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'fresh'):
                fixture.run()
            fixture.output = fixture.root / 'outside'
            with self.assertRaises(ValueError):
                fixture.run()
            fixture.mocks['validate_expansion'].assert_not_called()
            fixture.mocks['export_handoff'].assert_not_called()
            fixture.mocks['route_board'].assert_not_called()

    def test_missing_tools_leave_a4_and_a5_not_run_and_no_native_calls(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.tools['java'] = {'status': 'NOT_FOUND', 'path': None}
            report = fixture.run()
            self.assertEqual((report['a4'], report['a5']), ('NOT_RUN', 'NOT_RUN'))
            self.assertEqual(report['router']['status'], 'NOT_RUN')
            self.assertIsNone(report['counts']['drc']['violations'])
            for name in ('route_board', 'run_drc', 'export_outputs'):
                fixture.mocks[name].assert_not_called()

    def test_failed_route_never_claims_drc_or_fabrication_success(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.mocks['route_board'].side_effect = None
            fixture.mocks['route_board'].return_value = {'status': 'FAIL', 'reason': 'Session invalid'}
            report = fixture.run()
            self.assertEqual((report['a4'], report['a5']), ('NOT_RUN', 'NOT_RUN'))
            self.assertNotEqual(report['status'], 'PASS')
            fixture.mocks['run_drc'].assert_not_called()
            fixture.mocks['export_outputs'].assert_not_called()
            self.assertEqual(Path(report['board']).parent.name, 'handoff')

    def test_fabrication_reread_failure_blocks_a5_even_after_clean_native_drc(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.mocks['export_outputs'].side_effect = None
            fixture.mocks['export_outputs'].return_value = {'status': 'FAIL', 'reason': 'Missing position'}
            report = fixture.run()
            self.assertEqual(report['a4'], 'PASS')
            self.assertEqual(report['a5'], 'FAIL')
            self.assertEqual(report['status'], 'FAIL')

    def test_layout_unknowns_and_native_findings_remain_visible_and_block_acceptance(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.layout.update(result='NOT_CHECKABLE', checks=[
                {'kind': 'IDENTITY', 'result': 'PASS'},
                {'kind': 'RETURN_PATH', 'result': 'NOT_CHECKABLE', 'reason': 'Unsupported connectivity proof'}])
            fixture.drc.update(a4='FAIL', status='FAIL', report={
                'violations': [{'type': 'clearance'}], 'unconnected_items': [{'type': 'unconnected'}],
                'schematic_parity': []})
            report = fixture.run()
            self.assertEqual((report['a3'], report['a4'], report['a5']), ('FAIL', 'FAIL', 'FAIL'))
            self.assertEqual(report['counts']['layout']['NOT_CHECKABLE'], 1)
            self.assertEqual(report['counts']['drc']['violations'], 1)
            self.assertEqual(report['counts']['drc']['unconnected_items'], 1)
            self.assertEqual(report['not_checkable'][0]['kind'], 'RETURN_PATH')

    def test_placement_failure_preserves_reason_and_never_routes(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.mocks['place_components'].side_effect = PlacementError('No fit', constraints=[2], states=10)
            report = fixture.run()
            self.assertEqual(report['placement']['constraint_indexes'], [2])
            self.assertEqual(report['placement']['search_states'], 10)
            self.assertEqual((report['a3'], report['a4'], report['a5']), ('FAIL', 'NOT_RUN', 'NOT_RUN'))
            fixture.mocks['route_board'].assert_not_called()

    def test_failed_version_probe_is_failure_not_missing_tool(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.tools['kicad'] = {'status': 'FAIL', 'path': '/bad/kicad', 'reason': 'Version probe failed'}
            report = fixture.run()
            self.assertEqual(report['router']['status'], 'FAIL')
            self.assertNotEqual(report['status'], 'PASS')
            fixture.mocks['route_board'].assert_not_called()

    def test_missing_bringup_ranges_block_readiness_not_valid_fabrication_evidence(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            fixture = PipelineFixture(Path(folder)).install(stack)
            fixture.bringup.update(range_coverage='UNKNOWN', unresolved_rail_ranges=['RAIL'])
            report = fixture.run()
            self.assertEqual(report['a5'], 'PASS')
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(report['bringup']['unresolved_rail_ranges'], ['RAIL'])
