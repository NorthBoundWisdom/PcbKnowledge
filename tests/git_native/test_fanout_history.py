import copy
import unittest
from pcbknowledge.v2.fanout_history import combine
from tests.git_native.test_fanout_solver import candidate


def proposal(uuid, x):
    return {'rules':{'clearance':.15},'source_sha256':'hash','source_files_sha256':{'source':'hash'},
            'requests':[dict(uuid=uuid,reference='U'+str(x),pad='1',net='N'+str(x))],
            'verified_candidates':{uuid:[candidate('N'+str(x),[x,0],[x,2])]}}


class HistoryTests(unittest.TestCase):
    def test_union_all_endpoints_and_repeated_physical_provenance(self):
        a,b=proposal('first',0),proposal('second',3)
        repeated=proposal('new-native-uuid',0)
        result=combine([a,b,repeated])
        self.assertEqual(set(result['allocation']),{'first','second'})
        self.assertEqual(len(result['endpoint_provenance']['first']),2)
        self.assertEqual(len(result['requests']),2)

    def test_authority_change_and_missing_endpoint_rejected(self):
        a,b=proposal('a',0),proposal('b',3)
        b['source_sha256']='changed'
        with self.assertRaises(ValueError):combine([a,b])
        b=proposal('b',3);b['verified_candidates']['b']=[]
        with self.assertRaises(ValueError):combine([a,b])

    def test_union_reallocates_jointly_not_independent_overlaps(self):
        with self.assertRaises(ValueError):combine([proposal('a',0),proposal('b',.5)])

if __name__=='__main__':unittest.main()
