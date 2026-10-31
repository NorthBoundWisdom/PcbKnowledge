"""Tool-free checks over native KiCad boards; handler probes are not identity proofs."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from pcbknowledge.v2.boardview import parse_board
from pcbknowledge.v2.layout import LayoutChecks, check_layout
from pcbknowledge.v2.layout_conductor_keepout import check_conductor_keepout
from pcbknowledge.v2.layout_guard import check_guard_ring
from pcbknowledge.v2.layout_kelvin import check_kelvin
from pcbknowledge.v2.layout_return import check_return_path
from tests.git_native.test_v2_layout import FixtureCatalog, intent, q
from tests.git_native.test_v2_layout_kelvin import Catalog as KelvinCatalog, fixture as kelvin_fixture
from tests.git_native.test_v2_underbody import region

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/layout/native'
EXPECTED = {
    'simple-routed': ['PASS'] * 8,
    'return-straight': ['PASS'], 'return-arc': ['PASS'], 'return-signal-via': ['NOT_CHECKABLE'],
    'guard-two-face': ['PASS'], 'kelvin-control': ['PASS'], 'kelvin-disconnected': ['FAIL'],
    'underbody-clear': ['PASS'], 'underbody-crossing': ['FAIL'],
}


def file_hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(FIXTURES.glob('*.kicad_pcb'))}


def native_reports():
    boards = {name: parse_board(FIXTURES / (name + '.kicad_pcb')) for name in EXPECTED}
    before = deepcopy(boards)
    reports = []
    full = check_layout(boards['simple-routed'], intent(), FixtureCatalog())
    reports.append({'board': 'simple-routed', 'scope': 'FULL_SIMPLE_FIXTURE_IDENTITY_AND_LAYOUT',
                    'identity': full['checks'][0], 'full_report': full,
                    'checks': [row for row in full['checks'] if 'index' in row]})
    for name in ('return-straight', 'return-arc', 'return-signal-via'):
        rule = {'kind': 'RETURN_PATH', 'net': 'SIGNAL', 'return_net': 'GND'}
        reports.append(probe(name, check_return_path(boards[name], rule)))
    guard = {'kind': 'GUARD_RING', 'net': 'SIGNAL', 'guard_net': 'BIAS',
             'min_width': q(.2), 'min_clearance': q(.25)}
    reports.append(probe('guard-two-face', check_guard_ring(boards['guard-two-face'], guard)))
    _, rule, design = kelvin_fixture()
    for name in ('kelvin-control', 'kelvin-disconnected'):
        reports.append(probe(name, check_kelvin(boards[name], rule, design, KelvinCatalog())))
    rule = {'kind': 'CONDUCTOR_KEEPOUT', 'subject': 'L1', 'region': region()}
    for name in ('underbody-clear', 'underbody-crossing'):
        reports.append(probe(name, check_conductor_keepout(boards[name], rule)))
    reports.extend(unsupported_probes(boards))
    if boards != before:
        raise AssertionError('Layout checks mutated parsed native board inputs')
    return boards, reports


def probe(name, finding):
    return {'board': name, 'scope': 'ISOLATED_HANDLER_PROBE_NO_FULL_GRAPH_IDENTITY', 'checks': [finding]}


def unsupported_probes(boards):
    rules = [
        ('simple-routed', {'kind': 'CLEARANCE_MIN', 'subjects': ['A', 'B'], 'min_clearance': q(.2)}),
        ('simple-routed', {'kind': 'ORIENTATION', 'subject': 'A', 'angle': q(0, 'deg')}),
        ('simple-routed', {'kind': 'TEST_POINT', 'net': 'N', 'subject': 'A.pin:1'}),
        ('kelvin-control', {'kind': 'DIFFERENTIAL_PAIR', 'nets': ['P', 'N'],
                            'min_width': q(.2), 'gap': q(.2), 'max_skew': q(1)}),
    ]
    return [probe(name, LayoutChecks(boards[name], {'components': []}, None).check(rule))
            for name, rule in rules]


def per_kind_metrics(findings, kinds):
    result = {}
    for kind in kinds:
        counts = Counter(row['result'] for row in findings if row['kind'] == kind)
        total = sum(counts.values())
        result[kind] = {
            'check_count': total,
            'status_counts': {status: counts[status] for status in ('PASS', 'FAIL', 'NOT_CHECKABLE')},
            'not_checkable_fraction': counts['NOT_CHECKABLE'] / total,
        }
    return result


def metrics():
    hashes = file_hashes()
    boards, reports = native_reports()
    if file_hashes() != hashes:
        raise AssertionError('Native board files changed during checks')
    findings = [row for report in reports for row in report['checks']]
    counts = Counter(row['result'] for row in findings)
    registry = json.loads((ROOT / 'knowledge/registry/layout-constraints.json').read_text())['entries']
    kinds = sorted({row['kind'] for row in findings})
    total = len(findings)
    return {
        'scope': 'Native saved boards; one full simple-fixture identity check and isolated handler probes.',
        'routing_certified': False, 'boards': [
            {'name': name, 'sha256': hashes[name + '.kicad_pcb'],
             'primitive_counts': {key: len(board[key]) for key in ('segments', 'arcs', 'vias', 'zones')}}
            for name, board in sorted(boards.items())],
        'reports': reports, 'registry_kind_count': len(registry), 'covered_kinds': kinds,
        'missing_kinds': sorted(set(registry) - set(kinds)), 'check_count': total,
        'per_kind': per_kind_metrics(findings, kinds),
        'status_counts': {status: counts[status] for status in ('PASS', 'FAIL', 'NOT_CHECKABLE')},
        'status_fractions': {status: counts[status] / total for status in ('PASS', 'FAIL', 'NOT_CHECKABLE')},
        'rate_denominator': 'All 20 registry-kind check instances, including intentional FAIL controls and NC probes.',
    }


class NativeBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = metrics()

    def test_expected_native_board_results_and_identity_scope(self):
        for report in self.report['reports'][:9]:
            with self.subTest(board=report['board']):
                self.assertEqual([row['result'] for row in report['checks']], EXPECTED[report['board']])
        simple = self.report['reports'][0]
        self.assertEqual(simple['identity']['result'], 'PASS')
        self.assertEqual(simple['full_report']['result'], 'PASS')
        self.assertFalse(simple['full_report']['routing_certified'])
        for report in self.report['reports'][1:]:
            self.assertEqual(report['scope'], 'ISOLATED_HANDLER_PROBE_NO_FULL_GRAPH_IDENTITY')
            self.assertNotIn('identity', report)

    def test_every_registry_kind_reported_without_false_unsupported_pass(self):
        self.assertEqual(self.report['registry_kind_count'], 16)
        self.assertEqual(len(self.report['covered_kinds']), 16)
        self.assertEqual(self.report['missing_kinds'], [])
        self.assertEqual(self.report['check_count'], 20)
        self.assertEqual(self.report['status_counts'], {'PASS': 13, 'FAIL': 2, 'NOT_CHECKABLE': 5})
        self.assertEqual(self.report['status_fractions'], {'PASS': .65, 'FAIL': .1, 'NOT_CHECKABLE': .25})
        for report in self.report['reports'][-4:]:
            self.assertEqual(report['checks'][0]['result'], 'NOT_CHECKABLE')
            self.assertIn('Unsupported layout constraint', report['checks'][0]['reason'])

    def test_per_kind_not_checkable_rates_use_actual_instance_denominators(self):
        per_kind = self.report['per_kind']
        self.assertEqual(set(per_kind), set(self.report['covered_kinds']))
        self.assertEqual(len(per_kind), 16)
        unsupported = {'CLEARANCE_MIN', 'ORIENTATION', 'TEST_POINT', 'DIFFERENTIAL_PAIR'}
        for kind, row in per_kind.items():
            denominator = 3 if kind == 'RETURN_PATH' else 2 if kind in ('KELVIN', 'CONDUCTOR_KEEPOUT') else 1
            expected_nc = 1 if kind in unsupported or kind == 'RETURN_PATH' else 0
            with self.subTest(kind=kind):
                self.assertEqual(row['check_count'], denominator)
                self.assertEqual(sum(row['status_counts'].values()), denominator)
                self.assertEqual(row['status_counts']['NOT_CHECKABLE'], expected_nc)
                self.assertEqual(row['not_checkable_fraction'], expected_nc / denominator)
        self.assertEqual(per_kind['RETURN_PATH']['status_counts'], {'PASS': 2, 'FAIL': 0, 'NOT_CHECKABLE': 1})
        for kind in ('KELVIN', 'CONDUCTOR_KEEPOUT'):
            self.assertEqual(per_kind[kind]['status_counts'], {'PASS': 1, 'FAIL': 1, 'NOT_CHECKABLE': 0})

    def test_native_primitives_and_immutable_file_bytes(self):
        boards = {row['name']: row for row in self.report['boards']}
        self.assertEqual(len(boards), 9)
        self.assertGreater(boards['return-arc']['primitive_counts']['arcs'], 0)
        self.assertGreater(boards['return-signal-via']['primitive_counts']['vias'], 0)
        self.assertGreater(boards['return-straight']['primitive_counts']['segments'], 0)
        self.assertGreater(boards['return-straight']['primitive_counts']['zones'], 0)
        self.assertEqual(file_hashes(), {name + '.kicad_pcb': row['sha256'] for name, row in boards.items()})


if __name__ == '__main__':
    print(json.dumps(metrics(), sort_keys=True, allow_nan=False))
