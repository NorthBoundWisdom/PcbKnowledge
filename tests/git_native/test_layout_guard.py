"""Measured guard enclosure, full protected copper extents and contact mutations."""
import copy
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.layout import LayoutChecks
from pcbknowledge.v2.layout_guard import check_guard_ring


def pad(at, net, size=(.2, .2)):
    return {'at': at, 'net': net, 'kind': 'smd', 'shape': 'rect', 'size': list(size),
            'rotation': 0, 'layers': ['F.Cu'], 'geometry_unsupported': False}


def board():
    corners = [[0, 0], [4, 0], [4, 4], [0, 4]]
    return {'unsupported': [], 'copper_layers': ['F.Cu', 'B.Cu'], 'arcs': [], 'vias': [], 'zones': [],
            'outline': {'closed': True, 'rectangular': True, 'bounds': [-1, -1, 5, 5]},
            'segments': [{'start': a, 'end': b, 'width': .3, 'layer': 'F.Cu', 'net': 'BIAS'}
                         for a, b in zip(corners, corners[1:] + corners[:1])],
            'footprints': {'U1': {'pads': {'1': [pad([2, 2], 'SUM')], '2': [pad([0, 0], 'BIAS')]}}}}


RULE = {'kind': 'GUARD_RING', 'net': 'SUM', 'guard_net': 'BIAS',
        'min_clearance': {'value': .2, 'unit': 'mm'}, 'min_width': {'value': .25, 'unit': 'mm'}}


