"""Synthetic exact-removal, source preservation and deterministic reservation tests."""
import copy
import unittest
from pcbknowledge.v2.sexpr import parse
from pcbknowledge.v2.boardview import children
from pcbknowledge.v2.reservation_core import compose, copper_index, choose, digest

ORIGINAL = '(kicad_pcb (net 1 "N") (net 2 "OTHER") (zone (net 1)))'
CURRENT = ORIGINAL[:-1] + '''(segment (start 2 0) (end 2 2) (width .15)
(layer "F.Cu") (net 2) (uuid "block"))
(segment (start 9 0) (end 9 2) (width .3) (layer "B.Cu") (net 1) (uuid "keep")))'''
CANDIDATE = dict(net='N', layer='F.Cu', start=[0, 0], bend=None, end=[3, 0],
                 width=.15, via_diameter=.8, via_drill=.3)


def proposal():
    return {'source_sha256': digest(ORIGINAL), 'current_sha256': digest(CURRENT),
            'request': {'uuid': 'pad-uuid'},
            'selection': {'candidate': copy.deepcopy(CANDIDATE), 'blockers': [
                {'uuid': 'block', 'net': 'OTHER', 'node': children(parse(CURRENT), 'segment')[0]}]}}


class ReservationTests(unittest.TestCase):
    def test_exact_removal_all_other_nodes_retained(self):
        output, receipt = compose(ORIGINAL, CURRENT, proposal())
        expected = [n for n in parse(CURRENT) if n != children(parse(CURRENT), 'segment')[0]]
        self.assertEqual(parse(output)[:len(expected)], expected)
        self.assertEqual(receipt['retained_copper_count'], 1)
        self.assertEqual(receipt['added_segments'], 1)
        self.assertEqual(receipt['added_vias'], 1)
        self.assertTrue(receipt['all_other_nodes_preserved'])
        self.assertEqual(compose(ORIGINAL, CURRENT, proposal())[0], output)

    def test_unknown_duplicate_and_changed_blocker_rejected(self):
        for mode in ('uuid', 'geometry', 'duplicate'):
            p = proposal()
            if mode == 'uuid':
                p['selection']['blockers'][0]['uuid'] = 'wrong'
            elif mode == 'geometry':
                p['selection']['blockers'][0]['node'][1][1] = 99
            else:
                p['selection']['blockers'] *= 2
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                compose(ORIGINAL, CURRENT, p)

    def test_mutation_and_net_change_rejected(self):
        with self.assertRaises(ValueError):
            compose(ORIGINAL+' ', CURRENT, proposal())
        with self.assertRaises(ValueError):
            compose(ORIGINAL, CURRENT+' ', proposal())
        source = ORIGINAL.replace('OTHER', 'CHANGED')
        p = proposal()
        p['source_sha256'] = digest(source)
        with self.assertRaises(ValueError):
            compose(source, CURRENT, p)

    def test_locks_groups_arcs_and_duplicate_uuid_fail(self):
        for text in (CURRENT.replace('(segment', '(segment locked', 1),
                     CURRENT[:-1]+'(group G))', CURRENT[:-1]+'(arc (uuid "a")))',
                     CURRENT.replace('"keep"', '"block"')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                copper_index(parse(text))

    def test_rank_count_then_nets_then_length_deterministically(self):
        a = proposal()['selection']
        b = copy.deepcopy(a)
        b['candidate']['end'] = [2, 0]
        self.assertEqual(choose([a, b]), b)
        self.assertEqual(choose([b, a]), b)
        a['blockers'] = []
        self.assertEqual(choose([b, a]), a)
        with self.assertRaises(ValueError):
            choose([])
        with self.assertRaises(ValueError):
            choose([a]*1025)


if __name__ == '__main__':
    unittest.main()
