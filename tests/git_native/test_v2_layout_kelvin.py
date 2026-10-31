"""Original tool-free Kelvin topology and finite-width geometry counterexamples."""
import copy
import unittest

from pcbknowledge.v2.boardview import board_from_text
from pcbknowledge.v2.layout_kelvin import MAX_PRIMITIVES, check_kelvin


def pad(x, y, net, size=(2, 2)):
    return {'at': [x, y], 'size': list(size), 'shape': 'rect', 'kind': 'smd', 'net': net,
            'layers': ['F.Cu'], 'rotation': 0, 'drill': None, 'geometry_unsupported': False}


def track(a, b, net='P', width=0.2, layer='F.Cu'):
    return {'start': list(a), 'end': list(b), 'net': net, 'width': width, 'layer': layer}


class Catalog:
    def get(self, identity, kind):
        if kind != 'part':
            raise ValueError('Unexpected catalog query')
        types = {'sense': ['ANALOG', 'ANALOG'], 'shunt': ['PASSIVE', 'PASSIVE'],
                 'load': ['POWER_IN', 'GROUND'], 'filter': ['PASSIVE', 'PASSIVE']}
        return {'pins': [{'number': str(i + 1), 'type': value} for i, value in enumerate(types[identity])]}


def fixture():
    footprints = {
        'U1': {'pads': {'1': [pad(-5, 3, 'P')], '2': [pad(-5, -3, 'N')]}},
        'R1': {'pads': {'1': [pad(0, 3, 'P')], '2': [pad(0, -3, 'N')]}},
        'J1': {'pads': {'1': [pad(5, 3, 'P')], '2': [pad(5, -3, 'N')]}},
    }
    board = {'outline': {'closed': True, 'rectangular': True, 'bounds': [-20, -20, 20, 20]},
             'footprints': footprints, 'segments': [track((-5, y), (0, y), net)
             for y, net in ((3, 'P'), (-3, 'N'))] + [track((0, y), (5, y), net)
             for y, net in ((3, 'P'), (-3, 'N'))], 'arcs': [], 'vias': [], 'zones': [], 'unsupported': []}
    rule = {'kind': 'KELVIN', 'target': 'R1', 'sense_nets': ['P', 'N'], 'branches': [
        {'sense': 'U1.pin:1', 'target': 'R1.pin:1'}, {'sense': 'U1.pin:2', 'target': 'R1.pin:2'}]}
    intent = {'components': [{'ref': ref, 'part': part}
                             for ref, part in [('U1', 'sense'), ('R1', 'shunt'), ('J1', 'load')]]}
    return board, rule, intent


def exported_board(board, extra=''):
    items = ['(kicad_pcb (net 0 "") (net 1 "P") (net 2 "N")']
    for ref, footprint in board['footprints'].items():
        items.append(f'(footprint "synthetic" (layer "F.Cu") (at 0 0) (property "Reference" "{ref}")')
        for number, pads in footprint['pads'].items():
            pad = pads[0]
            x, y = pad['at']
            net = 1 if pad['net'] == 'P' else 2
            items.append(f'(pad "{number}" smd rect (at {x} {y}) (size 2 2) (layers "F.Cu") (net {net}))')
        items.append(')')
    for segment in board['segments']:
        ax, ay = segment['start']
        bx, by = segment['end']
        net = 1 if segment['net'] == 'P' else 2
        items.append(f'(segment (start {ax} {ay}) (end {bx} {by}) (width 0.2) (layer "F.Cu") (net {net}))')
    items.append('(gr_rect (start -20 -20) (end 20 20) (layer "Edge.Cuts"))')
    return ''.join(items) + extra + ')'


