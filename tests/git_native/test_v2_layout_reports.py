"""Public layout report binding and fail-closed summary mutations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pcbknowledge.v2.layout import check_board
from pcbknowledge.v2.report_contracts import validate_layout_report
from tests.git_native.test_v2_layout import FixtureCatalog, board_text, intent


class LayoutReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'board.kicad_pcb'
        self.path.write_text(board_text(), encoding='utf-8')
        self.intent = intent()
        self.catalog = FixtureCatalog()
        self.report = check_board(self.path, self.intent, self.catalog)

    def validate(self, report):
        return validate_layout_report(report, self.catalog.schemas, intent=self.intent,
                                      board_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_actual_byte_binding_and_complete_rules(self):
        self.validate(self.report)
        self.assertEqual(self.report['status'], 'PASS')
        self.assertEqual(self.report['identity']['board_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(len([c for c in self.report['checks'] if 'index' in c]), len(self.intent['layout']))

    def test_summary_version_owned_keys_and_rule_coverage_tamper(self):
        changes = [lambda r: r.update(schema='unknown'), lambda r: r.update(extra=True),
                   lambda r: r.update(status='FAIL'),
                   lambda r: r['checks'][1].update(result='FAIL'),
                   lambda r: r['checks'].pop(1), lambda r: r['checks'].pop(),
                   lambda r: r['checks'].append(deepcopy(r['checks'][0])), lambda r: r['checks'][-1].update(index=0),
                   lambda r: r['checks'][1].update(kind='GROUP'),
                   lambda r: r['identity'].update(intent_sha256='f' * 64),
                   lambda r: r['identity'].update(board_sha256='f' * 64)]
        for mutate in changes:
            with self.subTest(mutation=changes.index(mutate)):
                report = deepcopy(self.report)
                mutate(report)
                with self.assertRaises(ValueError):
                    self.validate(report)

    def test_measured_pass_cannot_contradict_limits_or_collisions(self):
        changes = [(1, 'distance_mm', 1000000), (5, 'collisions', ['B']),
                   (6, 'min_width_mm', 0), (7, 'estimated_area_mm2', 1000000),
                   (8, 'area_mm2', 0), (13, 'misplaced', ['A'])]
        for index, field, value in changes:
            with self.subTest(field=field):
                report = deepcopy(self.report)
                report['checks'][index][field] = value
                with self.assertRaises(ValueError):
                    self.validate(report)
                with self.assertRaises(ValueError):
                    validate_layout_report(report, self.catalog.schemas)

    def test_copied_constraints_must_match_selected_intent(self):
        report = deepcopy(self.report)
        report['constraints'][0]['max_distance']['value'] = 100
        with self.assertRaisesRegex(ValueError, 'constraints differ'):
            self.validate(report)

    def test_distance_datum_cannot_substitute_a_different_measurement(self):
        report = deepcopy(self.report)
        report['constraints'][0]['datum'] = 'COPPER_EDGE'
        with self.assertRaisesRegex(ValueError, 'datum differs'):
            validate_layout_report(report, self.catalog.schemas)
        report = deepcopy(self.report)
        report['checks'][1].update(datum='COPPER_EDGE', limit_mm=3, subject_pad='1', target_pad='1',
                                   subject_pad_index=0, target_pad_index=0, net='N', common_layers=['F.Cu'])
        with self.assertRaisesRegex(ValueError, 'datum differs'):
            validate_layout_report(report, self.catalog.schemas)

    def test_guard_limits_and_closed_ring_summary_cannot_be_forged(self):
        from pcbknowledge.v2.report_measurements import scalar_consistency
        from pcbknowledge.v2.layout_guard import check_guard_ring
        from pcbknowledge.v2.boardview import parse_board
        from tests.git_native.test_v2_layout import q
        GUARD_RULE = {'kind': 'GUARD_RING', 'net': 'SIGNAL', 'guard_net': 'BIAS',
                      'min_width': q(.2), 'min_clearance': q(.25)}
        path = Path(__file__).parent.parent / 'fixtures/layout/native/guard-two-face.kicad_pcb'
        finding = check_guard_ring(parse_board(path), GUARD_RULE)
        self.assertEqual(finding['result'], 'PASS')
        scalar_consistency(finding, GUARD_RULE)
        for field, value in [('required_width_mm', 0), ('required_clearance_mm', 0),
                             ('min_clearance_mm', -100), ('closed_segments', 0), ('max_gap_mm', 1)]:
            mutated = deepcopy(finding)
            mutated['surfaces'][0][field] = value
            with self.assertRaises(ValueError):
                scalar_consistency(mutated, GUARD_RULE)

    def test_changed_actual_input_bytes_are_not_accepted(self):
        self.path.write_text(board_text() + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'different board bytes'):
            self.validate(self.report)

    def test_old_snapshot_without_report_definition_refuses(self):
        from pcbknowledge.v2.schema import ContractSchemas
        folder = Path(self.temp.name)
        envelope = deepcopy(self.catalog.schemas.load('envelope.schema.json'))
        del envelope['$defs']['layoutReport']
        (folder / 'envelope.schema.json').write_text(json.dumps(envelope), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unresolved schema pointer'):
            validate_layout_report(self.report, ContractSchemas(folder))

    def test_unknown_schema_is_not_replaced_by_software_fallback(self):
        from pcbknowledge.v2.schema import ContractSchemas
        empty = ContractSchemas(Path(self.temp.name))
        with self.assertRaises(FileNotFoundError):
            validate_layout_report(self.report, empty)


if __name__ == '__main__':
    unittest.main()
