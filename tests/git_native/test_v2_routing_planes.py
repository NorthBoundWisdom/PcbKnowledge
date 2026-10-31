"""Plane projection changes no boundary, rule, pad, keepout or source board."""
from copy import deepcopy
import unittest
from pcbknowledge.v2.routing_planes import project_routing_planes
from pcbknowledge.v2.specctra import read_specctra

DSN = '''(pcb test (unit mm) (structure (layer F.Cu) (layer B.Cu)
 (plane P (polygon F.Cu 0 0 0 10 0 10 10 0 10))
 (boundary (path pcb 0 0 0 10 0 10 10 0 10))
 (keepout fixed (circle F.Cu 2 3 4)) (rule (width .3) (clearance .15)))
 (library (image chip (pin PAD 1 2 3))) (network (net P (pins U1-1))))'''


def board():
    return {'nets': {'1': 'P'}, 'zones': [{'net': 'P', 'layer': 'F.Cu', 'filled_polygons': []}]}


class PlaneTests(unittest.TestCase):
    def test_exact_structural_change_is_only_plane_deletion_and_board_immutable(self):
        source = board()
        before = deepcopy(source)
        text, receipt = project_routing_planes(DSN, source)
        expected = read_specctra(DSN)
        structure = expected[3]
        structure[:] = [item for item in structure if not isinstance(item, list) or item[0] != 'plane']
        self.assertEqual(read_specctra(text), expected)
        self.assertEqual(source, before)
        self.assertEqual(receipt['excluded_planes'], [{'net': 'P', 'layer': 'F.Cu'}])
        self.assertTrue(receipt['source_zones_retained'])

    def test_malformed_unknown_and_unmatched_planes_fail(self):
        for old, new in [('plane P', 'plane WRONG'), ('polygon F.Cu', 'polygon In1.Cu'),
                         ('polygon F.Cu 0', 'polygon F.Cu 1'), ('10 10 0 10', '10 10 0'),
                         ('polygon F.Cu', 'circle F.Cu'), ('10 10 0 10', 'nan 10 0 10')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                project_routing_planes(DSN.replace(old, new, 1), board())
        value = board()
        value['zones'] = []
        with self.assertRaises(ValueError):
            project_routing_planes(DSN, value)

    def test_filled_zone_proof_is_not_silently_discarded(self):
        value = board()
        value['zones'][0]['filled_polygons'] = [[[0, 0], [1, 0], [1, 1]]]
        with self.assertRaises(ValueError):
            project_routing_planes(DSN, value)

    def test_no_planes_no_other_changes(self):
        text, _ = project_routing_planes(DSN, board())
        result, receipt = project_routing_planes(text, board())
        self.assertEqual(read_specctra(result), read_specctra(text))
        self.assertEqual(receipt['excluded_plane_count'], 0)
