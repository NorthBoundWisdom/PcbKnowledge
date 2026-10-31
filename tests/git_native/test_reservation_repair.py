"""Reservation orchestration is bounded, authenticated and retains partial runtime."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pcbknowledge.v2.reservation_repair import reserve_route
from pcbknowledge.v2.routing import route_board


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.build.mkdir()
        self.source = self.build / 'original.kicad_pcb'
        self.source.write_text('board')
        for suffix in ('.kicad_pro', '.kicad_dru'):
            self.source.with_suffix(suffix).write_text(suffix)
        self.output = self.build / 'output'
        self.paths = {name: self.source for name in ('original', 'current', 'prior', 'drc', 'intent', 'bundle')}
        self.paths['output'] = self.output
        self.files = {str(self.source): hashlib.sha256(self.source.read_bytes()).hexdigest()}
        self.tools = {name: {'path': '/explicit/' + name} for name in ('kicad', 'kicad_python', 'java', 'freerouting')}

    def call(self, tools=None):
        return reserve_route(self.source, self.source, self.source, self.source, self.source,
                             self.source, 'failed-pad', tools or self.tools, self.output, root=self.root)

    def authenticated(self):
        return patch('pcbknowledge.v2.reservation_repair._authenticate',
                     return_value=(self.paths, {}, object(), self.files))

    def test_missing_tools_not_run_without_output(self):
        with self.authenticated():
            result = self.call({'kicad': {'path': '/explicit/kicad'}})
        self.assertEqual(result['status'], 'NOT_RUN')
        self.assertFalse(self.output.exists())

    def test_invalid_authority_never_creates_output(self):
        with patch('pcbknowledge.v2.reservation_repair._authenticate', side_effect=ValueError('tampered')):
            with self.assertRaises(ValueError):
                self.call()
        self.assertFalse(self.output.exists())

    def test_downstream_failure_preserves_measured_router_time(self):
        def fail(root, paths, prepared, intent, bundle, tools, result):
            result['route'] = {'status': 'PASS', 'router': {'runtime_seconds': 12.5}}
            raise ValueError('native final failure')
        with self.authenticated(), patch('pcbknowledge.v2.reservation_repair._prepare', return_value=('seed', {})), \
                patch('pcbknowledge.v2.reservation_repair._route_and_check', side_effect=fail):
            result = self.call()
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['router_seconds'], 12.5)
        self.assertTrue((self.output / 'report.json').exists())

    def test_source_mutation_overrides_candidate_pass(self):
        def mutate(root, paths, prepared, intent, bundle, tools, result):
            result['status'] = 'PASS'
            self.source.write_text('changed')
        with self.authenticated(), patch('pcbknowledge.v2.reservation_repair._prepare', return_value=('seed', {})), \
                patch('pcbknowledge.v2.reservation_repair._route_and_check', side_effect=mutate):
            self.assertEqual(self.call()['status'], 'FAIL')

    def test_default_router_keeps_existing_no_scope_contract(self):
        with patch('pcbknowledge.v2.routing._route', return_value='PASS') as route:
            result = route_board(self.source, self.output, {}, object(), {}, root=self.root)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(route.call_args.args[-2:], (None, None))

    def test_scope_requires_bound_source_receipt_before_output(self):
        with self.assertRaises(ValueError):
            route_board(self.source, self.output, {}, object(), {}, root=self.root,
                        scope={'current': self.source, 'baseline': self.source})
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
