"""Nominal and guaranteed-bound matching follows ADR-024."""
import unittest
from pcbknowledge.v2.catalog import Catalog


class SelectionTests(unittest.TestCase):
    def candidates(self, value, request):
        catalog = object.__new__(Catalog)
        part = {'id':'part:example','parameters':{'output_voltage':value}}
        catalog.search = lambda *args, **kwargs: [part]
        return catalog._candidates({'role':'ldo.fixed','match':{'output_voltage':request}})

    def test_nominal_matches_value_or_typ_not_guaranteed_endpoints(self):
        for value in ({'value':3.3}, {'min':3.2,'typ':3.3,'max':3.4}, {'typ':3.3}):
            self.assertEqual(len(self.candidates({**value,'unit':'V'},{'value':3.3,'unit':'V'})),1)
        for value in ({'min':3.3,'max':3.3}, {'typ':3.2}, {'status':'UNKNOWN'}):
            with self.assertRaises(ValueError):
                self.candidates({**value,'unit':'V'},{'value':3.3,'unit':'V'})

    def test_bounds_require_guaranteed_limits_not_typical(self):
        self.candidates({'min':3.2,'typ':3.3,'max':3.4,'unit':'V'}, {'min':3.1,'max':3.5,'unit':'V'})
        self.candidates({'value':3.3,'unit':'V'}, {'min':3.2,'max':3.4,'unit':'V'})
        for value,request in [({'typ':3.3},{'min':3}),({'min':3.2},{'max':4}),
                              ({'min':3.2,'max':3.4},{'max':3.3}),
                              ({'value':3.3},{'status':'UNKNOWN'})]:
            with self.assertRaises(ValueError):
                self.candidates({**value,'unit':'V'},{**request,'unit':'V'})

    def test_units_cannot_match_by_number_alone(self):
        with self.assertRaises(ValueError):
            self.candidates({'value':3.3,'unit':'A'},{'value':3.3,'unit':'V'})
