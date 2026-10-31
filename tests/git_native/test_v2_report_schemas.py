"""Owned report shapes reject malformed payloads; vendor DRC fields remain native."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.v2.schema import ContractSchemas
from pcbknowledge.v2.report_contracts import validate_schema
from tests.git_native.test_layout_native_boards import native_reports
from tests.git_native.test_v2_bringup import inputs
from tests.git_native.test_v2_layout import intent
from pcbknowledge.v2.bringup import make_bringup

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {'bundle_commit': 'a' * 40, 'block_graph_sha256': 'b' * 64,
            'intent_sha256': 'c' * 64, 'board_sha256': 'd' * 64}


def layout_report():
    report = deepcopy(native_reports()[1][0]['full_report'])
    report.update(identity=deepcopy(IDENTITY), constraints=deepcopy(intent()['layout']), status=report['result'])
    return report


def native_drc():
    return {'schema': 'pcbknowledge.drc.v2', 'identity': None, 'layout_report': None,
            'board': '/synthetic/design.kicad_pcb', 'input_sha256': {
                'design.kicad_pcb': 'd' * 64, 'design.kicad_pro': 'e' * 64, 'design.kicad_dru': 'f' * 64},
            'drc_status': 'PASS', 'a4': 'PASS', 'status': 'NOT_CHECKABLE', 'exit_code': 0, 'finding_count': 0,
            'report': {'$schema': 'https://schemas.kicad.org/drc.v1.json', 'kicad_version': 'synthetic',
                       'violations': [], 'unconnected_items': [], 'schematic_parity': []}}


class ReportSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schemas = ContractSchemas(ROOT / 'schemas')

    def validate(self, report, name):
        validate_schema(report, 'layout' if name == 'layout-check' else name, self.schemas)

    def invalid(self, report, name):
        with self.assertRaises(ValueError):
            self.validate(report, name)

    def test_all_report_schemas_use_supported_offline_contract(self):
        filename = 'envelope.schema.json'
        self.schemas.check(self.schemas.load(filename), filename)

    def test_native_producer_findings_cover_measured_fail_and_typed_unknown(self):
        name = 'envelope.schema.json'
        shape = self.schemas.load(name)['$defs']['layoutReport']['$defs']['finding']
        for report in native_reports()[1]:
            for finding in report['checks']:
                value = {'index': 0, **finding}
                with self.subTest(board=report['board'], kind=value['kind']):
                    self.schemas.apply(value, shape, name)
                    value['undeclared_metric'] = 1
                    with self.assertRaises(ValueError):
                        self.schemas.apply(value, shape, name)

    def test_layout_public_identity_and_observation_envelope_required(self):
        original = layout_report()
        self.validate(original, 'layout-check')
        for key in original:
            changed = deepcopy(original)
            del changed[key]
            with self.subTest(missing=key):
                self.invalid(changed, 'layout-check')
        for key, value in [('schema', 'pcbknowledge.layout-check.v1'), ('routing_certified', True),
                           ('result', 'UNKNOWN'), ('identity', None), ('extra', 1)]:
            changed = deepcopy(original)
            changed[key] = value
            with self.subTest(key=key):
                self.invalid(changed, 'layout-check')
        for key in IDENTITY:
            changed = deepcopy(original)
            changed['identity'][key] = 'invalid'
            self.invalid(changed, 'layout-check')

    def test_layout_constraints_are_required_typed_original_rules(self):
        original = layout_report()
        self.assertEqual(original['constraints'], intent()['layout'])
        for value in (None, {}, [{'kind': 'PLACE_NEAR', 'invented': True}]):
            changed = deepcopy(original)
            changed['constraints'] = value
            self.invalid(changed, 'layout-check')

    def test_layout_numeric_and_variant_tampering(self):
        original = layout_report()
        near = next(i for i, row in enumerate(original['checks']) if row['kind'] == 'PLACE_NEAR')
        for value in (True, float('nan'), float('inf'), '3 mm', -1):
            changed = deepcopy(original)
            changed['checks'][near]['distance_mm'] = value
            self.invalid(changed, 'layout-check')
        for value in ({'kind': 'CLEARANCE_MIN', 'result': 'PASS', 'reason': 'invented', 'index': 0},
                      {'kind': 'RETURN_PATH', 'result': 'PASS', 'reason': 'missing measurements', 'index': 0},
                      {'kind': 'IDENTITY', 'result': 'PASS', 'reason': 'wrong index', 'index': 0}):
            changed = deepcopy(original)
            changed['checks'].append(value)
            self.invalid(changed, 'layout-check')

    def test_arc_measurements_and_guard_surface_shapes(self):
        reports = native_reports()[1]
        arc = deepcopy(next(r for r in reports if r['board'] == 'return-arc')['checks'][0])
        shape = self.schemas.load('envelope.schema.json')['$defs']['layoutReport']['$defs']['finding']
        for field, value in [('enclosure_bounds_mm', [0, 1]), ('covered', False), ('method', 'guessed')]:
            changed = {'index': 0, **deepcopy(arc)}
            changed['arcs'][0][field] = value
            with self.assertRaises(ValueError):
                self.schemas.apply(changed, shape, 'envelope.schema.json')
        guard = deepcopy(next(r for r in reports if r['board'] == 'guard-two-face')['checks'][0])
        guard['index'] = 0
        guard['surfaces'][0]['min_width_mm'] = True
        with self.assertRaises(ValueError):
            self.schemas.apply(guard, shape, 'envelope.schema.json')

    def test_bringup_producer_unknown_declared_and_located_shapes(self):
        args = inputs()
        report = make_bringup(*args)
        self.validate(report, 'bringup')
        for key, value in [('a6', 'PASS'), ('schema', 'pcbknowledge.bringup.v3'), ('unexpected', {})]:
            changed = deepcopy(report)
            changed[key] = value
            self.invalid(changed, 'bringup')
        changed = deepcopy(report)
        changed['rails'][0]['result'] = 'PASS'
        self.invalid(changed, 'bringup')
        changed = deepcopy(report)
        location = changed['rails'][0]['test_locations'][0]
        location.pop('reason')
        location.update(location_status='LOCATED', pad_centers_mm=[[1, 2]])
        self.validate(changed, 'bringup')
        location['pad_centers_mm'] = [[1, 2, 3]]
        self.invalid(changed, 'bringup')

    def test_bringup_programming_requires_named_signal_and_net(self):
        report = make_bringup(*inputs())
        for key in ('signal', 'net'):
            changed = deepcopy(report)
            del changed['programming'][0]['pinout'][0][key]
            self.invalid(changed, 'bringup')
        changed = deepcopy(report)
        changed['rails'][0]['test_locations'][0]['signal'] = 'misplaced'
        self.invalid(changed, 'bringup')

    def test_drc_vendor_extensions_and_closed_owned_wrapper(self):
        report = native_drc()
        report['report']['vendor_future_field'] = {'anything': ['native']}
        report['report']['violations'] = [{'type': 'synthetic', 'vendor_future_detail': {'severity': 'error'}}]
        report['finding_count'] = 1
        report.update(drc_status='FAIL', a4='FAIL', status='FAIL')
        self.validate(report, 'drc')
        report['vendor_future_field'] = True
        self.invalid(report, 'drc')

    def test_drc_native_error_and_not_run_variants(self):
        report = native_drc()
        self.validate(report, 'drc')
        for key in ('exit_code', 'finding_count', 'report'):
            changed = deepcopy(report)
            del changed[key]
            self.invalid(changed, 'drc')
        error = {key: value for key, value in report.items() if key not in ('exit_code', 'finding_count', 'report')}
        error.update(reason='synthetic unavailable tool', drc_status='NOT_RUN', a4='NOT_RUN', status='NOT_RUN')
        self.validate(error, 'drc')
        error.update(drc_status='FAIL', a4='FAIL', status='FAIL')
        self.validate(error, 'drc')
        error.update(drc_status='PASS', a4='PASS')
        self.invalid(error, 'drc')

    def test_drc_rejects_arbitrary_layout_pass_and_malformed_native_payload(self):
        original = native_drc()
        for key, value in [('layout_report', {'status': 'PASS'}), ('identity', {'board_sha256': 'd' * 64}),
                           ('finding_count', True), ('exit_code', 0.5), ('schema', 'kicad')]:
            report = deepcopy(original)
            report[key] = value
            self.invalid(report, 'drc')
        for key, value in [('$schema', 'https://example.invalid/schema'), ('violations', [{}]),
                           ('schematic_parity', None)]:
            report = deepcopy(original)
            report['report'][key] = value
            self.invalid(report, 'drc')
