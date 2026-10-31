import copy
import tempfile
import unittest
from pathlib import Path
from pcbknowledge.v2.fanout_native import checked_hash, checked_requests, native_pad_blocked


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(uuid='synthetic',reference='U1',pad='1',net='SIGNAL')
        self.index={'synthetic':self.row}

    def test_exact_request(self):
        self.assertEqual(checked_requests([self.row],self.index,{'synthetic'}),[self.row])

    def test_unknown_duplicate_nonfailed_and_wrong_net(self):
        for rows,index,failed in [([self.row,self.row],self.index,{'synthetic'}),
                                  ([self.row],{}, {'synthetic'}),
                                  ([self.row],self.index,set()),
                                  ([dict(self.row,net='WRONG')],self.index,{'synthetic'})]:
            with self.assertRaises(ValueError):checked_requests(rows,index,failed)

    def test_same_net_hole_obstacle_is_not_skipped(self):
        class Shape:
            def __init__(self, blocked): self.blocked=blocked
            def Collide(self, other, clearance): return self.blocked
        class Pad:
            def IsOnLayer(self, layer):return True
            def GetEffectiveShape(self, layer):return Shape(False)
            def HasDrilledHole(self):return True
            def GetEffectiveHoleShape(self):return Shape(True)
            def GetNetname(self):return 'SAME'
        self.assertTrue(native_pad_blocked(Pad(),'SAME',[object()],object(),150000,0,(0,2)))

    def test_source_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'board';path.write_text('original')
            import hashlib
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(checked_hash(path,digest),digest)
            path.write_text('mutated')
            with self.assertRaisesRegex(ValueError,'fingerprint'):checked_hash(path,digest)

if __name__=='__main__':unittest.main()
