"""Conditional engineering declaration contract without native dependencies."""
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock
from pcbknowledge.v2.schema import ContractSchemas
from pcbknowledge.v2.bringup_contract import apply_test_windows, bringup_sources, project_bringup, validate_bringup


def declaration():
    return {'prerequisites': ['Measure steady-state conditions and apply uncertainty guardbands.'], 'rails': [{
        'at': 'reg_U.pin:2', 'reference_at': 'reg_U.pin:1', 'expected_voltage': {
            'unit': 'V', 'min': 2.4, 'max': 2.6, 'basis': 'ENGINEERING_DEFAULT', 'note': 'Declared test window.',
            'conditions': {'ambient_temperature': {'unit': 'degC', 'value': 23}}},
        'supporting_evidence': [{'source': 'source:one', 'page': 1}]}]}


def intent():
    return {'nets': [{'name': 'RAIL', 'class': 'POWER', 'pins': [
        {'ref': 'reg_U', 'pin': '2'}, {'ref': 'load_C', 'pin': '1'}]},
        {'name': 'GND', 'class': 'GROUND', 'pins': [{'ref': 'reg_U', 'pin': '1'}]}]}


class ContractTests(unittest.TestCase):
    def test_noop_without_contract_and_immutable_copy_with_source_closure(self):
        target = intent()
        original = deepcopy(target)
        catalog = MagicMock()
        catalog.schemas.load.return_value = {'$defs': {'bringup': {}}}
        project_bringup({}, target, catalog, set())
        self.assertEqual(original, target)
        graph = {'bringup': declaration()}
        graph['bringup']['rails'][0]['expected_voltage']['evidence'] = {'source': 'source:two', 'page': 2}
        used = set()
        project_bringup(graph, target, catalog, used)
        self.assertEqual(used, {'source:one', 'source:two'})
        self.assertEqual(bringup_sources(target['bringup']), used)
        target['bringup']['rails'][0]['expected_voltage']['min'] = 2
        self.assertEqual(graph['bringup']['rails'][0]['expected_voltage']['min'], 2.4)

    def test_exact_power_ground_endpoints_and_duplicate_resolved_net(self):
        for mode in ('missing', 'ground', 'reference', 'duplicate'):
            value = {**intent(), 'bringup': declaration()}
            row = value['bringup']['rails'][0]
            if mode == 'missing':
                row['at'] = 'absent.pin:1'
            elif mode == 'ground':
                row['at'] = 'reg_U.pin:1'
            elif mode == 'reference':
                row['reference_at'] = 'reg_U.pin:2'
            else:
                duplicate = deepcopy(row)
                duplicate['at'] = 'load_C.pin:1'
                value['bringup']['rails'].append(duplicate)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_bringup(value)

    def test_missing_conditions_nonfinite_reversed_and_wrong_basis_fail(self):
        for mode in ('conditions', 'nan', 'reversed', 'basis', 'prerequisites'):
            value = {**intent(), 'bringup': declaration()}
            q = value['bringup']['rails'][0]['expected_voltage']
            if mode == 'conditions':
                q['conditions'] = {}
            elif mode == 'nan':
                q['min'] = float('nan')
            elif mode == 'reversed':
                q['min'] = 3
            elif mode == 'basis':
                q['basis'] = 'DATASHEET'
            else:
                value['bringup']['prerequisites'] = []
            with self.assertRaises(ValueError):
                validate_bringup(value)

    def test_plan_remains_unobserved_and_prior_context_is_preserved(self):
        prior = {'status': 'UNKNOWN', 'nominal': 2.5, 'declarations': [{'origin': 'part:one'}]}
        report = {'rails': [{'net': 'RAIL', 'expected_voltage': deepcopy(prior), 'result': 'NOT_RUN'}], 'a6': 'NOT_RUN'}
        result = apply_test_windows(report, {**intent(), 'bringup': declaration()}, locate=lambda pin: pin)
        expected = result['rails'][0]['expected_voltage']
        self.assertEqual(expected['contextual_expectation'], prior)
        self.assertEqual(expected['conditions_status'], 'NOT_RUN')
        self.assertEqual(result['prerequisites_status'], 'NOT_RUN')
        self.assertEqual(result['a6'], 'NOT_RUN')
        self.assertEqual(result['range_coverage'], 'COMPLETE')
        self.assertEqual(result['rails'][0]['declared_reference_location']['pin'], '1')

    def test_explicit_window_conflicting_with_nominal_fails(self):
        report = {'rails': [{'net': 'RAIL', 'expected_voltage': {'nominal': 5}}]}
        with self.assertRaises(ValueError):
            apply_test_windows(report, {**intent(), 'bringup': declaration()}, locate=lambda pin: pin)

    def test_embedded_schema_does_not_add_to_historical_schema_file_set(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for source in (root / 'schemas').glob('*.schema.json'):
                shutil.copyfile(source, directory / source.name)
            before = sorted(p.name for p in directory.iterdir())
            name = 'design-intent.schema.json'
            self.assertEqual(len(before), 16)
            self.assertEqual(before, sorted(p.name for p in directory.iterdir()))
            schema = ContractSchemas(directory)
            definition = schema.load(name)['$defs']['bringup']
            schema.check(definition, name)
            schema.apply(declaration(), definition, name)
            for field, invalid in (('unit', 'A'), ('conditions', {}), ('basis', 'DATASHEET')):
                value = declaration()
                value['rails'][0]['expected_voltage'][field] = invalid
                with self.assertRaises(ValueError):
                    schema.apply(value, definition, name)
