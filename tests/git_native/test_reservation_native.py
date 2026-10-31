"""Tool-free native adapter policy probes, using explicit synthetic shape responses."""
import types
import unittest
from unittest.mock import patch
from pcbknowledge.v2.reservation_native import _blockers
from tests.git_native.test_reservation_core import CANDIDATE


class Shape:
    def __init__(self, hits):
        self.hits = hits

    def Collide(self, other, clearance):
        return (other[0], clearance) in self.hits


class Item:
    def __init__(self, net='OTHER', hits=(), holes=(), locked=False, uid='one'):
        self.net, self.hits, self.holes, self.locked = net, hits, holes, locked
        self.m_Uuid = types.SimpleNamespace(AsString=lambda: uid)

    def IsLocked(self):
        return self.locked

    def IsOnLayer(self, layer):
        return layer == 0

    def GetNetname(self):
        return self.net

    def GetEffectiveShape(self, layer):
        return Shape(self.hits)

    def HasDrilledHole(self):
        return bool(self.holes)

    def GetEffectiveHoleShape(self):
        return Shape(self.holes)


def blockers(item):
    module = types.SimpleNamespace(F_Cu=0, B_Cu=31, VECTOR2I=lambda x, y: (x, y),
                                   SHAPE_SEGMENT=lambda a, b, w: ('line', w),
                                   SHAPE_CIRCLE=lambda p, r: ('circle', r))
    settings = types.SimpleNamespace(m_MinClearance=200000, m_HoleClearance=300000,
                                     m_HoleToHoleMin=400000)
    native = types.SimpleNamespace(GetTracks=lambda: [item], GetDesignSettings=lambda: settings)
    with patch.dict('sys.modules', {'pcbnew': module}):
        return _blockers(native, {'one': ['segment']}, CANDIDATE, {'clearance': .15})


class ReservationNativeTests(unittest.TestCase):
    def test_source_project_stronger_copper_floor(self):
        self.assertEqual(len(blockers(Item(hits={('line', 200000)}))), 1)
        self.assertEqual(blockers(Item(hits={('line', 150000)})), [])

    def test_same_net_holes_still_block(self):
        self.assertEqual(len(blockers(Item(net='N', holes={('line', 300000)}))), 1)
        self.assertEqual(len(blockers(Item(net='N', holes={('circle', 400000)}))), 1)

    def test_same_net_ordinary_copper_does_not_require_ripup(self):
        self.assertEqual(blockers(Item(net='N', hits={('line', 200000)})), [])

    def test_unknown_or_locked_item_rejected(self):
        for item in (Item(locked=True), Item(uid='unknown')):
            with self.assertRaises(ValueError):
                blockers(item)


if __name__ == '__main__':
    unittest.main()
