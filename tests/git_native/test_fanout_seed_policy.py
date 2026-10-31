import copy
import unittest
from pcbknowledge.v2.fanout_seed_policy import classify_seed


class SeedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.receipt=dict(board='/build/seed.kicad_pcb',output_sha256='hash',seed_via_uuids=['new'],
                          settings_sha256={'seed.kicad_pro':'project','seed.kicad_dru':'rules'})
        self.drc=dict(board='/build/seed.kicad_pcb',input_sha256={'seed.kicad_pcb':'hash','seed.kicad_pro':'project','seed.kicad_dru':'rules'},drc_status='FAIL',exit_code=5,finding_count=2,
                      report=dict(violations=[dict(type='via_dangling',severity='warning',items=[dict(uuid='new')])],
                                  unconnected_items=[{'type':'unconnected_items'}],schematic_parity=[]))

    def test_connectivity_incomplete_never_drc_pass(self):
        before=copy.deepcopy(self.drc)
        r=classify_seed(self.drc,self.receipt)
        self.assertTrue(r['routing_allowed']);self.assertEqual(r['status'],'INCOMPLETE')
        self.assertEqual(r['native_drc_status'],'FAIL');self.assertEqual(self.drc,before)
        self.assertEqual(r['violation_count'],1)

    def test_other_fault_unknown_uuid_duplicate_missing_are_blocked(self):
        for change in ['type','uuid','duplicate','missing']:
            d=copy.deepcopy(self.drc)
            if change=='type':d['report']['violations'][0]['type']='clearance'
            if change=='uuid':d['report']['violations'][0]['items'][0]['uuid']='old'
            if change=='duplicate':d['report']['violations']*=2
            if change=='missing':d['report']['violations']=[]
            d['finding_count']=sum(len(d['report'][k]) for k in ('violations','unconnected_items','schematic_parity'))
            self.assertFalse(classify_seed(d,self.receipt)['routing_allowed'])

    def test_changed_project_rules_are_rejected(self):
        for suffix in ('pro','dru'):
            d=copy.deepcopy(self.drc)
            d['input_sha256']['seed.kicad_'+suffix]='weakened'
            with self.assertRaises(ValueError):classify_seed(d,self.receipt)

    def test_unknown_process_state_or_inconsistent_count_rejected(self):
        for key,value in [('drc_status','NOT_RUN'),('exit_code',0),('finding_count',0)]:
            d=copy.deepcopy(self.drc);d[key]=value
            with self.assertRaises(ValueError):classify_seed(d,self.receipt)

    def test_wrong_source_hash_is_rejected(self):
        self.drc['input_sha256']['seed.kicad_pcb']='mutated'
        with self.assertRaises(ValueError):classify_seed(self.drc,self.receipt)

if __name__=='__main__':unittest.main()
