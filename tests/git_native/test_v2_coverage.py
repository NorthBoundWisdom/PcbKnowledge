"""Coverage must not promote incomplete or unevidenced selections."""
import copy
import unittest
from types import SimpleNamespace
from pcbknowledge.v2.coverage import coverage


class CoverageTests(unittest.TestCase):
    def fixture(self):
        records = {
            'source:test': {'id':'source:test','verification':'AGENT_VERIFIED'},
            'package:test': {'id':'package:test','verification':'AGENT_VERIFIED'},
            'part:test': {'id':'part:test','package':'package:test','verification':'AGENT_VERIFIED',
                          'evidence':{'source':'source:test','page':1}},
            'block:test': {'id':'block:test','verification':'AGENT_VERIFIED','ports':[],
                          'components':[{'ref':'R','select':{'part':'part:test'}}],
                          'parameters':{'resistance':{'required':True,'quantity':'resistance',
                              'fixed':{'value':5100,'unit':'ohm'}}}}}
        def quantity(value, kind):
            if value.get('status') == 'UNKNOWN':return
            if value['unit'] != 'ohm':raise ValueError('Wrong canonical unit')
        catalog=SimpleNamespace(records=records,structure=lambda *_:None,
            get=lambda identity,*_:records[identity],_candidates=lambda _: [records['part:test']],
            vocabulary=SimpleNamespace(quantity=quantity))
        graph={'instances':[{'id':'usb','block':'block:test','ports':[],
                            'parameters':{'resistance':{'value':5100,'unit':'ohm'}}}]}
        return catalog, graph

    def test_fixed_inputs_units_and_duplicates(self):
        catalog,graph=self.fixture();self.assertEqual(coverage(catalog,graph)['percent'],100)
        for value in [{'value':1,'unit':'ohm'},{'value':5100,'unit':'V'}, {'status':'UNKNOWN'}]:
            changed=copy.deepcopy(graph);changed['instances'][0]['parameters']['resistance']=value
            self.assertEqual(coverage(catalog,changed)['status'],'INCOMPLETE')
        graph['instances'].append(copy.deepcopy(graph['instances'][0]))
        self.assertEqual(coverage(catalog,graph)['ready'],0)

    def test_source_verification_and_undeclared_inputs(self):
        catalog,graph=self.fixture();catalog.records['source:test']['verification']='DRAFT'
        self.assertEqual(coverage(catalog,graph)['status'],'INCOMPLETE')
        catalog.records['source:test']['verification']='AGENT_VERIFIED'
        graph['instances'][0]['parameters']['surprise']={'value':1,'unit':'ohm'}
        self.assertEqual(coverage(catalog,graph)['status'],'INCOMPLETE')
