"""Seed-only protection tests; original synthetic ASTs, no native tools."""
import copy
import hashlib
import unittest

from pcbknowledge.v2.sexpr import dumps, parse
from pcbknowledge.v2.specctra import read_specctra
from pcbknowledge.v2.reservation_protection import protect_seed


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixture():
    segments = [['segment', ['start', '1', '2'], ['end', '1', '3'], ['width', '.15'],
                 ['layer', 'F.Cu'], ['net', '1'], ['uuid', 'a']],
                ['segment', ['start', '1', '3'], ['end', '2', '4'], ['width', '.15'],
                 ['layer', 'F.Cu'], ['net', '1'], ['uuid', 'b']]]
    via = ['via', ['at', '2', '4'], ['size', '.8'], ['drill', '.3'],
           ['layers', 'F.Cu', 'B.Cu'], ['net', '1'], ['uuid', 'c']]
    board = ['kicad_pcb', ['net', '0', ''], ['net', '1', 'N'], *segments, via]
    wire = ['wire', ['path', 'F.Cu', '150', '1000', '-2000', '1000', '-3000', '2000', '-4000'],
            ['net', 'N'], ['type', 'normal']]
    bulk = ['wire', ['path', 'B.Cu', '150', '5000', '-2000', '6000', '-3000'],
            ['net', 'N'], ['type', 'normal']]
    dsn = ['pcb', 'board', ['unit', 'um'], ['network', ['net', 'N']],
           ['library', ['padstack', 'Via[0-1]_800:300_um', ['shape', ['circle', 'F.Cu', '800']],
                        ['shape', ['circle', 'B.Cu', '800']], ['attach', 'off']]],
           ['wiring', wire, bulk, ['via', 'Via[0-1]_800:300_um', '2000', '-4000',
                                  ['net', 'N'], ['type', 'normal']]]]
    receipt = {'seed_nodes': copy.deepcopy([*segments, via]), 'added_segments': 2, 'added_vias': 1}
    return board, dsn, receipt


class ProtectionTests(unittest.TestCase):
    def call(self, board, dsn, receipt, **overrides):
        b, d = dumps(board), dumps(dsn)
        receipt = {**receipt, 'output_sha256': digest(b)}
        args = dict(expected_board_sha256=digest(b), expected_dsn_sha256=digest(d))
        args.update(overrides)
        return protect_seed(d, b, receipt, **args)

    def test_only_two_type_fields_change(self):
        b, d, r = fixture()
        before = copy.deepcopy(d)
        output, proof = self.call(b, d, r)
        actual = read_specctra(output)
        self.assertEqual((proof['protected_wires'], proof['protected_vias'], proof['seed_segments']), (1, 1, 2))
        actual[-1][1][-1][1] = 'normal'
        actual[-1][3][-1][1] = 'normal'
        self.assertEqual(actual, before)
        self.assertEqual(d, before)

    def test_reversed_polyline_and_split_wires(self):
        b, d, r = fixture()
        d[-1][1][1][3:] = ['2000', '-4000', '1000', '-3000', '1000', '-2000']
        self.call(b, d, r)
        d[-1][1][1][3:] = ['1000', '-2000', '1000', '-3000']
        d[-1].append(['wire', ['path', 'F.Cu', '150', '1000', '-3000', '2000', '-4000'],
                      ['net', 'N'], ['type', 'normal']])
        self.assertEqual(self.call(b, d, r)[1]['protected_wires'], 2)

    def test_reject_bulk_overreach_and_partial_coverage(self):
        for mutation in ('extra', 'missing', 'duplicate', 'width', 'layer'):
            b, d, r = fixture()
            path = d[-1][1][1]
            if mutation == 'extra':
                path.extend(['3000', '-5000'])
            elif mutation == 'missing':
                del path[-2:]
            elif mutation == 'duplicate':
                d[-1].append(copy.deepcopy(d[-1][1]))
            elif mutation == 'width':
                path[2] = '149'
            else:
                path[1] = 'inner'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.call(b, d, r)

    def test_reject_via_geometry_and_duplicates(self):
        for mutation in ('drill', 'diameter', 'position', 'duplicate'):
            b, d, r = fixture()
            if mutation == 'drill':
                d[-1][3][1] = 'Via[0-1]_800:200_um'
            elif mutation == 'diameter':
                d[-2][1][2][1][2] = '799'
            elif mutation == 'position':
                d[-1][3][2] = '2000.0001'
            else:
                d[-1].append(copy.deepcopy(d[-1][3]))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.call(b, d, r)

    def test_reject_untrusted_hash_uuid_geometry_and_count(self):
        b, d, r = fixture()
        with self.assertRaises(ValueError):
            self.call(b, d, r, expected_board_sha256='0' * 64)
        with self.assertRaises(ValueError):
            self.call(b, d, r, expected_dsn_sha256='0' * 64)
        for mutation in ('uuid', 'geometry', 'count', 'duplicate'):
            b, d, r = fixture()
            if mutation == 'uuid':
                r['seed_nodes'][0][-1][1] = 'unknown'
            elif mutation == 'geometry':
                r['seed_nodes'][0][1][1] = '1.0001'
            elif mutation == 'count':
                r['added_segments'] = 1
            else:
                b.append(copy.deepcopy(b[3]))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.call(b, d, r)

    def test_reject_unknown_net_non_normal_and_nonfinite(self):
        for mutation in ('net', 'state', 'number'):
            b, d, r = fixture()
            if mutation == 'net':
                d[-1][1][2][1] = 'UNKNOWN'
            elif mutation == 'state':
                d[-1][2][-1][1] = 'protect'
            else:
                d[-1][1][1][3] = 'NaN'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.call(b, d, r)


if __name__ == '__main__':
    unittest.main()
