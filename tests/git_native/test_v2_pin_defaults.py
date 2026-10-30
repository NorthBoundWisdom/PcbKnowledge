"""Unconnected INPUT defaults require source evidence and survive the handoff."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.v2.catalog import Catalog
from pcbknowledge.v2.intent import electrical_checks
from pcbknowledge.v2.pin_defaults import validate_default_checks, validate_unconnected_states
from pcbknowledge.v2.schema import validate
from pcbknowledge.v2.vocabulary import Vocabulary
from tests.git_native.test_v2_record_contracts import fixtures

ROOT = Path(__file__).resolve().parents[2]


class UnconnectedInputTests(unittest.TestCase):
    def setUp(self):
        data = fixtures()
        self.part = data['part']
        self.pin = self.part['pins'][0]
        self.pin['type'] = 'INPUT'
        self.pin['unconnected_state'] = {
            'state': 'ENABLED', 'evidence': [{'source': 'source:synthetic', 'page': 1}]}
        self.catalog = Catalog.__new__(Catalog)
        data['source']['license_class'] = 'PUBLIC_REFERENCE'
        self.catalog.records = {data['source']['id']: data['source']}
        self.catalog.vocabulary = Vocabulary.load(ROOT / 'knowledge/registry', ROOT / 'schemas')
        self.parts = {'U1': self.part}

    def test_source_backed_input_may_float_and_preserves_exact_evidence(self):
        validate(self.part, 'part.schema.json')
        validate_unconnected_states(self.catalog, self.part)
        checks = {c['id']: c for c in electrical_checks(self.parts, [])}
        check = checks['connection:U1:1']
        self.assertEqual(check['result'], 'PASS')
        self.assertEqual(check['unconnected_state'], self.pin['unconnected_state'])
        validate_default_checks(self.parts, [], checks)

    def test_ordinary_input_still_requires_connection(self):
        del self.pin['unconnected_state']
        checks = electrical_checks(self.parts, [])
        self.assertEqual(next(c for c in checks if c['id'] == 'connection:U1:1')['result'], 'FAIL')

    def test_connected_input_does_not_apply_unconnected_state(self):
        nets = [{'name': 'ENA', 'pins': [{'ref': 'U1', 'pin': '1'}]}]
        checks = {c['id']: c for c in electrical_checks(self.parts, nets)}
        self.assertEqual(checks['connection:U1:1']['result'], 'PASS')
        self.assertNotIn('unconnected_state', checks['connection:U1:1'])
        validate_default_checks(self.parts, nets, checks)
        checks['connection:U1:1']['unconnected_state'] = self.pin['unconnected_state']
        with self.assertRaisesRegex(ValueError, 'differ'):
            validate_default_checks(self.parts, nets, checks)

    def test_missing_empty_and_malformed_evidence_fail_schema(self):
        for value in ({'state': 'ENABLED'}, {'state': 'ENABLED', 'evidence': []},
                      {'state': 'ENABLED', 'evidence': [{'source': 'bad', 'page': 0}]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                part = deepcopy(self.part)
                part['pins'][0]['unconnected_state'] = value
                validate(part, 'part.schema.json')

    def test_unknown_state_and_wrong_pin_types_are_rejected(self):
        self.pin['unconnected_state']['state'] = 'GUESS'
        with self.assertRaisesRegex(ValueError, 'Unknown unconnected-states'):
            validate_unconnected_states(self.catalog, self.part)
        self.pin['unconnected_state']['state'] = 'ENABLED'
        for kind in ('POWER_IN', 'GROUND', 'OUTPUT', 'ANALOG', 'PASSIVE', 'BIDIRECTIONAL'):
            self.pin['type'] = kind
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'only for INPUT'):
                validate_unconnected_states(self.catalog, self.part)

    def test_missing_invalid_and_blocked_sources_are_rejected(self):
        source = self.catalog.records['source:synthetic']
        for license_class in ('UNKNOWN', 'RESTRICTED', 'LICENSED_BLOCKED_FOR_AI'):
            source['license_class'] = license_class
            with self.subTest(license=license_class), self.assertRaisesRegex(ValueError, 'License blocks'):
                validate_unconnected_states(self.catalog, self.part)
        source['license_class'] = 'PUBLIC_REFERENCE'
        self.pin['unconnected_state']['evidence'][0]['page'] = 2
        with self.assertRaisesRegex(ValueError, 'outside source'):
            validate_unconnected_states(self.catalog, self.part)
        self.catalog.records.clear()
        with self.assertRaisesRegex(ValueError, 'Missing source'):
            validate_unconnected_states(self.catalog, self.part)

    def test_omitted_or_forged_handoff_default_is_rejected(self):
        checks = {c['id']: c for c in electrical_checks(self.parts, [])}
        for replacement in (None, {'state': 'DISABLED', 'evidence': self.pin['unconnected_state']['evidence']}):
            bad = deepcopy(checks)
            if replacement is None:
                del bad['connection:U1:1']['unconnected_state']
            else:
                bad['connection:U1:1']['unconnected_state'] = replacement
            with self.assertRaisesRegex(ValueError, 'differ'):
                validate_default_checks(self.parts, [], bad)


if __name__ == '__main__':
    unittest.main()
