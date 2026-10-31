import unittest
from pcbknowledge.v2.fanout_anchors import attachment_points, inside_pad


class AnchorTests(unittest.TestCase):
    def test_rectangle_strict_interior_not_edge_or_outside(self):
        self.assertTrue(inside_pad([.9,.4],[2,1],'rect'))
        self.assertFalse(inside_pad([1,0],[2,1],'rect'))
        self.assertFalse(inside_pad([1.1,0],[2,1],'rect'))

    def test_rotated_rectangle_local_offsets(self):
        points=attachment_points([10,20],[4,2],90,'rect')
        self.assertEqual(points[0],[10,20]);self.assertEqual(points[1],[10,20.25]);self.assertIn([10,21],points)
        self.assertEqual(len(points),25)

    def test_oval_capsule_not_bounding_box(self):
        self.assertTrue(inside_pad([1.5,.5],[4,2],'oval'))
        self.assertFalse(inside_pad([1.8,.8],[4,2],'oval'))
        self.assertFalse(inside_pad([2,0],[4,2],'oval'))
        self.assertTrue(inside_pad([.5,1.5],[2,4],'oval'))

    def test_circle_and_unsupported_fail_closed(self):
        self.assertFalse(inside_pad([1,0],[2,2],'circle'))
        with self.assertRaises(ValueError):inside_pad([0,0],[2,1],'circle')
        with self.assertRaises(ValueError):attachment_points([0,0],[2,1],0,'custom')

if __name__=='__main__':unittest.main()
