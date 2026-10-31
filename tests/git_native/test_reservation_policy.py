"""Incomplete native findings stay FAIL and require exact release provenance."""
import copy
import json
import unittest
from pcbknowledge.v2.reservation_core import digest, compose
from pcbknowledge.v2.reservation_policy import classify_reservation
from tests.git_native.test_reservation_core import ORIGINAL, CURRENT, proposal

BASELINE = json.dumps({'board': '/build/prior.kicad_pcb',
                       'input_sha256': {'prior.kicad_pcb': 'prior', 'prior.kicad_pro': 'project',
                                        'prior.kicad_dru': 'rules'},
                       'report': {'violations': [], 'schematic_parity': [],
                                  'unconnected_items': [{}]}})


def fixture():
    p = proposal()
    output, receipt = compose(ORIGINAL, CURRENT, p)
    receipt.update(board='/build/seed.kicad_pcb', baseline_board='/build/prior.kicad_pcb',
                   baseline_board_sha256='prior', baseline_drc_sha256=digest(BASELINE),
                   settings_sha256={'seed.kicad_pro': 'project', 'seed.kicad_dru': 'rules'})
    uid = receipt['seed_via_uuids'][0]
    drc = {'board': receipt['board'], 'drc_status': 'FAIL', 'exit_code': 5, 'finding_count': 2,
           'input_sha256': {'seed.kicad_pcb': digest(output), **receipt['settings_sha256']},
           'report': {'violations': [{'type': 'via_dangling', 'severity': 'warning',
                                    'items': [{'uuid': uid, 'pos': {'x': 3, 'y': 0}}]}],
                      'unconnected_items': [{}], 'schematic_parity': []}}
    return drc, receipt


class ReservationPolicyTests(unittest.TestCase):
    def test_seed_warning_kept_as_incomplete_not_pass(self):
        drc, receipt = fixture()
        before = copy.deepcopy(drc)
        result = classify_reservation(drc, receipt, CURRENT, BASELINE)
        self.assertTrue(result['routing_allowed'])
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['native_drc_status'], 'FAIL')
        self.assertEqual(drc, before)

    def test_unknown_dangling_or_changed_position_blocks(self):
        for change in ('uuid', 'position', 'type', 'severity'):
            drc, receipt = fixture()
            item = drc['report']['violations'][0]
            if change == 'uuid':
                item['items'][0]['uuid'] = 'other'
            elif change == 'position':
                item['items'][0]['pos']['x'] += .001
            elif change == 'type':
                item['type'] = 'clearance'
            else:
                item['severity'] = 'error'
            with self.subTest(change=change):
                self.assertFalse(classify_reservation(drc, receipt, CURRENT, BASELINE)['routing_allowed'])

    def test_source_settings_baseline_and_counts_are_bound(self):
        for field in ('source', 'settings', 'baseline', 'count', 'exit'):
            drc, receipt = fixture()
            source, baseline = CURRENT, BASELINE
            if field == 'source':
                source += ' '
            elif field == 'settings':
                drc['input_sha256']['seed.kicad_pro'] = 'changed'
            elif field == 'baseline':
                baseline += ' '
            elif field == 'count':
                drc['finding_count'] += 1
            else:
                drc['exit_code'] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                classify_reservation(drc, receipt, source, baseline)

    def test_only_adjacent_retained_track_warning_allowed(self):
        current = CURRENT.replace('(start 9 0)', '(start 2 2)').replace('(net 1) (uuid "keep")',
                                                                 '(net 2) (uuid "keep")')
        current = current.replace('(layer "B.Cu")', '(layer "F.Cu")')
        p = proposal()
        p['current_sha256'] = digest(current)
        output, receipt = compose(ORIGINAL, current, p)
        drc, authority = fixture()
        receipt.update({k: authority[k] for k in ('board', 'baseline_drc_sha256', 'settings_sha256',
                                                             'baseline_board', 'baseline_board_sha256')})
        drc['input_sha256']['seed.kicad_pcb'] = digest(output)
        drc['report']['violations'].append({'type': 'track_dangling', 'severity': 'warning',
                                          'items': [{'uuid': 'keep', 'pos': {'x': 2, 'y': 2}}]})
        drc['finding_count'] += 1
        self.assertTrue(classify_reservation(drc, receipt, current, BASELINE)['routing_allowed'])
        drc['report']['violations'][-1]['items'][0]['pos']['y'] = 1
        self.assertFalse(classify_reservation(drc, receipt, current, BASELINE)['routing_allowed'])


if __name__ == '__main__':
    unittest.main()
