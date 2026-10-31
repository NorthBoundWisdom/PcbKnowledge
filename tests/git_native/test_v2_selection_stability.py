"""Verified catalog growth cannot silently choose a different manufacturer's part."""
from copy import deepcopy
from pathlib import Path
import unittest

from pcbknowledge.v2.catalog import Catalog, selected_candidate

ROOT = Path(__file__).resolve().parents[2]


def ambiguous_selections(catalog):
    found = []
    for block in catalog.search('block'):
        for component in block['components']:
            choices = [part for part in catalog._candidates(component['select'])
                       if part['verification'] in ('AGENT_VERIFIED', 'HUMAN_VERIFIED')]
            if len({part['mpn'] for part in choices}) > 1:
                found.append((block['id'], component['ref'], sorted(part['id'] for part in choices)))
    return found


class SelectionStabilityTests(unittest.TestCase):
    def test_committed_catalog_has_no_ambiguous_verified_mpn_selection(self):
        self.assertEqual(ambiguous_selections(Catalog(ROOT, ROOT / 'schemas')), [])

    def test_growth_guard_detects_new_verified_alternative(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        alternate = deepcopy(catalog.get('part:yageo-rc0603fr-0710kl'))
        alternate.update(id='part:synthetic-alternative', mpn='SYNTHETIC-DIFFERENT-MPN')
        catalog.records[alternate['id']] = alternate
        component = catalog.get('block:button-input')['components'][0]
        component['select'] = {'role': 'resistor', 'match': {'resistance': {'value': 10000, 'unit': 'ohm'}}}
        self.assertTrue(ambiguous_selections(catalog))

    def test_pinned_bulk_capacitors_ignore_earlier_verified_id(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        alternate = deepcopy(catalog.get('part:kemet-c0805c106k3pactu'))
        alternate.update(id='part:aaa-earlier-alternative', mpn='SYNTHETIC-DIFFERENT-MPN')
        catalog.records[alternate['id']] = alternate
        block = catalog.get('block:mcu-core')
        for component in block['components']:
            if component['ref'] in ('C6', 'C7'):
                self.assertEqual(component['select'], {'part': 'part:kemet-c0805c106k3pactu'})
                choices = catalog._candidates(component['select'])
                self.assertEqual(selected_candidate(choices)['id'], 'part:kemet-c0805c106k3pactu')


    def test_precision_resistor_promotion_preserves_existing_ten_kilohm_choices(self):
        catalog = Catalog(ROOT, ROOT / 'schemas')
        for name, refs in [('mcu-core', ('R1', 'R2', 'R3')), ('button-input', ('R1',))]:
            block = catalog.get('block:' + name)
            for component in block['components']:
                if component['ref'] in refs:
                    self.assertEqual(component['select'], {'part': 'part:yageo-rc0603fr-0710kl'})


if __name__ == '__main__':
    unittest.main()
