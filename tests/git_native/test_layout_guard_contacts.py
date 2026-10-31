"""Synthetic exact witnesses and unresolved contacts across two guard surfaces."""
import copy
import unittest

from pcbknowledge.v2.layout_guard_contacts import guard_connections


def track(start, end, layer='F.Cu'):
    return {'start': start, 'end': end, 'width': 0.2, 'layer': layer, 'net': 'GUARD'}


def fixture():
    tracks = [track([0, 0], [2, 0]), track([2, 0], [2, 2]),
              track([2, 2], [0, 2]), track([0, 2], [0, 0])]
    tracks.extend([dict(item, layer='B.Cu') for item in tracks.copy()])
    pad = {'at': [1, 0], 'size': [0.4, 0.4], 'shape': 'rect', 'kind': 'smd',
           'layers': ['F.Cu'], 'net': 'GUARD', 'rotation': 0, 'drill': None}
    board = {'footprints': {'U1': {'pads': {'1': [pad]}}},
             'vias': [{'at': [0, 0], 'size': 0.6, 'drill': 0.3,
                       'layers': ['F.Cu', 'B.Cu'], 'net': 'GUARD'}]}
    return board, tracks


class GuardContactTests(unittest.TestCase):
    def test_upper_pad_anchors_both_rings_through_annulus(self):
        board, tracks = fixture()
        result = guard_connections(board, 'GUARD', tracks)
        self.assertEqual(result['anchored_tracks'], set(range(8)))
        self.assertEqual(result['uncertain_tracks'], set())
        self.assertEqual(result['vias'][0]['proven_tracks'], [0, 3, 4, 7])
        self.assertTrue(result['vias'][0]['supported'])

    def test_wrong_net_or_disconnected_via_does_not_anchor_lower_ring(self):
        for change in ({'net': 'OTHER'}, {'at': [4, 4]}):
            board, tracks = fixture()
            board['vias'][0].update(change)
            result = guard_connections(board, 'GUARD', tracks)
            self.assertEqual(result['anchored_tracks'], {0, 1, 2, 3})
            self.assertFalse(result['uncertain_tracks'])

    def test_noncenter_overlap_is_uncertain_not_a_proven_bridge(self):
        board, tracks = fixture()
        board['vias'][0]['at'] = [0.05, 0]
        result = guard_connections(board, 'GUARD', tracks)
        self.assertEqual(result['anchored_tracks'], {0, 1, 2, 3})
        self.assertEqual(result['uncertain_tracks'], set(range(8)))
        self.assertFalse(result['vias'][0]['proven_tracks'])

    def test_unsupported_via_geometry_is_uncertain(self):
        for change in ({'geometry_unsupported': True}, {'size': 0.3}):
            board, tracks = fixture()
            board['vias'][0].update(change)
            result = guard_connections(board, 'GUARD', tracks)
            self.assertEqual(result['anchored_tracks'], {0, 1, 2, 3})
            self.assertEqual(result['uncertain_tracks'], set(range(8)))
            self.assertFalse(result['vias'][0]['supported'])

    def test_via_in_pad_is_not_assumed_to_bridge_drill_void(self):
        board, tracks = fixture()
        pad = board['footprints']['U1']['pads']['1'][0]
        pad.update(at=[0, 0], size=[0.05, 0.05])
        # No top tracks: only possible direct pad-to-via connection exists.
        result = guard_connections(board, 'GUARD', tracks[4:])
        self.assertFalse(result['anchored_tracks'])
        self.assertEqual(result['uncertain_tracks'], set(range(4)))
        self.assertTrue(result['vias'][0]['unproved_pad_contact'])

    def test_pad_track_contact_inside_a_drill_does_not_anchor_copper(self):
        board, tracks = fixture()
        board['footprints']['U1']['pads']['1'][0].update(at=[0, 0], size=[0.05, 0.05])
        result = guard_connections(board, 'GUARD', tracks)
        self.assertFalse(result['anchored_tracks'])
        self.assertEqual(result['uncertain_tracks'], set(range(8)))

    def test_remote_endpoint_must_be_strictly_beyond_drill_radius(self):
        board, _tracks = fixture()
        tracks = [track([0, 0], [0.15, 0], 'B.Cu')]
        result = guard_connections(board, 'GUARD', tracks)
        self.assertFalse(result['vias'][0]['proven_tracks'])
        self.assertEqual(result['uncertain_tracks'], {0})
        tracks[0]['end'] = [0.150001, 0]
        result = guard_connections(board, 'GUARD', tracks)
        self.assertEqual(result['vias'][0]['proven_tracks'], [0])

    def test_unsupported_pad_and_tangent_contact_are_not_roots(self):
        for change in ({'geometry_unsupported': True}, {'at': [1, 0.3]}):
            board, tracks = fixture()
            board['footprints']['U1']['pads']['1'][0].update(change)
            result = guard_connections(board, 'GUARD', tracks)
            self.assertFalse(result['anchored_tracks'])
            self.assertEqual(result['uncertain_tracks'], set(range(8)))

    def test_solid_pad_joins_disjoint_tracks_and_inputs_are_unchanged(self):
        board, _tracks = fixture()
        board['vias'] = []
        tracks = [track([0, 0], [0.9, 0]), track([1.1, 0], [2, 0]), track([2, 0], [2, 1])]
        original = copy.deepcopy((board, tracks))
        result = guard_connections(board, 'GUARD', tracks)
        self.assertEqual(result['anchored_tracks'], {0, 1, 2})
        self.assertEqual((board, tracks), original)

    def test_bad_track_inputs_refuse(self):
        for change in ({'net': 'OTHER'}, {'layer': 'In1.Cu'}, {'end': [0, 0]}, {'width': 0}):
            board, tracks = fixture()
            tracks[0].update(change)
            with self.assertRaises(ValueError):
                guard_connections(board, 'GUARD', tracks)


if __name__ == '__main__':
    unittest.main()
