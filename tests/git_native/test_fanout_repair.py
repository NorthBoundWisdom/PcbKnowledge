import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pcbknowledge.v2.fanout_repair import repair_routes


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.build=self.root/'build';self.build.mkdir()
        self.original=self.build/'source.kicad_pcb';self.original.write_text('original')
        for suffix in ('.kicad_pro','.kicad_dru'):self.original.with_suffix(suffix).write_text('authority')
        self.board=self.build/'prior.kicad_pcb';self.board.write_text('prior')
        self.drc=self.build/'prior.json';self.drc.write_text(json.dumps({'report':{'violations':[], 'schematic_parity':[], 'unconnected_items':[{}]}}))
        self.intent=self.build/'intent.json';self.intent.write_text('{}')
        (self.build/'graph.json').write_text('{}')
        validation=patch('pcbknowledge.v2.expansion.validate_expansion')
        self.validation=validation.start();self.addCleanup(validation.stop)
        self.bundle=self.build/'bundle.json';self.bundle.write_text('{}')

    def run_repair(self,budget):
        return repair_routes(self.original,self.board,self.drc,self.intent,self.bundle,{},self.build/'repairs',
                             root=self.root,max_repairs=budget,initial_router_seconds=2.5)

    @patch('pcbknowledge.v2.fanout_repair.Bundle')
    @patch('pcbknowledge.v2.fanout_repair._attempt')
    def test_zero_budget_no_subprocess(self,attempt,bundle):
        r=self.run_repair(0)
        self.assertEqual(r['status'],'FAIL');self.assertEqual(r['router_seconds_total'],2.5)
        attempt.assert_not_called()

    @patch('pcbknowledge.v2.fanout_repair.Bundle')
    @patch('pcbknowledge.v2.fanout_repair.extract_requests',return_value={'requests':[{'uuid':'synthetic'}],'physical_ids':{'synthetic':['U1','1','N',0,0]}})
    @patch('pcbknowledge.v2.fanout_repair._attempt')
    def test_prepare_failure_does_not_retry(self,attempt,selection,bundle):
        def failed(*args):args[2].mkdir();return {'status':'FAIL','reason':'unsupported geometry'}
        attempt.side_effect=failed
        r=self.run_repair(3)
        self.assertEqual(len(r['attempts']),1);self.assertEqual(r['status'],'FAIL')
        self.assertEqual(self.original.read_text(),'original')

    @patch('pcbknowledge.v2.fanout_repair.Bundle')
    @patch('pcbknowledge.v2.fanout_repair.extract_requests',return_value={'requests':[{'uuid':'synthetic'}],'physical_ids':{'synthetic':['U1','1','N',0,0]}})
    @patch('pcbknowledge.v2.fanout_repair._attempt')
    def test_final_success_stops_and_sums_measured_router_time(self,attempt,selection,bundle):
        def success(*args):
            directory=args[2];directory.mkdir()
            return {'status':'PASS','board':str(self.board),'drc_path':str(self.drc),
                    'route':{'router':{'runtime_seconds':3.25}}}
        attempt.side_effect=success
        r=self.run_repair(3)
        self.assertEqual(r['status'],'PASS');self.assertEqual(len(r['attempts']),1)
        self.assertEqual(r['router_seconds_total'],5.75)

    @patch('pcbknowledge.v2.fanout_repair.Bundle')
    @patch('pcbknowledge.v2.fanout_repair.extract_requests',return_value={'requests':[{'uuid':'synthetic'}],'physical_ids':{'synthetic':['U1','1','N',0,0]}})
    @patch('pcbknowledge.v2.fanout_repair._attempt')
    def test_downstream_failure_preserves_measured_route_receipt(self,attempt,selection,bundle):
        def failed_after_route(*args):
            args[2].mkdir()
            args[-1]['route']={'router':{'runtime_seconds':4.5},'status':'PASS'}
            raise ValueError('native report unreadable')
        attempt.side_effect=failed_after_route
        result=self.run_repair(2)
        self.assertEqual(result['router_seconds_total'],7.0)
        self.assertEqual(result['attempts'][0]['route']['status'],'PASS')
        self.assertEqual(result['status'],'FAIL')

    @patch('pcbknowledge.v2.fanout_repair.Bundle')
    def test_authentication_failure_creates_no_repair_output(self,bundle):
        self.validation.side_effect=ValueError('intent does not replay from graph')
        with self.assertRaises(ValueError):self.run_repair(1)
        self.assertFalse((self.build/'repairs').exists())

    @patch('pcbknowledge.v2.fanout_repair.Bundle')
    @patch('pcbknowledge.v2.fanout_repair.extract_requests',return_value={'requests':[{'uuid':'synthetic'}],'physical_ids':{'synthetic':['U1','1','N',0,0]}})
    @patch('pcbknowledge.v2.fanout_repair._attempt')
    def test_source_mutation_overrides_apparent_success(self,attempt,selection,bundle):
        def mutated(*args):
            args[2].mkdir()
            self.original.write_text('changed')
            return {'status':'PASS','board':str(self.board),'drc_path':str(self.drc)}
        attempt.side_effect=mutated
        result=self.run_repair(1)
        self.assertEqual(result['status'],'FAIL')
        self.assertIn('authority changed',result['reason'])

if __name__=='__main__':unittest.main()