class GuardRingTests(unittest.TestCase):
    def test_closed_enclosure_reports_measurements_and_registers(self):
        sample = board()
        original = copy.deepcopy(sample)
        report = check_guard_ring(sample, RULE)
        self.assertEqual(report['result'], 'PASS')
        self.assertEqual(report['closed_segments'], 4)
        self.assertEqual(report['layer'], 'F.Cu')
        self.assertEqual(report['min_width_mm'], .3)
        self.assertAlmostEqual(report['min_clearance_mm'], 1.75)
        self.assertEqual(sample, original)
        checker = LayoutChecks.__new__(LayoutChecks)
        checker.board = sample
        self.assertEqual(checker.check(RULE), report)

    def test_broken_and_narrow_ring_fail(self):
        sample = board()
        sample['segments'].pop()
        report = check_guard_ring(sample, RULE)
        self.assertEqual(report['result'], 'FAIL')
        self.assertEqual(len(report['open_endpoints']), 2)
        self.assertAlmostEqual(report['nearest_open_gap_mm'], 3.7)
        sample = board()
        sample['segments'][0]['width'] = .249999
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'FAIL')

    def test_exact_clearance_boundary_and_copper_outside_with_center_inside(self):
        sample = board()
        protected = sample['footprints']['U1']['pads']['1'][0]
        protected['at'] = [.45, 2]
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'PASS')
        protected['at'][0] = .449999
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'FAIL')
        protected.update(at=[.2, 2], size=[.6, .2])
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'FAIL')

    def test_all_sensitive_pads_tracks_and_guard_feed_copper_are_checked(self):
        for change in ('pad', 'track', 'feed', 'guard_pad'):
            sample = board()
            if change == 'pad':
                sample['footprints']['U1']['pads']['3'] = [pad([4.5, 2], 'SUM')]
            elif change == 'guard_pad':
                sample['footprints']['U1']['pads']['3'] = [pad([2, 2], 'BIAS')]
            else:
                start, end = ([2, 2], [4.5, 2]) if change == 'track' else ([0, 0], [2, 2])
                sample['segments'].append({'start': start, 'end': end, 'width': .2,
                                           'net': 'SUM' if change == 'track' else 'BIAS', 'layer': 'F.Cu'})
            self.assertEqual(check_guard_ring(sample, RULE)['result'], 'FAIL')

    def test_floating_guard_and_wrong_layer_fail(self):
        sample = board()
        sample['footprints']['U1']['pads']['2'][0]['at'] = [2, 3]
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'FAIL')
        sample = board()
        for track in sample['segments']:
            track['layer'] = 'B.Cu'
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'FAIL')

    def test_connected_feed_branch_establishes_guard_contact(self):
        sample = board()
        sample['footprints']['U1']['pads']['2'][0]['at'] = [-.5, 0]
        sample['segments'].append({'start': [-.5, 0], 'end': [0, 0], 'width': .3,
                                   'net': 'BIAS', 'layer': 'F.Cu'})
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'PASS')

    def test_unknown_geometry_and_unmodeled_slots_never_pass(self):
        for mutation in (lambda b: b['arcs'].append({'net': 'SUM'}),
                         lambda b: b['vias'].append({'net': 'BIAS'}),
                         lambda b: b['outline'].update(closed=False),
                         lambda b: b['footprints']['U1']['pads']['1'][0].update(rotation=45),
                         lambda b: b['segments'][0].update(start=[.1, 0])):
            sample = board()
            mutation(sample)
            self.assertEqual(check_guard_ring(sample, RULE)['result'], 'NOT_CHECKABLE')

    def test_through_pad_with_top_track_does_not_hide_bottom_exposure(self):
        sample = board()
        sample['footprints']['U1']['pads']['1'][0].update(layers=['*.Cu'], kind='thru_hole', drill=.05)
        sample['segments'].append({'start': [2, 2], 'end': [2.5, 2], 'width': .2,
                                   'net': 'SUM', 'layer': 'F.Cu'})
        report = check_guard_ring(sample, RULE)
        self.assertEqual(report['result'], 'FAIL')
        self.assertEqual(report['surfaces'][1]['layer'], 'B.Cu')
        self.assertEqual(report['surfaces'][1]['result'], 'FAIL')

    def test_possible_pad_bridge_is_unknown_not_a_false_broken_ring(self):
        sample = board()
        sample['segments'].pop()
        sample['footprints']['U1']['pads']['2'][0].update(at=[0, 2], size=[.2, 4.2])
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'NOT_CHECKABLE')

    def test_real_board_projection_on_both_surfaces(self):
        text = '''(kicad_pcb (version 20241229)
          (layers (0 "F.Cu" signal) (31 "B.Cu" signal)) (net 1 "SUM") (net 2 "BIAS")
          (gr_rect (start -1 -1) (end 5 5) (layer "Edge.Cuts"))
          (footprint "Test:Guard" (layer "F.Cu") (at 0 0) (property "Reference" "U1")
            (pad "1" smd rect (at 2 2) (size 0.2 0.2) (layers "F.Cu") (net 1 "SUM"))
            (pad "2" smd rect (at 0 0) (size 0.2 0.2) (layers "F.Cu") (net 2 "BIAS")))
          (segment (start 0 0) (end 4 0) (width 0.3) (layer "F.Cu") (net 2))
          (segment (start 4 0) (end 4 4) (width 0.3) (layer "F.Cu") (net 2))
          (segment (start 4 4) (end 0 4) (width 0.3) (layer "F.Cu") (net 2))
          (segment (start 0 4) (end 0 0) (width 0.3) (layer "F.Cu") (net 2)))'''
        for side in ('F.Cu', 'B.Cu'):
            changed = text.replace('(layer "F.Cu")', f'(layer "{side}")')
            changed = changed.replace('(layers "F.Cu")', f'(layers "{side}")')
            sample = board_from_text(changed)
            result = check_guard_ring(sample, RULE)
            self.assertEqual(result['result'], 'PASS')
            self.assertEqual(result['layer'], side)

    def test_two_surface_through_pad_guard_with_proven_via_feed(self):
        sample = board()
        sample['footprints']['U1']['pads']['1'][0].update(layers=['*.Cu'], kind='thru_hole', drill=.05)
        sample['footprints']['U1']['pads']['2'][0]['at'] = [-.5, 0]
        sample['segments'] += [{**track, 'layer': 'B.Cu'} for track in sample['segments']]
        sample['segments'].append({'start': [-.5, 0], 'end': [0, 0], 'width': .3,
                                   'net': 'BIAS', 'layer': 'F.Cu'})
        sample['vias'] = [{'at': [0, 0], 'size': .8, 'drill': .2, 'net': 'BIAS',
                           'layers': ['F.Cu', 'B.Cu']}]
        report = check_guard_ring(sample, RULE)
        self.assertEqual(report['result'], 'PASS', report)
        self.assertEqual([item['result'] for item in report['surfaces']], ['PASS', 'PASS'])
        self.assertEqual(len(report['via_connections']), 1)
        for mutation, expected in ((lambda b: b['vias'].clear(), 'FAIL'),
                                   (lambda b: b['segments'].pop(7), 'FAIL'),
                                   (lambda b: b['vias'][0].update(size=.6), 'FAIL'),
                                   (lambda b: b['vias'][0].update(at=[.01, 0]), 'NOT_CHECKABLE')):
            changed = copy.deepcopy(sample)
            mutation(changed)
            self.assertEqual(check_guard_ring(changed, RULE)['result'], expected)

    def test_remote_surface_feed_cannot_cross_a_physical_void(self):
        sample = board()
        sample['footprints']['U1']['pads']['1'][0]['layers'] = ['B.Cu']
        sample['footprints']['U1']['pads']['2'][0]['at'] = [-.8, 0]
        for track in sample['segments']:
            track['layer'] = 'B.Cu'
        sample['segments'].append({'start': [-.8, 0], 'end': [0, 0], 'width': .3,
                                   'layer': 'F.Cu', 'net': 'BIAS'})
        sample['vias'] = [{'at': [0, 0], 'size': .8, 'drill': .2, 'net': 'BIAS',
                           'layers': ['F.Cu', 'B.Cu']}]
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'PASS')
        sample['footprints']['U1']['pads']['3'] = [
            {**pad([-.4, 0], ''), 'kind': 'np_thru_hole', 'drill': .4}]
        self.assertEqual(check_guard_ring(sample, RULE)['result'], 'NOT_CHECKABLE')
