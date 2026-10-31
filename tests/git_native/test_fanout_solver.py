import copy
import unittest
from pcbknowledge.v2.fanout_solver import allocate, compatible, segment_distance, bounded_candidates, MAX_CANDIDATES


def candidate(net, start, end, layer='F.Cu', width=.15):
    return dict(net=net, start=start, end=end, layer=layer, width=width, via_diameter=.8, via_drill=.3, bend=None)


class FanoutTests(unittest.TestCase):
    def test_joint_allocation_staggers_adjacent_vias(self):
        rows={'a':[candidate('A',[0,0],[-.5,1.2])],
              'b':[candidate('B',[.5,0],[0,1.2]),candidate('B',[.5,0],[1.,2.5])]}
        before=copy.deepcopy(rows)
        result=allocate(rows,.15)
        self.assertEqual(result['allocation']['b']['end'],[1.,2.5])
        self.assertEqual(rows,before)
        self.assertEqual(result,allocate(dict(reversed(list(rows.items()))),.15))

    def test_crossing_traces_rejected(self):
        a=candidate('A',[-2,0],[2,0]);b=candidate('B',[0,-2],[0,2])
        self.assertFalse(compatible(a,b,.15))
        b['layer']='B.Cu'
        self.assertTrue(compatible(a,b,.15))

    def test_through_via_blocks_opposite_layer_trace(self):
        a=candidate('A',[0,0],[2,0]);b=candidate('B',[1,-2],[1,.1],'B.Cu')
        self.assertFalse(compatible(a,b,.15))

    def test_same_net_still_has_distinct_drills(self):
        self.assertFalse(compatible(candidate('A',[0,0],[0,1]),candidate('A',[1,0],[.5,1]),.15))

    def test_no_relaxation_or_partial_success(self):
        rows={'a':[candidate('A',[0,0],[0,1])],'b':[candidate('B',[.5,0],[.5,1])]}
        with self.assertRaisesRegex(ValueError,'No joint'):allocate(rows,.15)
        rows['b'].append(candidate('B',[.5,0],[.5,3]))
        with self.assertRaisesRegex(ValueError,'budget'):allocate(rows,.15,max_search_nodes=1)

    def test_reject_changing_width_net_origin(self):
        for key,value in [('width',.1),('net','X'),('start',[9,9])]:
            a=candidate('A',[0,0],[0,1]);b=copy.deepcopy(a);b[key]=value
            with self.assertRaisesRegex(ValueError,'changed'):allocate({'a':[a,b]},.15)

    def test_invalid_geometry_and_empty_candidates(self):
        for rows in [{},{'a':[]},{'a':[candidate('A',[0,0],[float('nan'),1])]},
                     {'a':[candidate('A',[0,0],[1e308,1])]},
                     {'a':[candidate('A',[-1e308,0],[0,1])]}]:
            with self.assertRaises(ValueError):allocate(rows,.15)

    def test_dogleg_corner_and_second_segment_block(self):
        a=candidate('A',[0,0],[2,1]);a['bend']=[1,0]
        b=candidate('B',[1.5,-1],[1.5,2])
        self.assertFalse(compatible(a,b,.15))
        b=candidate('B',[3,0],[1.1,-.1],'B.Cu')
        self.assertFalse(compatible(a,b,.15))

    def test_joint_doglegs_resolve_parallel_via_trace_conflict(self):
        a=candidate('A',[0,0],[0,2]);b=candidate('B',[.5,0],[.5,3])
        self.assertFalse(compatible(a,b,.15))
        a['bend']=[0,1];a['end']=[-1,2]
        b['bend']=[.5,1];b['end']=[1.5,2]
        self.assertTrue(compatible(a,b,.15))
        self.assertEqual(len(allocate({'a':[a],'b':[b]},.15)['allocation']),2)

    def test_90_degree_candidate_when_45_degree_path_collides(self):
        right=candidate('A',[0,0],[2,1]);right['bend']=[0,1]
        diagonal=candidate('A',[0,0],[2,3]);diagonal['bend']=[0,1]
        barrier=candidate('B',[1,2],[3,2])
        self.assertTrue(compatible(right,barrier,.15))
        self.assertFalse(compatible(diagonal,barrier,.15))
        result=allocate({'a':[diagonal,right],'b':[barrier]},.15)
        self.assertEqual(result['allocation']['a']['end'],[2,1])

    def test_third_leg_reaches_via_landing_outside_narrow_corridor(self):
        short=candidate('A',[0,1.5],[2,.5]);short['bend']=[0,.5]
        obstacle=candidate('B',[1,0],[5,0])
        self.assertFalse(compatible(short,obstacle,.15))
        escaped=dict(short,bend2=[2,.5],end=[3,1.5])
        self.assertTrue(compatible(escaped,obstacle,.15))
        blocked_exit=candidate('C',[2,1],[4,1])
        self.assertFalse(compatible(escaped,blocked_exit,.15))
        self.assertEqual(len(allocate({'a':[short,escaped],'b':[obstacle]},.15)['allocation']),2)

    def test_candidate_domain_limit_is_explicit_and_deterministic(self):
        rows=[candidate('A',[0,0],[0,i+1]) for i in range(MAX_CANDIDATES+1)]
        retained,receipt=bounded_candidates(list(reversed(rows)))
        self.assertEqual(len(retained),MAX_CANDIDATES)
        self.assertEqual(receipt['legal_examined'],MAX_CANDIDATES+1)
        self.assertEqual(receipt['truncated'],1)
        self.assertEqual(retained,rows[:MAX_CANDIDATES])
        self.assertEqual(bounded_candidates(rows[:MAX_CANDIDATES])[1]['truncated'],0)

    def test_segment_geometry(self):
        self.assertEqual(segment_distance([0,0],[1,0],[2,0],[3,0]),1)
        self.assertEqual(segment_distance([0,0],[1,1],[0,1],[1,0]),0)
        self.assertEqual(segment_distance([0,0],[1,0],[0,1],[1,1]),1)


if __name__=='__main__':unittest.main()
