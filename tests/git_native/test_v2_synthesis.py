"""Independent synthesis receipt and graph-equivalence evaluation contracts."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

from pcbknowledge.v2.synthesis import digest, evaluate, topology


def graph(identity='reference'):
    return {'id': identity, 'brief': 'G1', 'instances': [
        {'id':'source','block':'block:source','requirements':['power']},
        {'id':'load','block':'block:load','requirements':['load']}],
        'connections':[{'net':'supply','endpoints':[
            {'instance':'source','port':'OUT'},{'instance':'load','port':'IN'}]}]}


class SynthesisTests(unittest.TestCase):
    def test_topology_ignores_names_not_ports_or_blocks(self):
        original=graph();other=copy.deepcopy(original)
        other['instances'][0]['id']='another'
        other['connections'][0]['net']='different'
        other['connections'][0]['endpoints'][0]['instance']='another'
        self.assertEqual(topology(original),topology(other))
        other['connections'][0]['endpoints'][0]['port']='GROUND'
        self.assertNotEqual(topology(original),topology(other))

    def setup_attempts(self):
        bundle=SimpleNamespace(commit='a'*40,catalog=Mock(),briefs={'G1':{'id':'G1'}})
        attempts=[]
        for i in range(3):
            g=graph('attempt-'+str(i))
            attempts.append({'graph':g,'receipt':{'agent':'agent:independent-'+str(i),
                'reviewer':'agent:reviewer','bundle_commit':bundle.commit,
                'graph_sha256':digest(g),'brief_sha256':digest(bundle.briefs['G1']),
                'reference_accessed':False}})
        return bundle,attempts

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    @patch('pcbknowledge.v2.synthesis.expand',return_value={'status':'EXPANDED','checks':[],'refusals':[]})
    def test_counts_actual_attempts_and_refuses_bad_receipts(self,*_):
        bundle,attempts=self.setup_attempts()
        result=evaluate(bundle,graph(),attempts)
        self.assertEqual((result['status'],result['passed'],result['total']),('PASS',3,3))
        for change in ('agent','reviewer','reference_accessed','graph_sha256','bundle_commit'):
            bad=copy.deepcopy(attempts)
            bad[0]['receipt'][change]={'agent':'agent:independent-1','reviewer':'agent:independent-0',
                'reference_accessed':True,'graph_sha256':'bad','bundle_commit':'bad'}[change]
            with self.assertRaises(ValueError):evaluate(bundle,graph(),bad)
        with self.assertRaises(ValueError):evaluate(bundle,graph(),attempts[:2])

    @patch('pcbknowledge.v2.synthesis.validate_expansion')
    @patch('pcbknowledge.v2.synthesis.expand',return_value={'status':'REFUSED','checks':[],'refusals':['unsafe']})
    def test_expansion_refusal_is_not_a_pass(self,*_):
        bundle,attempts=self.setup_attempts();result=evaluate(bundle,graph(),attempts)
        self.assertEqual(result['status'],'FAIL');self.assertEqual(result['passed'],0)