class KelvinTests(unittest.TestCase):
    def setUp(self):
        self.board, self.rule, self.intent = fixture()

    def result(self):
        return check_kelvin(self.board, self.rule, self.intent, Catalog())['result']

    def test_clean_two_branches(self):
        self.assertEqual(self.result(), 'PASS')

    def test_read_only(self):
        before = copy.deepcopy((self.board, self.rule, self.intent))
        self.assertEqual(self.result(), 'PASS')
        self.assertEqual((self.board, self.rule, self.intent), before)

    def test_cardinal_rotation_and_circle(self):
        for footprint in self.board['footprints'].values():
            for pads in footprint['pads'].values():
                pads[0]['rotation'] = 90
                pads[0]['size'] = [1.5, 2]
        self.assertEqual(self.result(), 'PASS')
        self.board['footprints']['R1']['pads']['1'][0].update(shape='circle', size=[2, 2])
        self.assertEqual(self.result(), 'PASS')

    def test_pad_contact_needs_no_endpoint_equality(self):
        self.board['segments'][0]['start'] = [-3.95, 3]
        self.assertEqual(self.result(), 'PASS')

    def test_disconnected(self):
        self.board['segments'].pop(0)
        self.assertEqual(self.result(), 'FAIL')

    def test_wrong_target(self):
        self.rule['branches'][0]['target'] = 'R1.pin:2'
        self.rule['branches'][1]['target'] = 'R1.pin:1'
        self.assertEqual(self.result(), 'FAIL')

    def test_same_net_name_is_not_connection(self):
        self.board['segments'][0]['layer'] = 'B.Cu'
        self.assertEqual(self.result(), 'FAIL')

    def test_shared_load_segment(self):
        self.board['segments'][2] = track((-3, 3), (5, 3))
        self.assertEqual(self.result(), 'NOT_CHECKABLE')
        self.board['segments'][2] = track((-3, 3), (-3, 6))
        self.board['footprints']['J1']['pads']['1'][0]['at'] = [-3, 6]
        self.assertEqual(self.result(), 'FAIL')

    def test_supply_bypass_and_mcu_load_before_shunt(self):
        for index, y in ((0, 3), (1, -3)):
            with self.subTest(branch=index):
                self.board, self.rule, self.intent = fixture()
                self.board['footprints']['J1']['pads'][str(index + 1)][0]['at'] = [-2.5, y + 1]
                self.board['segments'].append(track((-2.5, y), (-2.5, y + 1)))
                self.assertEqual(self.result(), 'FAIL')

    def test_finite_width_contact_without_centerline_contact(self):
        self.board['footprints']['J1']['pads']['1'][0] = pad(-2.5, 4.05, 'P')
        self.board['segments'].pop(2)
        self.assertEqual(self.result(), 'FAIL')

    def test_optional_filter_is_not_prohibited(self):
        self.board['footprints']['C1'] = {'pads': {'1': [pad(-2.5, 4.05, 'P')]}}
        self.intent['components'].append({'ref': 'C1', 'part': 'filter'})
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_filter_does_not_hide_proven_load(self):
        self.board['footprints']['C1'] = {'pads': {'1': [pad(-2.5, 4.05, 'P')]}}
        self.intent['components'].append({'ref': 'C1', 'part': 'filter'})
        self.board['footprints']['J1']['pads']['1'][0]['at'] = [-3, 6]
        self.board['segments'][2] = track((-3, 3), (-3, 6))
        self.assertEqual(self.result(), 'FAIL')

    def test_crossing_long_track_cannot_hide_load(self):
        self.board['segments'][0] = track((-5, 3), (5, 3))
        self.board['segments'].pop(2)
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_tangent_contact(self):
        self.board['footprints']['J1']['pads']['1'][0]['at'] = [-3, 4.1]
        self.board['segments'].pop(2)
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_boundary_straddling_contact(self):
        self.board['segments'][2] = track((0, 3), (-0.95, 5))
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_missing_mapping(self):
        del self.rule['branches']
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_arcs_zones_vias_and_holes(self):
        for key in ('arcs', 'zones', 'vias'):
            with self.subTest(key=key):
                self.board, self.rule, self.intent = fixture()
                self.board[key] = [{}]
                self.assertEqual(self.result(), 'NOT_CHECKABLE')
        self.board, self.rule, self.intent = fixture()
        self.board['footprints']['U1']['pads']['1'][0]['drill'] = 0.3
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_multipad_and_noncardinal(self):
        self.board['footprints']['U1']['pads']['1'].append(pad(-5, 3, 'P'))
        self.assertEqual(self.result(), 'NOT_CHECKABLE')
        self.board, self.rule, self.intent = fixture()
        self.board['footprints']['U1']['pads']['1'][0]['rotation'] = 45
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_resource_and_nonfinite(self):
        self.board['segments'] *= MAX_PRIMITIVES
        self.assertEqual(self.result(), 'NOT_CHECKABLE')
        for value in (float('nan'), float('inf'), 1000001, 10 ** 400, True, 0, -1):
            with self.subTest(width=value):
                self.board, self.rule, self.intent = fixture()
                self.board['segments'][0]['width'] = value
                self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_net_labels_cannot_hide_load_contact(self):
        self.board['footprints']['J1']['pads']['1'][0] = pad(-2.5, 4.05, 'OTHER')
        self.board['segments'].pop(2)
        self.assertEqual(self.result(), 'FAIL')

    def test_wrong_net_track_is_not_connectivity(self):
        self.board['segments'][0]['net'] = 'OTHER'
        self.assertEqual(self.result(), 'FAIL')

    def test_ordered_net_mapping(self):
        self.rule['sense_nets'].reverse()
        self.assertEqual(self.result(), 'FAIL')

    def test_wrong_net_pad(self):
        self.board['footprints']['R1']['pads']['1'][0]['net'] = 'OTHER'
        self.assertEqual(self.result(), 'FAIL')

    def test_merged_board_nets(self):
        for footprint in self.board['footprints'].values():
            for pads in footprint['pads'].values():
                pads[0]['net'] = 'P'
        for segment in self.board['segments']:
            segment['net'] = 'P'
        self.assertEqual(self.result(), 'FAIL')

    def test_remote_foreign_via_and_zone(self):
        self.board['vias'] = [{'at': [100, 100], 'size': 1, 'drill': 0.4,
                               'net': 'OTHER', 'layers': ['F.Cu', 'B.Cu']}]
        self.board['zones'] = [{'net': 'OTHER', 'layer': 'F.Cu',
                                'polygons': [[[100, 100], [105, 100], [105, 105]]]}]
        self.assertEqual(self.result(), 'PASS')
        self.board['vias'][0]['at'] = [-2.5, 3]
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_remote_hole_and_drilled_pad(self):
        hole = pad(100, 100, '')
        hole.update(kind='np_thru_hole', drill=1, layers=['*.Cu'])
        self.board['footprints']['H1'] = {'pads': {'': [hole]}}
        self.assertEqual(self.result(), 'PASS')
        hole.update(kind='thru_hole', net='OTHER')
        self.assertEqual(self.result(), 'PASS')
        hole['at'] = [-2.5, 3]
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_offset_drill_envelope(self):
        hole = pad(100, 3, '')
        hole.update(kind='np_thru_hole', drill=1, layers=['*.Cu'], drill_offset=[-102.5, 0])
        self.board['footprints']['H1'] = {'pads': {'': [hole]}}
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_remote_foreign_arc(self):
        self.board['arcs'] = [{'start': [100, 100], 'mid': [101, 101], 'end': [102, 100],
                              'width': 0.2, 'layer': 'F.Cu', 'net': 'OTHER'}]
        self.assertEqual(self.result(), 'PASS')
        self.board['arcs'][0]['net'] = 'P'
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_nearby_foreign_zone(self):
        self.board['zones'] = [{'net': 'OTHER', 'layer': 'F.Cu',
                                'polygons': [[[-3, 2], [-2, 2], [-2, 4], [-3, 4]]]}]
        self.assertEqual(self.result(), 'NOT_CHECKABLE')
        self.board['zones'][0]['layer'] = 'B.Cu'
        self.assertEqual(self.result(), 'PASS')

    def test_cutout_and_outside_copper(self):
        self.board['outline']['closed'] = False
        self.assertEqual(self.result(), 'NOT_CHECKABLE')
        self.board, self.rule, self.intent = fixture()
        self.board['outline']['bounds'] = [-4, -20, 20, 20]
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_parsed_board_cutout_cannot_pass(self):
        text = exported_board(self.board)
        self.board = board_from_text(text)
        self.assertEqual(self.result(), 'PASS')
        extra = '(gr_rect (start -3.2 2.7) (end -2.8 3.3) (layer "Edge.Cuts"))'
        self.board = board_from_text(text[:-1] + extra + ')')
        self.assertFalse(self.board['outline']['closed'])
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_invalid_unsupported_dimensions(self):
        self.board['arcs'] = [{'start': [100, 100], 'mid': [101, 101], 'end': [102, 100],
                              'width': -1, 'layer': 'F.Cu', 'net': 'OTHER'}]
        self.assertEqual(self.result(), 'NOT_CHECKABLE')
        self.board['arcs'] = []
        hole = pad(100, 100, '')
        hole.update(kind='np_thru_hole', drill=-1, layers=['*.Cu'])
        self.board['footprints']['H1'] = {'pads': {'': [hole]}}
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_foreign_track_wholly_inside_target(self):
        self.board['segments'].append(track((-0.4, 3), (0.4, 3), net='OTHER'))
        self.assertEqual(self.result(), 'FAIL')

    def test_unassigned_track_wholly_inside_target(self):
        self.board['segments'].append(track((-0.4, 3), (0.4, 3), net=''))
        self.assertEqual(self.result(), 'NOT_CHECKABLE')

    def test_foreign_or_unassigned_load_leg_at_target(self):
        for net, expected in [('OTHER', 'FAIL'), ('', 'NOT_CHECKABLE')]:
            with self.subTest(net=net):
                self.board, self.rule, self.intent = fixture()
                self.board['segments'][2]['net'] = net
                self.assertEqual(self.result(), expected)


if __name__ == '__main__':
    unittest.main()
