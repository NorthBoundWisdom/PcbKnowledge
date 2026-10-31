"""Bring-up report schema, identity and cross-field invariants at production boundaries."""
from copy import deepcopy
import unittest

from pcbknowledge.v2.bringup import make_bringup, render_bringup
from pcbknowledge.v2.bringup_report_validation import validate_bringup_report
from pcbknowledge.v2.report_contracts import document_sha256
from tests.git_native.test_v2_bringup import inputs


class BringupReportValidationTests(unittest.TestCase):
    def setUp(self):
        self.args = inputs()
        self.schemas = self.args[3].schemas
        self.report = make_bringup(*self.args)

    def rejected(self, report):
        with self.assertRaises(ValueError):
            validate_bringup_report(report, self.schemas)
        with self.assertRaises(ValueError):
            render_bringup(report, schemas=self.schemas)

    def test_exact_identity_and_unchanged_inputs(self):
        before = deepcopy(self.args[:3])
        report = make_bringup(*self.args)
        self.assertEqual(before, self.args[:3])
        self.assertEqual(report['identity'], {
            'bundle_commit': self.args[0]['bundle_commit'],
            'block_graph_sha256': document_sha256(self.args[1]),
            'intent_sha256': document_sha256(self.args[0]), 'board_sha256': None})
        self.assertIs(validate_bringup_report(report, self.schemas), report)
        self.assertIn('NOT_RUN', render_bringup(report, schemas=self.schemas))

    def test_changed_graph_cannot_reuse_intent_identity(self):
        self.args[1]['instances'][0]['parameters']['output_voltage']['value'] = 3
        with self.assertRaisesRegex(ValueError, 'graph digest'):
            make_bringup(*self.args)

    def test_no_fake_catalog_or_render_schema_fallback(self):
        del self.args[3].schemas
        with self.assertRaises(AttributeError):
            make_bringup(*self.args)
        with self.assertRaises(TypeError):
            render_bringup(self.report)

    def test_summary_identity_observation_and_union_mutations_fail(self):
        for mode in ('coverage', 'unresolved', 'identity', 'hash', 'observed', 'a6', 'dual', 'extra', 'reversed'):
            report = deepcopy(self.report)
            if mode == 'coverage':
                report['range_coverage'] = 'UNKNOWN'
            elif mode == 'unresolved':
                report['unresolved_rail_ranges'] = ['invented']
            elif mode == 'identity':
                report['identity']['bundle_commit'] = 'b' * 40
            elif mode == 'hash':
                report['identity']['intent_sha256'] = 'not-a-hash'
            elif mode == 'observed':
                report['rails'][0]['result'] = 'PASS'
            elif mode == 'a6':
                report['a6'] = 'PASS'
            elif mode == 'dual':
                report['rails'][0]['expected_waveform'] = {}
            elif mode == 'extra':
                report['acceptance_passed'] = True
            else:
                report['rails'][0]['expected_voltage']['min'] = 100
            with self.subTest(mode=mode):
                self.rejected(report)

    def test_unknown_plan_requires_exact_ordered_unresolved_list(self):
        report = deepcopy(self.report)
        rail = report['rails'][0]
        rail['expected_voltage'] = {'status': 'UNKNOWN', 'reason': 'No measured window available.'}
        report['range_coverage'] = 'UNKNOWN'
        report['unresolved_rail_ranges'] = [rail['net']]
        self.assertIs(validate_bringup_report(report, self.schemas), report)
        report['unresolved_rail_ranges'] *= 2
        self.rejected(report)

    def test_duplicate_rails_and_unpaired_prerequisite_status_fail(self):
        report = deepcopy(self.report)
        report['rails'].append(deepcopy(report['rails'][0]))
        self.rejected(report)
        report = deepcopy(self.report)
        report['prerequisites_status'] = 'NOT_RUN'
        self.rejected(report)


class ConditionalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.git_native.test_v2_bringup_waveform import ROOT, read
        from pcbknowledge.v2.catalog import Catalog
        from pcbknowledge.v2.expansion import expand

        cls.catalog = Catalog(ROOT, ROOT / 'schemas')
        graph, brief = read('block-graph'), read('brief')
        intent = expand(cls.catalog, graph, brief, bundle_commit='a' * 40)
        cls.report = make_bringup(intent, graph, brief, cls.catalog)

    def test_forged_source_provenance_units_and_waveform_acquisition_rejected(self):
        for mode in ('basis', 'evidence', 'unit', 'missing', 'duration', 'location'):
            report = deepcopy(self.report)
            rail = next(row for row in report['rails'] if 'expected_waveform' in row)
            value = rail['expected_waveform']
            source = value['source_limits']['switch_node_absolute_voltage']
            if mode == 'basis':
                source.pop('evidence')
                source.update(basis='ENGINEERING_DEFAULT', note='Synthetic forged source claim.')
            elif mode == 'evidence':
                source.pop('evidence')
            elif mode == 'unit':
                source['unit'] = 'A'
            elif mode == 'missing':
                del value['source_limits']['switch_node_absolute_voltage']
            elif mode == 'duration':
                value['protocol']['negative_excursion_duration']['max'] = 1e-8
            else:
                rail['declared_reference_location']['pin'] = '7'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                render_bringup(report, schemas=self.catalog.schemas)

    def test_conditional_status_prerequisites_and_context_must_agree(self):
        for mode in ('conditions', 'shared', 'context'):
            report = deepcopy(self.report)
            rail = next(row for row in report['rails'] if row['net'] == 'PROTECTED_INPUT')
            if mode == 'conditions':
                rail['expected_voltage']['conditions_status'] = 'PASS'
            elif mode == 'shared':
                del report['prerequisites_status']
            else:
                prior = rail['expected_voltage']['contextual_expectation']
                prior['min'] = prior['max'] + 1
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                render_bringup(report, schemas=self.catalog.schemas)
